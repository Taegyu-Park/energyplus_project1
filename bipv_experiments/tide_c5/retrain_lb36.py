"""기존 ST1/ST2 학습 레시피(30 epoch, cosine, val MSE best)에서 lookback만 36으로 바꿔 재학습하고,
기존 체크포인트(lookback 144)와 같은 test 타임스텝(블록 내 step-0 위치 >= 144)에서 비교한다.
원본은 수정하지 않고 import만 한다. 체크포인트는 이 폴더의 checkpoints/에 저장."""
import sys, json, time, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[2]
TIDE = ROOT / "ai_model" / "tide"
sys.path.insert(0, str(TIDE))
from tide_model import TiDEModel
from train_tide import (ContiguousBlockTiDEDataset, PAST_COV_COLS, FUTURE_COV_COLS,
                        STRATEGY_1_TARGETS, STRATEGY_2_TARGETS, ANGLES, DATA_DIR)

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"; OUT.mkdir(exist_ok=True)
CK = HERE / "checkpoints"; CK.mkdir(exist_ok=True)
H = 24
REF = 144


def load():
    r = lambda n: pd.read_csv(DATA_DIR / f"case2_ks_{n}.csv")
    return r("train"), r("val"), r("test")


def build(model_kw, dev):
    return TiDEModel(**model_kw).to(dev)


def to_net(P, strategy, mean, std):
    """정규화된 예측(N,H,T) -> 물리 단위 net (N,H,10)."""
    X = P * std + mean
    if strategy == 1:
        return X
    pv, cool, heat = X[..., :10], X[..., 10:20], X[..., 20:]
    return cool / 3.0 + heat / 2.5 - pv


def keep_mask(te, lookback):
    ts = pd.to_datetime(te["timestamp"])
    bid = (ts.diff() > pd.Timedelta(minutes=10)).cumsum()
    keep = []
    for _, b in te.groupby(bid):
        nw = len(b) - (lookback + H) + 1
        if nw > 0:
            keep.extend([i + lookback >= REF for i in range(nw)])
    return np.array(keep)


def evaluate(model, te, tr_ds, strategy, lookback, dev):
    cols = STRATEGY_1_TARGETS if strategy == 1 else STRATEGY_2_TARGETS
    te_ds = ContiguousBlockTiDEDataset(te, cols, PAST_COV_COLS, FUTURE_COV_COLS,
                                       lookback, H, tr_ds.scaler_dict)
    mean = np.array([tr_ds.scaler_dict[c][0] for c in cols], dtype=np.float32)
    std = np.array([tr_ds.scaler_dict[c][1] for c in cols], dtype=np.float32)
    P, T = [], []
    model.eval()
    with torch.no_grad():
        for lb, pc, fc, hz in DataLoader(te_ds, 256):
            P.append(model(lb.to(dev), pc.to(dev), fc.to(dev)).cpu().numpy()); T.append(hz.numpy())
    P = np.concatenate(P); T = np.concatenate(T)
    keep = keep_mask(te, lookback); assert len(keep) == len(P)
    P, T = P[keep], T[keep]
    net_p = to_net(P, strategy, mean, std)[:, 0, :]
    net_t = to_net(T, strategy, mean, std)[:, 0, :]     # 정답 net (성분 조합, 검증됨)
    pick = net_p.argmin(1)
    ar = np.arange(len(pick))
    pv_t = (T * std + mean)
    chosen = net_t[ar, pick].sum()
    r = dict(net_chosen=float(chosen), net_oracle=float(net_t.min(1).sum()),
             net_best_fixed=float(net_t.sum(0).min()), net_fixed0=float(net_t.sum(0)[0]),
             angle_mae=float(np.abs(np.array(ANGLES)[pick] - np.array(ANGLES)[net_t.argmin(1)]).mean()),
             net_mae=float(np.abs(net_p - net_t).mean()),
             mse_norm=float(((P - T) ** 2).mean()), n=len(pick))
    if strategy == 2:
        r["pv_chosen"] = float(pv_t[:, 0, :10][ar, pick].sum())
        r["cool_chosen"] = float(pv_t[:, 0, 10:20][ar, pick].sum())
        r["heat_chosen"] = float(pv_t[:, 0, 20:][ar, pick].sum())
    return r


def eval_existing(strategy, dev):
    tr, va, te = load()
    ck = torch.load(TIDE / "checkpoints" / f"tide_strategy{strategy}_best.pt", map_location="cpu", weights_only=False)
    L = ck["lookback_len"]; cols = ck["target_cols"]
    tr_ds = ContiguousBlockTiDEDataset(tr, cols, PAST_COV_COLS, FUTURE_COV_COLS, L, H)
    sd = ck["model_state_dict"]
    model = TiDEModel(lookback_len=L, horizon_len=H, num_targets=len(cols), past_cov_dim=3, future_cov_dim=6,
                      hidden_dim=256, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
                      decoder_output_dim=32, dropout=0.1).to(dev)
    model.load_state_dict(sd)
    r = evaluate(model, te, tr_ds, strategy, L, dev)
    return dict(strategy=strategy, lookback=L, seed="existing", **r)


def train(strategy, lookback, seed, epochs, dev):
    torch.manual_seed(seed); np.random.seed(seed)
    tr, va, te = load()
    cols = STRATEGY_1_TARGETS if strategy == 1 else STRATEGY_2_TARGETS
    mk = lambda df, sc=None: ContiguousBlockTiDEDataset(df, cols, PAST_COV_COLS, FUTURE_COV_COLS, lookback, H, sc)
    tr_ds = mk(tr); va_ds = mk(va, tr_ds.scaler_dict)
    tl = DataLoader(tr_ds, 64, shuffle=True, drop_last=True); vl = DataLoader(va_ds, 64)
    model = TiDEModel(lookback_len=lookback, horizon_len=H, num_targets=len(cols), past_cov_dim=3,
                      future_cov_dim=6, hidden_dim=256, proj_dim=16, num_encoder_layers=2,
                      num_decoder_layers=2, decoder_output_dim=32, dropout=0.1).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)
    crit = nn.MSELoss()
    best, best_state, best_ep = 1e9, None, 0
    for ep in range(1, epochs + 1):
        model.train()
        for lb, pc, fc, hz in tl:
            lb, pc, fc, hz = [x.to(dev) for x in (lb, pc, fc, hz)]
            opt.zero_grad(); crit(model(lb, pc, fc), hz).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step()
        sch.step(); model.eval(); tot = 0
        with torch.no_grad():
            for lb, pc, fc, hz in vl:
                lb, pc, fc, hz = [x.to(dev) for x in (lb, pc, fc, hz)]
                tot += crit(model(lb, pc, fc), hz).item() * lb.size(0)
        v = tot / len(va_ds)
        if v < best:
            best, best_ep = v, ep
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    torch.save({"model_state_dict": best_state, "strategy": strategy, "lookback_len": lookback,
                "horizon_len": H, "target_cols": cols, "scaler": tr_ds.scaler_dict, "epoch": best_ep},
               CK / f"tide_strategy{strategy}_lb{lookback}_seed{seed}.pt")
    r = evaluate(model, te, tr_ds, strategy, lookback, dev)
    return dict(strategy=strategy, lookback=lookback, seed=seed, best_ep=best_ep, val_mse=best, **r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--epochs", type=int, default=30)
    a = ap.parse_args()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    f = OUT / "retrain_lb36.jsonl"
    rows = [eval_existing(1, dev), eval_existing(2, dev)]
    for strat in (1, 2):
        for s in a.seeds:
            t = time.time(); rows.append(train(strat, 36, s, a.epochs, dev)); rows[-1]["sec"] = time.time() - t
            print(json.dumps(rows[-1]), flush=True)
    for r in rows:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r) + "\n")
    print("DONE", flush=True)

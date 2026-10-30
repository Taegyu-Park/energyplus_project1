"""C5 절제 실험 (ST1): lookback 타깃 가림 / lookback 길이 변화.

원본(ai_model/tide)은 수정하지 않고 import만 한다.
평가: test 구간에서 horizon step 0 예측으로 argmin 각도를 고르고, 그 각도의 true net 합을 비교.
"""
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
                        STRATEGY_1_TARGETS, ANGLES, DATA_DIR)

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)
H = 24


def run(lookback, mask, seed, epochs, patience, dev):
    torch.manual_seed(seed); np.random.seed(seed)
    tr = pd.read_csv(DATA_DIR / "case2_ks_train.csv")
    va = pd.read_csv(DATA_DIR / "case2_ks_val.csv")
    te = pd.read_csv(DATA_DIR / "case2_ks_test.csv")
    mk = lambda df, sc=None: ContiguousBlockTiDEDataset(
        df, STRATEGY_1_TARGETS, PAST_COV_COLS, FUTURE_COV_COLS, lookback, H, sc)
    tr_ds = mk(tr); va_ds = mk(va, tr_ds.scaler_dict); te_ds = mk(te, tr_ds.scaler_dict)
    tl = DataLoader(tr_ds, 64, shuffle=True, drop_last=True)
    vl = DataLoader(va_ds, 64); el = DataLoader(te_ds, 256)

    model = TiDEModel(lookback_len=lookback, horizon_len=H, num_targets=10,
                      past_cov_dim=len(PAST_COV_COLS), future_cov_dim=len(FUTURE_COV_COLS),
                      hidden_dim=256, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
                      decoder_output_dim=32, dropout=0.1).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    crit = nn.MSELoss()

    def fwd(lb, pc, fc):
        if mask:
            lb = torch.zeros_like(lb)  # 정규화 평균값 = 정보 없음
        return model(lb, pc, fc)

    best, best_state, best_ep, bad = 1e9, None, 0, 0
    for ep in range(1, epochs + 1):
        model.train()
        for lb, pc, fc, hz in tl:
            lb, pc, fc, hz = [x.to(dev) for x in (lb, pc, fc, hz)]
            opt.zero_grad(); loss = crit(fwd(lb, pc, fc), hz); loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step()
        model.eval(); tot = 0
        with torch.no_grad():
            for lb, pc, fc, hz in vl:
                lb, pc, fc, hz = [x.to(dev) for x in (lb, pc, fc, hz)]
                tot += crit(fwd(lb, pc, fc), hz).item() * lb.size(0)
        v = tot / len(va_ds)
        if v < best:
            best, best_ep, bad = v, ep, 0
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state); model.eval()

    # test: step-0 예측 → argmin 각도 → true net
    ms, ss = tr_ds.scaler_dict[STRATEGY_1_TARGETS[0]], None
    mean = np.array([tr_ds.scaler_dict[c][0] for c in STRATEGY_1_TARGETS], dtype=np.float32)
    std = np.array([tr_ds.scaler_dict[c][1] for c in STRATEGY_1_TARGETS], dtype=np.float32)
    P, T = [], []
    with torch.no_grad():
        for lb, pc, fc, hz in el:
            lb, pc, fc = lb.to(dev), pc.to(dev), fc.to(dev)
            P.append(fwd(lb, pc, fc).cpu().numpy()); T.append(hz.numpy())
    P = np.concatenate(P) * std + mean; T = np.concatenate(T) * std + mean
    p0, t0 = P[:, 0, :], T[:, 0, :]          # (N,10)
    pick = p0.argmin(1)
    chosen = t0[np.arange(len(t0)), pick].sum()
    oracle = t0.min(1).sum()
    fixed = t0.sum(0)                         # 각도별 고정 합
    mae_ang = np.abs(np.array(ANGLES)[pick] - np.array(ANGLES)[t0.argmin(1)]).mean()
    return dict(lookback=lookback, mask=mask, seed=seed, best_ep=best_ep, val_mse=best,
                test_mse=float(((P - T) ** 2 / std ** 2).mean()),
                net_chosen=float(chosen), net_oracle=float(oracle),
                net_best_fixed=float(fixed.min()), best_fixed_angle=ANGLES[int(fixed.argmin())],
                net_fixed0=float(fixed[0]), net_fixed90=float(fixed[-1]),
                angle_mae=float(mae_ang), n=len(t0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--patience", type=int, default=3)
    a = ap.parse_args()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfgs = [(144, False), (144, True), (36, False), (72, False), (288, False)]
    f = OUT / "c5_st1_results.jsonl"
    for lb, mask in cfgs:
        for s in a.seeds:
            t = time.time()
            r = run(lb, mask, s, a.epochs, a.patience, dev); r["sec"] = time.time() - t
            print(json.dumps(r), flush=True)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(r) + "\n")

"""
bipv_mismatch/tide_policy/train_tide_oracle.py
==============================================
TiDE 각도 정책을 case2 스텝별 최적 각도(오라클)로 지도학습 (2026-11-02 사용자 결정, train_tide_policy.py 는 그대로 둠).

- 오라클 θ*ₜ: 조절 구간 스텝마다 case2 각도별 P, D 를 1° 격자로 선형 보간해
  |Pₜ(θ) − Dₜ(θ)| (= 잉여 + 부족, 1:1) 이 최소인 θ ∈ [θ_ST, 90]
- 출력: θ = θ_ST + (90 − θ_ST)·sigmoid(z) (조절 구간 밖은 θ_ST), train_tide_policy.to_theta 와 같음
- 손실: BCE_with_logits(z, r*)  (r* = (θ* − θ_ST)/(90 − θ_ST), 조절 구간 스텝 평균)
        + β · J/J_ST  (train_tide_policy 의 미스매치 비용, 1:1, 부드러운 hinge)
  BCE 기울기는 σ(z) − r* 라서 90° 에 붙어 있어도(포화) 기울기가 사라지지 않음
- 조절 구간: 태양추적 잉여 스텝 ± k 스텝 (기본 6 = 1시간, --k_dilate 0 이면 확장 없음), 각도 이동 벌점 없음
- 입력·분할·평가는 train_tide_policy.py 와 같음 (train IWEC / val TMYx2004 / test TMYx2011)

출력: tide_policy/out_oracle/{best.pt, scaler.json, history.json, summary.json} (대표 주 각도·E+ 스케줄은 eplus_week_oracle/prepare.py)
사용: python bipv_mismatch/tide_policy/train_tide_oracle.py --week_split train
"""

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import train_tide_policy as T  # noqa: E402

T.OUT_DIR = HERE / "out_oracle"
GRID = np.arange(0, 90.01, 1.0, dtype=np.float32)


def oracle_ratio(ds):
    """조절 구간 스텝의 오라클 비율 r* ∈ [0, 1] (구간 밖은 0), (N, 144)"""
    steps = np.stack([np.arange(s, s + T.DAY) for s in ds.idx])
    P, D, st = ds.P[steps], ds.D[steps], ds.theta_st[steps]
    x = GRID / 10
    i = np.clip(np.floor(x).astype(int), 0, 8)
    f = x - i
    c = np.abs((P[..., i] + f * (P[..., i + 1] - P[..., i])) - (D[..., i] + f * (D[..., i + 1] - D[..., i])))
    c[GRID[None, None, :] < st[..., None]] = np.inf
    best = GRID[c.argmin(-1)]
    span = np.maximum(90.0 - st, 1e-6)
    return np.where(ds.mask, (best - st) / span, 0.0).astype(np.float32), np.where(ds.mask, best, st)


class OracleDataset(torch.utils.data.Dataset):
    def __init__(self, ds):
        self.ds = ds
        self.r, self.best = oracle_ratio(ds)

    def __len__(self):
        return len(self.ds)

    def __getitem__(self, i):
        return (*self.ds[i], torch.from_numpy(self.r[i]))


def run_epoch(model, loader, device, args, opt=None):
    train = opt is not None
    model.train(train)
    tot, n = 0.0, 0
    with torch.set_grad_enabled(train):
        for lb, pc, fc, P, D, th_st, m, r in loader:
            lb, pc, fc, P, D, th_st, m, r = (t.to(device) for t in (lb, pc, fc, P, D, th_st, m, r))
            z = model(lb, pc, fc).squeeze(-1)
            bce = (F.binary_cross_entropy_with_logits(z, r, reduction="none") * m).sum() / m.sum().clamp(min=1)
            theta = T.to_theta(z.unsqueeze(-1), th_st, m)
            J, *_ = T.day_cost(theta, P, D, 1.0, 1.0, 0.0, args.smooth if train else None)
            J_st, *_ = T.day_cost(th_st, P, D, 1.0, 1.0, 0.0)
            loss = bce + args.beta * (J / J_st.clamp(min=1e-3)).mean()
            if train:
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
            tot += loss.item() * len(lb)
            n += len(lb)
    return tot / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta", type=float, default=0.2, help="미스매치 비용 보조 손실 가중치")
    ap.add_argument("--k_dilate", type=int, default=6)
    ap.add_argument("--smooth", type=float, default=50.0)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--week_split", default="train", choices=["train", "val", "test"])
    ap.add_argument("--week_start", default="2006-01-09")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    args.w_sur, args.lam_move = 1.0, 0.0  # export_week·summarize 용 (1:1, 이동 벌점 없음)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    T.OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] device {device} | β {args.beta} | k {args.k_dilate} | 오라클 1:1, θ ∈ [θ_ST, 90]")
    raw = {n: T.load_split(n) for n in ["train", "val", "test"]}
    scaler = T.fit_scaler(raw["train"][0])
    dss = {n: T.DayDataset(df, P, D, scaler, args.k_dilate) for n, (df, P, D) in raw.items()}
    ods = {n: OracleDataset(d) for n, d in dss.items()}
    (T.OUT_DIR / "scaler.json").write_text(json.dumps(scaler, indent=2), encoding="utf-8")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    model = T.build_model(args).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)
    tr_ld = DataLoader(ods["train"], batch_size=args.batch_size, shuffle=True)
    va_ld = DataLoader(ods["val"], batch_size=64)
    best, best_state, hist = (np.inf, 0), None, []
    for ep in range(1, args.epochs + 1):
        t = time.time()
        tr = run_epoch(model, tr_ld, device, args, opt)
        va = run_epoch(model, va_ld, device, args)
        sched.step()
        hist.append({"epoch": ep, "train": tr, "val": va})
        mark = ""
        if va < best[0]:
            best, best_state, mark = (va, ep), copy.deepcopy(model.state_dict()), " *"
        if ep == 1 or ep % 5 == 0 or mark:
            print(f"ep {ep:3d} | train {tr:.5f} | val {va:.5f} | {time.time() - t:4.1f}s{mark}", flush=True)
    model.load_state_dict(best_state)
    torch.save({"epoch": best[1], "model_state_dict": best_state, "args": vars(args)}, T.OUT_DIR / "best.pt")

    summary = {"args": vars(args)}
    for name in ["train", "val", "test"]:
        ds = dss[name]
        pol = T.baselines(ds)
        pol["오라클"] = ods[name].best
        pol["TiDE 오라클학습"] = T.rollout(model, ds, device)
        tab = T.summarize(pol, ds, 1.0, args)
        summary[name] = tab.round(3).to_dict(orient="index")
        print(f"\n===== {name} 겨울 평일 합계 (kWh, case2 보간, 07~07시) =====\n{tab.round(2).to_string()}")
    (T.OUT_DIR / "history.json").write_text(json.dumps({"best_epoch": best[1], "history": hist}, indent=2), encoding="utf-8")
    (T.OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[*] {T.OUT_DIR / 'best.pt'}")


if __name__ == "__main__":
    main()

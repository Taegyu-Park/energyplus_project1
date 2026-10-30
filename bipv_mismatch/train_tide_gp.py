"""
train_tide_gp.py
================
PLAN.md Step 4. ai_model/tide/train_tide.py를 복사·수정한 구매 전력 최소화용 TiDE 학습.

- 타깃: Strategy 2 (PV·냉방·난방 × 10각도 = 30성분, kWh/10분)
- 목적함수(구매 = max(HVAC − PV, 0))는 예측 후 계산 → 가치 기준이 바뀌어도 재학습 불필요
- 미래 기상은 TMY를 안다고 가정(PLAN Context)하므로 future covariate
- 분할 (2026-10-26 사용자 확정)
  - 모델 A: IWEC에서 VAL_BLOCKS(계절별 연속 2주, 앞뒤 1일 버퍼 제외)를 검증으로 두고
    EPOCHS 전부 학습 → 검증 손실 최소 에폭만 가져가고 가중치는 버림
  - 모델 B: IWEC 365일 전체로 같은 스케줄을 best epoch까지 학습 → TMYx 365일 테스트
- 테스트: 성분별 지표와 1단계 각도 선택(구매 최소, 동점이면 HVAC 최소)의 구매 전력 regret

출력: bipv_mismatch/checkpoints/tide_gp_{A,B}_*, tide_gp_B_tmyx_{eval.json, predictions.csv}
"""

import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.append(str(PROJECT_ROOT / "ai_model" / "tide"))
from tide_model import TiDEModel  # noqa: E402

DATA_DIR = BASE_DIR / "dataset"
CKPT_DIR = BASE_DIR / "checkpoints"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING = 3.0
COP_HEATING = 2.5
TIE_TOL_KWH = 1e-6  # 라벨(build_dataset.py)과 같은 동점 기준

# 모델 A 검증 블록 (월, 시작일, 종료일), 날짜는 구간 시작 시각 기준
VAL_BLOCKS = [(1, 15, 28), (4, 15, 28), (7, 15, 28), (10, 15, 28)]
BUFFER_DAYS = 1

TARGET_COLS = (
    [f"pv_gen_{a}" for a in ANGLES]
    + [f"cool_load_{a}" for a in ANGLES]
    + [f"heat_load_{a}" for a in ANGLES]
)
# 각도별 열적 상태(남측 존 온도)는 lookback에서만 관측 가능
PAST_COV_COLS = [f"south_zone_temp_{a}" for a in ANGLES]
FUTURE_COV_COLS = (
    ["outdoor_temp", "direct_solar", "diffuse_solar", "outdoor_rh", "dewpoint", "wind_speed",
     "sky_temp", "horiz_ir", "sky_cover", "sun_altitude", "sun_azimuth",
     "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos", "is_weekend",
     "occupancy", "heat_setpoint", "cool_setpoint"]
    + [f"cos_inc_{a}" for a in ANGLES]
    + [f"poa_{a}" for a in ANGLES]
)


# ── 데이터셋: 연속 블록 안에서만 윈도우를 자른다 (인덱스만 보관) ──
class BlockWindowDataset(Dataset):
    def __init__(self, df, scaler=None, lookback=144, horizon=24, stride=1):
        self.L, self.H = lookback, horizon
        cols = TARGET_COLS + PAST_COV_COLS + FUTURE_COV_COLS
        if scaler is None:
            scaler = {}
            for c in cols:
                s = float(df[c].std())
                scaler[c] = (float(df[c].mean()), s if s > 1e-6 else 1.0)
        self.scaler = scaler

        def norm(cs):
            m = np.array([scaler[c][0] for c in cs], dtype=np.float32)
            s = np.array([scaler[c][1] for c in cs], dtype=np.float32)
            return ((df[cs].to_numpy(dtype=np.float32) - m) / s).astype(np.float32)

        self.tgt = norm(TARGET_COLS)
        self.past = norm(PAST_COV_COLS)
        self.fut = norm(FUTURE_COV_COLS)

        ts = pd.to_datetime(df["timestamp"]).to_numpy()
        gap = np.r_[True, np.diff(ts) != np.timedelta64(10, "m")]
        starts = np.flatnonzero(gap)
        ends = np.r_[starts[1:], len(df)]
        win = lookback + horizon
        self.index = np.concatenate([
            np.arange(s, e - win + 1, stride) for s, e in zip(starts, ends) if e - s >= win
        ])

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        s = self.index[i]
        l, w = s + self.L, s + self.L + self.H
        return (
            torch.from_numpy(self.tgt[s:l]),
            torch.from_numpy(self.past[s:l]),
            torch.from_numpy(self.fut[s:w]),
            torch.from_numpy(self.tgt[l:w]),
        )


def run_epoch(model, loader, device, criterion, optimizer=None):
    train = optimizer is not None
    model.train(train)
    total, n = 0.0, 0
    with torch.set_grad_enabled(train):
        for lb, pc, fc, hz in loader:
            lb, pc, fc, hz = lb.to(device), pc.to(device), fc.to(device), hz.to(device)
            pred = model(lb, pc, fc)
            loss = criterion(pred, hz)
            if train:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()
            total += loss.item() * lb.size(0)
            n += lb.size(0)
    return total / n


def predict(model, ds, device, batch_size=512):
    """윈도우별 horizon 예측을 원 단위(kWh)로 되돌려 (N, H, 30)으로 반환."""
    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for lb, pc, fc, hz in DataLoader(ds, batch_size=batch_size):
            preds.append(model(lb.to(device), pc.to(device), fc.to(device)).cpu().numpy())
            trues.append(hz.numpy())
    m = np.array([ds.scaler[c][0] for c in TARGET_COLS], dtype=np.float32)
    s = np.array([ds.scaler[c][1] for c in TARGET_COLS], dtype=np.float32)
    return np.concatenate(preds) * s + m, np.concatenate(trues) * s + m


def choose_angle(pv, cool, heat):
    """구매 최소, 동점이면 HVAC 최소. 입력 (..., 10)."""
    hvac = cool / COP_COOLING + heat / COP_HEATING
    purchase = np.clip(hvac - pv, 0.0, None)
    tied = purchase <= purchase.min(axis=-1, keepdims=True) + TIE_TOL_KWH
    return np.where(tied, hvac, np.inf).argmin(axis=-1)


def evaluate_test(model, df_test, scaler, device, lookback, horizon):
    # stride = H: 겹치지 않게 예측해 각 스텝을 한 번씩 평가 (블록 첫 lookback 구간 제외)
    ds = BlockWindowDataset(df_test, scaler, lookback, horizon, stride=horizon)
    pred, true = predict(model, ds, device)
    pred = np.clip(pred, 0.0, None)
    n_a = len(ANGLES)

    comp = {}
    for k, name in enumerate(["pv_gen", "cool_load", "heat_load"]):
        p = pred[..., k * n_a:(k + 1) * n_a].ravel()
        t = true[..., k * n_a:(k + 1) * n_a].ravel()
        ss_res = np.sum((t - p) ** 2)
        ss_tot = np.sum((t - t.mean()) ** 2)
        comp[name] = {
            "mae_kwh": float(np.mean(np.abs(t - p))),
            "rmse_kwh": float(np.sqrt(np.mean((t - p) ** 2))),
            "r2": float(1 - ss_res / ss_tot),
        }

    # 결정 평가: 실제 값으로 계산한 구매/HVAC에 예측 선택 각도를 적용
    steps = (ds.index[:, None] + lookback + np.arange(horizon)).ravel()
    sub = df_test.iloc[steps]
    sel = choose_angle(pred[..., :n_a], pred[..., n_a:2 * n_a], pred[..., 2 * n_a:]).ravel()
    purchase = sub[[f"purchase_{a}" for a in ANGLES]].to_numpy()
    hvac = sub[[f"hvac_elec_{a}" for a in ANGLES]].to_numpy()
    rows = np.arange(len(sub))
    oracle = sub["optimal_angle_idx"].to_numpy()

    day = sub["sun_altitude"].to_numpy() > 0
    hit = sel == oracle
    near = np.abs(sel - oracle) <= 1
    # 실제로 구매 최소인 각도 집합 안에 들었는지 (동점이 많아 정확 일치보다 의미 있음)
    p_min = purchase.min(axis=1)
    in_tie = purchase[rows, sel] <= p_min + TIE_TOL_KWH

    decision = {
        "n_steps": int(len(sub)),
        "coverage_of_test": float(len(sub) / len(df_test)),
        "purchase_kwh": {
            "tide": float(purchase[rows, sel].sum()),
            "oracle_stage1": float(purchase[rows, oracle].sum()),
            **{f"fixed_{a}": float(purchase[:, i].sum()) for i, a in enumerate(ANGLES)},
        },
        "hvac_kwh": {
            "tide": float(hvac[rows, sel].sum()),
            "oracle_stage1": float(hvac[rows, oracle].sum()),
            **{f"fixed_{a}": float(hvac[:, i].sum()) for i, a in enumerate(ANGLES)},
        },
        "daytime_exact_hit": float(hit[day].mean()),
        "daytime_within_10deg": float(near[day].mean()),
        "daytime_min_purchase_rate": float(in_tie[day].mean()),
        "angle_mae_deg_daytime": float(np.abs(np.array(ANGLES)[sel] - np.array(ANGLES)[oracle])[day].mean()),
    }

    month = (pd.to_datetime(sub["timestamp"]) - pd.Timedelta(minutes=10)).dt.month.to_numpy()
    best_fixed = int(np.argmin(purchase.sum(axis=0)))
    decision["best_fixed_angle"] = ANGLES[best_fixed]
    decision["monthly_purchase_kwh"] = {
        int(m): {
            "tide": float(purchase[rows, sel][month == m].sum()),
            "oracle_stage1": float(purchase[rows, oracle][month == m].sum()),
            f"fixed_{ANGLES[best_fixed]}": float(purchase[month == m, best_fixed].sum()),
        }
        for m in range(1, 13)
    }

    out = pd.DataFrame({
        "timestamp": sub["timestamp"].to_numpy(),
        "pred_angle": np.array(ANGLES)[sel],
        "oracle_angle": np.array(ANGLES)[oracle],
        "purchase_pred_angle": purchase[rows, sel],
        "purchase_oracle": purchase[rows, oracle],
        "hvac_pred_angle": hvac[rows, sel],
        "hvac_oracle": hvac[rows, oracle],
    })
    return {"components": comp, "decision": decision}, out


def split_val(df):
    """VAL_BLOCKS를 검증으로, 그 앞뒤 BUFFER_DAYS를 버리고 나머지를 학습으로."""
    date = (pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)).dt.normalize()
    val = np.zeros(len(df), bool)
    buf = np.zeros(len(df), bool)
    for m, d0, d1 in VAL_BLOCKS:
        start = pd.Timestamp(2006, m, d0)
        end = pd.Timestamp(2006, m, d1)
        val |= ((date >= start) & (date <= end)).to_numpy()
        buf |= ((date >= start - pd.Timedelta(days=BUFFER_DAYS)) &
                (date <= end + pd.Timedelta(days=BUFFER_DAYS))).to_numpy()
    return df[~buf].reset_index(drop=True), df[val].reset_index(drop=True)


def train_model(args, device, df_train, df_val, stop_epoch, tag):
    """T_max=args.epochs 코사인 스케줄로 stop_epoch까지 학습. df_val이 있으면 매 에폭 검증."""
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    train_ds = BlockWindowDataset(df_train, None, args.lookback, args.horizon)
    loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
    val_loader = None
    if df_val is not None:
        val_ds = BlockWindowDataset(df_val, train_ds.scaler, args.lookback, args.horizon)
        val_loader = DataLoader(val_ds, batch_size=512)
        print(f"[{tag}] 윈도우 train {len(train_ds):,} / val {len(val_ds):,}")
    else:
        print(f"[{tag}] 윈도우 train {len(train_ds):,} (검증 없음)")

    model = TiDEModel(
        lookback_len=args.lookback, horizon_len=args.horizon, num_targets=len(TARGET_COLS),
        past_cov_dim=len(PAST_COV_COLS), future_cov_dim=len(FUTURE_COV_COLS),
        hidden_dim=args.hidden_dim, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
        decoder_output_dim=32, dropout=0.1,
    ).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    history = []
    for ep in range(1, stop_epoch + 1):
        t = time.time()
        tr = run_epoch(model, loader, device, criterion, optimizer)
        va = run_epoch(model, val_loader, device, criterion) if val_loader else None
        scheduler.step()
        history.append({"epoch": ep, "train_mse": tr, "val_mse": va})
        va_txt = f" | val {va:.5f}" if va is not None else ""
        print(f"[{tag}] ep {ep:3d} | train {tr:.5f}{va_txt} | {time.time() - t:5.1f}s", flush=True)
    return model, train_ds.scaler, history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--lookback", type=int, default=144)
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else
                          ("cpu" if args.device == "auto" else args.device))
    print(f"[*] device: {device}")
    print(f"[*] 타깃 {len(TARGET_COLS)}, past cov {len(PAST_COV_COLS)}, future cov {len(FUTURE_COV_COLS)}")
    CKPT_DIR.mkdir(parents=True, exist_ok=True)

    df_iwec = pd.read_csv(DATA_DIR / "case2_gp_dataset.csv")
    df_tmyx = pd.read_csv(DATA_DIR / "case2_gp_tmyx_dataset.csv")

    # ── 모델 A: best epoch 결정 ──
    df_tr, df_va = split_val(df_iwec)
    print(f"[A] 학습 {len(df_tr) // 144}일 / 검증 {len(df_va) // 144}일 / 버퍼 {(len(df_iwec) - len(df_tr) - len(df_va)) // 144}일")
    _, _, hist_a = train_model(args, device, df_tr, df_va, args.epochs, "A")
    best_epoch = min(hist_a, key=lambda h: h["val_mse"])["epoch"]
    print(f"[A] best epoch {best_epoch} (val MSE {hist_a[best_epoch - 1]['val_mse']:.5f})")
    with open(CKPT_DIR / "tide_gp_A_history.json", "w", encoding="utf-8") as f:
        json.dump({"val_blocks": VAL_BLOCKS, "buffer_days": BUFFER_DAYS,
                   "best_epoch": best_epoch, "history": hist_a}, f, indent=2)

    # ── 모델 B: IWEC 전체 학습 → TMYx 테스트 ──
    model, scaler, hist_b = train_model(args, device, df_iwec, None, best_epoch, "B")
    torch.save({
        "epoch": best_epoch, "model_state_dict": model.state_dict(), "args": vars(args),
        "target_cols": TARGET_COLS, "past_cov_cols": PAST_COV_COLS, "future_cov_cols": FUTURE_COV_COLS,
    }, CKPT_DIR / "tide_gp_B.pt")
    with open(CKPT_DIR / "tide_gp_B_scaler.json", "w", encoding="utf-8") as f:
        json.dump(scaler, f, indent=2)

    print("\n[B] TMYx 테스트")
    result, preds = evaluate_test(model, df_tmyx, scaler, device, args.lookback, args.horizon)
    result["best_epoch"] = best_epoch
    result["history_B"] = hist_b
    with open(CKPT_DIR / "tide_gp_B_tmyx_eval.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    preds.to_csv(CKPT_DIR / "tide_gp_B_tmyx_predictions.csv", index=False)
    print(json.dumps({k: v for k, v in result.items() if k != "history_B"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

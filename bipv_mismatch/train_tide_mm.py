"""
train_tide_mm.py
================
PLAN.md Step 4 (2026-10-29 규칙). train_tide_gp.py 를 복사·수정한 TiDE 학습.

- 타깃: 각도별 PV·냉방·난방·조명·조도 × 10각도 = 50성분 (에너지 kWh/10분, 조도 lux)
- 각도 선택은 예측 후 label_mismatch.choose_path 로 한다 (라벨과 같은 규칙)
  1. 모든 각도 구매 > 0 → 구매 최소, 2. 구매 0 각도 있음 → 채광(500 lx 상한, 1500 lx부터 벌점) + 움직임 최소
  구매 = max(냉방/3.0 + 난방/2.5 + 조명 − PV, 0)
- 분할 (2026-10-27 사용자 결정): train = IWEC, val = TMYx.2004-2018 (에폭 선택), test = TMYx.2011-2025
  dataset_final/case2_mm_{split}.csv + daylight_{split}.csv (extract_daylight.py)
- 겨울만 (2026-10-29 사용자 결정): horizon 이 11~3월 안에 있는 윈도우만 학습·검증·평가. lookback 은 10월 말로 넘어갈 수 있음.
  스케일러는 학습 연도 전체로 맞춘다.
- 입력 구조는 train_tide_gp.py 그대로 (10개 각도의 과거 성분·남측 존 온도를 lookback 으로 넣음.
  실제 각도 전환 운전에서는 관측할 수 없는 값이라는 미해결 문제가 남아 있음)

출력: bipv_mismatch/checkpoints/tide_mm_{best.pt, scaler.json, history.json, eval.json},
      tide_mm_{val,test}_predictions.csv
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

from train_tide_gp import run_epoch
from label_mismatch import choose_path, metrics, EVAL_MONTHS

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent / "ai_model" / "tide"))
from tide_model import TiDEModel  # noqa: E402

DATA_DIR = BASE_DIR / "dataset_final"
CKPT_DIR = BASE_DIR / "checkpoints"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING = 3.0
COP_HEATING = 2.5
COMPONENTS = ["pv_gen", "cool_load", "heat_load", "lights_kwh", "illum"]

TARGET_COLS = [f"{c}_{a}" for c in COMPONENTS for a in ANGLES]
PAST_COV_COLS = [f"south_zone_temp_{a}" for a in ANGLES]
FUTURE_COV_COLS = (
    ["outdoor_temp", "direct_solar", "diffuse_solar", "outdoor_rh", "dewpoint", "wind_speed",
     "sky_temp", "horiz_ir", "sky_cover", "sun_altitude", "sun_azimuth",
     "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos", "is_weekend",
     "occupancy", "heat_setpoint", "cool_setpoint"]
    + [f"cos_inc_{a}" for a in ANGLES]
    + [f"poa_{a}" for a in ANGLES]
)
EVAL_COLS = [f"{c}_{a}" for c in ["purchase", "surplus_pv", "demand_elec"] for a in ANGLES]


# ── 데이터셋: 연속 블록 안에서만 윈도우를 자른다 (train_tide_gp.py 와 같고 열 구성만 다름) ──
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

        # 겨울(EVAL_MONTHS) 연속 구간마다 horizon 이 그 구간 안에만 오게 자른다.
        # lookback 은 구간 앞(예: 11/1 예측에 10월 말)으로 넘어갈 수 있다. stride = H 이면 구간 첫 예측이 구간 시작.
        month = (pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)).dt.month.to_numpy()
        winter = np.isin(month, EVAL_MONTHS)
        edge = np.diff(np.r_[0, winter.astype(int), 0])
        self.blocks = []
        for s, e in zip(np.flatnonzero(edge == 1), np.flatnonzero(edge == -1)):
            first = max(s - lookback, 0)
            idx = np.arange(first, e - lookback - horizon + 1, stride)
            if len(idx):
                self.blocks.append(idx)
        self.index = np.concatenate(self.blocks)

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


def load_split(name: str) -> pd.DataFrame:
    cols = (["timestamp"] + [c for c in TARGET_COLS if not c.startswith("illum")]
            + PAST_COV_COLS + FUTURE_COV_COLS + EVAL_COLS)
    df = pd.read_csv(DATA_DIR / f"case2_mm_{name}.csv", usecols=lambda c: c in set(cols))
    dl = pd.read_csv(DATA_DIR / f"daylight_{name}.csv", usecols=["timestamp"] + [f"illum_{a}" for a in ANGLES])
    if not (dl["timestamp"].to_numpy() == df["timestamp"].to_numpy()).all():
        raise ValueError(f"{name}: daylight timestamp 불일치")
    return pd.concat([df, dl.drop(columns="timestamp")], axis=1)


def build_model(args) -> TiDEModel:
    return TiDEModel(
        lookback_len=args.lookback, horizon_len=args.horizon, num_targets=len(TARGET_COLS),
        past_cov_dim=len(PAST_COV_COLS), future_cov_dim=len(FUTURE_COV_COLS),
        hidden_dim=args.hidden_dim, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
        decoder_output_dim=32, dropout=0.1,
    )


def predict(model, ds, device, batch_size=512):
    """윈도우별 horizon 예측을 원 단위로 되돌려 (N, H, 50)으로 반환."""
    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for lb, pc, fc, hz in DataLoader(ds, batch_size=batch_size):
            preds.append(model(lb.to(device), pc.to(device), fc.to(device)).cpu().numpy())
            trues.append(hz.numpy())
    m = np.array([ds.scaler[c][0] for c in TARGET_COLS], dtype=np.float32)
    s = np.array([ds.scaler[c][1] for c in TARGET_COLS], dtype=np.float32)
    return np.concatenate(preds) * s + m, np.concatenate(trues) * s + m


def evaluate(model, df, scaler, device, args, rel_tol=0.0, night_tol=0.0):
    """겹치지 않는 윈도우(stride = H)로 겨울 연속 예측 → 예측값으로 각도 경로 → 실제값으로 채점.
    rel_tol: 예측값 경로에만 주는 규칙 1 허용오차 (예측 오차로 동점이 깨져 각도가 튀는 것을 막음). 오라클은 엄격.
    night_tol: 예측값 경로의 야간(태양고도 ≤ 0, 미리 아는 값) 허용오차. 야간 예측 오차로 각도가 10분마다 튀는 것을 막음."""
    ds = BlockWindowDataset(df, scaler, args.lookback, args.horizon, stride=args.horizon)
    pred, true = predict(model, ds, device)
    pred = np.clip(pred, 0.0, None).reshape(-1, len(TARGET_COLS))
    true = true.reshape(-1, len(TARGET_COLS))
    n_a = len(ANGLES)
    part = {c: slice(k * n_a, (k + 1) * n_a) for k, c in enumerate(COMPONENTS)}

    steps = (ds.index[:, None] + args.lookback + np.arange(args.horizon)).ravel()
    sub = df.iloc[steps].reset_index(drop=True)
    ts = pd.to_datetime(sub["timestamp"]) - pd.Timedelta(minutes=10)
    ev = ts.dt.month.isin(EVAL_MONTHS).to_numpy() & (sub["is_weekend"].to_numpy() == 0)
    day = sub["sun_altitude"].to_numpy() > 0

    comp = {}
    for c, sl in part.items():
        out = {}
        for tag, m in [("겨울전체", np.ones(len(sub), bool)), ("평가기간", ev)]:
            p, t = pred[m, sl].ravel(), true[m, sl].ravel()
            out[tag] = {"mae": float(np.mean(np.abs(t - p))),
                        "r2": float(1 - np.sum((t - p) ** 2) / np.sum((t - t.mean()) ** 2))}
        comp[c] = out

    # 예측 구매·조도로 각도 경로, 같은 스텝의 오라클(실제값). 겨울 구간(1~3월, 11~12월)마다 따로 경로를 잇는다.
    demand_p = pred[:, part["cool_load"]] / COP_COOLING + pred[:, part["heat_load"]] / COP_HEATING + pred[:, part["lights_kwh"]]
    P_pred = np.clip(demand_p - pred[:, part["pv_gen"]], 0.0, None)
    E_pred = pred[:, part["illum"]]
    P_true = sub[[f"purchase_{a}" for a in ANGLES]].to_numpy()
    E_true = sub[[f"illum_{a}" for a in ANGLES]].to_numpy()
    night = sub["sun_altitude"].to_numpy() <= 0
    tol_pred = np.where(night, night_tol, rel_tol)
    bounds = np.cumsum([0] + [len(b) * args.horizon for b in ds.blocks])
    paths = {"pred": ([], []), "orc": ([], [])}
    for a, b in zip(bounds[:-1], bounds[1:]):
        for key, (P, E, tol) in [("pred", (P_pred, E_pred, tol_pred)), ("orc", (P_true, E_true, 0.0))]:
            i, s = choose_path(P[a:b], E[a:b], args.daylight, args.lam, tol if np.isscalar(tol) else tol[a:b])
            paths[key][0].append(i)
            paths[key][1].append(s)
    idx_pred, surplus_pred = (np.concatenate(x) for x in paths["pred"])
    idx_orc, surplus_true = (np.concatenate(x) for x in paths["orc"])

    angles = np.array(ANGLES)
    rows = [metrics(sub, angles[idx_pred], "TiDE"), metrics(sub, angles[idx_orc], "오라클")]
    best_fixed = int(np.argmin(P_true[ev].sum(axis=0)))
    rows.append(metrics(sub, np.full(len(sub), ANGLES[best_fixed]), f"고정 {ANGLES[best_fixed]}°"))
    table = pd.DataFrame(rows).set_index("안")
    table.columns = [c.replace("연간_", "겨울전체_") for c in table.columns]  # sub 는 겨울 스텝만

    decision = {
        "coverage": float(len(sub) / len(df)),
        "규칙2시점_판정_일치율_주간평가기간": float((surplus_pred == surplus_true)[ev & day].mean()),
        "규칙2시점_실제비율_주간평가기간": float(surplus_true[ev & day].mean()),
        "각도_일치율_주간평가기간": float((idx_pred == idx_orc)[ev & day].mean()),
        "각도_10도이내_주간평가기간": float((np.abs(idx_pred - idx_orc) <= 1)[ev & day].mean()),
        "표": table.round(3).to_dict(orient="index"),
    }
    preds = pd.DataFrame({
        "timestamp": sub["timestamp"], "pred_angle": angles[idx_pred], "oracle_angle": angles[idx_orc],
        "pred_rule": np.where(surplus_pred, 2, 1), "true_rule": np.where(surplus_true, 2, 1),
        "purchase_pred_angle": P_true[np.arange(len(sub)), idx_pred],
        "illum_pred_angle": E_true[np.arange(len(sub)), idx_pred],
    })
    return {"components": comp, "decision": decision}, table, preds


def eval_tolerances(args, device, df_va, df_te, scaler):
    model = build_model(args).to(device)
    model.load_state_dict(torch.load(CKPT_DIR / "tide_mm_best.pt", map_location=device)["model_state_dict"])
    keys = ["평가_구매MWh", "평가_버림PV_MWh", "평가_잉여시점조도lx", "평가_잉여시점<500lx%",
            "평가_잉여시점>1500lx%", "평가_이동횟수/일", "평가_이동각도°/일"]
    pd.set_option("display.width", 250)
    for name, df in [("val", df_va), ("test", df_te)]:
        rows = {}
        for nt in [0.0, 0.01, 0.02, 0.05, 0.1, 1e9]:
            _, table, _ = evaluate(model, df, scaler, device, args, 0.0, nt)
            rows["야간 동점" if nt > 1 else f"야간 {nt * 100:g}%"] = table.loc["TiDE", keys]
        rows["오라클"] = table.loc["오라클", keys]
        print(f"\n===== {name} =====")
        print(pd.DataFrame(rows).round(2).to_string())


def export_schedules(args, device, dfs, scaler):
    """E+ 플러그인용 연간 스케줄 (timestamp, sun_altitude, optimal_angle; 52,560행, 순서대로 읽힘).
    겨울 예측 스텝은 TiDE 각도, 나머지(겨울 외, 예측 없는 1/1)는 기준안 태양추적(suntracking_w0s90)."""
    model = build_model(args).to(device)
    model.load_state_dict(torch.load(CKPT_DIR / "tide_mm_best.pt", map_location=device)["model_state_dict"])
    base = pd.read_csv(BASE_DIR.parent / "data" / "bipv_suntracking_angles_annual_winter0_summer90.csv")
    out_dir = BASE_DIR / "schedules"
    out_dir.mkdir(exist_ok=True)
    for name, df in dfs.items():
        if len(base) != len(df):
            raise ValueError("기준안 스케줄 행 수 불일치")
        for variant, nt in [("night_strict", 0.0), ("night_tie", 1e9)]:
            _, table, preds = evaluate(model, df, scaler, device, args, 0.0, nt)
            angle = base["optimal_angle"].to_numpy().copy()
            pos = df.reset_index(drop=True).reset_index().set_index("timestamp").loc[preds["timestamp"], "index"].to_numpy()
            angle[pos] = preds["pred_angle"].to_numpy()
            sched = pd.DataFrame({"timestamp": df["timestamp"].to_numpy(),
                                  "sun_altitude": df["sun_altitude"].to_numpy(), "optimal_angle": angle})
            path = out_dir / f"tide_mm_{name}_{variant}.csv"
            sched.to_csv(path, index=False)
            print(f"[*] {path.name}: TiDE {len(pos):,} 스텝 / 기준안 {len(df) - len(pos):,} 스텝 | "
                  f"평가기간 구매 {table.loc['TiDE', '평가_구매MWh']:.2f} MWh, 이동 {table.loc['TiDE', '평가_이동각도°/일']:.0f}°/일")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--lookback", type=int, default=144)
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--daylight", default="useful", choices=["raw", "useful"])
    ap.add_argument("--lam", type=float, default=0.05)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--eval_tol", action="store_true", help="학습 없이 tide_mm_best.pt 로 규칙 1 허용오차별 비교만")
    ap.add_argument("--export", action="store_true", help="학습 없이 tide_mm_best.pt 로 E+ 연간 각도 스케줄 CSV 생성")
    args = ap.parse_args()

    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else
                          ("cpu" if args.device == "auto" else args.device))
    print(f"[*] device: {device}")
    print(f"[*] 타깃 {len(TARGET_COLS)}, past cov {len(PAST_COV_COLS)}, future cov {len(FUTURE_COV_COLS)}")
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    df_tr, df_va, df_te = (load_split(n) for n in ["train", "val", "test"])
    train_ds = BlockWindowDataset(df_tr, None, args.lookback, args.horizon)
    if args.eval_tol:
        eval_tolerances(args, device, df_va, df_te, train_ds.scaler)
        return
    if args.export:
        export_schedules(args, device, {"val": df_va, "test": df_te}, train_ds.scaler)
        return
    val_ds = BlockWindowDataset(df_va, train_ds.scaler, args.lookback, args.horizon)
    loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=512)
    print(f"[*] 윈도우 train {len(train_ds):,} / val {len(val_ds):,}")

    model = build_model(args).to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    history, best = [], (np.inf, 0)
    for ep in range(1, args.epochs + 1):
        t = time.time()
        tr = run_epoch(model, loader, device, criterion, optimizer)
        va = run_epoch(model, val_loader, device, criterion)
        scheduler.step()
        history.append({"epoch": ep, "train_mse": tr, "val_mse": va})
        mark = ""
        if va < best[0]:
            best = (va, ep)
            mark = " *"
            torch.save({
                "epoch": ep, "model_state_dict": model.state_dict(), "args": vars(args),
                "target_cols": TARGET_COLS, "past_cov_cols": PAST_COV_COLS, "future_cov_cols": FUTURE_COV_COLS,
            }, CKPT_DIR / "tide_mm_best.pt")
        print(f"ep {ep:3d} | train {tr:.5f} | val {va:.5f} | {time.time() - t:5.1f}s{mark}", flush=True)
    print(f"[*] best epoch {best[1]} (val MSE {best[0]:.5f})")
    with open(CKPT_DIR / "tide_mm_scaler.json", "w", encoding="utf-8") as f:
        json.dump(train_ds.scaler, f, indent=2)
    with open(CKPT_DIR / "tide_mm_history.json", "w", encoding="utf-8") as f:
        json.dump({"best_epoch": best[1], "history": history}, f, indent=2)

    model.load_state_dict(torch.load(CKPT_DIR / "tide_mm_best.pt", map_location=device)["model_state_dict"])
    result = {"best_epoch": best[1], "args": vars(args)}
    pd.set_option("display.width", 250)
    for name, df in [("val", df_va), ("test", df_te)]:
        res, table, preds = evaluate(model, df, train_ds.scaler, device, args)
        result[name] = res
        preds.to_csv(CKPT_DIR / f"tide_mm_{name}_predictions.csv", index=False)
        print(f"\n===== {name} =====")
        print("성분 R² (겨울 전체 / 평가기간 평일): " + ", ".join(
            f"{c} {v['겨울전체']['r2']:.3f}/{v['평가기간']['r2']:.3f}" for c, v in res["components"].items()))
        print({k: round(v, 3) for k, v in res["decision"].items() if k != "표"})
        print(table.T.round(2).to_string())
    with open(CKPT_DIR / "tide_mm_eval.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

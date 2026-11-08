"""
train_tide_open.py
==================
잉여 구간 각도 제어 TiDE (2026-10-30 사용자 결정). 데이터: dataset_open/ (build_window_features.py)

목적: 11~3월 평일, 태양추적 기준 잉여 구간(PV_θST > L_θST)에서 PV 가 수요를 감당하는 한도까지 최대한 연다
     → 잉여 PV 를 일사 유입으로 돌려 난방·조명을 줄임. 구간 밖은 태양추적.

TiDE 는 각도별 PV·난방·조명(10각도 × 3 = 30) 예측만 담당하고, 각도는 예측값으로 정한다.
- 과거 입력: 태양추적 경로의 PV·난방·조명(lookback), 남측 존 온도·θ_ST (실제 운전에서 관측 가능한 값의 대리)
  10개 각도 전체의 과거값은 넣지 않는다 (관측 불가)
- 미래 입력: 기상·태양 위치·시간·스케줄·θ_ST + 각도별 cos 입사각, POA(→PV), 창 유입 일사 win_in(→난방·조명)
- 손실: MSE(정규화 30성분, 잉여 구간 스텝 가중 1+ALPHA_W) + BETA · pinball_τ(여유 y = PV − L, 잉여 구간 스텝만)
  τ < 0.5 → 여유 과대 예측(열었는데 부족)에 더 큰 벌점
- 학습 윈도우: horizon 전체가 11~3월인 윈도우 (주말 포함, 1스텝 간격). 에폭 선택: 검증(TMYx2004) 손실
- 분할: train IWEC / val TMYx.2004-2018 / test TMYx.2011-2025

각도 결정 (매일 07시 예측, 07:00~18:50 72스텝):
  구간_t = PV̂_θST > L̂_θST,  후보 θ ∈ [θ_ST, 90],  선택 = PV̂_θ ≥ (1+m)·L̂_θ 인 가장 큰 θ (없으면 θ_ST)
  후처리: θ − θ_ST < MIN_OPEN 이면 θ_ST, MIN_DWELL 스텝 미만으로 튀어나온 열림은 앞뒤 중 큰 각도로 낮춤
평가는 case2 실제값(선택 각도의 PV·수요)으로: 비교안 태양추적 / 잉여 구간 90° / TiDE / 오라클(실제값에 같은 규칙)

출력: checkpoints/tide_open_{best.pt, meta.json, eval.json}, schedules/open_{val,test}_m{m}.csv (E+ 플러그인 형식)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
sys.path.append(str(ROOT / "ai_model" / "tide"))
from tide_model import ResidualBlock, TiDEModel  # noqa: E402

DATA_DIR = BASE_DIR / "dataset_open"
CKPT_DIR = BASE_DIR / "checkpoints"
SCHED_DIR = BASE_DIR / "schedules"
SUNTRACKING = ROOT / "bipv_experiments" / "schedules" / "suntracking_w0s90.csv"

ANGLES = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
NA = len(ANGLES)
COP_HEATING = 2.5
WINTER = [11, 12, 1, 2, 3]
ISSUE_HOUR = 7
MIN_OPEN = 20      # θ_ST 보다 이만큼 이상 더 열 때만 제어
MIN_DWELL = 3      # 10분 스텝
M_LIST = [-0.05, 0.0, 0.05, 0.10]

TARGET_COLS = ([f"pv_gen_{a}" for a in ANGLES] + [f"heat_load_{a}" for a in ANGLES]
               + [f"lights_kwh_{a}" for a in ANGLES])
OBS_COLS = ["pv_st", "heat_st", "lights_st"]
PAST_COV_COLS = ["zone_temp_st", "theta_st"]
FUTURE_COV_COLS = (["outdoor_temp", "direct_solar", "diffuse_solar", "ghi", "outdoor_rh", "dewpoint", "wind_speed",
                    "sky_temp", "horiz_ir", "sky_cover", "sun_altitude", "sun_azimuth",
                    "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos", "is_weekend",
                    "occupancy", "heat_setpoint", "cool_setpoint", "theta_st"]
                   + [f"{c}_{a}" for c in ["cos_inc", "poa", "win_in"] for a in ANGLES])


# ── 모델: lookback 에 관측 가능한 태양추적 경로 값을 넣도록 TiDE 입력부만 바꾼다 ──
class TiDEObs(TiDEModel):
    def __init__(self, obs_dim: int, **kw):
        super().__init__(**kw)
        L, H, T, P = self.lookback_len, self.horizon_len, self.num_targets, self.proj_dim
        hidden, dropout = kw.get("hidden_dim", 256), kw.get("dropout", 0.1)
        enc_in = L * obs_dim + L * P + (L + H) * P
        blocks, d = [], enc_in
        for _ in range(kw.get("num_encoder_layers", 2)):
            blocks.append(ResidualBlock(d, hidden, hidden, dropout=dropout))
            d = hidden
        self.encoder = nn.Sequential(*blocks)
        self.lookback_residual = nn.Linear(L * obs_dim, H * T)


class OpenDataset(Dataset):
    def __init__(self, df, scaler, lookback, horizon, starts):
        self.L, self.H = lookback, horizon

        def norm(cs):
            m = np.array([scaler[c][0] for c in cs], dtype=np.float32)
            s = np.array([scaler[c][1] for c in cs], dtype=np.float32)
            return ((df[cs].to_numpy(dtype=np.float32) - m) / s).astype(np.float32)

        self.tgt, self.obs = norm(TARGET_COLS), norm(OBS_COLS)
        self.past, self.fut = norm(PAST_COV_COLS), norm(FUTURE_COV_COLS)
        self.win = df["window"].to_numpy(dtype=np.float32)
        self.starts = np.asarray(starts)  # horizon 시작 행

    def __len__(self):
        return len(self.starts)

    def __getitem__(self, i):
        h = self.starts[i]
        s, e = h - self.L, h + self.H
        f = torch.from_numpy
        return f(self.obs[s:h]), f(self.past[s:h]), f(self.fut[s:e]), f(self.tgt[h:e]), f(self.win[h:e])


def interval_start(df):
    return pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)


def train_starts(df, lookback, horizon):
    """horizon 전체가 11~3월 안인 시작 행 (1스텝 간격)"""
    winter = interval_start(df).dt.month.isin(WINTER).to_numpy()
    ok = np.convolve(winter, np.ones(horizon, int), "valid") == horizon  # ok[h]: h..h+H-1 모두 겨울
    h = np.flatnonzero(ok)
    return h[h >= lookback]


def issue_starts(df, lookback):
    """대상 평일(11~3월)의 07:00 시작 행"""
    t = interval_start(df)
    m = (df["target_day"] == 1) & (t.dt.hour == ISSUE_HOUR) & (t.dt.minute == 0)
    h = np.flatnonzero(m.to_numpy())
    return h[h >= lookback]


class Loss(nn.Module):
    def __init__(self, scaler, alpha_w, beta, tau):
        super().__init__()
        self.register_buffer("mean", torch.tensor([scaler[c][0] for c in TARGET_COLS]))
        self.register_buffer("std", torch.tensor([scaler[c][1] for c in TARGET_COLS]))
        self.alpha_w, self.beta, self.tau = alpha_w, beta, tau

    def margin(self, z):
        p = z * self.std + self.mean
        return p[..., :NA] - (p[..., NA:2 * NA] / COP_HEATING + p[..., 2 * NA:])

    def forward(self, pred, true, win):
        w = 1.0 + self.alpha_w * win
        mse = (((pred - true) ** 2).mean(-1) * w).sum() / w.sum()
        if self.beta == 0:
            return mse
        err = self.margin(true) - self.margin(pred)  # < 0: 여유 과대 예측
        pin = torch.maximum(self.tau * err, (self.tau - 1.0) * err).mean(-1)
        n = win.sum().clamp(min=1.0)
        return mse + self.beta * (pin * win).sum() / n


def run_epoch(model, loader, device, crit, opt=None):
    model.train(opt is not None)
    tot, n = 0.0, 0
    with torch.set_grad_enabled(opt is not None):
        for obs, pc, fc, hz, win in loader:
            obs, pc, fc, hz, win = (x.to(device) for x in (obs, pc, fc, hz, win))
            loss = crit(model(obs, pc, fc), hz, win)
            if opt is not None:
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
            tot += loss.item() * len(obs)
            n += len(obs)
    return tot / n


def predict(model, ds, device, scaler):
    """(N, H, 30) 원 단위 예측"""
    model.eval()
    out = []
    with torch.no_grad():
        for obs, pc, fc, _, _ in DataLoader(ds, batch_size=256):
            out.append(model(obs.to(device), pc.to(device), fc.to(device)).cpu().numpy())
    m = np.array([scaler[c][0] for c in TARGET_COLS], dtype=np.float32)
    s = np.array([scaler[c][1] for c in TARGET_COLS], dtype=np.float32)
    return np.clip(np.concatenate(out) * s + m, 0.0, None)


# ── 각도 결정 ──
def split_pl(x):
    """(.., 30) → PV (.., 10), 수요 L (.., 10) [겨울: 냉방 0]"""
    return x[..., :NA], x[..., NA:2 * NA] / COP_HEATING + x[..., 2 * NA:]


def smooth(theta, base):
    """열린(θ > θ_ST) 상태가 MIN_DWELL 스텝 미만으로 튀어나온 구간을 앞뒤 중 큰 각도(덜 열림 아님)로 낮춘다.
    덜 여는 방향으로만 바꾸므로 부족을 새로 만들지 않는다. 반복해 더 이상 바뀌지 않을 때까지."""
    th = theta.copy()
    for _ in range(20):
        changed = False
        b = np.flatnonzero(np.diff(th) != 0) + 1
        edges = np.r_[0, b, len(th)]
        for s, e in zip(edges[:-1], edges[1:]):
            if e - s >= MIN_DWELL or th[s] <= base[s:e].max():
                continue
            nb = [th[s - 1]] if s > 0 else []
            nb += [th[e]] if e < len(th) else []
            new = max([v for v in nb if v < th[s]], default=None)
            if new is None:
                continue
            th[s:e] = np.maximum(new, base[s:e])
            changed = True
        if not changed:
            break
    return th


def decide(pv, L, theta_st, m, window=None):
    """pv, L: (D, H, 10), theta_st: (D, H) → θ (D, H), 구간 (D, H). window 를 주면 그 구간을 쓴다(오라클)."""
    D, H = theta_st.shape
    ist = theta_st // 10
    take = lambda x: np.take_along_axis(x, ist[..., None], -1)[..., 0]
    win = (take(pv) > take(L)) if window is None else window.astype(bool)
    feas = (ANGLES[None, None, :] >= theta_st[..., None]) & (pv >= (1.0 + m) * L)
    best = np.where(feas, ANGLES[None, None, :], -1).max(-1)
    theta = np.where(win & (best >= 0), best, theta_st)
    theta = np.where(theta - theta_st < MIN_OPEN, theta_st, theta)
    for d in range(D):
        theta[d] = smooth(theta[d], theta_st[d])
    return theta, win


def evaluate(theta, true, theta_st, win_true):
    """case2 실제값으로 선택 각도의 결과 합산 (07:00~18:50, 대상 평일)"""
    pv, L = split_pl(true)
    idx = (theta // 10)[..., None]
    g = lambda x: np.take_along_axis(x, idx, -1)[..., 0]
    P, Ld = g(pv), g(L)
    heat, lights = g(true[..., NA:2 * NA]), g(true[..., 2 * NA:])
    buy, sur = np.clip(Ld - P, 0, None), np.clip(P - Ld, 0, None)
    pv_st, L_st = (np.take_along_axis(x, (theta_st // 10)[..., None], -1)[..., 0] for x in (pv, L))
    viol = (theta != theta_st) & (P < Ld)
    D = len(theta)
    moves = (np.diff(theta, axis=1) != 0).sum() / D
    deg = np.abs(np.diff(theta, axis=1)).sum() / D
    wm = win_true.astype(bool)
    return {
        "구매_kWh": buy.sum(), "잉여_kWh": sur.sum(), "PV_kWh": P.sum(), "수요_kWh": Ld.sum(),
        "난방열_kWh": heat.sum(), "조명_kWh": lights.sum(),
        "구간_구매_kWh": buy[wm].sum(), "구간_잉여_kWh": sur[wm].sum(),
        "구간_수요감소_kWh": (L_st - Ld)[wm].sum(), "구간_PV감소_kWh": (pv_st - P)[wm].sum(),
        "위반_스텝": int(viol.sum()), "위반_부족_kWh": (Ld - P)[viol].sum(),
        "제어_스텝": int((theta != theta_st).sum()), "이동_회수/일": moves, "이동_각도°/일": deg,
    }


def export_schedule(theta, starts, H, path):
    sched = pd.read_csv(SUNTRACKING)
    ang = sched["optimal_angle"].to_numpy().copy()
    for d, h in enumerate(starts):
        ang[h:h + H] = theta[d]
    sched["optimal_angle"] = ang.astype(int)
    sched.to_csv(path, index=False)


def r2(p, t):
    return 1.0 - ((p - t) ** 2).sum() / max(((t - t.mean()) ** 2).sum(), 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch_size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--lookback", type=int, default=144)
    ap.add_argument("--horizon", type=int, default=72)
    ap.add_argument("--alpha_w", type=float, default=4.0, help="잉여 구간 스텝 MSE 가중 (1+alpha_w)")
    ap.add_argument("--beta", type=float, default=1.0, help="여유 pinball 손실 계수")
    ap.add_argument("--tau", type=float, default=0.3, help="pinball 분위 (< 0.5 → 과대 예측 벌점 큼)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--eval_only", action="store_true")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    CKPT_DIR.mkdir(exist_ok=True)
    SCHED_DIR.mkdir(exist_ok=True)
    L, H = args.lookback, args.horizon

    dfs = {n: pd.read_csv(DATA_DIR / f"open_{n}.csv") for n in ["train", "val", "test"]}
    tr_starts = train_starts(dfs["train"], L, H)
    tr_rows = np.unique(np.concatenate([np.arange(h - L, h + H) for h in tr_starts]))
    cols = TARGET_COLS + OBS_COLS + PAST_COV_COLS + FUTURE_COV_COLS
    sub = dfs["train"].iloc[tr_rows]
    scaler = {c: (float(sub[c].mean()), float(sub[c].std()) if sub[c].std() > 1e-6 else 1.0) for c in cols}

    model = TiDEObs(obs_dim=len(OBS_COLS), lookback_len=L, horizon_len=H, num_targets=len(TARGET_COLS),
                    past_cov_dim=len(PAST_COV_COLS), future_cov_dim=len(FUTURE_COV_COLS),
                    hidden_dim=args.hidden_dim, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
                    decoder_output_dim=32, dropout=0.1).to(device)
    crit = Loss(scaler, args.alpha_w, args.beta, args.tau).to(device)
    ckpt = CKPT_DIR / "tide_open_best.pt"
    print(f"[*] device {device}, 타깃 {len(TARGET_COLS)}, obs {len(OBS_COLS)}, past {len(PAST_COV_COLS)}, "
          f"future {len(FUTURE_COV_COLS)}, 파라미터 {sum(p.numel() for p in model.parameters()):,}")

    if not args.eval_only:
        tr_ds = OpenDataset(dfs["train"], scaler, L, H, tr_starts)
        va_ds = OpenDataset(dfs["val"], scaler, L, H, train_starts(dfs["val"], L, H))
        tr_ld = DataLoader(tr_ds, batch_size=args.batch_size, shuffle=True, drop_last=True)
        va_ld = DataLoader(va_ds, batch_size=512)
        print(f"[*] 윈도우 train {len(tr_ds):,} / val {len(va_ds):,}")
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
        best, hist = float("inf"), []
        for ep in range(1, args.epochs + 1):
            t0 = time.time()
            tr = run_epoch(model, tr_ld, device, crit, opt)
            va = run_epoch(model, va_ld, device, crit)
            sch.step()
            hist.append({"epoch": ep, "train": tr, "val": va})
            mark = ""
            if va < best:
                best, mark = va, " *"
                torch.save(model.state_dict(), ckpt)
            print(f"  ep {ep:2d} train {tr:.4f} val {va:.4f} ({time.time() - t0:.0f}s){mark}", flush=True)
        meta = {"args": vars(args), "scaler": scaler, "history": hist, "target_cols": TARGET_COLS,
                "obs_cols": OBS_COLS, "past_cov_cols": PAST_COV_COLS, "future_cov_cols": FUTURE_COV_COLS}
        (CKPT_DIR / "tide_open_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    model.load_state_dict(torch.load(ckpt, map_location=device))

    # ── 각도 결정·평가 ──
    report = {}
    for split in ["val", "test"]:
        df = dfs[split]
        starts = issue_starts(df, L)
        ds = OpenDataset(df, scaler, L, H, starts)
        pred = predict(model, ds, device, scaler)
        rows = starts[:, None] + np.arange(H)[None, :]
        true = df[TARGET_COLS].to_numpy()[rows]
        theta_st = df["theta_st"].to_numpy().astype(int)[rows]
        win_true = df["window"].to_numpy()[rows]

        pv_p, L_p = split_pl(pred)
        pv_t, L_t = split_pl(true)
        _, win_pred = decide(pv_p, L_p, theta_st, 0.0)
        wt = win_true.astype(bool)
        rep = {"일수": len(starts),
               "구간_정밀도": float((win_pred & wt).sum() / max(win_pred.sum(), 1)),
               "구간_재현율": float((win_pred & wt).sum() / max(wt.sum(), 1)),
               "R2_구간": {k: float(r2(p[wt], t[wt])) for k, p, t in
                          [("PV", pv_p, pv_t), ("수요", L_p, L_t), ("여유", pv_p - L_p, pv_t - L_t)]}}

        rows_tab = {"태양추적": evaluate(theta_st, true, theta_st, win_true),
                    "구간90°": evaluate(np.where(wt, 90, theta_st), true, theta_st, win_true)}
        for m in M_LIST:
            th_o, _ = decide(pv_t, L_t, theta_st, m, window=win_true)
            th_p, _ = decide(pv_p, L_p, theta_st, m)
            rows_tab[f"오라클 m={m:+.2f}"] = evaluate(th_o, true, theta_st, win_true)
            rows_tab[f"TiDE m={m:+.2f}"] = evaluate(th_p, true, theta_st, win_true)
            export_schedule(th_p, starts, H, SCHED_DIR / f"open_{split}_m{m:+.2f}.csv")
            if m == 0.0:
                ang = th_p[wt]
                rep["TiDE_m0_구간각도분포%"] = {int(a): round(float((ang == a).mean() * 100), 1) for a in np.unique(ang)}
        tab = pd.DataFrame(rows_tab).T
        rep["표"] = tab.round(2).to_dict(orient="index")
        report[split] = rep

        print(f"\n===== {split} ({len(starts)}일, 07:00~18:50, case2 실제값) =====")
        print(f"구간 정밀도 {rep['구간_정밀도']:.3f} / 재현율 {rep['구간_재현율']:.3f} | 구간 R² " +
              ", ".join(f"{k} {v:.3f}" for k, v in rep["R2_구간"].items()))
        print(f"TiDE m=0 구간 각도 분포(%): {rep['TiDE_m0_구간각도분포%']}")
        show = ["구매_kWh", "잉여_kWh", "수요_kWh", "난방열_kWh", "조명_kWh", "구간_수요감소_kWh", "구간_PV감소_kWh",
                "위반_스텝", "위반_부족_kWh", "제어_스텝", "이동_회수/일", "이동_각도°/일"]
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(tab[show].round(1).to_string())

    (CKPT_DIR / "tide_open_eval.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=float),
                                                  encoding="utf-8")
    print(f"\n[*] {CKPT_DIR / 'tide_open_eval.json'}\n[*] {SCHED_DIR}/open_{{val,test}}_m*.csv")


if __name__ == "__main__":
    main()

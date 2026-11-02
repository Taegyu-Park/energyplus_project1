"""
bipv_mismatch/tide_policy/train_tide_policy.py
==============================================
TIDE_POLICY_OBJECTIVE.md 1차 구현: TiDE가 하루치(07시 ~ 다음 날 07시, 144스텝) PV 각도 궤적을 직접 출력한다.

- 손실 (날짜별 정규화, 채광 항 없음 μ = 0, 2026-11-02 사용자 결정):
    J_d(θ) = Σₜ [ w_def·max(D−P, 0) + w_sur·max(P−D, 0) ] + λ_move·Σₜ |θₜ − θₜ₋₁| / 10°
    loss  = J_d(θ) / J_d(θ_ST)       (학습은 softplus로 부드럽게 한 hinge, 평가는 hard hinge)
- 가중치: w_sur = 1 고정, w_def ∈ {1.0, 1.2, 1.4, 1.6}을 한 번에 학습·비교 (2026-11-02 사용자 결정)
- 각도: θ = θ_ST + (90 − θ_ST)·sigmoid(z), 조절 구간 M_d 밖은 θ_ST 고정
  M_d = 태양추적 잉여 스텝 {P_ST > D_ST}를 앞뒤 k스텝(기본 6 = 1시간) 넓힌 범위
- P, D: case2 10개 고정각 결과(dataset_final/case2_mm_*.csv의 pv_gen_{a}, demand_elec_{a})를 각도 사이 선형 보간
- θ_ST: data/bipv_suntracking_angles_annual_winter0_summer90.csv (52,560행, 순서대로 대응)
- 입력:
    lookback 타깃   net_ST = P_ST − D_ST (전날 07시 ~ 당일 07시)
    과거 공변량     P_ST, D_ST, 남측 존 온도(θ_ST), 외기온, 직달·확산 일사, 운량
    미래 공변량     train_tide_mm.py의 미래 공변량 + θ_ST + 태양추적 잉여 여부
  10개 각도의 과거 성분은 넣지 않는다 (실제 운전에서 관측 불가).
- 분할: train = IWEC, val = TMYx2004 (에폭 선택), test = TMYx2011. 겨울(11~3월)에 시작하는 날만.
- 비교: 태양추적(θ_ST), 잉여 구간 90° 규칙(태양추적 잉여 스텝만 90°), TiDE(w_def별)
  지표는 대리 모델(P_tab/D_tab 보간) 기준이며 E+ 폐루프 결과가 아니다.

출력: bipv_mismatch/tide_policy/out/
  w{w_def}_best.pt, scaler.json, history.json, summary.json
  week_angles.csv / week_angles.png: --week_split 의 --week_start 부터 --days 일 각도 궤적
  week_daily.csv: 같은 기간 날짜별 구매·잉여·미스매치

사용 (데이터가 있는 PC, 저장소 루트에서):
  uv run python bipv_mismatch/tide_policy/train_tide_policy.py
  uv run python bipv_mismatch/tide_policy/train_tide_policy.py --week_split train --week_start 2006-01-09
"""

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

HERE = Path(__file__).resolve().parent
MM_DIR = HERE.parent
ROOT = MM_DIR.parent
sys.path.append(str(ROOT / "ai_model" / "tide"))
from tide_model import TiDEModel  # noqa: E402

DATA_DIR = MM_DIR / "dataset_final"
ST_CSV = ROOT / "data" / "bipv_suntracking_angles_annual_winter0_summer90.csv"
OUT_DIR = HERE / "out"

ANGLES = list(range(0, 100, 10))
EVAL_MONTHS = [11, 12, 1, 2, 3]
DAY = 144          # 10분 × 144 = 24시간
DAY_START_HOUR = 7  # 하루 = 07시 ~ 다음 날 07시

PV_COLS = [f"pv_gen_{a}" for a in ANGLES]
DEM_COLS = [f"demand_elec_{a}" for a in ANGLES]
ZONE_COLS = [f"south_zone_temp_{a}" for a in ANGLES]
FUTURE_BASE = (
    ["outdoor_temp", "direct_solar", "diffuse_solar", "outdoor_rh", "dewpoint", "wind_speed",
     "sky_temp", "horiz_ir", "sky_cover", "sun_altitude", "sun_azimuth",
     "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos", "is_weekend",
     "occupancy", "heat_setpoint", "cool_setpoint"]
    + [f"cos_inc_{a}" for a in ANGLES]
    + [f"poa_{a}" for a in ANGLES]
)
LOOKBACK_COLS = ["net_st"]
PAST_COLS = ["pv_st", "dem_st", "zone_st", "outdoor_temp", "direct_solar", "diffuse_solar", "sky_cover"]
FUTURE_COLS = FUTURE_BASE + ["theta_st", "sur_st"]


# ── 데이터 ─────────────────────────────────────────────────────────────
def load_split(name: str):
    need = {"timestamp", *PV_COLS, *DEM_COLS, *ZONE_COLS, *FUTURE_BASE}
    df = pd.read_csv(DATA_DIR / f"case2_mm_{name}.csv", usecols=lambda c: c in need)
    st = pd.read_csv(ST_CSV)
    if len(st) != len(df):
        raise ValueError(f"{name}: 태양추적 스케줄 {len(st)}행 ≠ 데이터 {len(df)}행")
    d_alt = np.abs(st["sun_altitude"].to_numpy() - df["sun_altitude"].to_numpy()).max()
    if d_alt > 1.0:
        raise ValueError(f"{name}: 태양고도 불일치 (최대 {d_alt:.2f}°), 스케줄 행 순서 확인 필요")

    P = df[PV_COLS].to_numpy(np.float32)
    D = df[DEM_COLS].to_numpy(np.float32)
    theta_st = st["optimal_angle"].to_numpy(np.float32)
    k = np.rint(theta_st / 10).astype(int).clip(0, 9)
    rows = np.arange(len(df))
    df["theta_st"] = theta_st
    df["pv_st"] = P[rows, k]
    df["dem_st"] = D[rows, k]
    df["zone_st"] = df[ZONE_COLS].to_numpy()[rows, k]
    df["net_st"] = df["pv_st"] - df["dem_st"]
    df["sur_st"] = (df["net_st"] > 0).astype(np.float32)
    df["start"] = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)  # 구간 끝 라벨 → 시작 시각
    return df, P, D


def fit_scaler(df):
    sc = {}
    for c in dict.fromkeys(LOOKBACK_COLS + PAST_COLS + FUTURE_COLS):
        s = float(df[c].std())
        sc[c] = (float(df[c].mean()), s if s > 1e-6 else 1.0)
    return sc


class DayDataset(Dataset):
    """하루(07시 시작) 단위 샘플. lookback = 직전 144스텝, horizon = 144스텝."""

    def __init__(self, df, P, D, scaler, k_dilate):
        start = df["start"]
        ok = ((start.dt.hour == DAY_START_HOUR) & (start.dt.minute == 0)
              & start.dt.month.isin(EVAL_MONTHS)).to_numpy()
        idx = np.flatnonzero(ok)
        self.idx = idx[(idx >= DAY) & (idx + DAY <= len(df))]
        self.dates = start.iloc[self.idx].dt.normalize().to_numpy()
        self.weekday = (start.iloc[self.idx].dt.dayofweek < 5).to_numpy()
        self.start = start.to_numpy()

        def norm(cols):
            m = np.array([scaler[c][0] for c in cols], np.float32)
            s = np.array([scaler[c][1] for c in cols], np.float32)
            return (df[cols].to_numpy(np.float32) - m) / s

        self.lb, self.pc, self.fc = norm(LOOKBACK_COLS), norm(PAST_COLS), norm(FUTURE_COLS)
        self.P, self.D = P, D
        self.theta_st = df["theta_st"].to_numpy(np.float32)
        sur = df["sur_st"].to_numpy() > 0
        win = np.ones(2 * k_dilate + 1)
        # 하루 단위로 넓힌다 (날짜 경계를 넘어 번지지 않게)
        self.mask = np.stack([np.convolve(sur[s:s + DAY], win, "same") > 0 for s in self.idx])
        self.sur = np.stack([sur[s:s + DAY] for s in self.idx])

    def __len__(self):
        return len(self.idx)

    def __getitem__(self, i):
        s = self.idx[i]
        h = slice(s, s + DAY)
        return (torch.from_numpy(self.lb[s - DAY:s]), torch.from_numpy(self.pc[s - DAY:s]),
                torch.from_numpy(self.fc[s - DAY:s + DAY]), torch.from_numpy(self.P[h]),
                torch.from_numpy(self.D[h]), torch.from_numpy(self.theta_st[h]),
                torch.from_numpy(self.mask[i]))


# ── 각도·비용 ──────────────────────────────────────────────────────────
def to_theta(z, theta_st, mask):
    theta = theta_st + (90.0 - theta_st) * torch.sigmoid(z.squeeze(-1))
    return torch.where(mask, theta, theta_st)


def lerp_tab(tab, theta):
    """tab: (B, T, 10) 각도별 값, theta: (B, T) [°] → 10° 격자 사이 선형 보간"""
    x = theta / 10.0
    i = x.floor().clamp(0, 8).long()
    f = x - i
    a = tab.gather(-1, i.unsqueeze(-1)).squeeze(-1)
    b = tab.gather(-1, (i + 1).unsqueeze(-1)).squeeze(-1)
    return a + f * (b - a)


def day_cost(theta, P, D, w_def, w_sur, lam_move, smooth=None):
    """반환: (J, 구매, 잉여, 이동[°]) 각 (B,). smooth=k 이면 softplus(k·x)/k 로 부드럽게 한 hinge."""
    e = lerp_tab(P, theta) - lerp_tab(D, theta)
    if smooth:
        sur, dfc = F.softplus(e * smooth) / smooth, F.softplus(-e * smooth) / smooth
    else:
        sur, dfc = e.clamp(min=0), (-e).clamp(min=0)
    move = (theta[:, 1:] - theta[:, :-1]).abs().sum(1)
    J = (w_def * dfc + w_sur * sur).sum(1) + lam_move * move / 10.0
    return J, dfc.sum(1), sur.sum(1), move


def build_model(args):
    return TiDEModel(
        lookback_len=DAY, horizon_len=DAY, num_targets=len(LOOKBACK_COLS),
        past_cov_dim=len(PAST_COLS), future_cov_dim=len(FUTURE_COLS),
        hidden_dim=args.hidden_dim, proj_dim=16, num_encoder_layers=2, num_decoder_layers=2,
        decoder_output_dim=32, dropout=0.1,
    )


def run_epoch(model, loader, device, w_def, args, optimizer=None):
    """평균 정규화 손실 J/J_ST. optimizer 가 있으면 학습(부드러운 hinge), 없으면 평가(hard hinge)."""
    train = optimizer is not None
    model.train(train)
    total, n = 0.0, 0
    with torch.set_grad_enabled(train):
        for lb, pc, fc, P, D, th_st, m in loader:
            lb, pc, fc, P, D, th_st, m = (t.to(device) for t in (lb, pc, fc, P, D, th_st, m))
            theta = to_theta(model(lb, pc, fc), th_st, m)
            smooth = args.smooth if train else None
            J, *_ = day_cost(theta, P, D, w_def, args.w_sur, args.lam_move, smooth)
            J_st, *_ = day_cost(th_st, P, D, w_def, args.w_sur, args.lam_move)
            loss = (J / J_st.clamp(min=1e-3)).mean()
            if train:
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total += loss.item() * len(lb)
            n += len(lb)
    return total / n


@torch.no_grad()
def rollout(model, ds, device):
    model.eval()
    out = []
    for lb, pc, fc, P, D, th_st, m in DataLoader(ds, batch_size=64):
        z = model(lb.to(device), pc.to(device), fc.to(device))
        out.append(to_theta(z, th_st.to(device), m.to(device)).cpu())
    return torch.cat(out).numpy()


def policy_metrics(theta, ds, w_def, args):
    """날짜별 구매·잉여·미스매치·이동 (hard hinge, 대리 모델 기준). theta: (N, 144)"""
    P = torch.from_numpy(np.stack([ds.P[s:s + DAY] for s in ds.idx]))
    D = torch.from_numpy(np.stack([ds.D[s:s + DAY] for s in ds.idx]))
    th = torch.as_tensor(theta, dtype=torch.float32)
    J, buy, sur, move = day_cost(th, P, D, w_def, args.w_sur, args.lam_move)
    f64 = lambda x: x.numpy().astype(np.float64)  # noqa: E731
    return pd.DataFrame({"date": ds.dates, "weekday": ds.weekday, "J": f64(J), "purchase": f64(buy),
                         "surplus": f64(sur), "mismatch": f64(buy + sur), "move_deg": f64(move)})


def baselines(ds):
    th_st = np.stack([ds.theta_st[s:s + DAY] for s in ds.idx])
    return {"태양추적": th_st, "잉여구간90°": np.where(ds.sur, 90.0, th_st)}


def summarize(theta_by_policy, ds, w_def, args):
    """평일 합계 (kWh), 이동은 °/일"""
    rows = {}
    for name, th in theta_by_policy.items():
        m = policy_metrics(th, ds, w_def, args)
        m = m[m.weekday]
        rows[name] = {"구매": m.purchase.sum(), "잉여": m.surplus.sum(), "미스매치": m.mismatch.sum(),
                      "이동°/일": m.move_deg.mean(), "일수": len(m)}
    return pd.DataFrame(rows).T


# ── 주간 출력 ──────────────────────────────────────────────────────────
def export_week(models, dss, args, device):
    ds = dss[args.week_split]
    t0 = pd.Timestamp(args.week_start)
    sel = np.flatnonzero((ds.dates >= t0) & (ds.dates < t0 + pd.Timedelta(days=args.days)))
    if len(sel) == 0:
        raise ValueError(f"{args.week_split}: {args.week_start}부터 {args.days}일에 해당하는 날이 없음")
    sub = copy.copy(ds)
    sub.idx, sub.dates, sub.weekday = ds.idx[sel], ds.dates[sel], ds.weekday[sel]
    sub.mask, sub.sur = ds.mask[sel], ds.sur[sel]

    pol = baselines(sub)
    for w, model in models.items():
        pol[f"TiDE w_def={w:g}"] = rollout(model, sub, device)

    steps = np.concatenate([np.arange(s, s + DAY) for s in sub.idx])
    P = torch.from_numpy(ds.P[steps])
    D = torch.from_numpy(ds.D[steps])
    cols = {"start": ds.start[steps], "mask": sub.mask.ravel().astype(int)}
    for name, th in pol.items():
        th = th.ravel()
        tt = torch.as_tensor(th, dtype=torch.float32)[None]
        cols[f"angle[{name}]"] = np.round(th, 2)
        cols[f"pv[{name}]"] = lerp_tab(P[None], tt)[0].numpy().round(4)
        cols[f"dem[{name}]"] = lerp_tab(D[None], tt)[0].numpy().round(4)
    pd.DataFrame(cols).to_csv(OUT_DIR / "week_angles.csv", index=False, encoding="utf-8-sig")

    daily = []
    for name, th in pol.items():
        m = policy_metrics(th, sub, 1.0, args).assign(policy=name)
        daily.append(m[["policy", "date", "purchase", "surplus", "mismatch", "move_deg"]])
    daily = pd.concat(daily)
    daily.round({"purchase": 3, "surplus": 3, "mismatch": 3, "move_deg": 2}).to_csv(OUT_DIR / "week_daily.csv", index=False, encoding="utf-8-sig")
    print(f"\n===== {args.week_split} {args.week_start} ~ {args.days}일: 정책별 합계 (kWh, 대리 모델) =====")
    print(daily.groupby("policy", sort=False)[["purchase", "surplus", "mismatch", "move_deg"]].sum().round(2).to_string())

    plt.rcParams["font.family"] = ["Malgun Gothic", "NanumGothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(16, 4.5))
    t = pd.to_datetime(cols["start"])
    ax.step(t, pol["태양추적"].ravel(), where="post", color="#64748b", lw=1.2, ls="--", label="태양추적")
    ax.step(t, pol["잉여구간90°"].ravel(), where="post", color="#94a3b8", lw=1.0, label="잉여구간 90°")
    colors = ["#2563eb", "#16a34a", "#d97706", "#dc2626"]
    for c, w in zip(colors, models):
        ax.step(t, pol[f"TiDE w_def={w:g}"].ravel(), where="post", color=c, lw=1.4, label=f"TiDE w_def={w:g}")
    ax.set_ylabel("PV 각도 [°]")
    ax.set_ylim(-3, 93)
    ax.legend(ncol=6, fontsize=9, loc="upper left")
    ax.set_title(f"{args.week_split} {args.week_start} ~ {args.days}일: TiDE 각도 (w_sur = 1)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "week_angles.png", dpi=150)
    plt.close(fig)
    print(f"[*] {OUT_DIR / 'week_angles.csv'}\n[*] {OUT_DIR / 'week_daily.csv'}\n[*] {OUT_DIR / 'week_angles.png'}")


# ── main ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="1.0,1.2,1.4,1.6", help="w_def 목록 (w_sur = 1)")
    ap.add_argument("--w_sur", type=float, default=1.0)
    ap.add_argument("--lam_move", type=float, default=0.05, help="kWh per 10° 이동")
    ap.add_argument("--k_dilate", type=int, default=6, help="조절 구간 확장 스텝 (6 = 1시간)")
    ap.add_argument("--smooth", type=float, default=50.0, help="softplus 기울기 [1/kWh]")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden_dim", type=int, default=256)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--week_split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--week_start", default="2006-01-09", help="주간 출력 시작일 (2006-01-09 = 월요일)")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available()
                          else ("cpu" if args.device == "auto" else args.device))
    weights = [float(w) for w in args.weights.split(",")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] device {device} | w_def {weights} (w_sur {args.w_sur}) | λ_move {args.lam_move} | k {args.k_dilate}")

    raw = {n: load_split(n) for n in ["train", "val", "test"]}
    scaler = fit_scaler(raw["train"][0])
    dss = {n: DayDataset(df, P, D, scaler, args.k_dilate) for n, (df, P, D) in raw.items()}
    print("[*] 날짜 수 " + ", ".join(f"{n} {len(d)}" for n, d in dss.items()))
    with open(OUT_DIR / "scaler.json", "w", encoding="utf-8") as f:
        json.dump(scaler, f, indent=2)

    train_loader = DataLoader(dss["train"], batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(dss["val"], batch_size=64)
    models, history, summary = {}, {}, {"args": vars(args)}
    for w in weights:
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)
        model = build_model(args).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)
        best, best_state, hist = (np.inf, 0), None, []
        print(f"\n--- w_def = {w:g} ---")
        for ep in range(1, args.epochs + 1):
            t = time.time()
            tr = run_epoch(model, train_loader, device, w, args, opt)
            va = run_epoch(model, val_loader, device, w, args)
            sched.step()
            hist.append({"epoch": ep, "train": tr, "val": va})
            mark = ""
            if va < best[0]:
                best, best_state, mark = (va, ep), copy.deepcopy(model.state_dict()), " *"
            if ep == 1 or ep % 5 == 0 or mark:
                print(f"ep {ep:3d} | train J/J_ST {tr:.5f} | val {va:.5f} | {time.time() - t:4.1f}s{mark}", flush=True)
        model.load_state_dict(best_state)
        torch.save({"epoch": best[1], "model_state_dict": best_state, "args": vars(args), "w_def": w},
                   OUT_DIR / f"w{w:g}_best.pt")
        models[w], history[f"{w:g}"] = model, {"best_epoch": best[1], "history": hist}

    pd.set_option("display.width", 200)
    for name in ["val", "test"]:
        ds = dss[name]
        pol = baselines(ds)
        for w, model in models.items():
            pol[f"TiDE w_def={w:g}"] = rollout(model, ds, device)
        tab = summarize(pol, ds, 1.0, args)
        summary[name] = tab.round(3).to_dict(orient="index")
        print(f"\n===== {name} 겨울 평일 합계 (kWh, 대리 모델, 07~07시) =====")
        print(tab.round(2).to_string())

    with open(OUT_DIR / "history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    export_week(models, dss, args, device)


if __name__ == "__main__":
    main()

"""
plot_open_angles.py
===================
train_tide_open.py 가 만든 각도 스케줄(테스트 TMYx2011, m=0) 시각화.
  (a) 11~3월 평일 × 07~19시 각도 지도 (태양추적에서 바뀐 스텝만 색, 나머지 회색)
  (b) 1월 둘째 주 평일 5일: 태양추적 vs TiDE 각도, 잉여 구간 음영
  (c) 그 주 가운데 하루: 선택 각도의 PV·수요 (case2 실제값) vs 태양추적
출력: figures_open/open_angles_test_m0.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "figures_open" / "open_angles_test_m0.png"
WEEK = ("2006-01-09", "2006-01-13")  # 월~금
DAY = "2006-01-11"
ANGLES = np.arange(0, 100, 10)

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def main():
    df = pd.read_csv(BASE_DIR / "dataset_open" / "open_test.csv")
    sch = pd.read_csv(BASE_DIR / "schedules" / "open_test_m+0.00.csv")
    df["t"] = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)
    df["theta"] = sch["optimal_angle"].to_numpy()
    df["theta_st"] = df["theta_st"].astype(int)
    r = np.arange(len(df))
    pick = lambda c, th: df[[f"{c}_{a}" for a in ANGLES]].to_numpy()[r, th // 10]
    dem = lambda th: pick("heat_load", th) / 2.5 + pick("lights_kwh", th)
    df["pv_sel"], df["dem_sel"] = pick("pv_gen", df["theta"].to_numpy()), dem(df["theta"].to_numpy())
    df["dem_st"] = dem(df["theta_st"].to_numpy())

    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.3, 0.9, 0.9], hspace=0.42)

    # (a) 각도 지도
    ax = fig.add_subplot(gs[0])
    d = df[(df["target_day"] == 1) & (df["t"].dt.hour >= 7) & (df["t"].dt.hour < 19)].copy()
    d["date"], d["hm"] = d["t"].dt.date, d["t"].dt.hour + d["t"].dt.minute / 60
    grid = d.pivot(index="hm", columns="date", values="theta").astype(float)
    ctrl = d.pivot(index="hm", columns="date", values="theta").ne(d.pivot(index="hm", columns="date", values="theta_st"))
    dates = list(grid.columns)
    ax.imshow(np.where(ctrl, np.nan, 1.0), aspect="auto", origin="lower", cmap="Greys", vmin=0, vmax=4,
              extent=[0, len(dates), 7, 19])
    im = ax.imshow(np.where(ctrl, grid, np.nan), aspect="auto", origin="lower", cmap="viridis", vmin=40, vmax=90,
                   extent=[0, len(dates), 7, 19])
    ticks = [i for i, x in enumerate(dates) if x.day <= 7 and (i == 0 or dates[i - 1].month != x.month)]
    ax.set_xticks([i + 0.5 for i in ticks], [f"{dates[i].month}월" for i in ticks])
    ax.set_yticks(range(7, 20, 2), [f"{h:02d}:00" for h in range(7, 20, 2)])
    ax.set_title(f"(a) 11~3월 평일 {len(dates)}일 × 07~19시: 태양추적에서 벗어난 각도 (회색 = 태양추적 유지)",
                 loc="left", fontweight="bold")
    fig.colorbar(im, ax=ax, label="각도 [°] (90 = 수평·개방)", pad=0.01)

    # (b) 한 주 각도
    ax = fig.add_subplot(gs[1])
    w = df[(df["t"] >= WEEK[0]) & (df["t"] < pd.Timestamp(WEEK[1]) + pd.Timedelta(days=1))
           & (df["t"].dt.hour >= 6) & (df["t"].dt.hour < 20)]
    for day, g in w.groupby(w["t"].dt.date):
        win = g["window"].to_numpy() == 1
        for s, e in zip(*np.where(np.diff(np.r_[0, win, 0]) != 0)[0].reshape(-1, 2).T):
            ax.axvspan(g["t"].iloc[s], g["t"].iloc[e - 1] + pd.Timedelta(minutes=10), color="#10b981", alpha=0.15, lw=0)
        ax.step(g["t"], g["theta_st"], where="post", color="#64748b", lw=1.3, ls="--")
        ax.step(g["t"], g["theta"], where="post", color="#2563eb", lw=1.8)
    ax.plot([], [], color="#64748b", ls="--", label="태양추적")
    ax.plot([], [], color="#2563eb", lw=1.8, label="TiDE (m=0)")
    ax.fill_between([], [], color="#10b981", alpha=0.15, label="잉여 구간 (태양추적 기준)")
    ax.set_ylim(-5, 100)
    ax.set_ylabel("각도 [°]")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H시"))
    ax.legend(ncol=3, fontsize=9, loc="upper left")
    ax.set_title(f"(b) {WEEK[0][5:]} ~ {WEEK[1][5:]} 평일 (06~20시만 표시)", loc="left", fontweight="bold")

    # (c) 하루 PV·수요
    ax = fig.add_subplot(gs[2])
    g = df[(df["t"].dt.date == pd.Timestamp(DAY).date()) & (df["t"].dt.hour >= 7) & (df["t"].dt.hour < 19)]
    ax.step(g["t"], g["pv_st"], where="post", color="#f59e0b", ls="--", lw=1.2, label="PV 태양추적")
    ax.step(g["t"], g["pv_sel"], where="post", color="#f59e0b", lw=1.8, label="PV TiDE 각도")
    ax.step(g["t"], g["dem_st"], where="post", color="#1e293b", ls="--", lw=1.2, label="수요 태양추적")
    ax.step(g["t"], g["dem_sel"], where="post", color="#1e293b", lw=1.8, label="수요 TiDE 각도")
    ax2 = ax.twinx()
    ax2.step(g["t"], g["theta"], where="post", color="#2563eb", lw=1, alpha=0.5)
    ax2.set_ylim(0, 300)
    ax2.set_yticks([0, 30, 60, 90])
    ax2.set_ylabel("각도 [°]", color="#2563eb")
    ax.set_ylabel("kWh / 10분")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.legend(ncol=4, fontsize=9, loc="upper right")
    ax.set_title(f"(c) {DAY[5:]}: 선택 각도의 PV·수요 (case2 실제값, 수요 = 난방/2.5 + 조명)", loc="left", fontweight="bold")

    fig.suptitle("TiDE 잉여 구간 각도 제어 — 테스트 기상 TMYx 2011-2025, m = 0", fontsize=14, fontweight="bold")
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"[*] {OUT}")


if __name__ == "__main__":
    main()

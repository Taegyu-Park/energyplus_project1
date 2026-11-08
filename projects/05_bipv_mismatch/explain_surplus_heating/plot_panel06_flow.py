"""
bipv_mismatch/explain_surplus_heating/plot_panel06_flow.py
==========================================================
공모전 패널 06번 "case2 데이터 → 가공 → TiDE → PV 각도" 흐름도에 들어갈 미니 그래프 3개 (2026-11-04).
대표일 1/17 (05번과 같음), 자료는 실제 결과.

1) dm_panel06_a_window : 태양고도 추적 PV·수요(case3 E+ 연간), 잉여 음영 + 조절 구간(잉여 ± 1시간) 띠
2) dm_panel06_b_oracle : 15:30 한 시점의 case2 각도별 |PV − 수요| (1° 보간), 최소점 = 정답 각도
3) dm_panel06_c_angle  : 하루 루버 각도, 태양추적(점선) vs TiDE 최종(실선, 10° 반올림), 조절 구간 띠

스타일은 plot_panel_dm.py 와 같고, 흐름도 상자 글자(4.2pt)에 맞춰 글자만 4.2pt 로 줄임.
출력: explain_surplus_heating/figures/dm_panel06_*.svg (+ .png)
실행: python bipv_mismatch/explain_surplus_heating/plot_panel06_flow.py
"""

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

import plot_panel_dm as P

FS = 4.2
D = P.DAY05
ANG = P.WINTER / "angles_winter.csv"
CASE2 = P.BM / "dataset_final" / "case2_mm_train.csv"
T_ORACLE = D + pd.Timedelta(hours=15, minutes=30)
X0, X1 = D + pd.Timedelta(hours=6), D + pd.Timedelta(hours=20)
WIN_C = "#f1f5f9"


def style():
    P.style()
    mpl.rcParams.update({k: FS for k in ("font.size", "axes.labelsize", "axes.titlesize", "xtick.labelsize",
                                         "ytick.labelsize", "legend.fontsize")})
    mpl.rcParams.update({"xtick.major.size": 1.5, "ytick.major.size": 1.5, "xtick.major.pad": 1, "ytick.major.pad": 1,
                         "axes.labelpad": 1, "axes.linewidth": 0.4, "xtick.major.width": 0.4, "ytick.major.width": 0.4})


def hours(ax):
    ax.set_xlim(X0, X1)
    ax.set_xticks([D + pd.Timedelta(hours=h) for h in (6, 12, 18)])
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - D).total_seconds() / 3600):d}시"))


def window(ang):
    m = ang.index[ang["mask"] == 1]
    return m.min(), m.max() + P.STEP


def band(ax, a, b, y, text):
    ax.axvspan(a, b, color=WIN_C, lw=0, zorder=0)
    ax.text(a + (b - a) / 2, y, text, ha="center", va="top", color=P.INK3)


def chart_window(ang):
    x = P.load_day(P.ST_SQL, D).loc[X0:X1]
    t = x.index + P.STEP / 2
    a, b = window(ang)
    fig, ax = plt.subplots(figsize=(66 / 72, 40 / 72))
    top = max(x.pv.max(), x.load.max()) * 1.22
    band(ax, a, b, top * 0.99, "조절 구간")
    ax.fill_between(t, x.pv, x.load, where=x.pv > x.load, interpolate=True, color=P.TARGET_TINT, lw=0)
    ax.plot(t, x.load, color=P.INK1, lw=0.6)
    ax.plot(*P.pv_curve(x.pv), color=P.TARGET, lw=0.7)
    s = x.index[x.pv > x.load]
    ax.text(s.min() + (s.max() - s.min()) / 2, x.pv.max() * 0.55, "잉여", ha="center", color=P.TARGET_DEEP)
    ax.text(X0 + pd.Timedelta(minutes=10), x.load.max() * 1.03, "수요", va="bottom", color=P.INK1)
    ax.text(b + pd.Timedelta(minutes=20), x.pv[s.max()] * 0.95, "PV", color=P.TARGET)
    ax.set_ylim(0, top)
    ax.set_yticks([])
    hours(ax)
    print(f"[a] 조절 구간 {a:%H:%M}~{b:%H:%M}, 잉여 구간 {s.min():%H:%M}~{s.max() + P.STEP:%H:%M}")
    P.save(fig, "dm_panel06_a_window")


def chart_oracle():
    c2 = pd.read_csv(CASE2, parse_dates=["timestamp"])
    c2.index = c2.timestamp - P.STEP
    A = np.arange(0, 100, 10)
    r = c2.loc[T_ORACLE]
    m10 = np.abs(r[[f"pv_gen_{k}" for k in A]].to_numpy(float) - r[[f"demand_elec_{k}" for k in A]].to_numpy(float))
    g = np.arange(0, 91)
    m = np.abs(np.interp(g, A, r[[f"pv_gen_{k}" for k in A]].to_numpy(float))
               - np.interp(g, A, r[[f"demand_elec_{k}" for k in A]].to_numpy(float)))
    k = int(g[m.argmin()])
    fig, ax = plt.subplots(figsize=(66 / 72, 40 / 72))
    ax.plot(g, m, color=P.INK2, lw=0.6)
    ax.plot(A, m10, "o", ms=1.4, color=P.INK3, mew=0)
    ax.plot(k, m[k], "o", ms=2.6, color=P.LOSS, mew=0, zorder=3)
    ax.annotate(f"정답 {k}°", (k, m[k]), xytext=(-2, 1), textcoords="offset points", ha="right", va="bottom",
                color=P.LOSS)
    ax.text(2, m.max() * 1.18, f"{T_ORACLE:%H:%M} 한 시점", va="top", color=P.INK3)
    ax.set_xlim(-3, 93)
    ax.set_ylim(0, m.max() * 1.2)
    ax.set_xticks([0, 30, 60, 90], ["0°", "30°", "60°", "90°"])
    ax.set_yticks([])
    ax.set_ylabel("|PV − 수요|")
    print(f"[b] {T_ORACLE:%H:%M} 정답 각도 {k}°, 10° 값 {np.round(m10, 2)}")
    P.save(fig, "dm_panel06_b_oracle")


def chart_angle(ang):
    x = ang.loc[X0:X1 - P.STEP]
    a, b = window(ang)
    fig, ax = plt.subplots(figsize=(92 / 72, 40 / 72))
    band(ax, a, b, 66, "조절 구간")
    ax.step(x.index, x.theta_st, where="post", color=P.INK3, lw=0.6, ls=(0, (2.4, 1.2)), label="태양고도 추적")
    ax.step(x.index, x.tide, where="post", color=P.EVAL, lw=0.8, label="TiDE")
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 45, 90], ["0°", "45°", "90°"])
    hours(ax)
    P.legend(ax, loc="lower left", bbox_to_anchor=(0, 1), ncol=2)
    print(f"[c] TiDE 최대 {x.tide.max():.0f}°, 태양추적 최대 {x.theta_st.max():.0f}°")
    P.save(fig, "dm_panel06_c_angle")


def main():
    style()
    ang = pd.read_csv(ANG, parse_dates=["start"]).set_index("start").loc[D:D + pd.Timedelta(hours=24) - P.STEP]
    chart_window(ang)
    chart_oracle()
    chart_angle(ang)


if __name__ == "__main__":
    main()

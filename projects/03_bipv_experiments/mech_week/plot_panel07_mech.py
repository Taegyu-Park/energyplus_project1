"""
projects/03_bipv_experiments/mech_week/plot_panel07_mech.py
===============================================
공모전 패널 7번 ① 메커니즘 그래프 (2026-11-05). 1/9, 태양고도 추적 vs TiDE, 같은 x축(0~24시) 4단:
  1) 루버 각도  2) 남측 창 투과 일사  3) 남측 존 바닥 표면 온도(축열)  4) 시간별 부하 변화 (TiDE − 추적: 난방·조명·PV)
자료: mech_week/runs/{mech_st, mech_tide}. eplus_week_oracle 과 같은 설정·같은 시작일(1/2)이며
      창 투과 일사·표면 온도·표면 열류를 추가로 출력함 (batch.json)
스타일은 projects/05_bipv_mismatch/explain_surplus_heating/plot_panel_dm.py 를 가져와 씀 (원본 수정 안 함)
출력: mech_week/figures/dm_panel07_mech_day0109.svg (+ .png)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from load_mech import RUNS, load  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
HEAT, LIGHT = "#be123c", "#64748b"


def main(D=P.DAY):
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    sl = slice(D, D + pd.Timedelta(hours=24) - P.STEP)
    a, b = load(RUNS["st"], D.day, D.day + 1)[sl], load(RUNS["tide"], D.day, D.day + 1)[sl]
    t = a.index + P.STEP / 2
    ang = pd.read_csv(P.ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(pd.date_range(D, D + pd.Timedelta(hours=24) - P.STEP, freq=P.STEP)).fillna(0)
    win = ang.index[ang["mask"] == 1]
    w0, w1 = win.min(), win.max() + P.STEP
    d = (b - a)[["heat", "lights", "pv"]].resample("h").sum()
    tot = (b - a)[["heat", "lights", "pv", "sol_s", "purchase"]].sum()
    after = (b - a).heat[w1:].sum()
    print(f"Δ 하루: {tot.round(2).to_dict()} | 조절 구간 뒤 난방 {after:.2f} | 바닥 최대차 "
          f"{(b.t_floor - a.t_floor).max():.2f}°C, 24시 {(b.t_floor - a.t_floor).iloc[-1]:.2f}°C")

    fig, ax = P.fig_ax(240, 4, 1, sharex=True, gridspec_kw=dict(height_ratios=[0.8, 1, 1, 1.35], hspace=0.18))
    for x in ax:
        x.axvspan(w0, w1, color=P.EVAL, alpha=0.06, lw=0)
        P.hour_axis(x, d=D, grid=False)

    def title(x, s, color=P.INK1):
        x.text(0.004, 0.96, s, transform=x.transAxes, ha="left", va="top", color=color)

    # 1) 각도
    ax[0].step(ang.index, ang.theta_st, where="post", color=P.FROZEN, lw=0.9, ls=P.DASH, label="태양고도 추적")
    ax[0].step(ang.index, ang.tide, where="post", color=P.EVAL, lw=1.0, label="TiDE")
    ax[0].set_ylim(-5, 100)
    ax[0].set_yticks([0, 45, 90])
    ax[0].set_ylabel("각도 [°]")
    ax[0].text(w0 + (w1 - w0) * 0.56, 60, f"조절 구간 {w0:%H:%M}~{w1:%H:%M}", ha="center", va="center", color=P.EVAL)
    P.legend(ax[0], loc="upper left", ncol=2)

    # 2) 남측 창 투과 일사 (10분 kWh × 6 = kW)
    ax[1].fill_between(t, a.sol_s * 6, b.sol_s * 6, where=b.sol_s > a.sol_s, interpolate=True, color=P.TARGET_TINT, lw=0)
    ax[1].plot(t, a.sol_s * 6, color=P.FROZEN, lw=0.8, ls=P.DASH)
    ax[1].plot(t, b.sol_s * 6, color=P.EVAL, lw=1.0)
    ax[1].set_ylabel("일사 [kW]")
    ax[1].set_ylim(0, b.sol_s.max() * 6 * 1.3)
    title(ax[1], f"남측 창 투과 일사  {a.sol_s.sum():.1f} → {b.sol_s.sum():.1f} kWh")

    # 3) 바닥 표면 온도 (축열)
    dt = b.t_floor - a.t_floor
    ax[2].fill_between(t, a.t_floor, b.t_floor, where=b.t_floor > a.t_floor, interpolate=True, color=P.TARGET_TINT, lw=0)
    ax[2].plot(t, a.t_floor, color=P.FROZEN, lw=0.8, ls=P.DASH)
    ax[2].plot(t, b.t_floor, color=P.EVAL, lw=1.0)
    ax[2].set_ylabel("온도 [°C]")
    ax[2].set_ylim(np.floor(a.t_floor.min()) - 1, np.ceil(b.t_floor.max()) + 3)
    title(ax[2], "남측 존 바닥 표면 온도 (축열)")
    pk = dt.idxmax()
    ax[2].annotate(f"최대 +{dt.max():.1f}°C", (pk + P.STEP / 2, b.t_floor[pk]), xytext=(0, 3), textcoords="offset points",
                   ha="center", va="bottom", color=P.TARGET_DEEP)
    ax[2].text(0.996, 0.96, f"24시에도 +{dt.iloc[-1]:.1f}°C", transform=ax[2].transAxes, ha="right", va="top",
               color=P.TARGET_DEEP)

    # 4) 시간별 부하 변화 (TiDE − 추적)
    x0 = d.index + pd.Timedelta(minutes=30)
    bw = pd.Timedelta(minutes=17)
    for k, (col, c, lab) in enumerate([("pv", P.TARGET, "PV 발전"), ("heat", HEAT, "난방 전력"), ("lights", LIGHT, "조명 전력")]):
        ax[3].bar(x0 + (k - 1) * bw, d[col], width=bw, color=c, lw=0, label=f"{lab} {tot[col]:+.1f} kWh")
    ax[3].axhline(0, color=P.RULE, lw=0.6)
    ax[3].set_ylim(-10.5, 2.5)
    ax[3].set_ylabel("변화 [kWh/h]")
    ax[3].set_xlabel("시각 [h]")
    title(ax[3], "시간별 변화 (TiDE − 태양고도 추적)")
    ax[3].annotate(f"구간 뒤 난방 {after:+.1f} kWh", (w1 + pd.Timedelta(hours=1.3), d.heat[w1.floor("h"):].min()),
                   xytext=(6, -8), textcoords="offset points", ha="left", va="top", color=HEAT,
                   arrowprops=dict(arrowstyle="-", color=HEAT, lw=0.5))
    P.legend(ax[3], loc="lower left", ncol=1)  # 막대가 없는 0~9시 자리
    P.save(fig, f"dm_panel07_mech_day{D:%m%d}", mt="3pt", mb="22pt")


if __name__ == "__main__":
    main()

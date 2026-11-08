"""
projects/03_bipv_experiments/mech_week/plot_panel07_pv.py
=============================================
공모전 패널 7번의 기존 ① 그래프(dm_panel07a)에서 위쪽 각도 칸을 뺀 판. PV 발전·전력 수요만 그린다 (2026-11-05).
자료와 스타일은 projects/05_bipv_mismatch/explain_surplus_heating/plot_panel_dm.py 의 panel07a 와 같다. 원본 파일은 수정하지 않고 함수만 가져온다.
- 태양고도 추적: projects/04_pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400
- TiDE: projects/05_bipv_mismatch/tide_policy/eplus_week_oracle/runs/week_tide_oracle
출력: projects/03_bipv_experiments/mech_week/figures/dm_panel07_pv_day0109.svg (+ .png)
실행: python projects/03_bipv_experiments/mech_week/plot_panel07_pv.py
"""

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"


def main(D=P.DAY):
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    a, b = P.load_day(P.ST_SQL, D), P.load_day(P.TIDE, D)
    t = a.index + P.STEP / 2
    ang = pd.read_csv(P.ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(pd.date_range(D, D + pd.Timedelta(hours=24) - P.STEP, freq=P.STEP)).fillna(0)
    win = ang.index[ang["mask"] == 1]
    print(f"{D:%m/%d} 조절 {win.min():%H:%M}~{win.max() + P.STEP:%H:%M} | 태양추적 PV {a.pv.sum():.1f} 수요 {a.load.sum():.1f}"
          f" 잉여 {a.surplus.sum():.1f} 부족 {a.purchase.sum():.1f} | TiDE PV {b.pv.sum():.1f} 수요 {b.load.sum():.1f}"
          f" 잉여 {b.surplus.sum():.1f} 부족 {b.purchase.sum():.1f}")
    fig, ax = P.fig_ax(125)
    ax.axvspan(win.min(), win.max() + P.STEP, color=P.EVAL, alpha=0.06, lw=0)
    ax.text(win.min() + (win.max() - win.min()) / 2, 6.95, f"조절 구간 {win.min():%H:%M}~{win.max() + P.STEP:%H:%M}",
            ha="center", va="top", color=P.EVAL)
    ax.fill_between(t, a.pv, a.load, where=a.pv > a.load, interpolate=True, color=P.TARGET_TINT, lw=0,
                    label=f"태양추적 잉여 {a.surplus.sum():.1f} kWh")
    ax.fill_between(t, b.pv, b.load, where=b.pv > b.load, interpolate=True, color=P.TARGET_MID, alpha=0.55, lw=0,
                    label=f"TiDE 잉여 {b.surplus.sum():.1f} kWh")
    ax.plot(*P.pv_curve(a.pv), color=P.TARGET, lw=0.8, ls=P.DASH, label="PV · 태양추적")
    ax.plot(*P.pv_curve(b.pv), color=P.TARGET, lw=1.0, label="PV · TiDE")
    ax.plot(t, a.load, color=P.INK1, lw=0.8, ls=P.DASH, label="수요 · 태양추적")
    ax.plot(t, b.load, color=P.INK1, lw=0.9, label="수요 · TiDE")
    ax.set_ylim(0, 7.2)
    ax.set_ylabel("kWh")
    ax.set_xlabel("시각 [h]")
    P.hour_axis(ax, d=D, grid=False)
    P.legend(ax, loc="lower left", bbox_to_anchor=(0, 1), ncol=3)  # 범례는 그래프 위 바깥 (조절 구간 글자와 겹치지 않게)
    P.save(fig, f"dm_panel07_pv_day{D:%m%d}", mt="20pt", mb="22pt")


if __name__ == "__main__":
    main()

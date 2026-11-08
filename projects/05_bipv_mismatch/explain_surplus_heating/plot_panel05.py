"""
projects/05_bipv_mismatch/explain_surplus_heating/plot_panel05.py
=====================================================
공모전 패널(Figma 26건물에너지시뮬레이션, Document 1660:938) 05번 칸용 그림 (2026-11-03).
1/9 (IWEC, 평일) 태양고도 추적 제어의 PV 발전·전력 수요, 잉여(PV > 수요)·부족(수요 > PV) 음영.

- 자료: projects/04_pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400 (case3 E+), 수요 = 냉방/3.0 + 난방/2.5 + 조명
- 패널 칸 폭(386 pt)에 맞춘 크기, 글꼴 Noto Sans KR, svg 텍스트는 글자 그대로 (Figma 에서 편집 가능)

출력: explain_surplus_heating/figures/panel05_day0109_suntracking.{png,svg}
실행: python projects/05_bipv_mismatch/explain_surplus_heating/plot_panel05.py
"""

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
BM = HERE.parent
sys.path.insert(0, str(BM / "eplus_jan13"))
from plot_day import C_DEM, C_PV  # noqa: E402

sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

DAY = pd.Timestamp("2006-01-09")
STEP = pd.Timedelta(minutes=10)
OUT = HERE / "figures" / f"panel05_day{DAY:%m%d}_suntracking.png"
W_PT, H_PT = 386, 190
C_DEF = "#94a3b8"


def main():
    x = load(RUNS["태양추적"]).loc[DAY:DAY + pd.Timedelta(hours=24) - STEP]
    t = x.index + STEP / 2
    sur, dfc = x.surplus.sum(), x.purchase.sum()
    s = x.index[x.pv > x.load]
    print(f"PV {x.pv.sum():.1f}, 수요 {x.load.sum():.1f}, 잉여 {sur:.1f}, 부족 {dfc:.1f} kWh, "
          f"잉여 구간 {s.min():%H:%M}~{s.max() + STEP:%H:%M}")

    mpl.rcParams.update({"font.family": "Noto Sans KR", "svg.fonttype": "none", "axes.unicode_minus": False,
                         "font.size": 6.5, "axes.linewidth": 0.5, "xtick.major.width": 0.5,
                         "ytick.major.width": 0.5, "xtick.major.size": 2, "ytick.major.size": 2})
    fig, ax = plt.subplots(figsize=(W_PT / 72, H_PT / 72))
    ax.fill_between(t, x.pv, x.load, where=x.pv > x.load, interpolate=True, color=C_PV, alpha=0.35, lw=0,
                    label=f"잉여 발전 {sur:.1f} kWh")
    ax.fill_between(t, x.pv, x.load, where=x.load > x.pv, interpolate=True, color=C_DEF, alpha=0.25, lw=0,
                    label=f"부족 (구매) {dfc:.1f} kWh")
    ax.plot(t, x.load, color=C_DEM, lw=1.0, label="전력 수요")
    ax.plot(t, x.pv, color=C_PV, lw=1.2, label="PV 발전")
    ax.annotate("정오 전후 잉여", (s.min() + (s.max() - s.min()) / 2, x.pv.max()), xytext=(0, 4),
                textcoords="offset points", ha="center", fontsize=6.5, color="#b45309")
    ax.annotate("아침 예열", (DAY + pd.Timedelta(hours=7, minutes=30), x.load.max()), xytext=(14, -2),
                textcoords="offset points", ha="left", va="top", fontsize=6.5, color="#475569")
    ax.annotate("오후 난방", (DAY + pd.Timedelta(hours=17, minutes=30), 3.3), xytext=(0, 4),
                textcoords="offset points", ha="center", fontsize=6.5, color="#475569")

    ax.set_xlim(DAY, DAY + pd.Timedelta(hours=24))
    ax.set_ylim(0, 7.2)
    ax.set_yticks(range(0, 8))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - DAY).total_seconds() / 3600):d}"))
    ax.set_xlabel("시각 [h]", labelpad=2)
    ax.set_ylabel("kWh / 10분", labelpad=2)
    ax.tick_params(pad=1.5)
    ax.grid(axis="y", lw=0.4, alpha=0.4)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    h, lab = ax.get_legend_handles_labels()
    order = [3, 2, 0, 1]
    ax.legend([h[i] for i in order], [lab[i] for i in order], ncol=2, frameon=False, loc="upper right",
              fontsize=6.5, handlelength=1.4, columnspacing=1.0, borderaxespad=0.2)
    fig.subplots_adjust(left=0.075, right=0.98, bottom=0.15, top=0.98)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, transparent=True)
    fig.savefig(OUT.with_suffix(".svg"), transparent=True)
    plt.close(fig)
    print(f"[*] {OUT} (+ .svg)")


if __name__ == "__main__":
    main()

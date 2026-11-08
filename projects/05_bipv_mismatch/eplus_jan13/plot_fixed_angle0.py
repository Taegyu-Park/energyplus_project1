"""
eplus_jan13/plot_fixed_angle0.py
================================
jan13_fixed_angles 그림에서 0° 고정만 남긴 버전: 1/13 (IWEC) case2 각도 0° 고정의 PV 발전·수요.
- 자료: dataset_final/case2_mm_train.csv (IWEC) 의 pv_gen_A, demand_elec_A (= 냉방/3.0 + 난방/2.5 + 조명)
- timestamp 는 구간 종료 라벨 → 구간 시작 시각(−10분), 곡선은 plot_day.py 와 같은 PCHIP 보간
- 색은 PV 주황·수요 남색 (plot_day.py 와 같음)

출력: eplus_jan13/jan13_fixed_angle0.{png,svg}
"""

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import dartwork_mpl as dm
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from scipy.interpolate import PchipInterpolator

from plot_day import C_DEM, C_PV, DAY0, flatten_svg
from analyze import HERE

CASE2 = HERE.parent / "dataset_final" / "case2_mm_train.csv"
ANGLES = [0]
ALPHA = {0: 1.0}


def main():
    c2 = pd.read_csv(CASE2, usecols=["timestamp"] + [f"{c}_{a}" for c in ("pv_gen", "demand_elec") for a in ANGLES],
                     parse_dates=["timestamp"])
    c2.index = c2.timestamp - pd.Timedelta(minutes=10)
    end = DAY0 + pd.Timedelta(hours=24)
    x = c2.loc[DAY0:end - pd.Timedelta(minutes=10)]
    t_fine = pd.date_range(DAY0, end, freq="1min")

    def curve(s):
        tm = np.r_[0.0, (s.index - DAY0).total_seconds() / 3600 + 5 / 60, 24.0]
        v = np.r_[s.iloc[0], s.to_numpy(), s.iloc[-1]]
        return t_fine, PchipInterpolator(tm, v)((t_fine - DAY0).total_seconds() / 3600)

    dm.style.use("presentation-kr")
    plt.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "path"
    fig, ax = plt.subplots(figsize=(18 / 2.54, 11 / 2.54))
    for a in ANGLES:
        ax.plot(*curve(x[f"pv_gen_{a}"]), color=C_PV, lw=1.4, alpha=ALPHA[a])
        ax.plot(*curve(x[f"demand_elec_{a}"]), color=C_DEM, lw=1.4, alpha=ALPHA[a])
        print(f"{a:2d}°: PV {x[f'pv_gen_{a}'].sum():6.2f}, 수요 {x[f'demand_elec_{a}'].sum():6.2f} kWh")

    ax.set_xlim(DAY0, end)
    ax.set_ylim(0, 7.2)
    ax.spines["left"].set_bounds(0, 7)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - DAY0).total_seconds() / 3600):d}"))
    ax.tick_params(labelsize=11)
    ax.set_xlabel("시각 [h]", fontsize=13, labelpad=10)
    ax.set_ylabel("kWh", fontsize=13)
    ax.grid(axis="y", alpha=0.3)
    h = [Line2D([], [], color=C_PV, lw=1.6), Line2D([], [], color=C_DEM, lw=1.6)]
    labels = ["PV 발전", "수요"]
    ax.legend(h, labels, ncol=1, fontsize=9, frameon=False, loc="upper right", handlelength=1.6,
              borderaxespad=0.2, labelspacing=0.35, columnspacing=1.0)
    ax.set_title(f"{DAY0.month}/{DAY0.day}, 0° 고정 PV 발전과 수요 (case2)", fontsize=14, fontweight="bold", pad=8)
    dm.simple_layout(fig)
    out = HERE / "jan13_fixed_angle0.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", transparent=True)
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight", transparent=True)
    flatten_svg(out.with_suffix(".svg"))
    plt.close(fig)
    print(f"[*] {out} (+ .svg)")


if __name__ == "__main__":
    main()

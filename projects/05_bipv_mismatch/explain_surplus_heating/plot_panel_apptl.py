"""
projects/05_bipv_mismatch/explain_surplus_heating/plot_panel_apptl.py
=========================================================
공모전 패널(Figma 26건물에너지시뮬레이션, Document 1660:938) 05·07번 칸 그림을 A-PPTL 디자인 토큰 색으로 (2026-11-03).

- 색 (A-PPTL Color 컬렉션): PV = target/strong, 잉여 = target/tint, 수요 = ink/primary, 부족 = frozen/tint,
  태양고도 추적(기준) = frozen/strong 점선, TiDE = eval/strong 실선, 글자 = ink/secondary·tertiary, 격자 = line/grid
- 흰 바탕, 헤어라인, 그림자·그라데이션 없음. 글꼴 Noto Sans KR (Inter 에 한글이 없어서), svg 텍스트는 글자 그대로

1) panel05_day0109_suntracking_apptl : 1/9 태양고도 추적의 PV 발전·전력 수요, 잉여·부족 음영 (plot_panel05.py 와 같은 내용)
2) panel07_day0109_cumulative        : 1/9 태양고도 추적 vs TiDE 최종, 난방 전력·조명 전력·PV 발전 누적 (0시부터)

자료: case3 E+ (태양추적 projects/04_pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400, TiDE tide_policy/eplus_week_oracle/runs/week_tide_oracle)
출력: explain_surplus_heating/figures/panel0{5,7}_*.{png,svg}
실행: python projects/05_bipv_mismatch/explain_surplus_heating/plot_panel_apptl.py
"""

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
BM = HERE.parent
sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

TIDE = BM / "tide_policy" / "eplus_week_oracle" / "runs" / "week_tide_oracle" / "eplusout.sql"
DAY = pd.Timestamp("2006-01-09")
STEP = pd.Timedelta(minutes=10)
OUT = HERE / "figures"

INK1, INK2, INK3 = "#0f172a", "#334155", "#64748b"
GRID, RULE = "#e2e8f0", "#cbd5e1"
TARGET, TARGET_TINT, TARGET_DEEP = "#ea580c", "#ffedd5", "#9a3412"
FROZEN, FROZEN_TINT = "#475569", "#e2e8f0"
EVAL = "#0f766e"
LOSS = "#be123c"


def style():
    mpl.rcParams.update({
        "font.family": "Noto Sans KR", "svg.fonttype": "none", "axes.unicode_minus": False, "font.size": 8,
        "text.color": INK2, "axes.labelcolor": INK2, "xtick.color": INK3, "ytick.color": INK3,
        "axes.edgecolor": RULE, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.major.size": 2, "ytick.major.size": 2, "xtick.major.pad": 1.5, "ytick.major.pad": 1.5,
    })


def hour_axis(ax, step=3):
    ax.set_xlim(DAY, DAY + pd.Timedelta(hours=24))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=step))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - DAY).total_seconds() / 3600):d}"))
    ax.grid(axis="y", color=GRID, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def save(fig, name):
    out = OUT / f"{name}.png"
    fig.savefig(out, dpi=300, transparent=True)
    fig.savefig(out.with_suffix(".svg"), transparent=True)
    plt.close(fig)
    print(f"[*] {out} (+ .svg)")


def day(df):
    return df.loc[DAY:DAY + pd.Timedelta(hours=24) - STEP]


def panel05(st):
    x = day(st)
    t = x.index + STEP / 2
    sur, dfc = x.surplus.sum(), x.purchase.sum()
    s = x.index[x.pv > x.load]
    fig, ax = plt.subplots(figsize=(386 / 72, 190 / 72))
    ax.fill_between(t, x.pv, x.load, where=x.pv > x.load, interpolate=True, color=TARGET_TINT, lw=0,
                    label=f"잉여 발전 {sur:.1f} kWh")
    ax.fill_between(t, x.pv, x.load, where=x.load > x.pv, interpolate=True, color=FROZEN_TINT, alpha=0.7, lw=0,
                    label=f"부족 (구매) {dfc:.1f} kWh")
    ax.plot(t, x.load, color=INK1, lw=1.0, label="전력 수요")
    ax.plot(t, x.pv, color=TARGET, lw=1.2, label="PV 발전")
    ax.annotate("정오 전후 잉여", (s.min() + (s.max() - s.min()) / 2, x.pv.max()), xytext=(0, 4),
                textcoords="offset points", ha="center", color=TARGET_DEEP)
    ax.annotate("아침 예열", (DAY + pd.Timedelta(hours=7, minutes=30), x.load.max()), xytext=(14, -2),
                textcoords="offset points", ha="left", va="top", color=INK3)
    ax.annotate("오후 난방", (DAY + pd.Timedelta(hours=17, minutes=30), 3.3), xytext=(0, 4),
                textcoords="offset points", ha="center", color=INK3)
    ax.set_ylim(0, 7.2)
    ax.set_yticks(range(0, 8))
    hour_axis(ax)
    ax.set_xlabel("시각 [h]", labelpad=2)
    ax.set_ylabel("kWh / 10분", labelpad=2)
    h, lab = ax.get_legend_handles_labels()
    order = [3, 2, 0, 1]
    ax.legend([h[i] for i in order], [lab[i] for i in order], ncol=2, frameon=False, loc="upper right",
              handlelength=1.4, columnspacing=1.0, borderaxespad=0.2)
    fig.subplots_adjust(left=0.08, right=0.975, bottom=0.17, top=0.98)
    save(fig, f"panel05_day{DAY:%m%d}_suntracking_apptl")


def panel07(st, td):
    a, b = day(st), day(td)
    t = a.index + STEP
    rows = [("난방 전력", "heat", 1 / 2.5), ("조명 전력", "lights", 1.0), ("PV 발전", "pv", 1.0)]
    fig, axes = plt.subplots(1, 3, figsize=(386 / 72, 140 / 72), sharex=True)
    for ax, (title, col, k) in zip(axes, rows):
        ca, cb = (a[col] * k).cumsum(), (b[col] * k).cumsum()
        ax.plot(t, ca, color=FROZEN, lw=1.0, ls=(0, (3, 1.6)), label="태양고도 추적")
        ax.plot(t, cb, color=EVAL, lw=1.3, label="TiDE")
        d = cb.iloc[-1] - ca.iloc[-1]
        ax.set_title(title, loc="left", fontsize=8, color=INK1, pad=12)
        ax.text(0, 1.03, f"{ca.iloc[-1]:.1f} → {cb.iloc[-1]:.1f} kWh ({d:+.1f})", transform=ax.transAxes,
                fontsize=8, color=EVAL, va="bottom")
        ax.set_ylim(0, max(ca.iloc[-1], cb.iloc[-1]) * 1.08)
        hour_axis(ax, step=6)
        ax.set_xlabel("시각 [h]", labelpad=1.5)
    axes[0].set_ylabel("누적 kWh", labelpad=2)
    axes[1].legend(frameon=False, loc="upper left", handlelength=1.6, borderaxespad=0.1, fontsize=8)
    fig.subplots_adjust(left=0.085, right=0.99, bottom=0.235, top=0.8, wspace=0.36)
    save(fig, f"panel07_day{DAY:%m%d}_cumulative")


def main():
    style()
    OUT.mkdir(parents=True, exist_ok=True)
    st, td = load(RUNS["태양추적"]), load(TIDE)
    panel05(st)
    panel07(st, td)


if __name__ == "__main__":
    main()

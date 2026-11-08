"""
projects/05_bipv_mismatch/explain_surplus_heating/plot_factors.py
=====================================================
"잉여 발전 → 난방 부하 저감" 개념 설명용 그림을 요소별로 나눠 그림 (2026-11-03).

1) fig1_angle_effects : case2 고정 각도(0·30·60·90°) 1/10 하루, 행마다 한 요소
                        PV 발전 / 남측 창 투과 일사 / 난방 전력(난방/2.5) / 조명 전력. 냉방은 겨울이라 0
2) fig2_angle_totals  : case2 1/10 하루 합계를 0° 대비 변화로 (각도 x축): PV, 난방, 조명
3) fig3_eplus_day     : case3 E+ 1/10, 태양추적 vs 잉여구간 90° — 각도 / PV·수요 / 난방 전력 / 조명 전력
4) fig4_eplus_ledger  : case3 E+ 평일(1/9~1/13) 합계, 태양추적 → 잉여구간 90° 로 바꿨을 때 항목별 변화

하루 = 07시 ~ 다음 날 07시, 수요 = 냉방/3.0 + 난방/2.5 + 조명 (기존과 같음)
출력: explain_surplus_heating/figures/*.{png,svg}
실행: python projects/05_bipv_mismatch/explain_surplus_heating/plot_factors.py
"""

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import dartwork_mpl as dm
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
BM = HERE.parent
sys.path.insert(0, str(BM / "eplus_jan13"))
from plot_day import C_DEM, C_PV, flatten_svg  # noqa: E402

sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

OUT = HERE / "figures"
CASE2 = BM / "dataset_final" / "case2_mm_train.csv"
ANG_WEEK = BM / "tide_policy" / "eplus_week" / "angles_week.csv"
DAY = pd.Timestamp("2006-01-10")
D0, D1 = DAY + pd.Timedelta(hours=7), DAY + pd.Timedelta(hours=31)
STEP = pd.Timedelta(minutes=10)
ANGLES = [0, 30, 60, 90]
C_HEAT, C_LIGHT, C_SUN = "#dc2626", "#0d9488", "#ca8a04"
C_ST, C_90 = "#64748b", "#10b981"
C_SUR = "#f59e0b"


def shades(color, n):
    """같은 색의 옅은 → 진한 단계 (각도 0° → 90°)"""
    rgb = np.array(mpl.colors.to_rgb(color))
    return [tuple(1 - (1 - rgb) * t) for t in np.linspace(0.3, 1.0, n)]


def hour_axis(ax):
    ax.set_xlim(D0, D1)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(1, 24, 3)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{mdates.num2date(v).hour:d}"))
    ax.grid(axis="y", alpha=0.3)


def save(fig, name):
    out = OUT / f"{name}.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", transparent=True)
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight", transparent=True)
    flatten_svg(out.with_suffix(".svg"))
    plt.close(fig)
    print(f"[*] {out} (+ .svg)")


def load_case2():
    cols = ["timestamp"] + [f"{c}_{a}" for c in ("pv_gen", "heat_load", "cool_load", "lights_kwh", "south_win_tx")
                            for a in range(0, 91, 10)]
    c2 = pd.read_csv(CASE2, usecols=cols, parse_dates=["timestamp"])
    c2.index = c2.timestamp - STEP
    return c2.loc[D0:D1 - STEP]


def fig1(x):
    rows = [("PV 발전", "pv_gen", 1.0, C_PV), ("남측 창 투과 일사 (실내로 들어온 햇빛)", "south_win_tx", 1.0, C_SUN),
            ("난방 전력 (난방 부하 / 2.5)", "heat_load", 1 / 2.5, C_HEAT), ("조명 전력", "lights_kwh", 1.0, C_LIGHT)]
    fig, axes = plt.subplots(len(rows), 1, figsize=(16 / 2.54, 17 / 2.54), sharex=True)
    for ax, (title, col, k, c) in zip(axes, rows):
        for a, cc in zip(ANGLES, shades(c, len(ANGLES))):
            ax.plot(x.index + STEP / 2, x[f"{col}_{a}"] * k, color=cc, lw=1.4, label=f"{a}°")
        ax.set_title(title, fontsize=11, loc="left", fontweight="bold", pad=3)
        ax.set_ylabel("kWh / 10분", fontsize=9)
        ax.tick_params(labelsize=9)
        ax.set_ylim(bottom=0)
        ax.legend(ncol=4, fontsize=8, frameon=False, loc="upper right", handlelength=1.4, columnspacing=0.8)
        hour_axis(ax)
    axes[-1].set_xlabel("시각 [h]", fontsize=11)
    fig.suptitle(f"{DAY.month}/{DAY.day} 고정 각도별 요소 (case2, 0° 닫힘 → 90° 열림, 냉방 부하 0)",
                 fontsize=12, fontweight="bold", y=0.995)
    fig.subplots_adjust(left=0.1, right=0.98, bottom=0.07, top=0.92, hspace=0.32)
    save(fig, "fig1_angle_effects")


def fig2(x):
    A = list(range(0, 91, 10))
    tot = pd.DataFrame({a: dict(pv=x[f"pv_gen_{a}"].sum(), heat=x[f"heat_load_{a}"].sum() / 2.5,
                                light=x[f"lights_kwh_{a}"].sum(), cool=x[f"cool_load_{a}"].sum() / 3.0)
                        for a in A}).T
    d = tot - tot.loc[0]
    print("[fig2] 0° 대비 하루 변화 (kWh)\n", d.round(1).to_string())
    fig, ax = plt.subplots(figsize=(14 / 2.54, 9 / 2.54))
    ax.axhline(0, color="#94a3b8", lw=0.8)
    for col, lab, c in [("pv", "PV 발전", C_PV), ("heat", "난방 전력", C_HEAT), ("light", "조명 전력", C_LIGHT)]:
        ax.plot(A, d[col], color=c, lw=1.8, marker="o", ms=4, label=lab)
        ax.annotate(f"{d[col].iloc[-1]:+.0f}", (90, d[col].iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=c)
    ax.set_xticks(A)
    ax.set_xlim(-3, 99)
    ax.set_xlabel("고정 각도 [°] (0° 닫힘 → 90° 열림)", fontsize=10)
    ax.set_ylabel("0° 대비 하루 변화 [kWh]", fontsize=10)
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=9, frameon=False, loc="lower left")
    ax.set_title(f"{DAY.month}/{DAY.day} 각도를 열수록 PV도, 난방·조명도 줄어든다 (case2)",
                 fontsize=11, fontweight="bold")
    dm.simple_layout(fig)
    save(fig, "fig2_angle_totals")


def fig3(st, r9, ang):
    s = slice(D0, D1 - STEP)
    a, b, g = st.loc[s], r9.loc[s], ang.loc[s]
    win = g.index[g.rule90 != g.theta_st]
    w0, w1 = win.min(), win.max() + STEP
    t = a.index + STEP / 2
    fig, axes = plt.subplots(4, 1, figsize=(16 / 2.54, 18 / 2.54), sharex=True,
                             gridspec_kw=dict(height_ratios=[0.7, 1.3, 1, 0.8]))
    ax = axes[0]
    ax.step(g.index, g.theta_st, where="post", color=C_ST, lw=1.3, ls="--", label="태양추적")
    ax.step(g.index, g.rule90, where="post", color=C_90, lw=1.5, label="잉여구간 90°")
    ax.set_ylim(-5, 100)
    ax.set_yticks([0, 45, 90])
    ax.set_title("각도", fontsize=11, loc="left", fontweight="bold", pad=3)
    ax.set_ylabel("°", fontsize=9)
    ax = axes[1]
    ax.fill_between(t, a.load, a.pv, where=a.pv > a.load, color=C_SUR, alpha=0.25, lw=0,
                    label="태양추적 잉여 발전")
    ax.plot(t, a.pv, color=C_PV, lw=1.3, ls="--", label="PV · 태양추적")
    ax.plot(t, b.pv, color=C_PV, lw=1.6, label="PV · 잉여구간 90°")
    ax.plot(t, a.load, color=C_DEM, lw=1.1, ls="--", label="수요 · 태양추적")
    ax.plot(t, b.load, color=C_DEM, lw=1.4, label="수요 · 잉여구간 90°")
    ax.set_title("PV 발전과 수요", fontsize=11, loc="left", fontweight="bold", pad=3)
    ax.set_ylim(bottom=0)
    for ax, col, k, c, title in [(axes[2], "heat", 1 / 2.5, C_HEAT, "난방 전력"),
                                 (axes[3], "lights", 1.0, C_LIGHT, "조명 전력")]:
        ax.plot(t, a[col] * k, color=c, lw=1.2, ls="--", label="태양추적")
        ax.plot(t, b[col] * k, color=c, lw=1.5, label="잉여구간 90°")
        diff = (b[col] - a[col]) * k
        d_in = diff.loc[win].sum()
        d_out = diff.sum() - d_in
        txt = f"구간 안 {d_in:+.1f} kWh" + (f", 구간 뒤 {d_out:+.1f} kWh" if abs(d_out) > 0.05 else "")
        ax.set_title(f"{title}  ({txt})", fontsize=11, loc="left", fontweight="bold", pad=3)
        ax.set_ylim(bottom=0)
    for ax in axes:
        ax.axvspan(w0, w1, color=C_90, alpha=0.08, lw=0)
        ax.tick_params(labelsize=9)
        if ax is not axes[0]:
            ax.set_ylabel("kWh / 10분", fontsize=9)
        ax.legend(ncol=2 if ax is axes[1] else 3, fontsize=8, frameon=False, loc="upper right",
                  handlelength=1.6, columnspacing=0.8)
        hour_axis(ax)
    axes[-1].set_xlabel("시각 [h]", fontsize=11)
    dpv = (b.pv - a.pv).sum()
    dsur = (b.surplus - a.surplus).sum()
    fig.suptitle(f"{DAY.month}/{DAY.day} case3 E+: 잉여 구간에만 90° (PV {dpv:+.1f} kWh 중 잉여 {dsur:+.1f} kWh)",
                 fontsize=12, fontweight="bold", y=0.995)
    fig.subplots_adjust(left=0.1, right=0.98, bottom=0.07, top=0.92, hspace=0.32)
    save(fig, "fig3_eplus_day")


def fig4(st, r9, ang):
    rec = []
    for d in pd.date_range("2006-01-09", "2006-01-13"):
        s = slice(d + pd.Timedelta(hours=7), d + pd.Timedelta(hours=31) - STEP)
        a, b, g = st.loc[s], r9.loc[s], ang.loc[s]
        inw = a.index.isin(g.index[g.rule90 != g.theta_st])
        dd = b - a
        rec.append(dict(pv=dd.pv.sum(), sur=dd.surplus.sum(), pur_in=dd.purchase[inw].sum(),
                        pur_out=dd.purchase[~inw].sum(), heat_in=dd.heat[inw].sum() / 2.5,
                        heat_out=dd.heat[~inw].sum() / 2.5, light=dd.lights.sum(), cool=dd.cool.sum() / 3.0))
    r = pd.DataFrame(rec).sum()
    print("[fig4] 평일 합계 변화 (kWh)\n", r.round(2).to_string())
    items = [("PV 발전", r.pv, C_PV),
             ("(그중) 잉여 전력 감소", r.sur, C_SUR),
             ("난방 전력 · 잉여 구간 안", r.heat_in, C_HEAT),
             ("난방 전력 · 구간 뒤 (축열 이월)", r.heat_out, "#f87171"),
             ("조명 전력", r.light, C_LIGHT),
             ("냉방 전력", r.cool, "#3b82f6"),
             ("구매 전력 · 잉여 구간 안", r.pur_in, "#475569"),
             ("구매 전력 · 구간 뒤", r.pur_out, "#94a3b8"),
             ("구매 전력 합계", r.pur_in + r.pur_out, C_DEM)]
    fig, ax = plt.subplots(figsize=(15 / 2.54, 10 / 2.54))
    y = np.arange(len(items))[::-1]
    for yi, (lab, v, c) in zip(y, items):
        ax.barh(yi, v, color=c, height=0.62)
        ax.annotate(f"{v:+.1f}", (v, yi), xytext=(-4 if v < 0 else 4, 0), textcoords="offset points",
                    ha="right" if v < 0 else "left", va="center", fontsize=9)
    ax.set_yticks(y, [i[0] for i in items], fontsize=9)
    ax.axvline(0, color="#94a3b8", lw=0.8)
    for yy in (y[1] - 0.5, y[5] - 0.5):
        ax.axhline(yy, color="#cbd5e1", lw=0.6, ls=":")
    lo = min(v for _, v, _ in items)
    ax.set_xlim(lo * 1.2, 40)
    ax.set_xlabel("태양추적 → 잉여구간 90° 변화 [kWh]", fontsize=10)
    ax.tick_params(axis="x", labelsize=9)
    ax.grid(axis="x", alpha=0.3)
    ax.set_title("평일 5일(1/9~1/13) 합계, case3 E+", fontsize=11, fontweight="bold")
    dm.simple_layout(fig)
    save(fig, "fig4_eplus_ledger")


def main():
    dm.style.use("presentation-kr")
    plt.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "path"
    OUT.mkdir(parents=True, exist_ok=True)
    x = load_case2()
    fig1(x)
    fig2(x)
    st, r9 = load(RUNS["태양추적"]), load(RUNS["잉여구간90°"])
    ang = pd.read_csv(ANG_WEEK, parse_dates=["start"]).set_index("start")
    fig3(st, r9, ang)
    fig4(st, r9, ang)


if __name__ == "__main__":
    main()

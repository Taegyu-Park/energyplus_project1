"""
bipv_mismatch/explain_surplus_heating/plot_panel_layout2.py
===========================================================
공모전 패널(Figma 26건물에너지시뮬레이션, Document 1660:938) 2차 배치용 그림, 글자 6pt (2026-11-03).
색은 A-PPTL 토큰 값 (plot_panel_apptl.py 와 같음).

1) panel03_iwec_temperature : 광주 IWEC 연간 외기온 (일평균 + 일 최저~최고 범위), 겨울 학습 기간(11~3월)·대표일 1/9 표시
2) panel05_day0109_st_6pt   : 1/9 태양고도 추적 PV 발전·전력 수요, 잉여·부족 음영
3) panel07a_day0109_profile : 1/9 태양고도 추적 vs TiDE 최종, 루버 각도 + PV 발전·전력 수요
4) panel07b_day0109_cum     : 1/9 난방 전력·조명 전력·PV 발전 누적 (0시부터)
5) panel07c_day0109_ledger  : 1/9 하루 변화 폭포 그래프 (TiDE − 태양추적): PV 감소 중 자가소비분 → 난방 → 조명 → 구매 전력
6) panel07d_weekdays        : 평일 1/9~1/13 날짜별 잉여·부족, 태양추적 vs TiDE (eplus_week_oracle/results_daily.csv)

자료: IWEC EPW(data/KOR_Kwangju.471560_IWEC (1).epw), case3 E+ (태양추적 c3_FE_ST_lw_dl400, TiDE eplus_week_oracle/week_tide_oracle)
출력: explain_surplus_heating/figures/*.{png,svg}
실행: python bipv_mismatch/explain_surplus_heating/plot_panel_layout2.py
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
ROOT = BM.parent
sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

import plot_panel_apptl as A  # noqa: E402  (색 상수, hour_axis, save)

EPW = ROOT / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
TIDE = A.TIDE
ANGLES = BM / "tide_policy" / "eplus_week_oracle" / "angles_week.csv"
DAY, STEP = A.DAY, A.STEP
W = 386
FS = 6


def style():
    A.style()
    mpl.rcParams.update({"font.size": FS, "legend.fontsize": FS, "axes.titlesize": FS, "lines.linewidth": 0.9})


def legend(ax, **kw):
    return ax.legend(frameon=False, handlelength=1.4, columnspacing=0.9, borderaxespad=0.1, **kw)


def iwec_temperature():
    epw = pd.read_csv(EPW, skiprows=8, header=None)
    t = pd.date_range("2006-01-01", periods=len(epw), freq="h")
    tdb = pd.Series(epw[6].to_numpy(), index=t)
    d = tdb.resample("D").agg(["mean", "min", "max"])
    print(f"[IWEC] 연평균 {tdb.mean():.1f} °C, 최저 {tdb.min():.1f}, 최고 {tdb.max():.1f}, "
          f"1월 평균 {tdb[tdb.index.month == 1].mean():.1f}, 8월 평균 {tdb[tdb.index.month == 8].mean():.1f}")
    fig, ax = plt.subplots(figsize=(W / 72, 64 / 72))
    for a, b in [("2006-01-01", "2006-04-01"), ("2006-11-01", "2007-01-01")]:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=A.FROZEN_TINT, alpha=0.6, lw=0)
    ax.fill_between(d.index, d["min"], d["max"], color=A.TARGET_TINT, lw=0, label="일 최저~최고")
    ax.plot(d.index, d["mean"], color=A.TARGET, lw=0.9, label="일평균")
    ax.axvline(DAY, color=A.EVAL, lw=0.7, ls=(0, (2, 1.2)))
    ax.annotate("대표일 1/9", (DAY, d["max"].max()), xytext=(3, -1), textcoords="offset points", va="top",
                color=A.EVAL, fontsize=FS)
    ax.text(pd.Timestamp("2006-02-15"), -11.5, "학습·평가 기간(11~3월)", ha="center", va="bottom", color=A.INK3)
    ax.text(pd.Timestamp("2006-12-01"), -11.5, "(11~12월)", ha="center", va="bottom", color=A.INK3)
    ax.axhline(0, color=A.RULE, lw=0.5)
    ax.set_xlim(pd.Timestamp("2006-01-01"), pd.Timestamp("2007-01-01"))
    ax.set_ylim(-13, 38)
    ax.set_xticks(pd.date_range("2006-01-01", "2006-12-01", freq="MS"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{mdates.num2date(v).month}월"))
    ax.set_ylabel("외기온 [°C]", labelpad=1.5)
    ax.grid(axis="y", color=A.GRID, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    legend(ax, loc="upper right", ncol=2)
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.2, top=0.97)
    A.save(fig, "panel03_iwec_temperature")


def panel05(st):
    x = A.day(st)
    t = x.index + STEP / 2
    sur, dfc = x.surplus.sum(), x.purchase.sum()
    s = x.index[x.pv > x.load]
    fig, ax = plt.subplots(figsize=(W / 72, 128 / 72))
    ax.fill_between(t, x.pv, x.load, where=x.pv > x.load, interpolate=True, color=A.TARGET_TINT, lw=0,
                    label=f"잉여 발전 {sur:.1f} kWh")
    ax.fill_between(t, x.pv, x.load, where=x.load > x.pv, interpolate=True, color=A.FROZEN_TINT, alpha=0.7, lw=0,
                    label=f"부족 (구매) {dfc:.1f} kWh")
    ax.plot(t, x.load, color=A.INK1, lw=0.9, label="전력 수요")
    ax.plot(t, x.pv, color=A.TARGET, lw=1.0, label="PV 발전")
    ax.annotate("정오 전후 잉여", (s.min() + (s.max() - s.min()) / 2, x.pv.max()), xytext=(0, 3),
                textcoords="offset points", ha="center", color=A.TARGET_DEEP)
    ax.annotate("아침 예열", (DAY + pd.Timedelta(hours=7, minutes=30), x.load.max()), xytext=(10, -1),
                textcoords="offset points", ha="left", va="top", color=A.INK3)
    ax.annotate("오후 난방", (DAY + pd.Timedelta(hours=17, minutes=30), 3.3), xytext=(0, 3),
                textcoords="offset points", ha="center", color=A.INK3)
    ax.set_ylim(0, 7.2)
    ax.set_yticks(range(0, 8))
    A.hour_axis(ax)
    ax.set_xlabel("시각 [h]", labelpad=1.5)
    ax.set_ylabel("kWh / 10분", labelpad=1.5)
    h, lab = ax.get_legend_handles_labels()
    order = [3, 2, 0, 1]
    legend(ax, handles=[h[i] for i in order], labels=[lab[i] for i in order], ncol=2, loc="upper right")
    fig.subplots_adjust(left=0.065, right=0.98, bottom=0.17, top=0.98)
    A.save(fig, f"panel05_day{DAY:%m%d}_st_6pt")


def panel07a(st, td):
    a, b = A.day(st), A.day(td)
    t = a.index + STEP / 2
    ang = pd.read_csv(ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(pd.date_range(DAY, DAY + pd.Timedelta(hours=24) - STEP, freq=STEP)).fillna(0)  # 07시 이전은 밤(0°)
    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(W / 72, 170 / 72), sharex=True,
                                   gridspec_kw=dict(height_ratios=[1, 2.6], hspace=0.12))
    win = ang.index[ang["mask"] == 1]
    for ax in (ax0, ax1):
        ax.axvspan(win.min(), win.max() + STEP, color=A.EVAL, alpha=0.06, lw=0)
    ax0.step(ang.index, ang.theta_st, where="post", color=A.FROZEN, lw=0.9, ls=(0, (3, 1.6)), label="태양고도 추적")
    ax0.step(ang.index, ang.tide, where="post", color=A.EVAL, lw=1.0, label="TiDE")
    ax0.set_ylim(-5, 100)
    ax0.set_yticks([0, 45, 90])
    ax0.set_ylabel("각도 [°]", labelpad=1.5)
    ax0.text(win.min() + (win.max() - win.min()) / 2, 52, f"조절 구간 {win.min():%H:%M}~{win.max() + STEP:%H:%M}",
             ha="center", va="center", color=A.EVAL)
    legend(ax0, loc="upper left")
    ax1.fill_between(t, a.pv, a.load, where=a.pv > a.load, interpolate=True, color=A.TARGET_TINT, lw=0,
                     label=f"태양추적 잉여 {a.surplus.sum():.1f} kWh")
    ax1.fill_between(t, b.pv, b.load, where=b.pv > b.load, interpolate=True, color=A.TARGET_TINT, lw=0,
                     hatch="////", edgecolor=A.TARGET, label=f"TiDE 잉여 {b.surplus.sum():.1f} kWh")
    ax1.plot(t, a.pv, color=A.TARGET, lw=0.8, ls=(0, (3, 1.6)), label="PV · 태양추적")
    ax1.plot(t, b.pv, color=A.TARGET, lw=1.0, label="PV · TiDE")
    ax1.plot(t, a.load, color=A.INK1, lw=0.8, ls=(0, (3, 1.6)), label="수요 · 태양추적")
    ax1.plot(t, b.load, color=A.INK1, lw=0.9, label="수요 · TiDE")
    ax1.set_ylim(0, 7.2)
    ax1.set_ylabel("kWh / 10분", labelpad=1.5)
    ax1.set_xlabel("시각 [h]", labelpad=1.5)
    legend(ax1, loc="upper right", ncol=3)
    for ax in (ax0, ax1):
        A.hour_axis(ax)
    mpl.rcParams["hatch.linewidth"] = 0.4
    fig.subplots_adjust(left=0.065, right=0.98, bottom=0.12, top=0.98)
    A.save(fig, f"panel07a_day{DAY:%m%d}_profile")


def panel07b(st, td):
    a, b = A.day(st), A.day(td)
    t = a.index + STEP
    rows = [("난방 전력", "heat", 1 / 2.5), ("조명 전력", "lights", 1.0), ("PV 발전", "pv", 1.0)]
    fig, axes = plt.subplots(1, 3, figsize=(W / 72, 112 / 72), sharex=True)
    for ax, (title, col, k) in zip(axes, rows):
        ca, cb = (a[col] * k).cumsum(), (b[col] * k).cumsum()
        ax.plot(t, ca, color=A.FROZEN, lw=0.9, ls=(0, (3, 1.6)), label="태양고도 추적")
        ax.plot(t, cb, color=A.EVAL, lw=1.1, label="TiDE")
        d = cb.iloc[-1] - ca.iloc[-1]
        ax.set_title(title, loc="left", color=A.INK1, pad=9)
        ax.text(0, 1.03, f"{ca.iloc[-1]:.1f} → {cb.iloc[-1]:.1f} kWh ({d:+.1f})", transform=ax.transAxes,
                color=A.EVAL, va="bottom")
        ax.set_ylim(0, max(ca.iloc[-1], cb.iloc[-1]) * 1.08)
        A.hour_axis(ax, step=6)
        ax.set_xlabel("시각 [h]", labelpad=1)
    axes[0].set_ylabel("누적 kWh", labelpad=1.5)
    legend(axes[1], loc="upper left")
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.2, top=0.82, wspace=0.3)
    A.save(fig, f"panel07b_day{DAY:%m%d}_cum")


def panel07c(st, td):
    a, b = A.day(st), A.day(td)
    d_pv, d_sur = (b.pv - a.pv).sum(), (b.surplus - a.surplus).sum()
    d_heat, d_light = ((b.heat - a.heat) / 2.5).sum(), (b.lights - a.lights).sum()
    d_cool = ((b.cool - a.cool) / 3.0).sum()
    d_pur = (b.purchase - a.purchase).sum()
    self_use = -(d_pv - d_sur)  # PV 감소 중 자가소비분 → 구매 증가 요인
    print(f"[07c] PV {d_pv:.2f}, 잉여 {d_sur:.2f}, 자가소비분 +{self_use:.2f}, 난방 {d_heat:.2f}, 조명 {d_light:.2f}, "
          f"냉방 {d_cool:.2f}, 구매 {d_pur:.2f} (합 {self_use + d_heat + d_light + d_cool:.2f})")
    steps = [("PV 감소 중\n자가소비분", self_use, A.LOSS), ("난방 저감", d_heat, A.EVAL), ("조명 저감", d_light, A.EVAL)]
    fig, ax = plt.subplots(figsize=(W / 72, 100 / 72))
    x0 = 0.0
    for i, (lab, v, c) in enumerate(steps):
        ax.barh(i, v, left=x0, color=c, height=0.56)
        ax.annotate(f"{v:+.1f}", (x0 + v, i), xytext=(3 if v > 0 else -3, 0), textcoords="offset points",
                    ha="left" if v > 0 else "right", va="center", color=c)
        if i < len(steps) - 1:
            ax.plot([x0 + v, x0 + v], [i + 0.28, i + 0.72], color=A.RULE, lw=0.5)
        x0 += v
    ax.barh(len(steps), d_pur, color=A.INK1, height=0.56)
    ax.annotate(f"{d_pur:+.1f}", (d_pur, len(steps)), xytext=(-3, 0), textcoords="offset points", ha="right",
                va="center", color=A.INK1)
    ax.barh(len(steps) + 1.2, d_sur, color=A.FROZEN_TINT, height=0.56, hatch="////", edgecolor=A.FROZEN)
    ax.annotate(f"{d_sur:+.1f}  원래 남던 전력이라 구매와 무관", (0, len(steps) + 1.2), xytext=(3, 0),
                textcoords="offset points", ha="left", va="center", color=A.FROZEN)
    ax.set_yticks(list(range(len(steps) + 1)) + [len(steps) + 1.2],
                  [s[0] for s in steps] + ["= 구매 전력 변화", "잉여 발전 변화"])
    ax.invert_yaxis()
    ax.axvline(0, color=A.RULE, lw=0.6)
    ax.set_xlim(-30, 20)
    ax.set_xlabel("TiDE − 태양고도 추적 [kWh / 일]", labelpad=1.5)
    ax.grid(axis="x", color=A.GRID, lw=0.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    mpl.rcParams["hatch.linewidth"] = 0.4
    fig.subplots_adjust(left=0.15, right=0.98, bottom=0.2, top=0.97)
    A.save(fig, f"panel07c_day{DAY:%m%d}_ledger")


def panel07d():
    d = pd.read_csv(BM / "tide_policy" / "eplus_week_oracle" / "results_daily.csv", parse_dates=["date"])
    d = d[d.date.dt.weekday < 5]
    pol = [("태양추적", "태양고도 추적", A.FROZEN), ("TiDE 오라클학습", "TiDE", A.EVAL)]
    days = sorted(d.date.unique())
    fig, axes = plt.subplots(1, 2, figsize=(W / 72, 100 / 72))
    for ax, (col, title) in zip(axes, [("surplus", "잉여 발전"), ("purchase", "부족 (구매)")]):
        for j, (k, lab, c) in enumerate(pol):
            v = d[d.policy == k].set_index("date").loc[days, col]
            ax.bar(np.arange(len(days)) + (j - 0.5) * 0.38, v, width=0.36, color=c if j else A.FROZEN_TINT,
                   edgecolor=c, lw=0.5, label=f"{lab} (합 {v.sum():.1f})")
        ax.set_xticks(range(len(days)), [f"{pd.Timestamp(x).month}/{pd.Timestamp(x).day}" for x in days])
        ax.set_title(title, loc="left", color=A.INK1, pad=3)
        ax.set_ylabel("kWh / 일", labelpad=1.5)
        ax.grid(axis="y", color=A.GRID, lw=0.5)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        legend(ax, loc="upper right" if col == "surplus" else "upper left")
    axes[1].set_ylim(0, 420)
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.14, top=0.9, wspace=0.25)
    A.save(fig, "panel07d_weekdays")


def main():
    style()
    mpl.rcParams["hatch.linewidth"] = 0.4
    A.OUT.mkdir(parents=True, exist_ok=True)
    iwec_temperature()
    st, td = load(RUNS["태양추적"]), load(TIDE)
    panel05(st)
    panel07a(st, td)
    panel07b(st, td)
    panel07c(st, td)
    panel07d()


if __name__ == "__main__":
    main()

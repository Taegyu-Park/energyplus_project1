"""
plot_compare_c_jan13.py
=======================
같은 축 스케일(07~19시, y 공통)로 나란히 비교:
  (1) eplus_jan13/jan13_surplus90.png — IWEC 1/13, case3 E+, 잉여 구간 10:20~14:10 수동 90°
  (2) figures_open/open_angles_test_m0.png (c) — TMYx2011 1/11, case2 각도별 값으로 본 TiDE 각도 (예상)
  (3) 참고: 같은 TMYx2011 1/11, case3 E+ 실제 (eplus_open/runs/open_m0_wk)
출력: figures_open/compare_c_vs_jan13.png
"""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "eplus_open"))
import analyze_week as W  # noqa: E402

OUT = BASE_DIR / "figures_open" / "compare_c_vs_jan13.png"
ANGLES = np.arange(0, 100, 10)
HOURS = (7, 19)
C_PV, C_DEM, C_OPEN, C_DEF = "#f59e0b", "#1e293b", "#10b981", "#dc2626"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def sched(path):
    a = pd.read_csv(path)["optimal_angle"].to_numpy()
    return pd.Series(a, index=pd.Timestamp("2006-01-01") + pd.to_timedelta(np.arange(len(a)) * 10, "min"))


def day_slice(df, day):
    d = pd.Timestamp(day)
    return df.loc[d + pd.Timedelta(hours=HOURS[0]): d + pd.Timedelta(hours=HOURS[1]) - pd.Timedelta(minutes=10)]


def jan13():
    W.EVAL = (pd.Timestamp("2006-01-13"), pd.Timestamp("2006-01-14"))
    st = W.load_sql(BASE_DIR.parent / "pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400/eplusout.sql")
    s9 = W.load_sql(BASE_DIR / "eplus_jan13/runs/jan13_surplus90/eplusout.sql")
    ang = sched(BASE_DIR / "eplus_jan13/schedules/st_jan13_surplus90.csv")
    return day_slice(st, "2006-01-13"), day_slice(s9, "2006-01-13"), ang


def case2_c(day):
    df = pd.read_csv(BASE_DIR / "dataset_open" / "open_test.csv")
    th = pd.read_csv(BASE_DIR / "schedules" / "open_test_m+0.00.csv")["optimal_angle"].to_numpy()
    st = df["theta_st"].to_numpy().astype(int)
    r = np.arange(len(df))
    pick = lambda c, a: df[[f"{c}_{x}" for x in ANGLES]].to_numpy()[r, a // 10]
    dem = lambda a: pick("heat_load", a) / 2.5 + pick("lights_kwh", a)
    idx = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)
    base = pd.DataFrame({"pv": pick("pv_gen", st), "load": dem(st)}, index=idx)
    ctrl = pd.DataFrame({"pv": pick("pv_gen", th), "load": dem(th)}, index=idx)
    return day_slice(base, day), day_slice(ctrl, day), pd.Series(th, index=idx)


def eplus_week(day):
    W.EVAL = (pd.Timestamp("2006-01-09"), pd.Timestamp("2006-01-14"))
    st = W.load_sql(W.RUNS["태양추적"])
    td = W.load_sql(W.RUNS["TiDE"])
    return day_slice(st, day), day_slice(td, day), sched(W.SCHED["TiDE"])


def panel(ax, base, ctrl, ang, st_ang, title, lab):
    opened = (ang.reindex(ctrl.index) != st_ang.reindex(ctrl.index)).to_numpy()
    tod = lambda i: pd.Timestamp("2000-01-01") + (i - i.normalize())  # 날짜 제거, 시각만
    t = tod(ctrl.index)
    te = t.append(pd.DatetimeIndex([t[-1] + pd.Timedelta(minutes=10)]))
    ext = lambda s: np.r_[s.to_numpy(), s.iloc[-1]]
    pv, ld = ext(ctrl.pv), ext(ctrl.load)
    op = np.r_[opened, opened[-1]]
    ax.fill_between(te, 0, 1, where=op, step="post", color=C_OPEN, alpha=0.12, lw=0, transform=ax.get_xaxis_transform())
    ax.fill_between(te, pv, ld, where=(ld > pv) & op, step="post", color=C_DEF, alpha=0.35, lw=0)
    ax.step(te, ext(base.pv), where="post", color=C_PV, lw=1.2, ls="--")
    ax.step(te, pv, where="post", color=C_PV, lw=1.8)
    ax.step(te, ext(base.load), where="post", color=C_DEM, lw=1.2, ls="--")
    ax.step(te, ld, where="post", color=C_DEM, lw=1.8)

    m = opened
    defi = (ctrl.load - ctrl.pv)[m]
    sur0 = (base.pv - base.load)[m].clip(lower=0).sum()
    info = (f"연 구간 {m.sum()}스텝 중 부족 {int((defi > 0).sum())}스텝 ({(defi > 0).mean():.0%}), "
            f"부족 {defi.clip(lower=0).sum():.2f} kWh / 원래 잉여 {sur0:.1f} kWh")
    ax.set_title(f"{title}\n{info}", loc="left", fontsize=10.5, fontweight="bold")
    ax.text(0.99, 0.04, lab, transform=ax.transAxes, va="bottom", ha="right", fontsize=9, color="#475569")
    ax.grid(axis="y", alpha=0.3)


def main():
    st_ang = sched(BASE_DIR.parent / "bipv_experiments/schedules/suntracking_w0s90.csv")
    rows = [
        (*jan13(), "(1) IWEC 1/13 — case3 E+, 잉여 구간 전체 90° 수동 고정 (jan13_surplus90.png)", "기상 IWEC · 결과 E+ case3"),
        (*case2_c("2006-01-11"), "(2) TMYx2011 1/11 — TiDE 각도, case2 각도별 값으로 본 예상 (open_angles_test_m0.png (c))",
         "기상 TMYx2011 · 결과 case2 (열관성 없음)"),
        (*eplus_week("2006-01-11"), "(3) 참고: TMYx2011 1/11 — TiDE 각도, case3 E+ 실제", "기상 TMYx2011 · 결과 E+ case3"),
    ]
    fig, axes = plt.subplots(len(rows), 1, figsize=(13, 12), sharex=True, sharey=True)
    for ax, (b, c, a, title, lab) in zip(axes, rows):
        panel(ax, b, c, a, st_ang, title, lab)
        ax.set_ylabel("kWh / 10분")
    axes[0].set_ylim(0, 7)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=1))
    axes[-1].set_xlim(pd.Timestamp(f"2000-01-01 {HOURS[0]:02d}:00"), pd.Timestamp(f"2000-01-01 {HOURS[1]:02d}:00"))
    axes[0].legend([plt.Line2D([], [], color=C_PV, ls="--"), plt.Line2D([], [], color=C_PV, lw=1.8),
                    plt.Line2D([], [], color=C_DEM, ls="--"), plt.Line2D([], [], color=C_DEM, lw=1.8),
                    plt.Rectangle((0, 0), 1, 1, color=C_OPEN, alpha=0.12), plt.Rectangle((0, 0), 1, 1, color=C_DEF, alpha=0.35)],
                   ["PV 태양추적", "PV 제어", "수요 태양추적", "수요 제어", "연 구간 (태양추적과 다른 각도)", "연 구간 내 부족"],
                   ncol=3, fontsize=9, loc="upper right")
    fig.suptitle("잉여 구간 개방 비교 (같은 스케일: 07~19시, 0~7 kWh/10분)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT, dpi=140)
    print(f"[*] {OUT}")


if __name__ == "__main__":
    main()

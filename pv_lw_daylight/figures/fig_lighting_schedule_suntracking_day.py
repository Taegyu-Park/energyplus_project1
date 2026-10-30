"""
pv_lw_daylight/figures/fig_lighting_schedule_suntracking_day.py
===============================================================
같은 날, PV 태양고도 추적형(case3) 기준으로 조명 전력을 좌우 비교한다.
  왼쪽: 기존 조명 스케줄 (설계 전력 × 스케줄)
  오른쪽: 실내 조도 400 lx 일정 유지 (주광 연동, Continuous)
남측 2개 존(BIPV_office_1_S, BIPV_office_2_S) 합계 [W/m²], 10분 해상도.

입력: pv_lw_daylight/runs/annual/c3_FE_ST_lw (기존 스케줄), c3_FE_ST_lw_dl400 (400 lx)
출력: pv_lw_daylight/figures/fig_lighting_schedule_suntracking_day.{png,svg,csv}
사용: python fig_lighting_schedule_suntracking_day.py [--date 04-12]
"""

import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import dartwork_mpl as dm

mpl.rcParams["svg.fonttype"] = "none"
dm.style.use("presentation")
for w in range(100, 1000, 50):  # SVG 내보내기 시 숫자 font weight KeyError 회피
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "runs" / "annual"
ANGLE_CSV = HERE.parents[1] / "bipv_experiments" / "schedules" / "suntracking_w0s90.csv"  # c3_FE_ST_* 각도 입력
OUT = HERE / "fig_lighting_schedule_suntracking_day"

ZONES = ("BIPV_OFFICE_1_S", "BIPV_OFFICE_2_S")
RUN_BASE, RUN_DL = "c3_FE_ST_lw", "c3_FE_ST_lw_dl400"
SETPOINT = 400
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

C_BASE = "#5a5a55"   # 중립 잉크 — 기존 스케줄
C_DL = "#4a90e2"     # 파랑 — 400 lx 일정
C_SUN = "#f59e0b"    # 태양고도·PV 각도
INK, MUTED, GRID = "#1f1f1d", "#6b6a63", "#e4e3dd"


def query(run: str, name: str, month: int, day: int) -> pd.DataFrame:
    with sqlite3.connect(RUNS / run / "eplusout.sql") as c:
        q = """select t.Hour h, t.Minute mi, t.DayType dt, d.KeyValue k, r.Value v from ReportData r
               join ReportDataDictionary d on r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
               join Time t on r.TimeIndex = t.TimeIndex
               where d.Name = ? and d.ReportingFrequency = 'Zone Timestep' and t.Month = ? and t.Day = ?"""
        df = pd.read_sql(q, c, params=(name, month, day))
    df["k"] = df.k.str.upper()
    df["start"] = df.h + df.mi / 60 - 1 / 6  # SQL 시각 = 타임스텝 끝 → 시작 시각 [h]
    return df


def south_area(run: str) -> float:
    with sqlite3.connect(RUNS / run / "eplusout.sql") as c:
        rows = c.execute("select upper(ZoneName), FloorArea * Multiplier from Zones").fetchall()
    return sum(a for z, a in rows if z in ZONES)


def lighting_wm2(run: str, month: int, day: int, area: float) -> pd.Series:
    df = query(run, "Zone Lights Electricity Energy", month, day)
    df = df[df.k.isin(ZONES)]
    return df.groupby("start").v.sum() / 600 / area  # J/10min → W → W/m²


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="04-12", help="MM-DD (평일, 기본: 4월 12일 수요일)")
    args = ap.parse_args()
    month, day = map(int, args.date.split("-"))

    area = south_area(RUN_BASE)
    base = lighting_wm2(RUN_BASE, month, day, area)
    dl = lighting_wm2(RUN_DL, month, day, area)
    sun = query(RUN_BASE, "Site Solar Altitude Angle", month, day).set_index("start").v
    day0 = pd.Timestamp(2006, month, day)  # 시뮬레이션 달력 (1/1 = 일요일)
    dow = day0.dayofweek
    i0 = (day0.dayofyear - 1) * 144  # 플러그인은 CSV 행 순서(스텝 번호)로 각도를 넣는다
    ang = pd.read_csv(ANGLE_CSV).optimal_angle.iloc[i0:i0 + 144]
    ang.index = np.arange(144) / 6

    table = pd.DataFrame({"base_schedule_Wm2": base, "dl400_Wm2": dl, "sun_altitude_deg": sun, "pv_angle_deg": ang})
    table.index.name = "hour_start"
    table.round(3).to_csv(OUT.with_suffix(".csv"))
    daily = {k: s.sum() * area / 6 / 1000 for k, s in (("base", base), ("dl", dl))}  # W·(1/6 h) → kWh/일
    print(f"남측 바닥면적 {area:.0f} m²  /  일 조명 전력량 [kWh]: 기존 {daily['base']:.1f}, 400 lx {daily['dl']:.1f}")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), sharey=True, gridspec_kw={"wspace": 0.08})
    y_max = np.ceil(max(base.max(), dl.max()) * 1.25)
    panels = [
        (axes[0], base, C_BASE, f"(a) Existing lighting schedule — {daily['base']:.1f} kWh/day"),
        (axes[1], dl, C_DL, f"(b) Constant {SETPOINT} lx (daylight-linked) — {daily['dl']:.1f} kWh/day"),
    ]
    for ax, s, color, title in panels:
        xs = np.r_[s.index.values, 24.0]
        ys = np.r_[s.values, s.values[-1]]
        ax.fill_between(xs, ys, step="post", color=color, alpha=0.18, lw=0)
        ax.step(xs, ys, where="post", color=color, lw=2)
        ax.set_title(title, loc="left", fontsize=12.5, color=INK, pad=10)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 3))
        ax.set_xlabel("Hour of day")
        ax.set_ylim(0, y_max)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    tw = axes[1].twinx()  # PV 각도(10° 단위, 이산) — 주광 연동 패널에만
    tw.step(np.r_[ang.index.values, 24.0], np.r_[ang.values, ang.values[-1]], where="post", color=C_SUN, lw=1.6)
    tw.set_ylim(0, 100)
    tw.set_yticks(range(0, 91, 10))
    tw.set_ylabel("PV angle [°]", color=C_SUN)
    tw.tick_params(axis="y", colors=C_SUN)

    axes[0].set_ylabel("South-zone lighting power [W/m²]")
    axes[1].plot([], [], color=C_SUN, lw=1.6, label="PV angle (sun-tracking, 10° steps)")
    axes[1].legend(loc="upper right", frameon=False, fontsize=9.5)
    fig.suptitle(f"{month}/{day} ({DOW[dow]}) — PV angle: sun-altitude tracking", x=0.125, ha="left",
                 y=1.02, fontsize=13.5, color=INK, fontweight="bold")

    for ext in ("png", "svg"):
        fig.savefig(OUT.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight")
    print(f"저장: {OUT}.png/.svg/.csv")


if __name__ == "__main__":
    main()

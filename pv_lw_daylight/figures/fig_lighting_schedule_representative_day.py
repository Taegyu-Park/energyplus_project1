"""
pv_lw_daylight/figures/fig_lighting_schedule_representative_day.py
==================================================================
기존 조명 스케줄(항상 설계 전력 × 스케줄)과 주광 연동 조명(실내 조도 400 lx 일정 유지)을 대표일 하루 시간별로 비교한다.
남측 2개 존(BIPV_office_1_S, BIPV_office_2_S) 합계, case2 고정각 0°·40°·90°.

(a) 남측 존 조명 전력 밀도 [W/m²] — 기존 스케줄 vs 400 lx 일정 제어 (각도별)
(b) 창으로 들어온 자연광 조도 [lx] (1층 남측 기준점) — 400 lx 에 못 미치는 만큼 조명이 채움

입력: pv_lw_daylight/runs/annual/c2_RF_lw_A40 (기존 스케줄), c2_RF_lw_dl400_A<각도> (주광 연동)
출력: pv_lw_daylight/figures/fig_lighting_schedule_representative_day.{png,svg,csv}
사용: python fig_lighting_schedule_representative_day.py [--date 04-12]
"""

import argparse
import sqlite3
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import dartwork_mpl as dm

mpl.rcParams["svg.fonttype"] = "none"
dm.style.use("presentation")
for w in range(100, 1000, 50):  # SVG 내보내기 시 숫자 font weight KeyError 회피
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "runs" / "annual"
OUT = HERE / "fig_lighting_schedule_representative_day"

ZONES = ("BIPV_OFFICE_1_S", "BIPV_OFFICE_2_S")
REF_ZONE = "BIPV_OFFICE_1_S"
ANGLES = (0, 40, 90)
SETPOINT = 400

C_BASE = "#5a5a55"                                   # 중립 잉크 — 기존 스케줄
C_ANGLE = {0: "#9ec5f0", 40: "#4a90e2", 90: "#1c4f8f"}  # 단일 색상(파랑) 명도 순 — 각도 크기
INK, MUTED, GRID = "#1f1f1d", "#6b6a63", "#e4e3dd"


def query(run: str, name: str, freq: str, month: int, day: int) -> pd.DataFrame:
    with sqlite3.connect(RUNS / run / "eplusout.sql") as c:
        q = """select t.Hour h, t.Minute mi, d.KeyValue k, r.Value v from ReportData r
               join ReportDataDictionary d on r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
               join Time t on r.TimeIndex = t.TimeIndex
               where d.Name = ? and d.ReportingFrequency = ? and t.Month = ? and t.Day = ?"""
        df = pd.read_sql(q, c, params=(name, freq, month, day))
    df["k"] = df.k.str.upper()
    return df


def south_area(run: str) -> float:
    with sqlite3.connect(RUNS / run / "eplusout.sql") as c:
        rows = c.execute("select upper(ZoneName), FloorArea * Multiplier from Zones").fetchall()
    return sum(a for z, a in rows if z in ZONES)


def lighting_wm2(run: str, month: int, day: int, area: float) -> pd.Series:
    df = query(run, "Zone Lights Electricity Energy", "Hourly", month, day)
    df = df[df.k.isin(ZONES)]
    return df.groupby("h").v.sum() / 3600 / area  # J/h → W → W/m², 인덱스 = 시간 끝(1~24)


def daylight_lx(run: str, month: int, day: int) -> pd.Series:
    df = query(run, "Daylighting Reference Point 1 Illuminance", "Zone Timestep", month, day)
    df = df[df.k == f"DLC_{REF_ZONE}"]  # Daylighting:Controls 이름
    end = df.h + df.mi / 60  # SQL 시각(시:분) = 타임스텝 끝 시각
    return pd.Series(df.v.values, index=(end - 5 / 60).values).sort_index()  # 10분 타임스텝 중앙


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="04-12", help="MM-DD (평일, 기본: 4월 12일 수요일 맑은 날)")
    args = ap.parse_args()
    month, day = map(int, args.date.split("-"))

    area = south_area("c2_RF_lw_A40")
    base = lighting_wm2("c2_RF_lw_A40", month, day, area)
    ctrl = {a: lighting_wm2(f"c2_RF_lw_dl400_A{a:02d}", month, day, area) for a in ANGLES}
    lux = {a: daylight_lx(f"c2_RF_lw_dl400_A{a:02d}", month, day) for a in ANGLES}

    table = pd.DataFrame({"base_schedule": base, **{f"dl400_A{a:02d}": s for a, s in ctrl.items()}})
    table.index.name = "hour_end"
    table.round(3).to_csv(OUT.with_suffix(".csv"))
    daily = table.sum() * area / 1000  # kWh/일
    print(f"남측 바닥면적 {area:.0f} m²  /  일 조명 전력량 [kWh]:", daily.round(1).to_dict())

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.32})
    x = lambda s: list(s.index - 1) + [s.index[-1]]          # 시간 끝 → 계단 시작점
    y = lambda s: list(s.values) + [s.values[-1]]

    ax1.step(x(base), y(base), where="post", color=C_BASE, lw=2, ls=(0, (4, 2.5)), label=f"Existing schedule ({daily['base_schedule']:.1f} kWh/day)")
    for a in ANGLES:
        ax1.step(x(ctrl[a]), y(ctrl[a]), where="post", color=C_ANGLE[a], lw=2,
                 label=f"{SETPOINT} lx constant, PV {a}° ({daily[f'dl400_A{a:02d}']:.1f} kWh/day)")
    ax1.set_ylabel("South-zone lighting power [W/m²]")
    ax1.set_ylim(0, 7.5)
    ax1.set_title(f"(a) Lighting power — {month}/{day} (weekday)", loc="left", fontsize=12.5, color=INK, pad=10)
    ax1.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=2)

    for a in ANGLES:
        ax2.plot(lux[a].index, lux[a].values, color=C_ANGLE[a], lw=2, label=f"PV {a}°")
    ax2.axhline(SETPOINT, color=INK, lw=1.2, ls=(0, (4, 2.5)))
    ax2.text(0.3, SETPOINT, f"Setpoint {SETPOINT} lx", va="bottom", fontsize=9.5, color=INK)
    ax2.set_yscale("symlog", linthresh=100)
    ax2.set_ylim(0, 40000)
    ax2.set_yticks([0, 100, 1000, 10000])
    ax2.set_yticklabels(["0", "100", "1,000", "10,000"])
    ax2.set_ylabel("Daylight illuminance [lx]\n(1F south, reference point)")
    ax2.set_title("(b) Daylight entering the room — lights fill the gap below 400 lx", loc="left",
                  fontsize=12.5, color=INK, pad=10)
    ax2.legend(loc="upper left", frameon=False, fontsize=9.5)
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 3))
    ax2.set_xlabel("Hour of day")

    for ax in (ax1, ax2):
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    for ext in ("png", "svg"):
        fig.savefig(OUT.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight")
    print(f"저장: {OUT}.png/.svg/.csv")


if __name__ == "__main__":
    main()

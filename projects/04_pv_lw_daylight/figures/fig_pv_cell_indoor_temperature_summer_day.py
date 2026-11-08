"""
pv_lw_daylight/figures/fig_pv_cell_indoor_temperature_summer_day.py
===================================================================
TMYx.2011-2025, case2 고정 0° (PV 장파 연동 + 주광 400 lx, 최종 조건) 여름 대표일 하루의
PV 셀 온도와 2층 남측 실내 온도를 한 축에 그린다. 외기 건구온도는 얇은 점선.
실내 온도는 PV 장파 연동 실행과, 그것만 끈 기준안(나머지 조건 동일)을 함께 그린다.

- PV: 2층 남측 창 앞의 1~3단 (단은 경첩 높이 기준, run_pvlw.generator_rows) — 단마다 타임스텝 출력이 있는 대표 모듈 1개
- 실내: BIPV_OFFICE_2_S Zone Mean Air Temperature
- 모두 10분 타임스텝 출력. 외기는 EPW 시간값을 E+가 타임스텝마다 선형 보간한 값

입력: bipv_mismatch/case2_KS_TMYx2011_final/case2_0/{eplusout.sql, pvlw_config.json} (PV 복사 적용)
      pv_lw_daylight/runs/annual/c2_mm_tmyx2011_base_A00/eplusout.sql (PV 복사 미적용)
출력: pv_lw_daylight/figures/fig_pv_cell_indoor_temperature_summer_day.{png,svg,csv}
사용: python fig_pv_cell_indoor_temperature_summer_day.py [--date 08-02]
"""

import argparse
import json
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
RUN = HERE.parent.parent / "bipv_mismatch" / "case2_KS_TMYx2011_final" / "case2_0"
BASE_RUN = HERE.parent / "runs" / "annual" / "c2_mm_tmyx2011_base_A00"
OUT = HERE / "fig_pv_cell_indoor_temperature_summer_day"

ZONE = "BIPV_OFFICE_2_S"
ROWS = (1, 2, 3)  # 2층 남측 창이 보는 단
C_ROW = {1: "#1c4f8f", 2: "#4a90e2", 3: "#9ec5f0"}  # 단일 색상(파랑) 명도 순 — 1단(맨 위)이 가장 진함
C_ZONE = "#eb6834"       # 실내 — PV 복사 적용
C_ZONE_BASE = "#f2a27e"  # 실내 — PV 복사 미적용 (같은 색상, 밝게 + 파선)
C_AIR = "#6b6a63"
INK, GRID = "#1f1f1d", "#e4e3dd"


def query(name: str, month: int, day: int, run: Path = RUN) -> pd.DataFrame:
    with sqlite3.connect(run / "eplusout.sql") as c:
        q = """select t.Hour h, t.Minute mi, d.KeyValue k, r.Value v from ReportData r
               join ReportDataDictionary d on r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
               join Time t on r.TimeIndex = t.TimeIndex
               where d.Name = ? and d.ReportingFrequency = 'Zone Timestep' and t.Month = ? and t.Day = ?
                 and t.WarmupFlag = 0"""
        df = pd.read_sql(q, c, params=(name, month, day))
    df["x"] = df.h + df.mi / 60 - 5 / 60  # SQL 시각 = 타임스텝 끝 → 10분 타임스텝 중앙
    df["k"] = df.k.str.upper()
    return df


def series(df: pd.DataFrame, key: str) -> pd.Series:
    s = df[df.k == key.upper()]
    if s.empty:
        raise KeyError(key)
    return pd.Series(s.v.values, index=s.x.values).sort_index()


def row_modules() -> dict:
    """단 → 타임스텝 셀 온도 출력이 있는 모듈 (run_pvlw.py 가 단마다 첫 모듈에 출력을 붙인다)"""
    cfg = json.loads((RUN / "pvlw_config.json").read_text(encoding="utf-8"))
    keys = cfg["cell_keys"][str(cfg["fixed_angle"])]
    return {r: keys[str(r)][0] for r in ROWS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="08-02",
                    help="MM-DD (기본: 8월 2일 수요일 — 원본 2023년 매시 관측, 맑고 더운 평일)")
    args = ap.parse_args()
    month, day = map(int, args.date.split("-"))

    cell = query("Generator PV Cell Temperature", month, day)
    tc = {r: series(cell, m) for r, m in row_modules().items()}
    zone = series(query("Zone Mean Air Temperature", month, day), ZONE)
    zone_base = series(query("Zone Mean Air Temperature", month, day, BASE_RUN), ZONE)
    air = series(query("Site Outdoor Air Drybulb Temperature", month, day), "ENVIRONMENT")

    table = pd.DataFrame({**{f"Tcell_row{r}": s for r, s in tc.items()}, "T_zone_2F_S": zone,
                          "T_zone_2F_S_noPVLW": zone_base, "T_outdoor": air})
    table.index.name = "hour_mid"
    table.round(2).to_csv(OUT.with_suffix(".csv"))
    print(f"행 {len(table)} (10분 타임스텝) / 셀 최고:", {r: round(s.max(), 1) for r, s in tc.items()},
          f"/ 실내 {zone.min():.1f}~{zone.max():.1f} / 외기 {air.min():.1f}~{air.max():.1f} °C")

    fig, ax = plt.subplots(figsize=(10, 5.6))
    rows = pd.DataFrame(tc)
    spread = (rows.max(axis=1) - rows.min(axis=1)).max()
    if spread < 0.5:  # 0° 수직은 단끼리 서로 가리지 않아 1~3단이 사실상 같다 → 한 줄
        mean = rows.mean(axis=1)
        ax.plot(mean.index, mean.values, color=C_ROW[1], lw=2,
                label=f"PV cell, rows 1–3 (max {mean.max():.1f} °C; row spread ≤ {spread:.2f} °C)")
    else:
        for r in ROWS:
            ax.plot(tc[r].index, tc[r].values, color=C_ROW[r], lw=2, label=f"PV cell, row {r} (max {tc[r].max():.1f} °C)")
    ax.plot(zone_base.index, zone_base.values, color=C_ZONE_BASE, lw=2, ls=(0, (4, 2.5)),
            label="Indoor air, 2F south — without PV longwave")
    ax.plot(zone.index, zone.values, color=C_ZONE, lw=2, label="Indoor air, 2F south — with PV longwave")
    ax.plot(air.index, air.values, color=C_AIR, lw=0.9, ls=(0, (1, 2)), label="Outdoor air (dry-bulb)")

    ax.set_ylabel("Temperature [°C]")
    ax.set_title(f"PV cell and indoor temperature — case2 fixed 0°, TMYx 2011–2025, {month}/{day} (weekday)",
                 loc="left", fontsize=12.5, color=INK, pad=10)
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hour of day")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)

    for ext in ("png", "svg"):
        fig.savefig(OUT.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight")
    print(f"저장: {OUT}.png/.svg/.csv")


if __name__ == "__main__":
    main()

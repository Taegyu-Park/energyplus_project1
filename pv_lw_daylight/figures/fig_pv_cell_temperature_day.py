"""
pv_lw_daylight/figures/fig_pv_cell_temperature_day.py
=====================================================
case2 고정각 30° (PV 장파 연동 실행) 하루 동안의 PV 셀 온도를 외기·하늘 온도, 일사와 함께 그린다.

(a) PV 셀 온도 [°C] — 단별 대표 모듈(1·3·5·6단) 평균 + 외기 건구온도, 하늘 온도
(b) 일사 [W/m²] — 법선면 직달, 수평면 산란

입력: pv_lw_daylight/runs/annual/c2_RF_lw_A30 (셀 온도 타임스텝 출력이 있는 모듈만 사용)
출력: pv_lw_daylight/figures/fig_pv_cell_temperature_day.{png,svg,csv}
사용: python fig_pv_cell_temperature_day.py [--date 05-18]
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
RUN = HERE.parent / "runs" / "annual" / "c2_RF_lw_A30"
OUT = HERE / "fig_pv_cell_temperature_day"

MODULES = {1: "PV_1_30_04", 3: "PV_3_30_01", 5: "PV_5_30_07", 6: "PV_6_30_08"}  # 단 → 대표 모듈
C_CELL = "#1c4f8f"  # 단별 차이가 작아(≤ 약 1.6 °C) 평균 한 줄로 표시
C_AIR, C_SKY = "#5a5a55", "#a3a29a"
C_DIR, C_DIF = "#e0a030", "#b07a1c"
INK, GRID = "#1f1f1d", "#e4e3dd"


def query(name: str, month: int, day: int) -> pd.DataFrame:
    with sqlite3.connect(RUN / "eplusout.sql") as c:
        q = """select t.Hour h, t.Minute mi, d.KeyValue k, r.Value v from ReportData r
               join ReportDataDictionary d on r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
               join Time t on r.TimeIndex = t.TimeIndex
               where d.Name = ? and d.ReportingFrequency = 'Zone Timestep' and t.Month = ? and t.Day = ?"""
        df = pd.read_sql(q, c, params=(name, month, day))
    df["x"] = df.h + df.mi / 60 - 5 / 60  # SQL 시각 = 타임스텝 끝 → 10분 타임스텝 중앙
    df["k"] = df.k.str.upper()
    return df


def series(df: pd.DataFrame, key: str) -> pd.Series:
    s = df[df.k == key]
    return pd.Series(s.v.values, index=s.x.values).sort_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="05-18", help="MM-DD (기본: 5월 18일, 4~5월 중 일사 최대인 맑은 날)")
    args = ap.parse_args()
    month, day = map(int, args.date.split("-"))

    cell = query("Generator PV Cell Temperature", month, day)
    tc = {r: series(cell, m) for r, m in MODULES.items()}
    air = series(query("Site Outdoor Air Drybulb Temperature", month, day), "ENVIRONMENT")
    sky = series(query("Site Sky Temperature", month, day), "ENVIRONMENT")
    dni = series(query("Site Direct Solar Radiation Rate per Area", month, day), "ENVIRONMENT")
    dif = series(query("Site Diffuse Solar Radiation Rate per Area", month, day), "ENVIRONMENT")

    table = pd.DataFrame({**{f"Tcell_row{r}": s for r, s in tc.items()},
                          "T_outdoor": air, "T_sky": sky, "DNI": dni, "DHI": dif})
    table.index.name = "hour_mid"
    table.round(2).to_csv(OUT.with_suffix(".csv"))
    print("일 최고 셀 온도 [°C]:", {r: round(s.max(), 1) for r, s in tc.items()},
          f"/ 외기 최고 {air.max():.1f}, 하늘 최저 {sky.min():.1f}")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.6, 1], "hspace": 0.3})

    rows = pd.DataFrame(tc)
    mean, spread = rows.mean(axis=1), (rows.max(axis=1) - rows.min(axis=1)).max()
    ax1.plot(mean.index, mean.values, color=C_CELL, lw=2.2,
             label=f"PV cell (rows 1·3·5·6 mean, max {mean.max():.1f} °C; row spread ≤ {spread:.1f} °C)")
    ax1.plot(air.index, air.values, color=C_AIR, lw=1.8, ls=(0, (4, 2.5)), label="Outdoor air (dry-bulb)")
    ax1.plot(sky.index, sky.values, color=C_SKY, lw=1.6, ls=(0, (1, 2)), label="Sky temperature")
    ax1.set_ylabel("Temperature [°C]")
    ax1.set_title(f"(a) PV cell temperature — case2 fixed 30°, {month}/{day}", loc="left",
                  fontsize=12.5, color=INK, pad=10)
    ax1.legend(loc="upper left", frameon=False, fontsize=9.5)

    ax2.fill_between(dni.index, dni.values, color=C_DIR, alpha=0.25, lw=0)
    ax2.plot(dni.index, dni.values, color=C_DIR, lw=2, label="Direct normal")
    ax2.plot(dif.index, dif.values, color=C_DIF, lw=2, label="Diffuse horizontal")
    ax2.set_ylabel("Solar radiation [W/m²]")
    ax2.set_ylim(0, None)
    ax2.set_title("(b) Solar radiation (weather file)", loc="left", fontsize=12.5, color=INK, pad=10)
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

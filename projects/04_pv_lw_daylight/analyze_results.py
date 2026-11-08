"""
pv_lw_daylight/analyze_results.py
==================================================
PV 복사·주광 연동 조명의 효과를 case2(각도별)·case3(태양추적)에 대해 정리한다.

- 지표(kWh): 난방·냉방 열부하, HVAC 전력(냉방/3.0 + 난방/2.5), 조명 전력(전체·남측), 수요 = HVAC + 전체 조명, PV
- 기간: 연간 / 난방기 평일(11/1~3/31, 월~금)
- 효과 분리
  * PV 복사 효과 = lw − base
  * 조명 효과   = lw_dl400 − lw
  * 합계        = lw_dl400 − base
  * 설정조도 민감도 = lw_dl300, lw_dl600 − base
- 출력: results/summary_long.csv, results/effects.csv, 화면에 요약표

사용: python pv_lw_daylight/analyze_results.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs" / "annual"
OUT = HERE / "results"
CASE3_BASE = RUNS / "c3_FE_ST_base"  # case3 기준안 (DifferentialEnthalpy, Eg 1.25)
COP_C, COP_H = 3.0, 2.5
S_ZONES = ("BIPV_OFFICE_1_S", "BIPV_OFFICE_2_S")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
FREQ_ORDER = ["Zone Timestep", "HVAC System Timestep", "Hourly"]
VARIANTS = ["base", "lw", "lw_dl400", "lw_dl300", "lw_dl600"]


def read_var(conn, name: str) -> pd.DataFrame:
    """가장 짧은 빈도 하나로 (Month, DayType, KeyValue, Value) — 웜업·설계일 제외"""
    freqs = [r[0] for r in conn.execute("SELECT DISTINCT ReportingFrequency FROM ReportDataDictionary WHERE Name=?", (name,))]
    freqs = [f for f in FREQ_ORDER if f in freqs]
    if not freqs:
        return pd.DataFrame(columns=["Month", "DayType", "KeyValue", "Value"])
    return pd.read_sql(
        """SELECT t.Month, t.DayType, upper(d.KeyValue) AS KeyValue, rd.Value FROM ReportData rd
           JOIN ReportDataDictionary d ON rd.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
           JOIN Time t ON rd.TimeIndex = t.TimeIndex
           WHERE d.Name = ? AND d.ReportingFrequency = ? AND t.WarmupFlag = 0
             AND t.EnvironmentPeriodIndex = (SELECT MAX(EnvironmentPeriodIndex) FROM Time)""",
        conn, params=[name, freqs[0]])


def metrics(run: Path) -> dict:
    conn = sqlite3.connect(run / "eplusout.sql")
    data = {
        "heating": read_var(conn, "Zone Ideal Loads Supply Air Total Heating Energy"),
        "cooling": read_var(conn, "Zone Ideal Loads Supply Air Total Cooling Energy"),
        "lights": read_var(conn, "Zone Lights Electricity Energy"),
        "pv": read_var(conn, "Facility Total Produced Electricity Energy"),
    }
    conn.close()
    out = {}
    for period in ("annual", "heat_wkday"):
        sel = {}
        for k, df in data.items():
            if period == "heat_wkday":
                df = df[df.Month.isin([11, 12, 1, 2, 3]) & df.DayType.isin(WEEKDAYS)]
            sel[k] = df
        h = sel["heating"].Value.sum() / 3.6e6
        c = sel["cooling"].Value.sum() / 3.6e6
        li = sel["lights"].Value.sum() / 3.6e6
        li_s = sel["lights"][sel["lights"].KeyValue.isin(S_ZONES)].Value.sum() / 3.6e6
        hvac = c / COP_C + h / COP_H
        out[period] = {"heating": h, "cooling": c, "hvac": hvac, "lights": li, "lights_s": li_s,
                       "demand": hvac + li, "pv": sel["pv"].Value.sum() / 3.6e6}
    return out


def run_dirs() -> dict:
    """(case, angle, variant) → 실행 폴더"""
    dirs = {}
    for v in VARIANTS:
        for a in range(0, 100, 10):
            p = RUNS / f"c2_RF_{v}_A{a:02d}"
            if (p / "eplusout.sql").exists() and (p / "summary.json").exists():
                dirs[("case2", f"A{a:02d}", v)] = p
        p = CASE3_BASE if v == "base" else RUNS / f"c3_FE_ST_{v}"
        if (p / "eplusout.sql").exists() and (p / "eplusout.end").exists():
            dirs[("case3", "ST", v)] = p
    return dirs


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for (case, angle, v), p in sorted(run_dirs().items()):
        for period, m in metrics(p).items():
            rows.append({"case": case, "angle": angle, "variant": v, "period": period, **m})
    long = pd.DataFrame(rows)
    long.to_csv(OUT / "summary_long.csv", index=False)

    keys = ["case", "angle", "period"]
    wide = long.pivot_table(index=keys, columns="variant", values=["heating", "cooling", "hvac", "lights", "demand", "pv"])
    eff = pd.DataFrame(index=wide.index)

    def diff(metric, a, b):
        if (metric, a) in wide.columns and (metric, b) in wide.columns:
            return wide[(metric, a)] - wide[(metric, b)]
        return pd.Series(float("nan"), index=wide.index)

    if ("demand", "base") in wide.columns:
        eff["base_hvac"] = wide[("hvac", "base")]
        eff["base_lights"] = wide[("lights", "base")]
        eff["base_demand"] = wide[("demand", "base")]
    for m in ("heating", "cooling", "hvac"):
        eff[f"LW_d{m}"] = diff(m, "lw", "base")
    eff["DL_dlights"] = diff("lights", "lw_dl400", "lw")
    eff["DL_dhvac"] = diff("hvac", "lw_dl400", "lw")
    eff["TOT_ddemand"] = diff("demand", "lw_dl400", "base")
    eff["TOT_ddemand_pct"] = 100 * eff["TOT_ddemand"] / eff.get("base_demand", float("nan"))
    eff["L300_ddemand"] = diff("demand", "lw_dl300", "base")
    eff["L600_ddemand"] = diff("demand", "lw_dl600", "base")
    eff.to_csv(OUT / "effects.csv")

    pd.set_option("display.width", 200)
    for period in ("annual", "heat_wkday"):
        e = eff.xs(period, level="period").round(1)
        print(f"\n=== {period} (kWh) ===")
        print(e.to_string())
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()

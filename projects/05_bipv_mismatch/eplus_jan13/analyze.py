"""
eplus_jan13/analyze.py
======================
잉여 90° 실행(runs/jan13_surplus90)과 기준안 태양추적 연간 실행(pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400) 비교.

- 검증: 1/6~1/12(스케줄 동일) 일별 PV·HVAC·조명이 연간 실행과 일치하는지
- 평가: 1/13 07시 ~ 1/14 07시, 수요 L = 냉방/3.0 + 난방/2.5 + 조명, 구매 = Σ max(L − PV, 0) (10분)
- 시간대별 분해와 10분 시계열 그림

출력: eplus_jan13/{compare_jan13.csv, jan13_surplus90.png, jan13_surplus90.svg}
"""

import sqlite3
from pathlib import Path

import pandas as pd

from plot_day import plot_day

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RUNS = {
    "suntracking": ROOT / "pv_lw_daylight" / "runs" / "annual" / "c3_FE_ST_lw_dl400" / "eplusout.sql",
    "surplus90": HERE / "runs" / "jan13_surplus90" / "eplusout.sql",
}
VARS = {
    "Generator Produced DC Electricity Energy": "pv",
    "Zone Ideal Loads Supply Air Total Cooling Energy": "cool",
    "Zone Ideal Loads Supply Air Total Heating Energy": "heat",
    "Zone Lights Electricity Energy": "lights",
}
COP_COOLING, COP_HEATING = 3.0, 2.5
J_TO_KWH = 1 / 3.6e6
EVAL = ("2006-01-13 07:00", "2006-01-14 07:00")  # 구간 시작 시각 기준 [start, end)
BANDS = [(7, 10, "07-10 아침"), (10, 14, "10-14 잉여 구간"), (14, 19, "14-19 오후·저녁"),
         (19, 24, "19-24 밤"), (24, 31, "익일 00-07")]


def load(sql: Path) -> pd.DataFrame:
    names = ",".join(f"'{n}'" for n in VARS)
    q = f"""SELECT t.Month, t.Day, t.Hour, t.Minute, d.Name, SUM(v.Value) AS val
            FROM ReportData v
            JOIN ReportDataDictionary d ON v.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON v.TimeIndex = t.TimeIndex
            WHERE d.ReportingFrequency = 'Zone Timestep' AND d.Name IN ({names})
              AND t.Month = 1 AND t.Day BETWEEN 6 AND 14 AND (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)
            GROUP BY t.TimeIndex, d.Name"""
    with sqlite3.connect(sql) as con:
        raw = pd.read_sql(q, con)
    # 구간 종료 라벨 → 구간 시작 시각
    raw["t"] = (pd.to_datetime(dict(year=2006, month=raw.Month, day=raw.Day))
                + pd.to_timedelta(raw.Hour, "h") + pd.to_timedelta(raw.Minute, "m") - pd.Timedelta(minutes=10))
    df = raw.pivot_table(index="t", columns="Name", values="val").rename(columns=VARS) * J_TO_KWH
    df["hvac"] = df.cool / COP_COOLING + df.heat / COP_HEATING
    df["load"] = df.hvac + df.lights
    df["purchase"] = (df.load - df.pv).clip(lower=0)
    df["surplus"] = (df.pv - df.load).clip(lower=0)
    return df


def main():
    d = {k: load(p) for k, p in RUNS.items()}
    st, s9 = d["suntracking"], d["surplus90"]

    print("[검증] 1/6~1/12 일별 차이 (surplus90 − 연간 태양추적, kWh)")
    cols = ["pv", "heat", "cool", "lights", "purchase"]
    pre = (s9.loc[:"2006-01-12"] - st.loc[s9.index[0]:"2006-01-12"])[cols]
    print(pre.groupby(pre.index.date).sum().round(2).to_string())

    ev = slice(EVAL[0], pd.Timestamp(EVAL[1]) - pd.Timedelta(minutes=10))
    rows = []
    for name, df in d.items():
        x = df.loc[ev]
        rows.append({"run": name, **{c: x[c].sum() for c in ["pv", "heat", "cool", "lights", "hvac", "load", "purchase", "surplus"]}})
    tab = pd.DataFrame(rows).set_index("run")
    tab.loc["차이"] = tab.loc["surplus90"] - tab.loc["suntracking"]
    print(f"\n[평가] {EVAL[0]} ~ {EVAL[1]} 합계 (kWh, heat·cool은 열량)")
    print(tab.round(2).to_string())

    print("\n[시간대별] 구매 / 잉여 / PV / 수요 (태양추적 → 잉여90°, kWh)")
    for h0, h1, label in BANDS:
        def band(df):
            x = df.loc[ev]
            hr = (x.index - pd.Timestamp("2006-01-13")).total_seconds() / 3600
            return x[(hr >= h0) & (hr < h1)]
        a, b = band(st), band(s9)
        print(f"  {label:14s} 구매 {a.purchase.sum():6.2f} → {b.purchase.sum():6.2f} | 잉여 {a.surplus.sum():6.2f} → {b.surplus.sum():6.2f}"
              f" | PV {a.pv.sum():6.2f} → {b.pv.sum():6.2f} | 수요 {a.load.sum():6.2f} → {b.load.sum():6.2f}")

    out = pd.concat({k: v.loc[ev] for k, v in d.items()}, axis=1)
    out.to_csv(HERE / "compare_jan13.csv")

    plot_day(st, s9, "90° 고정", [("2006-01-13 10:20", "2006-01-13 14:10", "#10b981", "PV 발전 잉여 구간", "#047857")],
             "잉여 구간 90° 고정 vs 태양추적", HERE / "jan13_surplus90.png")
    print(f"\n[*] {HERE / 'compare_jan13.csv'}\n[*] {HERE / 'jan13_surplus90.png'}")


if __name__ == "__main__":
    main()

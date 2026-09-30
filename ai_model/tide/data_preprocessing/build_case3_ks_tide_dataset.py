"""
build_case3_ks_tide_dataset.py
==============================
Builds a case3-only (sun-tracking BIPV, south) dataset from
'case_analysis/bipv_variation/5zone_NSEW_korean/case3_v3_south_prev_backup/eplusout.sql'
using the same preprocessing as build_case2_ks_tide_dataset.py, then splits it
with the same monthly block split as split_case2_ks_dataset.py
(Train: days 1-21, Val: days 22-25, Test: day 26-end).
"""

import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path("C:/Users/taegyu/Codes/energyplus_project1")
CASE3_SQL = (BASE_DIR / "case_analysis" / "bipv_variation" / "5zone_NSEW_korean"
             / "case3_v3_south_prev_backup" / "eplusout.sql")
SUN_SCHED_CSV = BASE_DIR / "data" / "bipv_suntracking_angles_annual.csv"
OUT_DIR = BASE_DIR / "ai_model" / "tide" / "data" / "dataset"

COP_COOLING = 3.0
COP_HEATING = 2.5
JOULES_TO_KWH = 1.0 / 3.6e6

WEATHER_MAP = {
    'Site Outdoor Air Drybulb Temperature': 'outdoor_temp',
    'Site Direct Solar Radiation Rate per Area': 'direct_solar',
    'Site Diffuse Solar Radiation Rate per Area': 'diffuse_solar',
    'Site Solar Altitude Angle': 'sun_altitude',
    'Site Solar Azimuth Angle': 'sun_azimuth',
}
LOAD_NAMES = [
    'Zone Ideal Loads Supply Air Total Heating Energy',
    'Zone Ideal Loads Supply Air Total Cooling Energy',
    'Facility Total Produced Electricity Energy',
]


def read_pivot(conn, names, agg):
    quoted = ",".join(f"'{n}'" for n in names)
    q = f"""
    SELECT r.TimeIndex, rd.Name, {agg}(r.Value) AS Val
    FROM ReportData r
    JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
    JOIN Time t ON r.TimeIndex = t.TimeIndex
    WHERE t.WarmupFlag = 0 AND t.Interval = 10 AND rd.Name IN ({quoted})
    GROUP BY r.TimeIndex, rd.Name
    """
    raw = pd.read_sql_query(q, conn)
    piv = raw.pivot(index='TimeIndex', columns='Name', values='Val')
    piv.columns = [c.strip() for c in piv.columns]
    return piv


def main():
    # read-only / immutable so a running or locked simulation cannot interfere
    uri = f"file:{CASE3_SQL.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)

    weather = read_pivot(conn, list(WEATHER_MAP), "MAX").rename(columns=WEATHER_MAP)
    loads = read_pivot(conn, LOAD_NAMES, "SUM").fillna(0.0)
    conn.close()
    assert len(weather) == len(loads) == 52560, (len(weather), len(loads))

    dt_index = pd.date_range('2026-01-01 00:10:00', periods=len(weather), freq='10min')
    df = weather.copy()
    df.index = dt_index
    df.index.name = 'timestamp'

    hour_float = dt_index.hour + dt_index.minute / 60.0
    doy = dt_index.dayofyear
    df['hour_sin'] = np.sin(2.0 * np.pi * hour_float / 24.0)
    df['hour_cos'] = np.cos(2.0 * np.pi * hour_float / 24.0)
    df['month_sin'] = np.sin(2.0 * np.pi * doy / 365.25)
    df['month_cos'] = np.cos(2.0 * np.pi * doy / 365.25)
    df['direct_solar'] = df['direct_solar'].clip(lower=0.0)
    df['diffuse_solar'] = df['diffuse_solar'].clip(lower=0.0)

    pv = loads['Facility Total Produced Electricity Energy'].values * JOULES_TO_KWH
    cool = loads['Zone Ideal Loads Supply Air Total Cooling Energy'].values * JOULES_TO_KWH
    heat = loads['Zone Ideal Loads Supply Air Total Heating Energy'].values * JOULES_TO_KWH
    df['pv_gen'] = pv
    df['cool_load'] = cool
    df['heat_load'] = heat
    df['net_energy'] = cool / COP_COOLING + heat / COP_HEATING - pv

    sched = pd.read_csv(SUN_SCHED_CSV)
    assert len(sched) == len(df)
    assert (pd.to_datetime(sched['timestamp']).values == dt_index.values).all(), "schedule timestamps misaligned"
    df['tracking_angle'] = sched['optimal_angle'].values

    # ── validation ──
    print(f"rows={len(df):,} cols={df.shape[1]} NaN={int(df.isnull().sum().sum())}")
    if df.isnull().sum().sum() > 0:
        raise ValueError("NaN in dataset")
    night = df['sun_altitude'] <= 0
    print(f"night PV sum (expected 0): {df.loc[night, 'pv_gen'].sum():.4f} kWh")
    print(f"annual: PV={pv.sum():,.1f}  Cool={cool.sum():,.1f}  Heat={heat.sum():,.1f}  Net={df['net_energy'].sum():,.1f} kWh")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = df.reset_index()
    df.to_csv(OUT_DIR / "case3_ks_bipv_tide_dataset.csv", index=False)

    days = df['timestamp'].dt.day
    splits = {"train": days <= 21, "val": (days >= 22) & (days <= 25), "test": days >= 26}
    for name, mask in splits.items():
        part = df[mask]
        part.to_csv(OUT_DIR / f"case3_ks_{name}.csv", index=False)
        print(f"{name}: {len(part):,} rows ({len(part)/len(df)*100:.2f}%)")
    assert sum(m.sum() for m in splits.values()) == len(df)


if __name__ == "__main__":
    main()

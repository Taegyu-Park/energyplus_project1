"""
build_case2_ks_tide_dataset.py
==============================
Extracts simulation results from 10 discrete BIPV tilt angles (0° to 90°)
in 'case_analysis/normal/case2_KS/case2_{angle}/eplusout.sql',
calculates zone heating/cooling electrical loads and PV generation (kWh),
computes net energy for all angles, derives optimal tilt angle labels,
and exports a comprehensive, ready-to-train time-series dataset for TiDE / Supervised Learning.
"""

import os
import sqlite3
import time
import numpy as np
import pandas as pd
from pathlib import Path

# ── 1. Configuration & Constants ─────────────────────────────────────────────
BASE_DIR = Path("C:/Users/taegyu/Codes/energyplus_project1")
CASE_DIR = BASE_DIR / "case_analysis" / "normal" / "case2_KS"
OUT_CSV  = BASE_DIR / "data" / "case2_ks_bipv_tide_dataset.csv"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING = 3.0
COP_HEATING = 2.5
JOULES_TO_KWH = 1.0 / 3.6e6

# ── 2. Weather & Geometry Features (Common across all angles) ─────────────────
def extract_weather_and_time(sample_sql_path: Path):
    print(f"[*] Extracting weather & sun geometry from {sample_sql_path.name}...")
    conn = sqlite3.connect(sample_sql_path)
    
    # Extract contiguous 10-minute time indices
    time_query = """
    SELECT TimeIndex, Month, Day, Hour, Minute
    FROM Time
    WHERE WarmupFlag = 0 AND Interval = 10
    ORDER BY TimeIndex
    """
    df_time = pd.read_sql_query(time_query, conn)
    num_steps = len(df_time)
    print(f"    -> Verified timestep count: {num_steps} (Expected 52,560 for 365 days)")
    
    # Extract weather & solar geometry variables
    weather_query = """
    SELECT 
        r.TimeIndex,
        rd.Name,
        r.Value
    FROM ReportData r
    JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
    JOIN Time t ON r.TimeIndex = t.TimeIndex
    WHERE t.WarmupFlag = 0 AND t.Interval = 10
      AND rd.Name IN (
          'Site Outdoor Air Drybulb Temperature',
          'Site Direct Solar Radiation Rate per Area',
          'Site Diffuse Solar Radiation Rate per Area',
          'Site Solar Altitude Angle',
          'Site Solar Azimuth Angle'
      )
    """
    df_raw = pd.read_sql_query(weather_query, conn)
    conn.close()
    
    # Pivot to columns
    df_weather = df_raw.pivot(index='TimeIndex', columns='Name', values='Value')
    df_weather.columns = [c.strip() for c in df_weather.columns]
    
    # Rename to clean feature names
    rename_map = {
        'Site Outdoor Air Drybulb Temperature': 'outdoor_temp',
        'Site Direct Solar Radiation Rate per Area': 'direct_solar',
        'Site Diffuse Solar Radiation Rate per Area': 'diffuse_solar',
        'Site Solar Altitude Angle': 'sun_altitude',
        'Site Solar Azimuth Angle': 'sun_azimuth'
    }
    df_weather = df_weather.rename(columns=rename_map)
    
    # Align with continuous Datetime Index (2026-01-01 00:10:00 to 2026-12-31 24:00:00)
    dt_index = pd.date_range(start='2026-01-01 00:10:00', periods=num_steps, freq='10min')
    df_weather.index = dt_index
    df_weather.index.name = 'timestamp'
    
    # Add cyclical temporal encodings (Known Future)
    hour_float = dt_index.hour + dt_index.minute / 60.0
    day_of_year = dt_index.dayofyear
    
    df_weather['hour_sin'] = np.sin(2.0 * np.pi * hour_float / 24.0)
    df_weather['hour_cos'] = np.cos(2.0 * np.pi * hour_float / 24.0)
    df_weather['month_sin'] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    df_weather['month_cos'] = np.cos(2.0 * np.pi * day_of_year / 365.25)
    
    # Sanity clipping for solar irradiance
    df_weather['direct_solar'] = df_weather['direct_solar'].clip(lower=0.0)
    df_weather['diffuse_solar'] = df_weather['diffuse_solar'].clip(lower=0.0)
    
    print(f"    -> Weather features extracted: {list(df_weather.columns)}")
    return df_weather


# ── 3. Angle-specific Loads & PV Generation Extraction ────────────────────────
def extract_angle_data(angle: int):
    sql_path = CASE_DIR / f"case2_{angle}" / "eplusout.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file missing for angle {angle}: {sql_path}")
    
    conn = sqlite3.connect(sql_path)
    loads_pv_query = """
    SELECT 
        r.TimeIndex,
        rd.Name,
        SUM(r.Value) as TotalValue
    FROM ReportData r
    JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
    JOIN Time t ON r.TimeIndex = t.TimeIndex
    WHERE t.WarmupFlag = 0 AND t.Interval = 10
      AND rd.Name IN (
          'Zone Ideal Loads Supply Air Total Heating Energy',
          'Zone Ideal Loads Supply Air Total Cooling Energy',
          'Facility Total Produced Electricity Energy'
      )
    GROUP BY r.TimeIndex, rd.Name
    """
    df_raw = pd.read_sql_query(loads_pv_query, conn)
    conn.close()
    
    df_piv = df_raw.pivot(index='TimeIndex', columns='Name', values='TotalValue').fillna(0.0)
    df_piv.columns = [c.strip() for c in df_piv.columns]
    
    pv_j   = df_piv.get('Facility Total Produced Electricity Energy', pd.Series(0.0, index=df_piv.index))
    cool_j = df_piv.get('Zone Ideal Loads Supply Air Total Cooling Energy', pd.Series(0.0, index=df_piv.index))
    heat_j = df_piv.get('Zone Ideal Loads Supply Air Total Heating Energy', pd.Series(0.0, index=df_piv.index))
    
    # Convert Joules to kWh
    pv_kwh   = pv_j * JOULES_TO_KWH
    cool_kwh = cool_j * JOULES_TO_KWH
    heat_kwh = heat_j * JOULES_TO_KWH
    
    # Calculate Net Energy (kWh): (Cooling/COP_c + Heating/COP_h) - PV
    net_kwh  = (cool_kwh / COP_COOLING) + (heat_kwh / COP_HEATING) - pv_kwh
    
    return {
        f"pv_gen_{angle}": pv_kwh.values,
        f"cool_load_{angle}": cool_kwh.values,
        f"heat_load_{angle}": heat_kwh.values,
        f"net_energy_{angle}": net_kwh.values
    }


# ── 4. Main Build Pipeline ────────────────────────────────────────────────────
def main():
    start_time = time.time()
    print("=" * 70)
    print("Starting BIPV Case2_KS TiDE Dataset Construction Pipeline")
    print("=" * 70)
    
    # 1. Base weather & time extraction
    sample_sql = CASE_DIR / "case2_0" / "eplusout.sql"
    df_dataset = extract_weather_and_time(sample_sql)
    
    # 2. Iterate through all 10 angles
    all_angle_data = {}
    for angle in ANGLES:
        t_angle = time.time()
        print(f"[*] Processing angle {angle:>2}° from case2_{angle}/eplusout.sql...")
        data_dict = extract_angle_data(angle)
        all_angle_data.update(data_dict)
        print(f"    -> Done in {time.time() - t_angle:.2f}s")
        
    df_angles = pd.DataFrame(all_angle_data, index=df_dataset.index)
    df_merged = pd.concat([df_dataset, df_angles], axis=1)
    
    # 3. Calculate Optimal Angle and Optimal Net Energy
    print("\n[*] Calculating optimal tilt angle (argmin Net Energy) per timestep...")
    net_cols = [f"net_energy_{a}" for a in ANGLES]
    net_matrix = df_merged[net_cols].values  # Shape: (52560, 10)
    
    opt_indices = np.argmin(net_matrix, axis=1)  # 0 to 9
    opt_angles = np.array(ANGLES)[opt_indices]   # 0 to 90
    opt_net_energy = np.min(net_matrix, axis=1)
    
    df_merged['optimal_angle_idx'] = opt_indices
    df_merged['optimal_angle'] = opt_angles
    df_merged['optimal_net_energy'] = opt_net_energy
    
    # 4. Data Quality & Integrity Validation
    print("\n" + "=" * 70)
    print("Dataset Sanity & Integrity Validation Report")
    print("=" * 70)
    print(f"1. Total Rows: {len(df_merged):,} (Expected 52,560)")
    print(f"2. Total Columns: {df_merged.shape[1]}")
    
    null_counts = df_merged.isnull().sum().sum()
    print(f"3. Missing / NaN Values: {null_counts}")
    if null_counts > 0:
        raise ValueError("Critical error: Dataset contains NaN values!")
    
    # Night validation: when sun altitude <= 0, PV generation must be zero
    night_mask = df_merged['sun_altitude'] <= 0
    pv_cols = [f"pv_gen_{a}" for a in ANGLES]
    night_pv_sum = df_merged.loc[night_mask, pv_cols].sum().sum()
    print(f"4. Nighttime PV Generation Total (sun_altitude <= 0): {night_pv_sum:.4f} kWh (Expected 0.0)")
    
    # Optimal angle distribution summary
    print("\n5. Annual Optimal Tilt Angle Distribution (% of time):")
    angle_dist = df_merged['optimal_angle'].value_counts(normalize=True).sort_index() * 100.0
    for a, pct in angle_dist.items():
        print(f"   - {a:>2}° : {pct:6.2f}%")
        
    # Daylight optimal angle distribution (excluding nighttime)
    day_mask = df_merged['sun_altitude'] > 0
    day_dist = df_merged.loc[day_mask, 'optimal_angle'].value_counts(normalize=True).sort_index() * 100.0
    print("\n6. Daytime-Only Optimal Tilt Angle Distribution (sun_altitude > 0):")
    for a, pct in day_dist.items():
        print(f"   - {a:>2}° : {pct:6.2f}%")
        
    # Annual Net Energy Savings vs Fixed Angles
    print("\n7. Annual Net Energy Comparison (MWh/year):")
    opt_annual_mwh = df_merged['optimal_net_energy'].sum() / 1000.0
    print(f"   - Optimal Dynamic Control : {opt_annual_mwh:8.2f} MWh/yr")
    for a in [0, 30, 60, 90]:
        fixed_annual_mwh = df_merged[f"net_energy_{a}"].sum() / 1000.0
        diff_pct = (fixed_annual_mwh - opt_annual_mwh) / fixed_annual_mwh * 100.0
        print(f"   - Fixed {a:>2}° BIPV           : {fixed_annual_mwh:8.2f} MWh/yr  (Optimal saves +{diff_pct:.2f}%)")
        
    # 5. Export to CSV
    print("\n" + "=" * 70)
    print(f"Saving compiled dataset to: {OUT_CSV}")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_merged.to_csv(OUT_CSV, index=True)
    file_size_mb = os.path.getsize(OUT_CSV) / (1024 * 1024)
    print(f"Export Complete! File size: {file_size_mb:.2f} MB")
    print(f"Total Pipeline Runtime: {time.time() - start_time:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()

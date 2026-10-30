"""
bipv_experiments/analysis/sql_extract.py
========================================
EnergyPlus eplusout.sql 에서 timestep(10분) 단위 기상·부하·PV 를 추출하는 공용 함수.
(ai_model/tide/data_preprocessing/build_case2_ks_tide_dataset.py 의 추출 로직과 동일한 정의)

net_energy = cooling/3.0 + heating/2.5 - PV  (kWh, zone 합계)
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

COP_COOLING = 3.0
COP_HEATING = 2.5
J_TO_KWH = 1.0 / 3.6e6

WEATHER_VARS = {
    "Site Outdoor Air Drybulb Temperature": "outdoor_temp",
    "Site Direct Solar Radiation Rate per Area": "direct_solar",
    "Site Diffuse Solar Radiation Rate per Area": "diffuse_solar",
    "Site Solar Altitude Angle": "sun_altitude",
    "Site Solar Azimuth Angle": "sun_azimuth",
}
LOAD_VARS = {
    "Facility Total Produced Electricity Energy": "pv_gen",
    "Zone Ideal Loads Supply Air Total Cooling Energy": "cool_load",
    "Zone Ideal Loads Supply Air Total Heating Energy": "heat_load",
}


def _query(sql_path: Path, names: list[str], agg: str) -> pd.DataFrame:
    conn = sqlite3.connect(sql_path)
    placeholders = ",".join("?" for _ in names)
    df = pd.read_sql_query(
        f"""SELECT r.TimeIndex, d.Name, {agg}(r.Value) AS Value
            FROM ReportData r
            JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON r.TimeIndex = t.TimeIndex
            WHERE t.WarmupFlag = 0 AND t.Interval = 10 AND d.Name IN ({placeholders})
            GROUP BY r.TimeIndex, d.Name""",
        conn,
        params=names,
    )
    conn.close()
    return df.pivot(index="TimeIndex", columns="Name", values="Value").fillna(0.0)


def extract_weather(sql_path: Path, start: str = "2026-01-01 00:10:00") -> pd.DataFrame:
    df = _query(sql_path, list(WEATHER_VARS), "AVG").rename(columns=WEATHER_VARS)
    df.index = pd.date_range(start=start, periods=len(df), freq="10min", name="timestamp")
    df["direct_solar"] = df["direct_solar"].clip(lower=0.0)
    df["diffuse_solar"] = df["diffuse_solar"].clip(lower=0.0)
    return df


def extract_loads_pv(sql_path: Path, suffix: str = "") -> pd.DataFrame:
    df = _query(sql_path, list(LOAD_VARS), "SUM").rename(columns=LOAD_VARS)
    for c in LOAD_VARS.values():
        if c not in df:
            df[c] = 0.0
    df = df[list(LOAD_VARS.values())] * J_TO_KWH
    df["net_energy"] = df["cool_load"] / COP_COOLING + df["heat_load"] / COP_HEATING - df["pv_gen"]
    if suffix:
        df.columns = [f"{c}_{suffix}" for c in df.columns]
    return df.reset_index(drop=True)


def stitch(df: pd.DataFrame, angles: np.ndarray, col: str, angle_list=range(0, 100, 10)) -> np.ndarray:
    """고정각 데이터셋에서 매 timestep 스케줄 각도에 해당하는 값을 골라 반환 (이어 붙이기 평가)"""
    mat = df[[f"{col}_{a}" for a in angle_list]].values
    idx = (np.asarray(angles) // 10).astype(int)
    return mat[np.arange(len(df)), idx]

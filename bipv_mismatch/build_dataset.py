"""
build_dataset.py
================
PLAN.md Step 3. bipv_mismatch/<기상 폴더>/case2_{a}/eplusout.sql 에서 TiDE 학습 데이터셋을 만든다.

기본(--set final, 2026-10-28): 최종 조건(PV 장파 연동, 주광 연동 400 lx, DifferentialEnthalpy, Eg 1.25)
3개 기상 파일을 1년씩 학습/검증/테스트로 쓴다.
  train = IWEC (case2_KS_IWEC_final), val = TMYx.2004-2018 (case2_KS_TMYx2004), test = TMYx.2011-2025 (case2_KS_TMYx2011_final)
--set legacy: 이전 조건(장파·주광 없음) case2_KS / case2_KS_TMYx → dataset/ (옛 출력, 재현용)

- 단위: 에너지는 10분 스텝당 kWh
- PV: Generator Produced DC Electricity Energy 96개 합
- HVAC 전력 = 냉방/3.0 + 난방/2.5, 조명은 주광 연동이라 각도마다 다르다 → lights_kwh_{a}
- 수요 = HVAC 전력 + 조명 (2026-10-29 사용자 결정), 구매 = max(수요 − PV, 0), 잉여 PV = max(PV − 수요, 0)
- 1단계 라벨: 구매 최소 각도, 동점이면 수요 최소
- 각도 a의 PV 표면 기울기 = 90 − a (0° 수직, 90° 수평), 방위 180°
- timestamp는 E+ 기상 연도 2006 그대로(요일 보존)

출력: --set final  → bipv_mismatch/dataset_final/case2_mm_{train,val,test}.csv (기상 파일 1개 = CSV 1개)
      --set legacy → bipv_mismatch/dataset/case2_gp_dataset.csv, case2_gp_{train,val,test}.csv,
                     --weather tmyx 이면 case2_gp_tmyx_dataset.csv (옛 파일 이름 그대로)
"""

import argparse
import time
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FINAL_SPLITS = {  # 분할 이름 → 결과 폴더
    "train": "case2_KS_IWEC_final",
    "val": "case2_KS_TMYx2004",
    "test": "case2_KS_TMYx2011_final",
}
LEGACY = {"iwec": "case2_KS", "tmyx": "case2_KS_TMYx"}

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING = 3.0
COP_HEATING = 2.5
J_TO_KWH = 1.0 / 3.6e6
GROUND_ALBEDO = 0.2
TIE_TOL_KWH = 1e-6  # 구매 전력 동점 판정 (10분 스텝당 kWh)

SOUTH_ZONES = ["BIPV_OFFICE_1_S", "BIPV_OFFICE_2_S"]
SOUTH_WINDOWS = ["BIPV_OFFICE_1_S..WALL_S_GLZ0", "BIPV_OFFICE_2_S..WALL_S_GLZ0"]

SITE_VARS = {
    "Site Outdoor Air Drybulb Temperature": "outdoor_temp",
    "Site Direct Solar Radiation Rate per Area": "direct_solar",
    "Site Diffuse Solar Radiation Rate per Area": "diffuse_solar",
    "Site Outdoor Air Relative Humidity": "outdoor_rh",
    "Site Outdoor Air Dewpoint Temperature": "dewpoint",
    "Site Wind Speed": "wind_speed",
    "Site Sky Temperature": "sky_temp",
    "Site Horizontal Infrared Radiation Rate per Area": "horiz_ir",
    "Site Total Sky Cover": "sky_cover",
    "Site Solar Altitude Angle": "sun_altitude",
    "Site Solar Azimuth Angle": "sun_azimuth",
    "Site Day Type Index": "day_type_index",
}

PER_ANGLE_VARS = [
    "Generator Produced DC Electricity Energy",
    "Generator PV Cell Temperature",
    "Zone Ideal Loads Supply Air Total Cooling Energy",
    "Zone Ideal Loads Supply Air Total Heating Energy",
    "Zone Mean Air Temperature",
    "Zone Operative Temperature",
    "Surface Window Transmitted Solar Radiation Energy",
    "Zone Lights Electricity Energy",
]

SCHEDULE_VARS = [
    "Zone People Occupant Count",
    "Zone Thermostat Heating Setpoint Temperature",
    "Zone Thermostat Cooling Setpoint Temperature",
    "Zone Electric Equipment Electricity Energy",
]


def read_vars(sql_path: Path, names) -> pd.DataFrame:
    """Zone Timestep(10분) 값을 (TimeIndex, Name, KeyValue, Value) long 형식으로 읽는다."""
    placeholders = ",".join("?" * len(names))
    query = f"""
    SELECT r.TimeIndex, d.Name, d.KeyValue, r.Value
    FROM ReportData r
    JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
    JOIN Time t ON r.TimeIndex = t.TimeIndex
    WHERE t.WarmupFlag = 0 AND t.Interval = 10
      AND d.ReportingFrequency = 'Zone Timestep'
      AND d.Name IN ({placeholders})
    """
    with sqlite3.connect(sql_path) as conn:
        return pd.read_sql_query(query, conn, params=list(names))


def series(df: pd.DataFrame, name: str, keys=None, agg="sum") -> pd.Series:
    sub = df[df["Name"] == name]
    if keys is not None:
        sub = sub[sub["KeyValue"].str.upper().isin([k.upper() for k in keys])]
    if sub.empty:
        raise KeyError(f"{name} (keys={keys}) 없음")
    return sub.groupby("TimeIndex")["Value"].agg(agg)


def extract_common(sql_path: Path) -> pd.DataFrame:
    print(f"[*] 공통 feature 추출: {sql_path.parent.name}")
    with sqlite3.connect(sql_path) as conn:
        n_steps = conn.execute("SELECT COUNT(*) FROM Time WHERE WarmupFlag = 0 AND Interval = 10").fetchone()[0]
    if n_steps != 52560:
        raise ValueError(f"타임스텝 {n_steps} (기대 52,560)")

    raw = read_vars(sql_path, list(SITE_VARS) + SCHEDULE_VARS)
    site = raw[raw["Name"].isin(SITE_VARS)].pivot(index="TimeIndex", columns="Name", values="Value")
    df = site.rename(columns=SITE_VARS)

    # 스케줄 (각도 무관, 0° 기준)
    df["occupancy"] = series(raw, "Zone People Occupant Count")
    df["heat_setpoint"] = series(raw, "Zone Thermostat Heating Setpoint Temperature", agg="mean")
    df["cool_setpoint"] = series(raw, "Zone Thermostat Cooling Setpoint Temperature", agg="mean")
    df["equip_kwh"] = series(raw, "Zone Electric Equipment Electricity Energy") * J_TO_KWH

    df.index = pd.date_range("2006-01-01 00:10:00", periods=n_steps, freq="10min", name="timestamp")

    df["direct_solar"] = df["direct_solar"].clip(lower=0.0)
    df["diffuse_solar"] = df["diffuse_solar"].clip(lower=0.0)
    alt = np.radians(df["sun_altitude"].clip(lower=0.0))
    df["ghi"] = df["direct_solar"] * np.sin(alt) + df["diffuse_solar"]

    # 시간 인코딩. 날짜·요일은 구간 시작 시각 기준(E+는 24:00 스텝을 그날로 본다)
    idx = df.index
    start = idx - pd.Timedelta(minutes=10)
    hour = idx.hour + idx.minute / 60.0
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["month_sin"] = np.sin(2 * np.pi * start.dayofyear / 365.25)
    df["month_cos"] = np.cos(2 * np.pi * start.dayofyear / 365.25)
    dow = start.dayofweek  # 0=월
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    df["is_weekend"] = (dow >= 5).astype(float)

    # E+ Day Type Index(1=일 ... 7=토)와 pandas 요일 일치 확인
    expected = ((dow + 1) % 7) + 1
    if not np.array_equal(df["day_type_index"].to_numpy().astype(int), np.asarray(expected)):
        raise ValueError("Day Type Index와 2006년 요일 불일치")

    # 각도별 패널 입사각 cos θ와 POA (등방성 확산)
    alt_r = np.radians(df["sun_altitude"])
    az_r = np.radians(df["sun_azimuth"])
    up = (df["sun_altitude"] > 0).astype(float)
    for a in ANGLES:
        beta = np.radians(90 - a)
        cos_inc = np.sin(alt_r) * np.cos(beta) + np.cos(alt_r) * np.sin(beta) * np.cos(az_r - np.pi)
        cos_inc = (cos_inc * up).clip(lower=0.0)
        df[f"cos_inc_{a}"] = cos_inc
        df[f"poa_{a}"] = (
            df["direct_solar"] * cos_inc
            + df["diffuse_solar"] * (1 + np.cos(beta)) / 2
            + GROUND_ALBEDO * df["ghi"] * (1 - np.cos(beta)) / 2
        )
    return df


def extract_angle(case_dir: Path, angle: int) -> dict:
    sql_path = case_dir / f"case2_{angle}" / "eplusout.sql"
    raw = read_vars(sql_path, PER_ANGLE_VARS)

    pv = series(raw, "Generator Produced DC Electricity Energy") * J_TO_KWH
    cool = series(raw, "Zone Ideal Loads Supply Air Total Cooling Energy") * J_TO_KWH
    heat = series(raw, "Zone Ideal Loads Supply Air Total Heating Energy") * J_TO_KWH
    n_pv = raw.loc[raw["Name"] == "Generator Produced DC Electricity Energy", "KeyValue"].nunique()
    if n_pv != 96:
        raise ValueError(f"{angle}°: PV 발전기 {n_pv}개 (기대 96)")

    hvac = cool / COP_COOLING + heat / COP_HEATING
    lights = series(raw, "Zone Lights Electricity Energy") * J_TO_KWH
    demand = hvac + lights
    out = {
        f"pv_gen_{angle}": pv,
        f"cool_load_{angle}": cool,
        f"heat_load_{angle}": heat,
        f"hvac_elec_{angle}": hvac,
        f"lights_kwh_{angle}": lights,
        f"demand_elec_{angle}": demand,
        f"purchase_{angle}": (demand - pv).clip(lower=0.0),
        f"surplus_pv_{angle}": (pv - demand).clip(lower=0.0),
        f"pv_cell_temp_{angle}": series(raw, "Generator PV Cell Temperature", agg="mean"),
        f"south_zone_temp_{angle}": series(raw, "Zone Mean Air Temperature", SOUTH_ZONES, "mean"),
        f"south_zone_optemp_{angle}": series(raw, "Zone Operative Temperature", SOUTH_ZONES, "mean"),
        f"south_win_tx_{angle}": series(raw, "Surface Window Transmitted Solar Radiation Energy", SOUTH_WINDOWS) * J_TO_KWH,
    }
    return {k: v.to_numpy() for k, v in out.items()}


def label_stage1(df: pd.DataFrame) -> pd.DataFrame:
    """구매 최소 각도, 동점(TIE_TOL 이내)이면 수요(HVAC+조명) 최소, 그래도 동점이면 작은 각도."""
    purchase = df[[f"purchase_{a}" for a in ANGLES]].to_numpy()
    hvac = df[[f"hvac_elec_{a}" for a in ANGLES]].to_numpy()
    demand = df[[f"demand_elec_{a}" for a in ANGLES]].to_numpy()
    p_min = purchase.min(axis=1, keepdims=True)
    tied = purchase <= p_min + TIE_TOL_KWH
    idx = np.where(tied, demand, np.inf).argmin(axis=1)
    rows = np.arange(len(df))
    return pd.DataFrame({
        "optimal_angle_idx": idx,
        "optimal_angle": np.array(ANGLES)[idx],
        "optimal_purchase": purchase[rows, idx],
        "optimal_hvac_elec": hvac[rows, idx],
        "optimal_demand_elec": demand[rows, idx],
        "optimal_pv_gen": df[[f"pv_gen_{a}" for a in ANGLES]].to_numpy()[rows, idx],
        "n_tied_angles": tied.sum(axis=1),
    }, index=df.index)


def build(case_dir: Path) -> pd.DataFrame:
    print(f"[*] 기상 폴더: {case_dir.name}")
    t0 = time.time()
    df = extract_common(case_dir / "case2_0" / "eplusout.sql")
    angle_cols = {}
    for a in ANGLES:
        t = time.time()
        angle_cols.update(extract_angle(case_dir, a))
        print(f"[*] {a:>2}° 추출 ({time.time() - t:.1f}s)")
    df = pd.concat([df, pd.DataFrame(angle_cols, index=df.index)], axis=1)
    df = pd.concat([df, label_stage1(df)], axis=1)

    if df.isnull().any().any():
        raise ValueError(f"NaN 존재: {df.columns[df.isnull().any()].tolist()}")

    # ── 검증 리포트 ──
    print("\n" + "=" * 70)
    print(f"행 {len(df):,}, 열 {df.shape[1]}")
    night = df["sun_altitude"] <= 0
    print(f"야간 PV 합: {df.loc[night, [f'pv_gen_{a}' for a in ANGLES]].to_numpy().sum():.4f} kWh")
    print("\n각도별 연간 합계 (MWh): PV / 냉방 / 난방 / HVAC전력 / 조명 / 수요 / 구매 / 잉여PV")
    for a in ANGLES:
        s = [df[f"{c}_{a}"].sum() / 1000 for c in ["pv_gen", "cool_load", "heat_load", "hvac_elec", "lights_kwh", "demand_elec", "purchase", "surplus_pv"]]
        print(f"  {a:>2}°: " + " / ".join(f"{v:6.2f}" for v in s))
    print(f"  1단계 오라클: 구매 {df['optimal_purchase'].sum() / 1000:6.2f} / 수요 {df['optimal_demand_elec'].sum() / 1000:6.2f}")

    day = ~night
    print("\n주간 1단계 라벨 분포 (%):")
    print((df.loc[day, "optimal_angle"].value_counts(normalize=True).sort_index() * 100).round(2).to_string())
    print(f"주간 구매 동점(2개 이상 각도) 비율: {(df.loc[day, 'n_tied_angles'] > 1).mean() * 100:.1f}%")
    print("PV 입사 근사 상관 (poa_a vs pv_gen_a, 주간):")
    print("  " + ", ".join(f"{a}°={np.corrcoef(df.loc[day, f'poa_{a}'], df.loc[day, f'pv_gen_{a}'])[0, 1]:.3f}" for a in ANGLES))
    print(f"[*] {case_dir.name} 완료 ({time.time() - t0:.1f}s)\n")
    return df


def split(df: pd.DataFrame):
    """legacy 전용: 월별 블록 분할(1~21 / 22~25 / 26~말일)"""
    day = (df.index - pd.Timedelta(minutes=10)).day
    return df[day <= 21], df[(day >= 22) & (day <= 25)], df[day >= 26]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["final", "legacy"], default="final")
    ap.add_argument("--weather", choices=list(LEGACY), default="iwec", help="--set legacy 에서만 사용")
    args = ap.parse_args()

    if args.set == "final":
        out_dir = BASE_DIR / "dataset_final"
        out_dir.mkdir(parents=True, exist_ok=True)
        cols = None
        for name, folder in FINAL_SPLITS.items():
            df = build(BASE_DIR / folder)
            if cols is not None and list(df.columns) != cols:
                raise ValueError(f"{name}: 열 구성이 train과 다름")
            cols = list(df.columns)
            df.to_csv(out_dir / f"case2_mm_{name}.csv")
            print(f"[*] {name} ({folder}): {len(df):,}행 → {out_dir / f'case2_mm_{name}.csv'}")
        return

    out_dir = BASE_DIR / "dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = build(BASE_DIR / LEGACY[args.weather])
    if args.weather == "tmyx":
        df.to_csv(out_dir / "case2_gp_tmyx_dataset.csv")
        return
    df.to_csv(out_dir / "case2_gp_dataset.csv")
    for name, part in zip(["train", "val", "test"], split(df)):
        part.to_csv(out_dir / f"case2_gp_{name}.csv")
        print(f"[*] {name}: {len(part):,}행")


if __name__ == "__main__":
    main()

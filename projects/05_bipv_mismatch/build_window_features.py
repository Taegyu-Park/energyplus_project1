"""
build_window_features.py
========================
잉여 구간 각도 제어용 TiDE 데이터 준비 (2026-10-30 사용자 결정).

- 대상: 11~3월 평일, 태양추적(projects/03_bipv_experiments/schedules/suntracking_w0s90.csv) 기준 잉여 구간
  window = PV_θST > L_θST, L = 난방/2.5 + 냉방/3.0 + 조명 (case2 각도별 결과에서 시점마다 θ_ST 열 선택)
  (IWEC 에서 case3 태양추적 연간 결과 잉여 시점의 97%와 일치, case2 기준이 부분집합)
- 태양추적 경로 열(_st): 실제 운전에서 관측 가능한 값의 대리 (TiDE 과거 입력)
- 창 유입 일사 win_in_{a}: 남측 수직면 직달 일사를 태양 프로파일각 5° 구간별로 나눈 항 + 확산 + 지면 반사에
  각도별 계수를 곱한 값. 계수는 학습(IWEC) 낮 시간 south_win_tx_{a} 로만 최소제곱 적합 → 검증·테스트에 그대로 적용
  (POA 는 열린 각도에서 창 투과 일사를 설명하지 못함: 90° 상관 0.38 vs 이 피처 0.97, TMYx2011 겨울 낮)

입력: dataset_final/case2_mm_{train,val,test}.csv
출력: dataset_open/open_{train,val,test}.csv, dataset_open/win_in_coef.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shared.paths import EXPERIMENTS, ROOT

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "dataset_final"
OUT_DIR = BASE_DIR / "dataset_open"
SUNTRACKING = EXPERIMENTS / "schedules" / "suntracking_w0s90.csv"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
COP_COOLING, COP_HEATING = 3.0, 2.5
WINTER = [11, 12, 1, 2, 3]
GROUND_ALBEDO = 0.2
PROFILE_BINS = np.arange(5, 90, 5)  # 프로파일각 구간 경계 → 18개 구간

COMMON_COLS = ["timestamp", "diffuse_solar", "direct_solar", "horiz_ir", "dewpoint", "outdoor_temp", "outdoor_rh",
               "sky_temp", "sun_altitude", "sun_azimuth", "sky_cover", "wind_speed", "occupancy", "heat_setpoint",
               "cool_setpoint", "ghi", "hour_sin", "hour_cos", "month_sin", "month_cos", "dow_sin", "dow_cos",
               "is_weekend"]
PER_ANGLE = ["cos_inc", "poa", "pv_gen", "cool_load", "heat_load", "lights_kwh", "south_zone_temp", "south_win_tx"]


def solar_terms(df: pd.DataFrame) -> np.ndarray:
    """창 유입 일사 회귀 설계행렬: [프로파일각 구간별 직달(수직면) 18개, 확산(수직면), 지면 반사(수직면)]"""
    alt = np.radians(df["sun_altitude"].to_numpy())
    rel = np.radians(df["sun_azimuth"].to_numpy()) - np.pi
    up = alt > 0
    cos_v = np.where(up, np.cos(alt) * np.cos(rel), 0.0).clip(min=0.0)
    profile = np.degrees(np.arctan2(np.tan(alt), np.clip(np.cos(rel), 1e-3, None)))
    k = np.digitize(profile, PROFILE_BINS)
    beam = df["direct_solar"].to_numpy() * cos_v
    cols = [np.where(k == i, beam, 0.0) for i in range(len(PROFILE_BINS) + 1)]
    cols.append(np.where(up, df["diffuse_solar"].to_numpy() * 0.5, 0.0))
    cols.append(np.where(up, GROUND_ALBEDO * df["ghi"].to_numpy() * 0.5, 0.0))
    return np.column_stack(cols)


def build(name: str, theta_st: np.ndarray, coef: dict | None) -> tuple[pd.DataFrame, dict]:
    usecols = set(COMMON_COLS) | {f"{c}_{a}" for c in PER_ANGLE for a in ANGLES}
    df = pd.read_csv(SRC_DIR / f"case2_mm_{name}.csv", usecols=lambda c: c in usecols)
    if len(df) != len(theta_st):
        raise ValueError(f"{name}: 행 수 {len(df)} != 태양추적 스케줄 {len(theta_st)}")
    t = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)  # 구간 시작 시각

    X = solar_terms(df)
    if coef is None:  # 학습 분할에서만 적합
        day = df["sun_altitude"].to_numpy() > 0
        coef = {str(a): np.linalg.lstsq(X[day], df.loc[day, f"south_win_tx_{a}"].to_numpy(), rcond=None)[0].tolist()
                for a in ANGLES}
    out = {}
    for a in ANGLES:
        out[f"win_in_{a}"] = (X @ np.array(coef[str(a)])).clip(min=0.0)
        out[f"demand_{a}"] = (df[f"heat_load_{a}"] / COP_HEATING + df[f"cool_load_{a}"] / COP_COOLING
                              + df[f"lights_kwh_{a}"]).to_numpy()

    rows = np.arange(len(df))
    idx = theta_st // 10
    pick = lambda c: df[[f"{c}_{a}" for a in ANGLES]].to_numpy()[rows, idx]
    demand_all = np.column_stack([out[f"demand_{a}"] for a in ANGLES])
    out["theta_st"] = theta_st.astype(float)
    out["pv_st"] = pick("pv_gen")
    out["heat_st"] = pick("heat_load")
    out["lights_st"] = pick("lights_kwh")
    out["demand_st"] = demand_all[rows, idx]
    out["zone_temp_st"] = pick("south_zone_temp")
    out["target_day"] = (t.dt.month.isin(WINTER) & (t.dt.dayofweek < 5)).astype(int).to_numpy()
    out["window"] = ((out["pv_st"] > out["demand_st"]) & (out["target_day"] == 1)).astype(int)

    keep = COMMON_COLS + [f"{c}_{a}" for c in ["cos_inc", "poa", "pv_gen", "heat_load", "lights_kwh"] for a in ANGLES]
    res = pd.concat([df[keep], pd.DataFrame(out, index=df.index)], axis=1)
    return res, coef


def main():
    OUT_DIR.mkdir(exist_ok=True)
    theta_st = pd.read_csv(SUNTRACKING)["optimal_angle"].to_numpy().astype(int)
    coef = None
    for name in ["train", "val", "test"]:
        df, coef = build(name, theta_st, coef)
        df.to_csv(OUT_DIR / f"open_{name}.csv", index=False)

        t = pd.to_datetime(df["timestamp"]) - pd.Timedelta(minutes=10)
        day = (df["sun_altitude"] > 0) & t.dt.month.isin(WINTER)
        wday = df["target_day"] == 1
        r = lambda a: np.corrcoef(df.loc[day, f"win_in_{a}"], pd.read_csv(
            SRC_DIR / f"case2_mm_{name}.csv", usecols=[f"south_win_tx_{a}"]).loc[day, f"south_win_tx_{a}"])[0, 1]
        print(f"[{name}] {len(df):,}행 | 대상 평일 {t[wday].dt.date.nunique()}일 | 잉여 구간 {df['window'].sum():,}스텝 "
              f"({t[df['window'] == 1].dt.date.nunique()}일) | 잉여 PV {((df['pv_st'] - df['demand_st']).clip(lower=0) * df['window']).sum():,.0f} kWh")
        print("   창 유입 일사 상관 (겨울 낮): " + ", ".join(f"{a}°={r(a):.3f}" for a in (0, 30, 60, 90)))
    (OUT_DIR / "win_in_coef.json").write_text(json.dumps(coef, indent=1), encoding="utf-8")
    print(f"[*] {OUT_DIR}")


if __name__ == "__main__":
    main()

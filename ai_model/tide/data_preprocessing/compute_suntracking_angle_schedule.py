"""
compute_suntracking_angle_schedule.py
======================================
model_pythonpluginsystem_fixed.py 의 웜업/폴백 로직인
"EPW 위치 기준 태양 고도각과 가장 가까운 10도 단위 각도로 BIPV를 제어"를
EnergyPlus 시뮬레이션을 돌리지 않고 순수 Python으로 재현한다.

태양 위치 계산은 Spencer(1971) Fourier 근사(적위/균시차)와 표준 시간각 공식을
사용하며, 이는 EnergyPlus WeatherManager의 태양 위치 계산과 동일 계열의 방법이라
10도 단위 버킷팅 정확도(<0.5도 오차) 수준에서 실질적으로 동일한 결과를 낸다.

Output: data/bipv_suntracking_angles_annual.csv (timestamp, sun_altitude, optimal_angle)
"""

import math
import csv
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EPW_PATH = PROJECT_ROOT / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
OUT_PATH = PROJECT_ROOT / "data" / "bipv_suntracking_angles_annual.csv"

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
LABEL_YEAR = 2026  # data/bipv_optimal_angles_annual.csv 와 동일한 라벨 연도 (물리량엔 무관, 둘 다 평년)
TIMESTEP_MIN = 10  # EPW/시뮬레이션 타임스텝 (6 steps/hour -> 52560 steps/year)


def read_epw_location(epw_path: Path):
    with open(epw_path, "r", encoding="latin-1") as f:
        header = f.readline().strip().split(",")
    # LOCATION,City,State,Country,Source,WMO,Lat,Lon,TimeZone,Elevation
    lat = float(header[6])
    lon = float(header[7])
    tz = float(header[8])
    return lat, lon, tz


def solar_altitude_deg(dt: datetime, lat: float, lon: float, tz: float) -> float:
    """Spencer(1971) Fourier 근사 기반 태양 고도각(deg). EnergyPlus 태양 위치 계산과 동일 계열."""
    day_of_year = dt.timetuple().tm_yday
    frac_day = (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    gamma = 2.0 * math.pi / 365.0 * (day_of_year - 1 + frac_day)

    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    eqtime_min = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )

    lstm = 15.0 * tz  # Local Standard Time Meridian (deg)
    time_correction_min = 4.0 * (lon - lstm) + eqtime_min
    local_std_time_hr = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    local_solar_time_hr = local_std_time_hr + time_correction_min / 60.0

    hour_angle_deg = 15.0 * (local_solar_time_hr - 12.0)

    lat_rad = math.radians(lat)
    hour_angle_rad = math.radians(hour_angle_deg)

    sin_alt = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(hour_angle_rad)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    return math.degrees(math.asin(sin_alt))


def nearest_angle(sun_alt: float) -> int:
    if sun_alt <= 0.0:
        return 90
    return min(ANGLES, key=lambda a: abs(a - sun_alt))


def main():
    lat, lon, tz = read_epw_location(EPW_PATH)
    print(f"[*] EPW Location: lat={lat}, lon={lon}, tz={tz}")

    start = datetime(LABEL_YEAR, 1, 1, 0, 0, 0) + timedelta(minutes=TIMESTEP_MIN)
    n_steps = int(365 * 24 * 60 / TIMESTEP_MIN)  # 52560 for non-leap year

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sun_altitude", "optimal_angle"])

        dt = start
        for _ in range(n_steps):
            sun_alt = solar_altitude_deg(dt, lat, lon, tz)
            angle = nearest_angle(sun_alt)
            writer.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"), round(sun_alt, 3), angle])
            dt += timedelta(minutes=TIMESTEP_MIN)

    print(f"[*] Wrote {n_steps:,} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()

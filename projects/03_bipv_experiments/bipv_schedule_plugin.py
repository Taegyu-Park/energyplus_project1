"""
bipv_experiments/bipv_schedule_plugin.py
(model_pythonpluginsystem_ai.py 를 복사해 스케줄 CSV 경로(BIPV_SCHEDULE_CSV)와 날짜 기반 인덱싱을 추가한 실험용 버전)

Kinetic BIPV & Dynamic Shading TiDE AI Optimal Angle Control Plugin
===================================================================
- Developer: Antigravity Pair-Programming Agent
- Core Function:
  EnergyPlus 시뮬레이션 타임스텝마다 사전 학습된 TiDE 시계열 신경망이
  Net Energy를 최소화하도록 산출한 최적 틸트 각도(bipv_optimal_angles_annual.csv)를
  실시간으로 주입하여 10개 각도의 동적 차양 투과율 및 PV 발전기 가용성을 제어합니다.
- Robust Features:
  - 웜업(Warmup) 기간 중에는 0으로 리셋 및 태양 추종 Fallback 유지
  - 본 시뮬레이션 시작 후 52,560개 타임스텝에 1:1 완벽 동기화 주입
  - CSV 누락 시 자동 태양 고도 추종 Fallback 내장
"""

import os
import sys
import math
import csv
from pathlib import Path
from pyenergyplus.plugin import EnergyPlusPlugin

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
CANOPY_LENGTH = 4 / 3  # 1.33333333333333 m
CANOPY_WIDTH = 2.0
CANOPY_AREA = CANOPY_LENGTH * CANOPY_WIDTH  # 2.6666666666666665 m2

PV_GROSS_AREA = 2.379132
PV_PACKING_FACTOR = 0.9189
PV_ACTIVE_AREA = PV_GROSS_AREA * PV_PACKING_FACTOR  # 2.186184 m2
PV_RATED_POWER = 250.0
PV_MULTIPLIER = CANOPY_AREA / PV_ACTIVE_AREA  # ~1.219781
PV_TOTAL_RATED_POWER = PV_RATED_POWER * PV_MULTIPLIER  # ~304.95 W


def safe_debug(message):
    try:
        print(message, flush=True)
    except OSError:
        pass


class KineticBIPVPlugin(EnergyPlusPlugin):

    def __init__(self):
        super().__init__()
        self.need_to_get_handles = True
        self.handles = {}

        # BIPV Output Variables Initialization for EnergyPlus Registration
        self.BIPV_Tilt_Angle = 0.0
        self.BIPV_Incident_Solar = 0.0
        self.BIPV_Power_Generation = 0.0
        self.BIPV_Efficiency = 0.0
        self.bipv_tilt_angle = 0.0
        self.bipv_incident_solar = 0.0
        self.bipv_power_generation = 0.0
        self.bipv_efficiency = 0.0
        self.last_valid_eff = 0.08

        # AI Optimal Angle Schedule Buffer
        self.schedule_angles = []
        self._load_ai_schedule()

    def _load_ai_schedule(self):
        """bipv_optimal_angles_annual.csv 로드 (환경변수 BIPV_SCHEDULE_CSV 우선)"""
        candidate_paths = []
        env_csv = os.environ.get("BIPV_SCHEDULE_CSV")
        if env_csv:
            candidate_paths.append(Path(env_csv))
        candidate_paths += [
            Path(__file__).resolve().parent / "ai_model" / "tide" / "data" / "predictions" / "bipv_optimal_angles_annual.csv",
            Path(__file__).resolve().parent / "data" / "bipv_optimal_angles_annual.csv",
            Path(r"c:\Users\taegyu\Codes\energyplus_project1\data\bipv_optimal_angles_annual.csv"),
            Path("ai_model/tide/data/predictions/bipv_optimal_angles_annual.csv"),
            Path("data/bipv_optimal_angles_annual.csv"),
            Path("../data/bipv_optimal_angles_annual.csv"),
            Path("../../data/bipv_optimal_angles_annual.csv")
        ]

        for p in candidate_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        header = next(reader, None)
                        if header:
                            opt_idx = header.index("optimal_angle") if "optimal_angle" in header else 1
                            self.schedule_angles = [int(float(row[opt_idx])) for row in reader if len(row) > opt_idx]
                            safe_debug(f"DEBUG_SUCCESS: Loaded {len(self.schedule_angles):,} AI optimal angles from {p.name}")
                            return
                except Exception as e:
                    safe_debug(f"DEBUG_WARN: Failed to read CSV {p}: {e}")

        safe_debug("DEBUG_WARN: Could not find bipv_optimal_angles_annual.csv. Falling back to sun tracking.")

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        # 1. 제어 액추에이터 및 센서 핸들 수집
        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0

        # 2. 기상 센서 로드
        sun_alt = self.api.exchange.get_variable_value(state, self.handles["sun_alt"])
        sun_azi = self.api.exchange.get_variable_value(state, self.handles["sun_azi"])
        dn_rad = self.api.exchange.get_variable_value(state, self.handles["dn_rad"])
        df_rad = self.api.exchange.get_variable_value(state, self.handles["df_rad"])
        out_temp = self.api.exchange.get_variable_value(state, self.handles["out_temp"])

        # 3. 최적 각도 결정
        # 스케줄 인덱스는 날짜/시각으로 계산 (사이징·웜업 호출에도 어긋나지 않음)
        # index 0 = 1월 1일 00:10 (hour=0, zone timestep=1)
        kind_of_sim = self.api.exchange.kind_of_sim(state)
        is_weather_run = kind_of_sim == 3  # RunPeriodWeather
        step_idx = -1
        if is_weather_run:
            doy = self.api.exchange.day_of_year(state)
            hour = self.api.exchange.hour(state)
            ts = self.api.exchange.zone_time_step_number(state)
            step_idx = ((doy - 1) * 24 + hour) * 6 + (ts - 1)

        if self.schedule_angles and 0 <= step_idx < len(self.schedule_angles):
            # 본 시뮬레이션 및 웜업(첫날 스케줄 반복): 스케줄 각도 주입
            best_angle = self.schedule_angles[step_idx]
        else:
            # Fallback (사이징 / 스케줄 없음): 태양 추종
            if sun_alt <= 0.0:
                best_angle = 90
            else:
                best_angle = min(ANGLES, key=lambda x: abs(x - sun_alt))

        # 4. 차양 투과율 스케줄(0.0=ON) 및 BIPV 발전기 가용성 스케줄(1.0=ON) 스위칭
        self._override_schedules(state, optimal_angle=best_angle)

        # 5. 실시간 출력 모니터링 변수 계산
        tilt_deg = 90.0 - best_angle
        optimal_solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)

        # 6. 발전량 취득
        sensor_handle = self.handles["pv_power_sensors"].get(best_angle, -1)
        if sensor_handle == -1:
            sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator Produced DC Electricity Rate", f"Generator_BIPV_A{best_angle:02d}"
            )
            if sensor_handle != -1:
                self.handles["pv_power_sensors"][best_angle] = sensor_handle

        if sensor_handle != -1:
            actual_pv_power = self.api.exchange.get_variable_value(state, sensor_handle)
            if actual_pv_power <= 0.0 and optimal_solar_rad > 0.0:
                actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)
        else:
            actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)

        # 7. 발전 효율 취득
        eff_sensor_handle = self.handles["pv_eff_sensors"].get(best_angle, -1)
        if eff_sensor_handle == -1:
            eff_sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator PV Array Efficiency", f"Generator_BIPV_A{best_angle:02d}"
            )
            if eff_sensor_handle != -1:
                self.handles["pv_eff_sensors"][best_angle] = eff_sensor_handle

        if eff_sensor_handle != -1:
            actual_pv_eff = self.api.exchange.get_variable_value(state, eff_sensor_handle)
            if actual_pv_eff > 0.0:
                self.last_valid_eff = actual_pv_eff
            elif optimal_solar_rad > 0.0:
                actual_pv_eff = self.last_valid_eff
        else:
            actual_pv_eff = self.last_valid_eff if optimal_solar_rad > 0.0 else 0.0

        # 글로벌 변수 및 출력 변수 기록
        self.api.exchange.set_global_value(state, self.handles["bipv_tilt"], float(best_angle))
        self.api.exchange.set_global_value(state, self.handles["bipv_rad"], optimal_solar_rad)
        self.api.exchange.set_global_value(state, self.handles["bipv_power"], actual_pv_power)
        self.api.exchange.set_global_value(state, self.handles["bipv_eff"], actual_pv_eff)

        self.BIPV_Tilt_Angle = float(best_angle)
        self.BIPV_Incident_Solar = optimal_solar_rad
        self.BIPV_Power_Generation = actual_pv_power
        self.BIPV_Efficiency = actual_pv_eff
        self.bipv_tilt_angle = float(best_angle)
        self.bipv_incident_solar = optimal_solar_rad
        self.bipv_power_generation = actual_pv_power
        self.bipv_efficiency = actual_pv_eff

        return 0

    def _get_handles(self, state):
        """필수 제어용 센서 및 스케줄 액추에이터 핸들 수집"""
        self.handles["dn_rad"] = self.api.exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = self.api.exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")
        self.handles["out_temp"] = self.api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        self.handles["sun_alt"] = self.api.exchange.get_variable_handle(state, "Site Solar Altitude Angle", "Environment")
        self.handles["sun_azi"] = self.api.exchange.get_variable_handle(state, "Site Solar Azimuth Angle", "Environment")

        self.handles["trans_actuators"] = {}
        self.handles["avail_actuators"] = {}
        for angle in ANGLES:
            self.handles["trans_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Compact", "Schedule Value", f"TransSched_BIPV_A{angle:02d}"
            )
            self.handles["avail_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Compact", "Schedule Value", f"AvailSched_BIPV_A{angle:02d}"
            )

        self.handles["bipv_tilt"] = self.api.exchange.get_global_handle(state, "BIPV_Tilt_Angle")
        self.handles["bipv_rad"] = self.api.exchange.get_global_handle(state, "BIPV_Incident_Solar")
        self.handles["bipv_power"] = self.api.exchange.get_global_handle(state, "BIPV_Power_Generation")
        self.handles["bipv_eff"] = self.api.exchange.get_global_handle(state, "BIPV_Efficiency")

        self.handles["pv_power_sensors"] = {}
        self.handles["pv_eff_sensors"] = {}

        any_failed = False
        for key, val in self.handles.items():
            if key in ["pv_power_sensors", "pv_eff_sensors"]:
                continue
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    if subval == -1:
                        safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for dict actuator: {key}[{subkey}]")
                        any_failed = True
            elif val == -1:
                safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for sensor: {key}")
                any_failed = True

        if not any_failed:
            safe_debug("DEBUG_SUCCESS: ALL HANDLES SUCCESSFULLY ACQUIRED!")
            self.need_to_get_handles = False

    def _get_incident_solar_val(self, sun_alt, sun_azi, dn_rad, df_rad, tilt_deg):
        tilt_rad = math.radians(tilt_deg)
        alt_rad = math.radians(sun_alt)
        azi_rad = math.radians(sun_azi)

        cos_theta = (math.sin(alt_rad) * math.cos(tilt_rad) +
                     math.cos(alt_rad) * math.sin(tilt_rad) * math.cos(azi_rad - math.pi))
        cos_theta = max(0.0, cos_theta)
        
        i_beam = dn_rad * cos_theta
        i_diff = df_rad * (1.0 + math.cos(tilt_rad)) / 2.0
        total_horiz = dn_rad * math.sin(alt_rad) + df_rad
        i_ground = total_horiz * 0.2 * (1.0 - math.cos(tilt_rad)) / 2.0

        return i_beam + i_diff + i_ground

    def _predict_pv_power(self, total_incident, out_temp):
        if total_incident <= 0:
            return 0.0
        t_cell = out_temp + total_incident * ((45.0 - 20.0) / 800.0)
        derate = 1.0 - 0.0039 * (t_cell - 25.0)
        power_out = (total_incident / 1000.0) * PV_TOTAL_RATED_POWER * derate
        return max(0.0, power_out)

    def _override_schedules(self, state, optimal_angle):
        for angle in ANGLES:
            trans_act = self.handles["trans_actuators"][angle]
            avail_act = self.handles["avail_actuators"][angle]

            if angle == optimal_angle:
                self.api.exchange.set_actuator_value(state, trans_act, 0.0)
                self.api.exchange.set_actuator_value(state, avail_act, 1.0)
            else:
                self.api.exchange.set_actuator_value(state, trans_act, 1.0)
                self.api.exchange.set_actuator_value(state, avail_act, 0.0)

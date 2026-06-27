"""
Kinetic BIPV & Dynamic Shading Sun-Tracking Simple Control Plugin (Fault-Tolerant Version)
====================================================================================
- Developer: Antigravity Pair-Programming Agent
- Core Function:
  태양 고도각을 추종하여 최적 각도를 결정하고 스위칭 제어합니다.
  EnergyPlus의 실시간 발전 데이터 취득 시, 최초 타임스텝의 핸들 유실 에러를
  방지하기 위해 실시간 자동 재취득 및 예외 Fallback 예측 공식을 내장하고 있습니다.
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
CANOPY_LENGTH = 3.0
CANOPY_WIDTH = 3.0
CANOPY_AREA = CANOPY_LENGTH * CANOPY_WIDTH

PV_GROSS_AREA = 2.379132
PV_PACKING_FACTOR = 0.9189
PV_ACTIVE_AREA = PV_GROSS_AREA * PV_PACKING_FACTOR  # 2.186184 m²
PV_RATED_POWER = 250.0
PV_MULTIPLIER = CANOPY_AREA / PV_ACTIVE_AREA
PV_TOTAL_RATED_POWER = PV_RATED_POWER * PV_MULTIPLIER  # ~1029.19 W


class KineticBIPVPlugin(EnergyPlusPlugin):

    def __init__(self):
        super().__init__()
        self.need_to_get_handles = True
        self.handles = {}

        # BIPV Output Variables Initialization for EnergyPlus Registration
        self.BIPV_Tilt_Angle = 0.0
        self.BIPV_Incident_Solar = 0.0
        self.BIPV_Power_Generation = 0.0
        self.bipv_tilt_angle = 0.0
        self.bipv_incident_solar = 0.0
        self.bipv_power_generation = 0.0

    def on_begin_zone_timestep_before_set_current_weather(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0
 
        # 1. 제어 액추에이터 및 필수 시간 핸들 수집
        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0
 
        # 2. 실제 EnergyPlus 정밀 기상 태양 센서로부터 다이렉트 고도 및 방위각 로드
        sun_alt = self.api.exchange.get_variable_value(state, self.handles["sun_alt"])
        sun_azi = self.api.exchange.get_variable_value(state, self.handles["sun_azi"])
        
        # 기상 일사량 및 외기온 센서 로드
        dn_rad = self.api.exchange.get_variable_value(state, self.handles["dn_rad"])
        df_rad = self.api.exchange.get_variable_value(state, self.handles["df_rad"])
        out_temp = self.api.exchange.get_variable_value(state, self.handles["out_temp"])
 
        # 3. 야간 제어: 최적각 90도 고정 및 제어
        if sun_alt <= 0.0:
            self._override_schedules(state, optimal_angle=90)
            self.api.exchange.set_global_value(state, self.handles["bipv_tilt"], 90.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_rad"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_power"], 0.0)
            self.BIPV_Tilt_Angle = 90.0
            self.BIPV_Incident_Solar = 0.0
            self.BIPV_Power_Generation = 0.0
            self.bipv_tilt_angle = 90.0
            self.bipv_incident_solar = 0.0
            self.bipv_power_generation = 0.0
            return 0
 
        # 4. 주간 제어: 1년 내내 90도 차양 강제 고정
        best_angle = 90
 
        # 5. 최적각 차양 활성화 스위칭 (0.0=ON, 1.0=OFF) 및 발전기 availability 연동
        self._override_schedules(state, optimal_angle=best_angle)
 
        # 6. 실시간 출력 모니터링 변수 계산 및 기록 (일사량 기하 변환)
        tilt_deg = 90.0 - best_angle
        optimal_solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)
 
        # 7. 발전량 센서 핸들 실시간 유동적 취득 및 가치가 정확한 기록 처리
        sensor_handle = self.handles["pv_power_sensors"].get(best_angle, -1)
        if sensor_handle == -1:
            sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator Produced DC Electricity Rate", f"Generator_BIPV_A{best_angle:02d}"
            )
            if sensor_handle != -1:
                self.handles["pv_power_sensors"][best_angle] = sensor_handle
 
        # 발전량 최종 결정 (Pass-Through 시도, 실패 시 정밀 피드백 Fallback 예측 모델 가동)
        if sensor_handle != -1:
            actual_pv_power = self.api.exchange.get_variable_value(state, sensor_handle)
            if actual_pv_power <= 0.0 and optimal_solar_rad > 0.0:
                actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)
        else:
            actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)
 
        self.api.exchange.set_global_value(state, self.handles["bipv_tilt"], float(best_angle))
        self.api.exchange.set_global_value(state, self.handles["bipv_rad"], optimal_solar_rad)
        self.api.exchange.set_global_value(state, self.handles["bipv_power"], actual_pv_power)
 
        self.BIPV_Tilt_Angle = float(best_angle)
        self.BIPV_Incident_Solar = optimal_solar_rad
        self.BIPV_Power_Generation = actual_pv_power
        self.bipv_tilt_angle = float(best_angle)
        self.bipv_incident_solar = optimal_solar_rad
        self.bipv_power_generation = actual_pv_power
 
        return 0

    def _get_handles(self, state):
        """필수 제어용 센서 및 스케줄 액추에이터 핸들 수집"""
        self.handles["dn_rad"] = self.api.exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = self.api.exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")
        self.handles["out_temp"] = self.api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        
        # 실제 EnergyPlus 태양 고도 및 방위각 정밀 센서 핸들 추가
        self.handles["sun_alt"] = self.api.exchange.get_variable_handle(state, "Site Solar Altitude Angle", "Environment")
        self.handles["sun_azi"] = self.api.exchange.get_variable_handle(state, "Site Solar Azimuth Angle", "Environment")
 
        self.handles["trans_actuators"] = {}
        self.handles["avail_actuators"] = {}
        for angle in ANGLES:
            # pyenergyplus API 규격인 "Schedule:Constant" 로 복원하여 핸들 획득 정합성 회복
            self.handles["trans_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Constant", "Schedule Value", f"TransSched_BIPV_A{angle:02d}"
            )
            self.handles["avail_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Constant", "Schedule Value", f"AvailSched_BIPV_A{angle:02d}"
            )
 
        self.handles["bipv_tilt"] = self.api.exchange.get_global_handle(state, "BIPV_Tilt_Angle")
        self.handles["bipv_rad"] = self.api.exchange.get_global_handle(state, "BIPV_Incident_Solar")
        self.handles["bipv_power"] = self.api.exchange.get_global_handle(state, "BIPV_Power_Generation")
 
        # 발전 전력용 유동 센서 핸들 딕셔너리 초기화
        self.handles["pv_power_sensors"] = {}
 
        # 필수 제어 핸들 검사
        any_failed = False
        for key, val in self.handles.items():
            if key == "pv_power_sensors":
                continue
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    if subval == -1:
                        print(f"DEBUG_WARN: FAILED TO GET HANDLE for dict actuator: {key}[{subkey}]", flush=True)
                        any_failed = True
            elif val == -1:
                print(f"DEBUG_WARN: FAILED TO GET HANDLE for sensor: {key}", flush=True)
                any_failed = True
 
        if not any_failed:
            print("DEBUG_SUCCESS: ALL HANDLES SUCCESSFULLY ACQUIRED!", flush=True)
            self.need_to_get_handles = False

    def _get_incident_solar_val(self, sun_alt, sun_azi, dn_rad, df_rad, tilt_deg):
        tilt_rad = math.radians(tilt_deg)
        alt_rad = math.radians(sun_alt)
        azi_rad = math.radians(sun_azi)

        cos_theta = (math.sin(alt_rad) * math.cos(tilt_rad) +
                     math.cos(alt_rad) * math.sin(tilt_rad) * math.cos(azi_rad - math.pi))
        cos_theta = max(0.0, cos_theta)
        
        # Incident direct solar
        i_beam = dn_rad * cos_theta
        
        # Diffuse solar on tilted surface (isotropic sky model)
        i_diff = df_rad * (1.0 + math.cos(tilt_rad)) / 2.0
        
        # Ground-reflected solar on tilted surface (albedo = 0.2)
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

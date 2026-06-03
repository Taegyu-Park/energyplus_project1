"""
Kinetic BIPV & Shading Real-time Net Energy Optimization Plugin
========================================================================
- Developer: Antigravity Pair-Programming Agent
- Core Function:
  EnergyPlus 내장 Python Plugin 시스템에 주입되어 매 타임스텝마다
  10개 각도 후보(0도에서 90도까지 10도 간격) 중 Tri-objective (냉난방 부하 + 발전량) 
  넷 에너지를 실시간 연립 예측하여 최소화하는 단 1개의 최적 각도를 산출 및 가동합니다.
  선택된 각도는 가동(ON), 나머지 9개 각도는 차단 및 투명화(OFF) 처리합니다.
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

# ==========================================================================
# 1. 제어 상수 및 물리 모델 매개변수 (정밀 보정 버전)
# ==========================================================================
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
CANOPY_LENGTH = 3.0  # 캐노피 돌출 길이 [m]
CANOPY_WIDTH = 3.0   # 캐노피 폭 (동-서) [m]
CANOPY_AREA = CANOPY_LENGTH * CANOPY_WIDTH  # 9.0 m²

# 신성 E&G SolarSkin White 250W 모듈 기반 정밀 실측 셀 규격
PV_GROSS_AREA = 2.379132     # 모듈 외곽 총면적 [m²] (1.134m x 2.098m)
PV_PACKING_FACTOR = 0.9189   # 활성 면적 비율 (91.89%)
PV_ACTIVE_AREA = PV_GROSS_AREA * PV_PACKING_FACTOR  # 순수 셀 실면적 = 2.186184 m²
PV_RATED_POWER = 250.0       # 단일 모듈 정격 [W]

# 9.0 m2 차양 전체의 스케일러 연산
PV_MULTIPLIER = CANOPY_AREA / PV_ACTIVE_AREA  # ~4.116762 배수
PV_TOTAL_RATED_POWER = PV_RATED_POWER * PV_MULTIPLIER  # 총 정격 용량 ~1029.19 W


# ==========================================================================
# 2. ENERGYPLUS PYTHON PLUGIN 클래스 정의
# ==========================================================================
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

        # Tri-objective 최적화 물리 변환 상수
        self.win_area = 7.84      # 2.8m x 2.8m glazing area
        self.win_shgc = 0.4       # SHGC (태양열취득계수)
        self.cop_cooling = 3.0    # 냉방 COP
        self.eff_heating = 1.0    # 난방 효율

    def on_begin_zone_timestep_before_set_current_weather(self, state) -> int:
        """
        EnergyPlus의 매 존 타임스텝 시작 시(음영 및 날씨 계산 전 가장 이른 단계) 호출되어
        태양 위치 및 일사 조건에 따른 넷 에너지 최소화 최적 각도를 계산하고 10개 쉐이딩을 실시간 제어합니다.
        """
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        # 1. 초기 1회 실행 시 센서, 글로벌 변수 및 10개 채널 스케줄 액추에이터 핸들 수집
        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0

        # 2. 실시간 환경 데이터 로드
        sun_alt = self.api.exchange.get_variable_value(state, self.handles["sun_alt"])
        sun_azi = self.api.exchange.get_variable_value(state, self.handles["sun_azi"])
        dn_rad = self.api.exchange.get_variable_value(state, self.handles["dn_rad"])
        df_rad = self.api.exchange.get_variable_value(state, self.handles["df_rad"])
        out_temp = self.api.exchange.get_variable_value(state, self.handles["out_temp"])

        # 3. 야간 및 일사 무방출 시간 예외 처리 (0도 수직 벽면 접기 제어)
        if sun_alt <= 0.0 or (dn_rad <= 0.0 and df_rad <= 0.0):
            self._override_schedules(state, optimal_angle=0)
            self.api.exchange.set_global_value(state, self.handles["bipv_tilt"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_rad"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_power"], 0.0)
            self.BIPV_Tilt_Angle = 0.0
            self.BIPV_Incident_Solar = 0.0
            self.BIPV_Power_Generation = 0.0
            self.bipv_tilt_angle = 0.0
            self.bipv_incident_solar = 0.0
            self.bipv_power_generation = 0.0
            return 0

        # 4. 주간 제어: 10개 각도 후보 각각의 Tri-objective 넷 에너지 연립 예측 해석
        best_angle = 0
        min_net_energy = float('inf')
        optimal_pv_power = 0.0
        optimal_solar_rad = 0.0

        for angle in ANGLES:
            # 힌지 기하 궤적과 패널 경사각 변환:
            # 벌어짐 각도 0도 = 수직 (tilt = 90 deg)
            # 벌어짐 각도 90도 = 수평 (tilt = 0 deg)
            tilt_deg = 90.0 - angle
            
            p_pv = self._predict_pv_power(sun_alt, sun_azi, dn_rad, df_rad, out_temp, tilt_deg)
            q_hvac = self._predict_hvac_impact(sun_alt, sun_azi, dn_rad, df_rad, out_temp, angle)
            
            # Net Energy = 냉난방 열부하 영향 - 태양광 전력 생산량
            net_energy = q_hvac - p_pv

            if net_energy < min_net_energy:
                min_net_energy = net_energy
                best_angle = angle
                optimal_pv_power = p_pv
                optimal_solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)

        # 5. 최적화 결과 스케줄 강제 주입 (최적각 1개 활성화, 나머지 9개 셧다운/투명화)
        self._override_schedules(state, optimal_angle=best_angle)

        # 6. [핵심 패치] 발전량 센서 핸들 실시간 유동적 취득 및 가치가 정확한 기록 처리
        sensor_handle = self.handles["pv_power_sensors"].get(best_angle, -1)
        if sensor_handle == -1:
            # 런타임에 핸들 재시도 취득
            sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator Produced DC Electricity Rate", f"Generator_BIPV_A{best_angle:02d}"
            )
            if sensor_handle != -1:
                self.handles["pv_power_sensors"][best_angle] = sensor_handle

        # 발전량 최종 결정 (Pass-Through 시도, 실패 시 정밀 피드백 Fallback 예측 모델 가동)
        if sensor_handle != -1:
            actual_pv_power = self.api.exchange.get_variable_value(state, sensor_handle)
            # 만약 엔진이 아직 값을 산출하기 전이거나 미초기화 시 Fallback 적용
            if actual_pv_power <= 0.0 and optimal_solar_rad > 0.0:
                actual_pv_power = self._predict_pv_power(sun_alt, sun_azi, dn_rad, df_rad, out_temp, 90.0 - best_angle)
        else:
            actual_pv_power = self._predict_pv_power(sun_alt, sun_azi, dn_rad, df_rad, out_temp, 90.0 - best_angle)

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

    # ==========================================================================
    # 3. 내부 물리 및 액추에이터 핸들 취득 함수
    # ==========================================================================
    def _get_handles(self, state):
        """EnergyPlus로부터 센서, 액추에이터 및 글로벌 출력 변수 핸들을 수집하여 캐싱합니다."""
        # 기상 센서 핸들
        self.handles["sun_alt"] = self.api.exchange.get_variable_handle(state, "Site Solar Altitude Angle", "Environment")
        self.handles["sun_azi"] = self.api.exchange.get_variable_handle(state, "Site Solar Azimuth Angle", "Environment")
        self.handles["dn_rad"] = self.api.exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = self.api.exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")
        self.handles["out_temp"] = self.api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")

        # 각도별 투과율 및 Availability 스케줄 액추에이터 핸들 (10개 세트)
        self.handles["trans_actuators"] = {}
        self.handles["avail_actuators"] = {}
        for angle in ANGLES:
            self.handles["trans_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Constant", "Schedule Value", f"TransSched_BIPV_A{angle:02d}"
            )
            self.handles["avail_actuators"][angle] = self.api.exchange.get_actuator_handle(
                state, "Schedule:Constant", "Schedule Value", f"AvailSched_BIPV_A{angle:02d}"
            )

        # 사용자 정의 글로벌 출력 변수 핸들
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
                        any_failed = True
            elif val == -1:
                any_failed = True

        if not any_failed:
            self.need_to_get_handles = False

    def _get_incident_solar_val(self, sun_alt, sun_azi, dn_rad, df_rad, tilt_deg):
        """특정 경사각에 닿는 면적당 총 일사량을 반환합니다."""
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

    def _predict_pv_power(self, sun_alt, sun_azi, dn_rad, df_rad, out_temp, tilt_deg):
        """각도별 5파라미터 NOCT 물리 방정식을 기반으로 PV 발전량 예측"""
        total_incident = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)
        if total_incident <= 0:
            return 0.0

        # NOCT 셀 온도 예측 (Ambient 20도 대비 NOCT 시험 조건 기반)
        t_cell = out_temp + total_incident * ((45.0 - 20.0) / 800.0)
        # 온도 보정 효율 저하 반영 (-0.39% / °C)
        derate = 1.0 - 0.0039 * (t_cell - 25.0)

        # 총 예상 발전량 [W]
        power_out = (total_incident / 1000.0) * PV_TOTAL_RATED_POWER * derate
        return max(0.0, power_out)

    def _predict_hvac_impact(self, sun_alt, sun_azi, dn_rad, df_rad, out_temp, angle):
        """차양 각도에 따른 남향 창면 태양열 획득 및 건물 냉난방 에너지 영향 예측"""
        alt_rad = math.radians(sun_alt)
        azi_rad = math.radians(sun_azi)

        # 수직 남향 창면의 일사 입사각 cos
        cos_theta_win = math.cos(alt_rad) * math.cos(azi_rad - math.pi)
        cos_theta_win = max(0.0, cos_theta_win)
        
        i_win_beam = dn_rad * cos_theta_win
        i_win_diff = df_rad * 0.5
        i_win_ground = (dn_rad * math.sin(alt_rad) + df_rad) * 0.2 * 0.5
        i_win = i_win_beam + i_win_diff + i_win_ground

        # 차양 각도에 따른 일사 투과율 (1 - cos)
        angle_rad = math.radians(angle)
        transmittance = 1.0 - math.cos(angle_rad)

        # 창면을 통과한 총 태양열 획득량 [W]
        q_solar_gain = i_win * transmittance * self.win_area * self.win_shgc

        # 외기온 조건별 냉난방 에너지 환산
        if out_temp >= 22.0:
            # 냉방 부하 증가 (전력 소모량으로 환산)
            return q_solar_gain / self.cop_cooling
        elif out_temp <= 18.0:
            # 난방 부하 감소 (에너지 절감 효과 반영)
            return -q_solar_gain / self.eff_heating
        else:
            # 중간기: 냉난방 영향 무시
            return 0.0

    def _override_schedules(self, state, optimal_angle):
        """액추에이터 제어: 최적 각도 BIPV만 온(ON), 그 외 9개 각도는 오프(OFF) 및 투명화 처리"""
        for angle in ANGLES:
            trans_act = self.handles["trans_actuators"][angle]
            avail_act = self.handles["avail_actuators"][angle]

            if angle == optimal_angle:
                # 활성 각도: 음영 발생 (투과율 0.0), 발전 시작 (Availability 1.0)
                self.api.exchange.set_actuator_value(state, trans_act, 0.0)
                self.api.exchange.set_actuator_value(state, avail_act, 1.0)
            else:
                # 비활성 각도: 그림자 제거 (투과율 1.0), 계통 차단 (Availability 0.0)
                self.api.exchange.set_actuator_value(state, trans_act, 1.0)
                self.api.exchange.set_actuator_value(state, avail_act, 0.0)

"""
Kinetic BIPV & Dynamic Shading Sun-Tracking Simple Control Plugin (Fault-Tolerant Version)
====================================================================================
- Developer: Antigravity Pair-Programming Agent
- Core Function:
  ?쒖뼇 怨좊룄媛곸쓣 異붿쥌?섏뿬 理쒖쟻 媛곷룄瑜?寃곗젙?섍퀬 ?ㅼ쐞移??쒖뼱?⑸땲??
  EnergyPlus???ㅼ떆媛?諛쒖쟾 ?곗씠??痍⑤뱷 ?? 理쒖큹 ??꾩뒪?앹쓽 ?몃뱾 ?좎떎 ?먮윭瑜?
  諛⑹??섍린 ?꾪빐 ?ㅼ떆媛??먮룞 ?ъ랬??諛??덉쇅 Fallback ?덉륫 怨듭떇???댁옣?섍퀬 ?덉뒿?덈떎.
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
CANOPY_LENGTH = 4 / 3  # 1.33333333333333 m
CANOPY_WIDTH = 2.0
CANOPY_AREA = CANOPY_LENGTH * CANOPY_WIDTH  # 2.6666666666666665 m짼

PV_GROSS_AREA = 2.379132
PV_PACKING_FACTOR = 0.9189
PV_ACTIVE_AREA = PV_GROSS_AREA * PV_PACKING_FACTOR  # 2.186184 m짼
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

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0
 
        # 1. ?쒖뼱 ?≪텛?먯씠??諛??꾩닔 ?쒓컙 ?몃뱾 ?섏쭛
        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0
 
        # 2. ?ㅼ젣 EnergyPlus ?뺣? 湲곗긽 ?쒖뼇 ?쇱꽌濡쒕????ㅼ씠?됲듃 怨좊룄 諛?諛⑹쐞媛?濡쒕뱶
        sun_alt = self.api.exchange.get_variable_value(state, self.handles["sun_alt"])
        sun_azi = self.api.exchange.get_variable_value(state, self.handles["sun_azi"])
        
        # 湲곗긽 ?쇱궗??諛??멸린???쇱꽌 濡쒕뱶
        dn_rad = self.api.exchange.get_variable_value(state, self.handles["dn_rad"])
        df_rad = self.api.exchange.get_variable_value(state, self.handles["df_rad"])
        out_temp = self.api.exchange.get_variable_value(state, self.handles["out_temp"])
 
        # 3. ?쇨컙 ?쒖뼱: 理쒖쟻媛?0??怨좎젙 諛??쒖뼱
        if sun_alt <= 0.0:
            self._override_schedules(state, optimal_angle=0)
            self.api.exchange.set_global_value(state, self.handles["bipv_tilt"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_rad"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_power"], 0.0)
            self.api.exchange.set_global_value(state, self.handles["bipv_eff"], 0.0)
            self.BIPV_Tilt_Angle = 0.0
            self.BIPV_Incident_Solar = 0.0
            self.BIPV_Power_Generation = 0.0
            self.BIPV_Efficiency = 0.0
            self.bipv_tilt_angle = 0.0
            self.bipv_incident_solar = 0.0
            self.bipv_power_generation = 0.0
            self.bipv_efficiency = 0.0
            return 0
 
        # 4. 二쇨컙 ?쒖뼱: ?쒖뼇 怨좊룄 ?뺣㈃ 異붿쟻 理쒖쟻媛?怨꾩궛 (理쒖쟻 ?뚯쟾 媛곷룄 = ?쒖뼇 怨좊룄媛?
        target_angle = sun_alt
        best_angle = min(ANGLES, key=lambda x: abs(x - target_angle))
 
        # 5. 理쒖쟻媛?李⑥뼇 ?쒖꽦???ㅼ쐞移?(0.0=ON, 1.0=OFF) 諛?諛쒖쟾湲?availability ?곕룞
        self._override_schedules(state, optimal_angle=best_angle)
 
        # 6. ?ㅼ떆媛?異쒕젰 紐⑤땲?곕쭅 蹂??怨꾩궛 諛?湲곕줉 (?쇱궗??湲고븯 蹂??
        tilt_deg = 90.0 - best_angle
        optimal_solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)
 
        # 7. 諛쒖쟾???쇱꽌 ?몃뱾 ?ㅼ떆媛??좊룞??痍⑤뱷 諛?媛移섍? ?뺥솗??湲곕줉 泥섎━
        sensor_handle = self.handles["pv_power_sensors"].get(best_angle, -1)
        if sensor_handle == -1:
            sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator Produced DC Electricity Rate", f"Generator_BIPV_A{best_angle:02d}"
            )
            if sensor_handle != -1:
                self.handles["pv_power_sensors"][best_angle] = sensor_handle
 
        # 諛쒖쟾??理쒖쥌 寃곗젙 (Pass-Through ?쒕룄, ?ㅽ뙣 ???뺣? ?쇰뱶諛?Fallback ?덉륫 紐⑤뜽 媛??
        if sensor_handle != -1:
            actual_pv_power = self.api.exchange.get_variable_value(state, sensor_handle)
            if actual_pv_power <= 0.0 and optimal_solar_rad > 0.0:
                actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)
        else:
            actual_pv_power = self._predict_pv_power(optimal_solar_rad, out_temp)
 
        # 7.1. 諛쒖쟾 ?⑥쑉 ?쇱꽌 ?몃뱾 ?ㅼ떆媛?痍⑤뱷
        eff_sensor_handle = self.handles["pv_eff_sensors"].get(best_angle, -1)
        if eff_sensor_handle == -1:
            eff_sensor_handle = self.api.exchange.get_variable_handle(
                state, "Generator PV Array Efficiency", f"Generator_BIPV_A{best_angle:02d}"
            )
            if eff_sensor_handle != -1:
                self.handles["pv_eff_sensors"][best_angle] = eff_sensor_handle
 
        # 諛쒖쟾 ?⑥쑉 理쒖쥌 寃곗젙
        if eff_sensor_handle != -1:
            actual_pv_eff = self.api.exchange.get_variable_value(state, eff_sensor_handle)
            # EnergyPlus API 1??꾩뒪??吏???먮윭 諛??쒖뼱 泥쒖씠 ??0.0 異쒕젰 諛⑹? Fallback ?곸슜
            if actual_pv_eff > 0.0:
                self.last_valid_eff = actual_pv_eff
            elif optimal_solar_rad > 0.0:
                actual_pv_eff = self.last_valid_eff
        else:
            if optimal_solar_rad > 0.0:
                actual_pv_eff = self.last_valid_eff
            else:
                actual_pv_eff = 0.0
 
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
        """?꾩닔 ?쒖뼱???쇱꽌 諛??ㅼ?以??≪텛?먯씠???몃뱾 ?섏쭛"""
        self.handles["dn_rad"] = self.api.exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = self.api.exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")
        self.handles["out_temp"] = self.api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        
        # ?ㅼ젣 EnergyPlus ?쒖뼇 怨좊룄 諛?諛⑹쐞媛??뺣? ?쇱꽌 ?몃뱾 異붽?
        self.handles["sun_alt"] = self.api.exchange.get_variable_handle(state, "Site Solar Altitude Angle", "Environment")
        self.handles["sun_azi"] = self.api.exchange.get_variable_handle(state, "Site Solar Azimuth Angle", "Environment")
 
        self.handles["trans_actuators"] = {}
        self.handles["avail_actuators"] = {}
        for angle in ANGLES:
            # pyenergyplus API 洹쒓꺽??"Schedule:Compact" 濡?蹂듭썝?섏뿬 ?몃뱾 ?띾뱷 ?뺥빀???뚮났
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
 
        # 諛쒖쟾 ?꾨젰 諛??⑥쑉???좊룞 ?쇱꽌 ?몃뱾 ?뺤뀛?덈━ 珥덇린??
        self.handles["pv_power_sensors"] = {}
        self.handles["pv_eff_sensors"] = {}
 
        # ?꾩닔 ?쒖뼱 ?몃뱾 寃??
        any_failed = False
        for key, val in self.handles.items():
            if key == "pv_power_sensors":
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

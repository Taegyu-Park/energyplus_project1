"""
Integrated Real-Scale Kinetic BIPV & DSF Outer Skin Control with 4-Facade Cavity Thermal Heat Gain
===================================================================================================
- Target: Real-Scale Office Building (32m x 18m x 8m, 10 Zones + 4 DSF Cavity Zones)
- Gwangju IWEC Climate (35.13°N, 126.92°E)
- Features:
  1. Coupled Kinetic BIPV Sun-Tracking (0° to 90°) & STPV 20% Transmittance Preservation on South Facade
  2. 2-Damper System Decoupled Control (Top/Bottom Stack & Outer Skin Louver Gap)
  3. 4-Facade BIPV Waste Heat Injection to DSF Cavities (BIPV/T Thermal Modeling):
     - South Facade: 80 modules (213.33 m2), 0° closed in winter (45% inward heat gain), tilted in summer (0% inward)
     - East Facade:  50 modules (133.33 m2), 0° vertical fixed outer skin (45% inward heat gain to Zone_Cavity_East)
     - North Facade: 80 modules (213.33 m2), 0° vertical fixed outer skin (45% inward heat gain to Zone_Cavity_North)
     - West Facade:  50 modules (133.33 m2), 0° vertical fixed outer skin (45% inward heat gain to Zone_Cavity_West)
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]

# PV & Thermal Parameters
PV_AREAS = {
    "South": 213.333333,  # m2 (80 modules * 2.186184 m2 * 1.219781 scaling)
    "East":  133.333333,  # m2 (50 modules * 2.186184 m2 * 1.219781 scaling)
    "North": 213.333333,  # m2 (80 modules * 2.186184 m2 * 1.219781 scaling)
    "West":  133.333333   # m2 (50 modules * 2.186184 m2 * 1.219781 scaling)
}

SURF_AZIS = {
    "South": math.pi,               # 180 deg
    "East":  math.pi / 2.0,         # 90 deg
    "North": 0.0,                   # 0 deg
    "West":  3.0 * math.pi / 2.0    # 270 deg
}

PV_ABSORPTANCE = 0.90          # Solar absorptance of BIPV surface (90%)
PV_BASE_EFFICIENCY = 0.15      # Nominal PV electrical efficiency (15%)
INWARD_HEAT_FRAC_CLOSED = 0.45 # Inward thermal transfer fraction when louvers are fully closed (0 deg)


def safe_debug(message):
    try:
        print(message, flush=True)
    except OSError:
        pass


class DSFKineticBIPVRealscaleThermalPlugin(EnergyPlusPlugin):

    def __init__(self):
        super().__init__()
        self.need_to_get_handles = True
        self.handles = {}

        self.bipv_tilt_angle = 0.0
        self.dsf_topbottom_damper = 0.0
        self.dsf_outerskin_damper = 0.0
        self.operating_mode = 0.0

        # South Facade
        self.bipv_incident_solar = 0.0
        self.bipv_power_generation = 0.0
        self.bipv_efficiency = 0.0
        self.bipv_waste_heat = 0.0
        self.bipv_cavity_heat_gain = 0.0

        # East / North / West Facades
        self.bipv_results = {
            "East":  {"solar": 0.0, "power": 0.0, "waste_heat": 0.0, "cavity_heat": 0.0},
            "North": {"solar": 0.0, "power": 0.0, "waste_heat": 0.0, "cavity_heat": 0.0},
            "West":  {"solar": 0.0, "power": 0.0, "waste_heat": 0.0, "cavity_heat": 0.0},
        }

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0

        exchange = self.api.exchange

        sun_alt = exchange.get_variable_value(state, self.handles["sun_alt"]) if self.handles.get("sun_alt", -1) != -1 else 0.0
        sun_azi = exchange.get_variable_value(state, self.handles["sun_azi"]) if self.handles.get("sun_azi", -1) != -1 else 0.0
        out_temp = exchange.get_variable_value(state, self.handles["out_temp"]) if self.handles.get("out_temp", -1) != -1 else 20.0
        dn_rad = exchange.get_variable_value(state, self.handles["dn_rad"]) if self.handles.get("dn_rad", -1) != -1 else 0.0
        df_rad = exchange.get_variable_value(state, self.handles["df_rad"]) if self.handles.get("df_rad", -1) != -1 else 0.0

        best_bipv_angle, mode, topbottom_damper, outerskin_damper = self._control_coupled_bipv_and_dsf(sun_alt, out_temp, dn_rad)

        # -------------------------------------------------------------
        # 1. SOUTH FACADE BIPV & CAVITY HEAT GAIN
        # -------------------------------------------------------------
        tilt_deg_s = 90.0 - best_bipv_angle
        solar_rad_s = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg_s, SURF_AZIS["South"])

        actual_pv_eff_s = PV_BASE_EFFICIENCY if solar_rad_s > 0.0 else 0.0
        pv_power_s = solar_rad_s * PV_AREAS["South"] * actual_pv_eff_s
        total_absorbed_heat_s = solar_rad_s * PV_AREAS["South"] * PV_ABSORPTANCE
        waste_heat_s = max(0.0, total_absorbed_heat_s - pv_power_s)

        inward_fraction_s = INWARD_HEAT_FRAC_CLOSED if best_bipv_angle == 0 else 0.0
        cavity_thermal_gain_s = waste_heat_s * inward_fraction_s

        # -------------------------------------------------------------
        # 2. EAST / NORTH / WEST FACADES (0° Vertical Fixed Outer Skin)
        # -------------------------------------------------------------
        cavity_thermal_gains = {"South": cavity_thermal_gain_s}

        for orient in ["East", "North", "West"]:
            solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, 90.0, SURF_AZIS[orient])
            actual_eff = PV_BASE_EFFICIENCY if solar_rad > 0.0 else 0.0
            pv_power = solar_rad * PV_AREAS[orient] * actual_eff
            total_absorbed = solar_rad * PV_AREAS[orient] * PV_ABSORPTANCE
            waste_heat = max(0.0, total_absorbed - pv_power)
            cavity_gain = waste_heat * INWARD_HEAT_FRAC_CLOSED

            self.bipv_results[orient] = {
                "solar": solar_rad,
                "power": pv_power,
                "waste_heat": waste_heat,
                "cavity_heat": cavity_gain
            }
            cavity_thermal_gains[orient] = cavity_gain

        # -------------------------------------------------------------
        # 3. OVERRIDE ACTUATOR SCHEDULES
        # -------------------------------------------------------------
        self._override_schedules(
            state,
            optimal_angle=best_bipv_angle,
            tb_damper=topbottom_damper,
            os_damper=outerskin_damper,
            cavity_gains=cavity_thermal_gains
        )

        # -------------------------------------------------------------
        # 4. UPDATE GLOBAL REPORTING VARIABLES
        # -------------------------------------------------------------
        self._update_global_variables(
            state,
            best_bipv_angle,
            topbottom_damper,
            outerskin_damper,
            mode,
            solar_rad_s,
            actual_pv_eff_s,
            pv_power_s,
            waste_heat_s,
            cavity_thermal_gain_s
        )

        return 0

    def _control_coupled_bipv_and_dsf(self, sun_alt: float, out_temp: float, dn_rad: float):
        if sun_alt > 0.0:  # Daytime
            if out_temp >= 15.0:
                mode = 1  # Summer/Warm Day: Solar Altitude Tracking & Open Top/Bottom Dampers
                ideal_tilt = 90.0 - sun_alt
                best_angle = min(ANGLES, key=lambda a: abs(a - ideal_tilt))
                topbottom_damper = 1.0
            else:
                mode = 3  # Winter/Cold Day: 0 deg Vertical Louver & Closed Top/Bottom Dampers
                best_angle = 0
                topbottom_damper = 0.0
        else:  # Nighttime
            if out_temp >= 10.0:
                mode = 2  # Summer/Warm Night: 90 deg Horizontal Louver & Open Top/Bottom Dampers
                best_angle = 90
                topbottom_damper = 1.0
            else:
                mode = 4  # Winter/Cold Night: 0 deg Vertical Louver & Closed Top/Bottom Dampers
                best_angle = 0
                topbottom_damper = 0.0

        # DSF OUTER SKIN LOUVER GAP DAMPER CONTROL
        outerskin_damper = 1.0 if best_angle > 0 else 0.0

        return best_angle, mode, topbottom_damper, outerskin_damper

    def _get_handles(self, state):
        exchange = self.api.exchange
        self.handles["dn_rad"] = exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")
        self.handles["out_temp"] = exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        self.handles["sun_alt"] = exchange.get_variable_handle(state, "Site Solar Altitude Angle", "Environment")
        self.handles["sun_azi"] = exchange.get_variable_handle(state, "Site Solar Azimuth Angle", "Environment")

        self.handles["trans_actuators"] = {}
        self.handles["avail_actuators"] = {}
        for angle in ANGLES:
            self.handles["trans_actuators"][angle] = exchange.get_actuator_handle(
                state, "Schedule:Compact", "Schedule Value", f"TransSched_BIPV_A{angle:02d}"
            )
            self.handles["avail_actuators"][angle] = exchange.get_actuator_handle(
                state, "Schedule:Compact", "Schedule Value", f"AvailSched_BIPV_A{angle:02d}"
            )

        # 2 DAMPER SCHEDULE ACTUATORS
        self.handles["damper_topbottom"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_Damper_TopBottom_Schedule"
        )
        self.handles["damper_outerskin"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_Damper_OuterSkin_Schedule"
        )

        # 4-FACADE CAVITY THERMAL HEAT GAIN SCHEDULE ACTUATORS
        self.handles["cavity_heat_gain_south"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_BIPV_Cavity_HeatGain_Schedule"
        )
        self.handles["cavity_heat_gain_east"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_BIPV_Cavity_HeatGain_Schedule_East"
        )
        self.handles["cavity_heat_gain_north"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_BIPV_Cavity_HeatGain_Schedule_North"
        )
        self.handles["cavity_heat_gain_west"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_BIPV_Cavity_HeatGain_Schedule_West"
        )

        # GLOBAL VARIABLE HANDLES - SOUTH
        self.handles["g_bipv_tilt"] = exchange.get_global_handle(state, "BIPV_Tilt_Angle")
        self.handles["g_damper"] = exchange.get_global_handle(state, "DSF_Damper_Opening")
        self.handles["g_mode"] = exchange.get_global_handle(state, "DSF_Operating_Mode")
        self.handles["g_bipv_rad"] = exchange.get_global_handle(state, "BIPV_Incident_Solar")
        self.handles["g_bipv_power"] = exchange.get_global_handle(state, "BIPV_Power_Generation")
        self.handles["g_bipv_eff"] = exchange.get_global_handle(state, "BIPV_Efficiency")
        self.handles["g_bipv_waste_heat"] = exchange.get_global_handle(state, "BIPV_Waste_Heat")
        self.handles["g_bipv_cavity_heat"] = exchange.get_global_handle(state, "BIPV_Cavity_Heat_Gain")

        # GLOBAL VARIABLE HANDLES - EAST / NORTH / WEST
        for orient in ["East", "North", "West"]:
            self.handles[f"g_bipv_rad_{orient.lower()}"] = exchange.get_global_handle(state, f"BIPV_Incident_Solar_{orient}")
            self.handles[f"g_bipv_power_{orient.lower()}"] = exchange.get_global_handle(state, f"BIPV_Power_Generation_{orient}")
            self.handles[f"g_bipv_waste_{orient.lower()}"] = exchange.get_global_handle(state, f"BIPV_Waste_Heat_{orient}")
            self.handles[f"g_bipv_cavity_{orient.lower()}"] = exchange.get_global_handle(state, f"BIPV_Cavity_Heat_Gain_{orient}")

        any_failed = False
        for key, val in self.handles.items():
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    if subval == -1:
                        safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for dict actuator: {key}[{subkey}]")
                        any_failed = True
            elif val == -1:
                safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for sensor/actuator/global: {key}")
                if "cavity" not in key and "waste" not in key:
                    any_failed = True

        if not any_failed:
            safe_debug("DEBUG_SUCCESS: ALL REAL-SCALE 4-FACADE THERMAL KINETIC BIPV & DSF HANDLES ACQUIRED!")
            self.need_to_get_handles = False

    def _get_incident_solar_val(self, sun_alt, sun_azi, dn_rad, df_rad, tilt_deg, surface_azi_rad):
        tilt_rad = math.radians(tilt_deg)
        alt_rad = math.radians(sun_alt)
        azi_rad = math.radians(sun_azi)

        cos_theta = (math.sin(alt_rad) * math.cos(tilt_rad) +
                     math.cos(alt_rad) * math.sin(tilt_rad) * math.cos(azi_rad - surface_azi_rad))
        cos_theta = max(0.0, cos_theta)
        
        i_beam = dn_rad * cos_theta
        i_diff = df_rad * (1.0 + math.cos(tilt_rad)) / 2.0
        total_horiz = dn_rad * math.sin(alt_rad) + df_rad
        i_ground = total_horiz * 0.2 * (1.0 - math.cos(tilt_rad)) / 2.0

        return i_beam + i_diff + i_ground

    def _override_schedules(self, state, optimal_angle: int, tb_damper: float, os_damper: float, cavity_gains: dict):
        exchange = self.api.exchange

        for angle in ANGLES:
            trans_act = self.handles["trans_actuators"][angle]
            avail_act = self.handles["avail_actuators"][angle]

            if angle == optimal_angle:
                if trans_act != -1:
                    exchange.set_actuator_value(state, trans_act, 0.20)
                if avail_act != -1:
                    exchange.set_actuator_value(state, avail_act, 1.0)
            else:
                if trans_act != -1:
                    exchange.set_actuator_value(state, trans_act, 1.00)
                if avail_act != -1:
                    exchange.set_actuator_value(state, avail_act, 0.0)

        h_tb = self.handles.get("damper_topbottom", -1)
        h_os = self.handles.get("damper_outerskin", -1)
        if h_tb != -1:
            exchange.set_actuator_value(state, h_tb, tb_damper)
        if h_os != -1:
            exchange.set_actuator_value(state, h_os, os_damper)

        # 4-FACADE CAVITY HEAT GAINS
        h_heat_s = self.handles.get("cavity_heat_gain_south", -1)
        h_heat_e = self.handles.get("cavity_heat_gain_east", -1)
        h_heat_n = self.handles.get("cavity_heat_gain_north", -1)
        h_heat_w = self.handles.get("cavity_heat_gain_west", -1)

        if h_heat_s != -1:
            exchange.set_actuator_value(state, h_heat_s, cavity_gains.get("South", 0.0))
        if h_heat_e != -1:
            exchange.set_actuator_value(state, h_heat_e, cavity_gains.get("East", 0.0))
        if h_heat_n != -1:
            exchange.set_actuator_value(state, h_heat_n, cavity_gains.get("North", 0.0))
        if h_heat_w != -1:
            exchange.set_actuator_value(state, h_heat_w, cavity_gains.get("West", 0.0))

    def _update_global_variables(self, state, tilt: int, tb_damp: float, os_damp: float, mode: int,
                                  solar_s: float, eff_s: float, power_s: float, waste_s: float, cavity_s: float):
        exchange = self.api.exchange
        self.bipv_tilt_angle = float(tilt)
        self.dsf_topbottom_damper = tb_damp
        self.dsf_outerskin_damper = os_damp
        self.operating_mode = float(mode)
        self.bipv_incident_solar = solar_s
        self.bipv_efficiency = eff_s
        self.bipv_power_generation = power_s
        self.bipv_waste_heat = waste_s
        self.bipv_cavity_heat_gain = cavity_s

        # South
        g_tilt = self.handles.get("g_bipv_tilt", -1)
        g_damp = self.handles.get("g_damper", -1)
        g_mode = self.handles.get("g_mode", -1)
        g_rad = self.handles.get("g_bipv_rad", -1)
        g_eff = self.handles.get("g_bipv_eff", -1)
        g_pwr = self.handles.get("g_bipv_power", -1)
        g_waste = self.handles.get("g_bipv_waste_heat", -1)
        g_cavity = self.handles.get("g_bipv_cavity_heat", -1)

        if g_tilt != -1:
            exchange.set_global_value(state, g_tilt, float(tilt))
        if g_damp != -1:
            exchange.set_global_value(state, g_damp, os_damp)
        if g_mode != -1:
            exchange.set_global_value(state, g_mode, float(mode))
        if g_rad != -1:
            exchange.set_global_value(state, g_rad, solar_s)
        if g_eff != -1:
            exchange.set_global_value(state, g_eff, eff_s)
        if g_pwr != -1:
            exchange.set_global_value(state, g_pwr, power_s)
        if g_waste != -1:
            exchange.set_global_value(state, g_waste, waste_s)
        if g_cavity != -1:
            exchange.set_global_value(state, g_cavity, cavity_s)

        # East / North / West
        for orient in ["East", "North", "West"]:
            res = self.bipv_results[orient]
            g_r = self.handles.get(f"g_bipv_rad_{orient.lower()}", -1)
            g_p = self.handles.get(f"g_bipv_power_{orient.lower()}", -1)
            g_w = self.handles.get(f"g_bipv_waste_{orient.lower()}", -1)
            g_c = self.handles.get(f"g_bipv_cavity_{orient.lower()}", -1)

            if g_r != -1:
                exchange.set_global_value(state, g_r, res["solar"])
            if g_p != -1:
                exchange.set_global_value(state, g_p, res["power"])
            if g_w != -1:
                exchange.set_global_value(state, g_w, res["waste_heat"])
            if g_c != -1:
                exchange.set_global_value(state, g_c, res["cavity_heat"])

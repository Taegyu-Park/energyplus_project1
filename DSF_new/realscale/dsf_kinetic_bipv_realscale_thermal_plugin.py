"""
Integrated Real-Scale Kinetic BIPV & DSF Outer Skin Control with Cavity Thermal Heat Gain
==========================================================================================
- Target: Real-Scale Office Building (32m x 18m x 8m, 10 Zones + 2 DSF South Cavity Zones)
- Gwangju IWEC Climate (35.13°N, 126.92°E)
- Features:
  1. Coupled Kinetic BIPV Sun-Tracking (0° to 90°) & STPV 20% Transmittance Preservation
  2. 2-Damper System Decoupled Control (Top/Bottom Stack & Outer Skin Louver Gap)
  3. BIPV Waste Heat Injection to DSF Cavity (BIPV/T Thermal Modeling):
     - When closed (0° vertical in winter/cold periods), absorbs solar radiation and injects
       the rear-side thermal waste heat (Q_absorbed - P_pv) into Zone_Cavity_South via OtherEquipment.
     - When tilted (>0° in summer), inward heat fraction is dynamically reduced as louver opens.
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]

# PV & Thermal Parameters
PV_TOTAL_AREA = 213.333333      # m2 (80 modules * 2.186184 m2 * 1.219781 scaling)
PV_ABSORPTANCE = 0.90          # Solar absorptance of BIPV surface (90%)
PV_BASE_EFFICIENCY = 0.15      # Nominal PV electrical efficiency (15%)
INWARD_HEAT_FRAC_CLOSED = 0.45 # Inward thermal transfer fraction when louvers are fully closed (0 deg)
INWARD_HEAT_FRAC_OPEN = 0.05   # Inward thermal transfer fraction when louvers are fully open (90 deg)


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
        self.bipv_incident_solar = 0.0
        self.bipv_power_generation = 0.0
        self.bipv_efficiency = 0.0
        self.bipv_waste_heat = 0.0
        self.bipv_cavity_heat_gain = 0.0

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

        tilt_deg = 90.0 - best_bipv_angle
        optimal_solar_rad = self._get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)

        actual_pv_eff = PV_BASE_EFFICIENCY if optimal_solar_rad > 0.0 else 0.0
        pv_power = optimal_solar_rad * PV_TOTAL_AREA * actual_pv_eff

        # --- BIPV Thermal Waste Heat Calculation ---
        # Total solar radiation incident on BIPV modules [W]
        total_solar_heat = optimal_solar_rad * PV_TOTAL_AREA
        # Solar radiation absorbed by BIPV modules [W]
        total_absorbed_heat = total_solar_heat * PV_ABSORPTANCE
        # Net thermal waste heat after electric power generation [W]
        waste_heat = max(0.0, total_absorbed_heat - pv_power)

        # Inward Heat Fraction:
        # - Closed (0 deg, Winter/Cold): 45% of waste heat is trapped and heats the DSF cavity
        # - Open (>0 deg, Summer/Warm tracking): Heat completely dissipates to ambient air due to external airflow & DSF ventilation (0%)
        if best_bipv_angle == 0:
            inward_fraction = INWARD_HEAT_FRAC_CLOSED
        else:
            inward_fraction = 0.0

        # Thermal heat injected into DSF Cavity [W]
        cavity_thermal_gain = waste_heat * inward_fraction

        # --- Override Schedules ---
        self._override_schedules(
            state,
            optimal_angle=best_bipv_angle,
            tb_damper=topbottom_damper,
            os_damper=outerskin_damper,
            cavity_heat_gain=cavity_thermal_gain
        )

        # --- Update Global Variables ---
        self._update_global_variables(
            state,
            best_bipv_angle,
            topbottom_damper,
            outerskin_damper,
            mode,
            optimal_solar_rad,
            actual_pv_eff,
            pv_power,
            waste_heat,
            cavity_thermal_gain
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

        # TYPE 2: DSF OUTER SKIN LOUVER GAP DAMPER CONTROL
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

        # CAVITY THERMAL HEAT GAIN SCHEDULE ACTUATOR
        self.handles["cavity_heat_gain"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_BIPV_Cavity_HeatGain_Schedule"
        )

        # GLOBAL VARIABLE HANDLES
        self.handles["g_bipv_tilt"] = exchange.get_global_handle(state, "BIPV_Tilt_Angle")
        self.handles["g_damper"] = exchange.get_global_handle(state, "DSF_Damper_Opening")
        self.handles["g_mode"] = exchange.get_global_handle(state, "DSF_Operating_Mode")
        self.handles["g_bipv_rad"] = exchange.get_global_handle(state, "BIPV_Incident_Solar")
        self.handles["g_bipv_power"] = exchange.get_global_handle(state, "BIPV_Power_Generation")
        self.handles["g_bipv_eff"] = exchange.get_global_handle(state, "BIPV_Efficiency")
        self.handles["g_bipv_waste_heat"] = exchange.get_global_handle(state, "BIPV_Waste_Heat")
        self.handles["g_bipv_cavity_heat"] = exchange.get_global_handle(state, "BIPV_Cavity_Heat_Gain")

        any_failed = False
        for key, val in self.handles.items():
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    if subval == -1:
                        safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for dict actuator: {key}[{subkey}]")
                        any_failed = True
            elif val == -1:
                safe_debug(f"DEBUG_WARN: FAILED TO GET HANDLE for sensor/actuator/global: {key}")
                if key not in ["cavity_heat_gain", "g_bipv_waste_heat", "g_bipv_cavity_heat"]:
                    any_failed = True

        if not any_failed:
            safe_debug("DEBUG_SUCCESS: ALL REAL-SCALE THERMAL KINETIC BIPV & DSF HANDLES ACQUIRED!")
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

    def _override_schedules(self, state, optimal_angle: int, tb_damper: float, os_damper: float, cavity_heat_gain: float):
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
        h_heat = self.handles.get("cavity_heat_gain", -1)

        if h_tb != -1:
            exchange.set_actuator_value(state, h_tb, tb_damper)
        if h_os != -1:
            exchange.set_actuator_value(state, h_os, os_damper)
        if h_heat != -1:
            exchange.set_actuator_value(state, h_heat, cavity_heat_gain)

    def _update_global_variables(self, state, tilt: int, tb_damp: float, os_damp: float, mode: int,
                                  solar: float, eff: float, power: float, waste_heat: float, cavity_heat: float):
        exchange = self.api.exchange
        self.bipv_tilt_angle = float(tilt)
        self.dsf_topbottom_damper = tb_damp
        self.dsf_outerskin_damper = os_damp
        self.operating_mode = float(mode)
        self.bipv_incident_solar = solar
        self.bipv_efficiency = eff
        self.bipv_power_generation = power
        self.bipv_waste_heat = waste_heat
        self.bipv_cavity_heat_gain = cavity_heat

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
            exchange.set_global_value(state, g_rad, solar)
        if g_eff != -1:
            exchange.set_global_value(state, g_eff, eff)
        if g_pwr != -1:
            exchange.set_global_value(state, g_pwr, power)
        if g_waste != -1:
            exchange.set_global_value(state, g_waste, waste_heat)
        if g_cavity != -1:
            exchange.set_global_value(state, g_cavity, cavity_heat)

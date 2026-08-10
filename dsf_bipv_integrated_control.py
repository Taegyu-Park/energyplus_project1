"""
Kinetic BIPV & DSF Integrated Control EnergyPlus Python Plugin
================================================================
- Target: Gwangju Climate 2-Story Kinetic BIPV + Double-Skin Facade (DSF)
- Functions:
  1. BIPV Solar Altitude Tracking & Nighttime Angle Control (Separate BIPV Logic)
  2. Four-Season DSF Top/Bottom Damper Opening Control (Separate DSF Damper Logic)
- Single File Implementation: Both control modules run in a single plugin class
  while maintaining modular, independent control logic.
"""

from pyenergyplus.plugin import EnergyPlusPlugin
import math

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]


class IntegratedDSFAndBIPVControlPlugin(EnergyPlusPlugin):

    def __init__(self):
        super().__init__()
        self.need_to_get_handles = True
        self.handles = {}

        # Global Output Variables for Monitoring in EnergyPlus CSV/ESO
        self.bipv_tilt_angle = 0.0
        self.dsf_bottom_damper = 0.0
        self.dsf_top_damper = 0.0
        self.operating_mode = 0  # 1: Summer Day, 2: Summer Night, 3: Winter Day, 4: Winter Night

    def _get_handles(self, state):
        """Safely fetch EnergyPlus variable and schedule handles"""
        exchange = self.api.exchange
        
        # Weather Sensors
        self.handles["sun_alt"] = exchange.get_variable_handle(state, "Site Solar Altitude", "Environment")
        self.handles["sun_azi"] = exchange.get_variable_handle(state, "Site Solar Azimuth", "Environment")
        self.handles["out_temp"] = exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        self.handles["dn_rad"] = exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")
        self.handles["df_rad"] = exchange.get_variable_handle(state, "Site Diffuse Solar Radiation Rate per Area", "Environment")

        # BIPV Angle Schedule Handles (TransSched_BIPV_A00 to A90)
        self.handles["bipv_scheds"] = {}
        for angle in ANGLES:
            sched_name = f"TransSched_BIPV_A{angle:02d}"
            h = exchange.get_actuator_handle(state, "Schedule:Compact", "Schedule Value", sched_name)
            if h != -1:
                self.handles["bipv_scheds"][angle] = h

        # DSF Damper Actuators (Schedules for AirflowNetwork openings)
        self.handles["damper_bottom"] = exchange.get_actuator_handle(state, "Schedule:Compact", "Schedule Value", "DSF_Damper_Bottom_Sched")
        self.handles["damper_top"] = exchange.get_actuator_handle(state, "Schedule:Compact", "Schedule Value", "DSF_Damper_Top_Sched")

        # Global Variables for EnergyPlus Output Reporting
        try:
            self.handles["g_bipv_tilt"] = exchange.get_global_handle(state, "BIPV_Tilt_Angle")
            self.handles["g_damper_bot"] = exchange.get_global_handle(state, "DSF_Bottom_Damper")
            self.handles["g_damper_top"] = exchange.get_global_handle(state, "DSF_Top_Damper")
            self.handles["g_mode"] = exchange.get_global_handle(state, "DSF_Operating_Mode")
        except Exception:
            pass

        self.need_to_get_handles = False

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        if self.need_to_get_handles:
            self._get_handles(state)

        exchange = self.api.exchange

        # -------------------------------------------------------------
        # 1. READ SENSORS
        # -------------------------------------------------------------
        sun_alt = exchange.get_variable_value(state, self.handles["sun_alt"]) if self.handles.get("sun_alt", -1) != -1 else 0.0
        out_temp = exchange.get_variable_value(state, self.handles["out_temp"]) if self.handles.get("out_temp", -1) != -1 else 20.0
        dn_rad = exchange.get_variable_value(state, self.handles["dn_rad"]) if self.handles.get("dn_rad", -1) != -1 else 0.0

        # -------------------------------------------------------------
        # 2. INDEPENDENT CONTROL LOGIC 1: Kinetic BIPV Louver Angle
        # -------------------------------------------------------------
        best_bipv_angle = self._control_bipv(sun_alt, out_temp)

        # -------------------------------------------------------------
        # 3. INDEPENDENT CONTROL LOGIC 2: DSF Top/Bottom Dampers
        # -------------------------------------------------------------
        bot_damper, top_damper, mode = self._control_dsf_dampers(sun_alt, out_temp, dn_rad)

        # -------------------------------------------------------------
        # 4. EXECUTE ACTUATORS (Apply Control Signals to EnergyPlus)
        # -------------------------------------------------------------
        self._apply_bipv_actuators(state, best_bipv_angle)
        self._apply_damper_actuators(state, bot_damper, top_damper)

        # -------------------------------------------------------------
        # 5. UPDATE GLOBAL REPORTING VARIABLES
        # -------------------------------------------------------------
        self._update_global_variables(state, best_bipv_angle, bot_damper, top_damper, mode)

        return 0

    def _control_bipv(self, sun_alt: float, out_temp: float) -> int:
        """
        [Modular BIPV Control Subroutine]
        Calculates optimal solar tracking tilt angle during daytime,
        and sets horizontal/closed angle at night to balance heat loss and daylit gains.
        """
        if sun_alt <= 0.0:  # Nighttime
            # Winter night: Close louvers (0 deg) to maximize thermal insulation buffer
            # Summer night: Horizontal louvers (90 deg) to maximize cavity natural ventilation flow
            return 0 if out_temp < 15.0 else 90
        else:  # Daytime Solar Altitude Tracking
            # Optimal BIPV Module Tilt Angle = 90 deg - Solar Altitude Angle (Direct Normal Normal Incident Tracking)
            ideal_tilt = 90.0 - sun_alt
            # Map ideal continuous tilt angle to nearest discrete 10-degree step (0, 10, ..., 90)
            best_angle = min(ANGLES, key=lambda a: abs(a - ideal_tilt))
            return best_angle

    def _control_dsf_dampers(self, sun_alt: float, out_temp: float, dn_rad: float):
        """
        [Modular DSF Damper Control Subroutine]
        Controls top and bottom damper opening factors (0.0 = Closed, 1.0 = Open)
        based on 4 seasonal & diurnal operating modes.
        """
        if out_temp >= 20.0 or (out_temp >= 15.0 and dn_rad > 200.0):  # Summer / Cooling Season
            if sun_alt > 0.0:  # Summer Daytime
                mode = 1
                bot_damper = 1.0  # Open bottom inlet
                top_damper = 1.0   # Open top outlet (Heat Exhaust via Natural Buoyancy Stack Effect)
            else:  # Summer Nighttime
                mode = 2
                bot_damper = 1.0  # Open bottom inlet
                top_damper = 1.0   # Open top outlet (Night Flush Cooling)
        else:  # Winter / Heating Season
            if sun_alt > 0.0 and dn_rad > 100.0:  # Winter Solar Daytime
                mode = 3
                bot_damper = 0.0  # Close dampers to trap solar thermal heat inside cavity (Preheating Air Buffer)
                top_damper = 0.0
            else:  # Winter Nighttime / Overcast
                mode = 4
                bot_damper = 0.0  # Close dampers completely to form sealed insulating thermal buffer
                top_damper = 0.0

        return bot_damper, top_damper, mode

    def _apply_bipv_actuators(self, state, active_angle: int):
        """Applies 1.0 (active) to selected BIPV angle schedule and 0.0 to all others"""
        exchange = self.api.exchange
        for angle, handle in self.handles.get("bipv_scheds", {}).items():
            if handle != -1:
                val = 1.0 if angle == active_angle else 0.0
                exchange.set_actuator_value(state, handle, val)

    def _apply_damper_actuators(self, state, bot_val: float, top_val: float):
        """Applies opening factor (0.0 to 1.0) to top and bottom damper schedule actuators"""
        exchange = self.api.exchange
        h_bot = self.handles.get("damper_bottom", -1)
        h_top = self.handles.get("damper_top", -1)

        if h_bot != -1:
            exchange.set_actuator_value(state, h_bot, bot_val)
        if h_top != -1:
            exchange.set_actuator_value(state, h_top, top_val)

    def _update_global_variables(self, state, tilt: int, bot: float, top: float, mode: int):
        """Updates internal states and EnergyPlus global variables for output reporting"""
        exchange = self.api.exchange
        self.bipv_tilt_angle = float(tilt)
        self.dsf_bottom_damper = bot
        self.dsf_top_damper = top
        self.operating_mode = mode

        g_tilt = self.handles.get("g_bipv_tilt", -1)
        g_bot = self.handles.get("g_damper_bot", -1)
        g_top = self.handles.get("g_damper_top", -1)
        g_mode = self.handles.get("g_mode", -1)

        if g_tilt != -1:
            exchange.set_global_variable_value(state, g_tilt, float(tilt))
        if g_bot != -1:
            exchange.set_global_variable_value(state, g_bot, bot)
        if g_top != -1:
            exchange.set_global_variable_value(state, g_top, top)
        if g_mode != -1:
            exchange.set_global_variable_value(state, g_mode, float(mode))

"""
Pure DSF (Double Skin Facade) Natural Ventilation & Damper Control Plugin
========================================================================
- Target Model: Real-Scale Office Building 2-Story DSF (4 Facades x 2 Floors)
- Location: Gwangju IWEC Climate (35.13°N, 126.92°E)
- System: Pure Double Skin Facade without BIPV
- Outer Skin Construction: Generic Double Pane (Identical to Inner Windows)
- Control Logic:
  1. Summer Daytime (T_out >= 20°C & Direct Normal Radiation > 100 W/m²):
     - Mode 1: Top/Bottom Damper = 1.0 (Full Open), Outer Skin Damper = 1.0 (Open)
     - Purpose: Thermal buoyancy chimney effect & dynamic convective heat extraction.
  2. Summer Nighttime (T_out >= 18°C & Nighttime):
     - Mode 2: Top/Bottom Damper = 1.0 (Full Open), Outer Skin Damper = 1.0 (Open)
     - Purpose: Night flushing cooling using ambient air.
  3. Winter Daytime (T_out < 15°C & Solar Radiation > 100 W/m²):
     - Mode 3: Top/Bottom Damper = 0.0 (Closed), Outer Skin Damper = 0.0 (Closed)
     - Purpose: Greenhouse thermal buffer trapping solar radiation to reduce heating load.
  4. Winter Nighttime (T_out < 10°C & Nighttime):
     - Mode 4: Top/Bottom Damper = 0.0 (Closed), Outer Skin Damper = 0.0 (Closed)
     - Purpose: Sealed insulating air gap to prevent building heat loss.
  5. Intermediate / Mild Conditions:
     - Mode 5: Modulated natural ventilation based on ambient and cavity temperature.
"""

from pyenergyplus.plugin import EnergyPlusPlugin


class DSFOnlyRealscalePlugin(EnergyPlusPlugin):

    def __init__(self):
        super().__init__()
        self.need_to_get_handles = True
        self.handles = {}

        # DSF Control Variables
        self.dsf_topbottom_damper = 0.0
        self.dsf_outerskin_damper = 0.0
        self.operating_mode = 0.0

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        if not self.api.exchange.api_data_fully_ready(state):
            return 0

        if self.need_to_get_handles:
            self._get_handles(state)
            if self.need_to_get_handles:
                return 0

        exchange = self.api.exchange

        sun_alt = exchange.get_variable_value(state, self.handles["sun_alt"]) if self.handles.get("sun_alt", -1) != -1 else 0.0
        out_temp = exchange.get_variable_value(state, self.handles["out_temp"]) if self.handles.get("out_temp", -1) != -1 else 20.0
        dn_rad = exchange.get_variable_value(state, self.handles["dn_rad"]) if self.handles.get("dn_rad", -1) != -1 else 0.0

        # Determine DSF Operating Mode & Damper Positions
        mode, topbottom_damper, outerskin_damper = self._control_dsf_dampers(sun_alt, out_temp, dn_rad)

        # Override Schedules
        self._override_schedules(state, tb_damper=topbottom_damper, out_damper=outerskin_damper)

        # Update Plugin Variables for Output Reporting
        self.dsf_topbottom_damper = topbottom_damper
        self.dsf_outerskin_damper = outerskin_damper
        self.operating_mode = float(mode)

        if self.handles.get("var_tb_damper", -1) != -1:
            exchange.set_global_value(state, self.handles["var_tb_damper"], self.dsf_topbottom_damper)
        if self.handles.get("var_out_damper", -1) != -1:
            exchange.set_global_value(state, self.handles["var_out_damper"], self.dsf_outerskin_damper)
        if self.handles.get("var_mode", -1) != -1:
            exchange.set_global_value(state, self.handles["var_mode"], self.operating_mode)

        return 0

    def _get_handles(self, state):
        exchange = self.api.exchange

        # Environmental Sensors
        self.handles["sun_alt"] = exchange.get_variable_handle(state, "Site Sun Altitude Angle", "Environment")
        self.handles["out_temp"] = exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        self.handles["dn_rad"] = exchange.get_variable_handle(state, "Site Direct Solar Radiation Rate per Area", "Environment")

        # Actuators (Damper Schedules)
        self.handles["act_tb_damper"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_Damper_TopBottom_Schedule"
        )
        self.handles["act_out_damper"] = exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "DSF_Damper_OuterSkin_Schedule"
        )

        # Plugin Output Variables
        self.handles["var_tb_damper"] = exchange.get_global_handle(state, "DSF_TopBottom_Damper")
        self.handles["var_out_damper"] = exchange.get_global_handle(state, "DSF_OuterSkin_Damper")
        self.handles["var_mode"] = exchange.get_global_handle(state, "DSF_Operating_Mode")

        # Check critical handles
        if self.handles["act_tb_damper"] == -1 or self.handles["act_out_damper"] == -1:
            self.need_to_get_handles = True
        else:
            self.need_to_get_handles = False

    def _control_dsf_dampers(self, sun_alt: float, out_temp: float, dn_rad: float):
        is_daytime = sun_alt > 0.0
        has_strong_sun = dn_rad > 100.0

        if out_temp >= 20.0 and is_daytime and has_strong_sun:
            # Mode 1: Summer Daytime Convective Exhaust
            mode = 1
            topbottom_damper = 1.0
            outerskin_damper = 1.0
        elif out_temp >= 18.0 and not is_daytime:
            # Mode 2: Summer Night Flushing Cooling
            mode = 2
            topbottom_damper = 1.0
            outerskin_damper = 1.0
        elif out_temp < 15.0 and is_daytime and has_strong_sun:
            # Mode 3: Winter Daytime Greenhouse Thermal Buffer
            mode = 3
            topbottom_damper = 0.0
            outerskin_damper = 0.0
        elif out_temp < 10.0 and not is_daytime:
            # Mode 4: Winter Night Insulating Buffer
            mode = 4
            topbottom_damper = 0.0
            outerskin_damper = 0.0
        else:
            # Mode 5: Intermediate Mild Condition
            mode = 5
            if 18.0 <= out_temp <= 24.0:
                topbottom_damper = 0.5
                outerskin_damper = 0.5
            else:
                topbottom_damper = 0.0
                outerskin_damper = 0.0

        return mode, topbottom_damper, outerskin_damper

    def _override_schedules(self, state, tb_damper: float, out_damper: float):
        exchange = self.api.exchange
        if self.handles.get("act_tb_damper", -1) != -1:
            exchange.set_actuator_value(state, self.handles["act_tb_damper"], tb_damper)
        if self.handles.get("act_out_damper", -1) != -1:
            exchange.set_actuator_value(state, self.handles["act_out_damper"], out_damper)

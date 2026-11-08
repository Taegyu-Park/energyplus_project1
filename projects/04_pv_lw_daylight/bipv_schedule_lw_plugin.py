"""
pv_lw_daylight/bipv_schedule_lw_plugin.py
==========================================================
case3(각도 제어)용: bipv_experiments/bipv_schedule_plugin.KineticBIPVPlugin 를 그대로 쓰고,
같은 콜백에서 각도를 정한 직후 다음을 수행한다(같은 콜백이라 플러그인 인스턴스 실행 순서에 의존하지 않음).
- PV 셀 온도 → 외피 장파복사 연동 (pv_lw_plugin.PVLongwaveCoupler, 설정에 surfaces 가 있을 때)
- 주광 연동 조명 전력 (pv_lw_plugin.DaylightTableCoupler, 설정에 daylight_table 이 있을 때)
"""

from bipv_schedule_plugin import KineticBIPVPlugin as _ScheduleBase
from pv_lw_plugin import DaylightTableCoupler, PVLongwaveCoupler, load_config


class KineticBIPVPlugin(_ScheduleBase):

    def __init__(self):
        super().__init__()
        cfg = load_config()
        self.couplers = []
        if cfg.get("surfaces"):
            self.couplers.append(PVLongwaveCoupler(self.api, cfg))
        if cfg.get("daylight_table"):
            self.couplers.append(DaylightTableCoupler(self.api, cfg["daylight_table"]))

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        rc = super().on_begin_zone_timestep_before_init_heat_balance(state)
        if not self.need_to_get_handles:  # 각도 제어 핸들이 준비돼 이번 스텝 각도가 정해진 경우만
            for c in self.couplers:
                c.update(state, int(self.bipv_tilt_angle))
        return rc

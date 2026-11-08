"""
pv_lw_daylight/bipv_schedule_lw_standalone.py
==========================================================
case3 단독 실행용 플러그인 (bipv_experiments/idf/case3_v3_south_fixed_lw_dl.idf 가 참조).
bipv_schedule_lw_plugin.KineticBIPVPlugin(각도 제어 + PV 장파 연동 + 주광 배율표 조명)을 그대로 쓰고,
run_pvlw.py 없이 EnergyPlus 를 직접 실행해도 동작하도록 환경변수 기본값만 채운다.
- PVLW_CONFIG       미지정 시 standalone/case3_lw_dl400_config.json (make_case3_lw_dl_idf.py 가 생성)
- BIPV_SCHEDULE_CSV 미지정 시 기준안 태양추적 bipv_experiments/schedules/suntracking_w0s90.csv
환경변수를 지정하면 그 값이 우선한다(다른 각도 스케줄·설정으로 실행할 때).
"""

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
os.environ.setdefault("PVLW_CONFIG", str(_HERE / "standalone" / "case3_lw_dl400_config.json"))
os.environ.setdefault("BIPV_SCHEDULE_CSV", str(_HERE.parent / "bipv_experiments" / "schedules" / "suntracking_w0s90.csv"))

from bipv_schedule_lw_plugin import KineticBIPVPlugin  # noqa: E402,F401

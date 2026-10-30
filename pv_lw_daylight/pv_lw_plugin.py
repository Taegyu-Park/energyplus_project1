"""
pv_lw_daylight/pv_lw_plugin.py
================================================
PV 셀 온도 → 남측 외피(창·외벽) 장파복사 연동.

- PV(Decoupled)가 계산한 셀 온도를 단(row)별 평균으로 읽는다.
- 외피 표면마다 SurfaceProperty:SurroundingSurfaces 의 주변 표면(PV 루버) 온도 스케줄을 유효온도로 actuate 한다.
    T_eff⁴ = [Σ_r F_r(θ)·T_r⁴ + (F_max − Σ_r F_r(θ))·T_bg⁴] / F_max
    T_bg⁴  = 0.5·[β·T_sky⁴ + (1−β)·T_out⁴] + 0.5·T_out⁴   (수직면의 하늘/공기/지면 배경, β=√0.5)
- PV 셀 온도는 직전 타임스텝 값이다(PV는 HVAC 이후 계산됨). 각도가 바뀐 스텝에는 직전 각도(실제 핀이 있던 각도)의
  발전기 온도를 쓰고, 뷰팩터는 현재 각도를 쓴다.
- 설정은 환경변수 PVLW_CONFIG(JSON 경로)로 받는다.

플러그인 클래스
- PVLongwaveFixedPlugin : 각도 고정(case2)용 독립 플러그인
- PVLongwaveCoupler     : case3 각도 제어 플러그인(bipv_schedule_lw_plugin)이 같은 콜백 안에서 호출하는 도우미
"""

import json
import math
import os

from pyenergyplus.plugin import EnergyPlusPlugin

K = 273.15
T_VALID = (-50.0, 120.0)


def load_config() -> dict:
    with open(os.environ["PVLW_CONFIG"], "r", encoding="utf-8") as f:
        return json.load(f)


class PVLongwaveCoupler:
    def __init__(self, api, cfg: dict):
        self.api = api
        self.cfg = cfg
        self.angles = cfg["angles"]
        self.rows = range(1, cfg["rows"] + 1)
        self.beta = cfg.get("beta_sky", math.sqrt(0.5))
        self.test_temp = cfg.get("test_fixed_temp")
        self.ready = False
        self.prev_angle = None
        self.h = {}

    def _get_handles(self, state) -> bool:
        ex = self.api.exchange
        self.h["t_out"] = ex.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        self.h["t_sky"] = ex.get_variable_handle(state, "Site Sky Temperature", "Environment")
        self.h["cell"] = {
            (a, r): [ex.get_variable_handle(state, "Generator PV Cell Temperature", g)
                     for g in self.cfg["cell_keys"][str(a)][str(r)]]
            for a in self.angles for r in self.rows
        }
        self.h["act"] = [ex.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", s["schedule"])
                         for s in self.cfg["surfaces"]]
        bad = [k for k in ("t_out", "t_sky") if self.h[k] == -1]
        bad += [f"cell{key}" for key, hs in self.h["cell"].items() if -1 in hs]
        bad += [s["schedule"] for s, a in zip(self.cfg["surfaces"], self.h["act"]) if a == -1]
        if bad:
            print(f"PVLW_WARN: 핸들 실패 {bad[:10]} (총 {len(bad)})", flush=True)
            return False
        print("PVLW_OK: 모든 핸들 확보", flush=True)
        return True

    def update(self, state, angle_now: int):
        ex = self.api.exchange
        if not ex.api_data_fully_ready(state):
            return
        if not self.ready:
            self.ready = self._get_handles(state)
            if not self.ready:
                return

        t_out = ex.get_variable_value(state, self.h["t_out"])
        t_sky = ex.get_variable_value(state, self.h["t_sky"])
        tb4 = 0.5 * (self.beta * (t_sky + K) ** 4 + (1 - self.beta) * (t_out + K) ** 4) + 0.5 * (t_out + K) ** 4

        a_temp = self.prev_angle if self.prev_angle in self.angles else angle_now
        t_row4 = {}
        for r in self.rows:
            vals = [ex.get_variable_value(state, h) for h in self.h["cell"][(a_temp, r)]]
            vals = [v for v in vals if T_VALID[0] < v < T_VALID[1]]
            t = sum(vals) / len(vals) if vals else t_out
            t_row4[r] = (t + K) ** 4

        for s, act in zip(self.cfg["surfaces"], self.h["act"]):
            if self.test_temp is not None:
                t_eff = self.test_temp
            elif s["fmax"] <= 0:  # 검증용(뷰팩터 0): 값은 영향 없음
                t_eff = t_out
            else:
                f = s["vf"][str(angle_now)]
                fsum = sum(f)
                num = sum(f[r - 1] * t_row4[r] for r in self.rows) + (s["fmax"] - fsum) * tb4
                t_eff = (num / s["fmax"]) ** 0.25 - K
            ex.set_actuator_value(state, act, t_eff)

        self.prev_angle = angle_now


class DaylightTableCoupler:
    """case3용 주광 연동 조명: case2 각도별 주광 실행에서 뽑은 조명 전력 배율 표로 남측 존 조명 전력을 설정한다.
    (case3는 10개 각도 차양을 모두 기하로 가져 EnergyPlus 주광 계산이 너무 느림 → 같은 기하의 case2 결과를 사용)
    조명 전력 = 설계 조명 전력 × 조명 스케줄 × 배율[현재 각도, 타임스텝]"""

    def __init__(self, api, dcfg: dict):
        self.api = api
        self.dcfg = dcfg
        self.table = {}  # (angle, zone) → [52560 배율]
        with open(dcfg["table"], "r", encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            cols = [[] for _ in header]
            for line in f:
                for i, v in enumerate(line.strip().split(",")):
                    cols[i].append(float(v))
        for name, col in zip(header, cols):
            if name.startswith("A"):
                a, zone = name[1:3], name[4:]
                self.table[(int(a), zone)] = col
        self.ready = False
        self.h = {}

    def _get_handles(self, state) -> bool:
        ex = self.api.exchange
        self.h["sched"] = ex.get_variable_handle(state, "Schedule Value", self.dcfg["schedule"])
        self.h["zones"] = []
        for zone, lights in zip(self.dcfg["zones"], self.dcfg["lights"]):
            act = ex.get_actuator_handle(state, "Lights", "Electricity Rate", lights)
            design = ex.get_internal_variable_handle(state, "Lighting Power Design Level", lights)
            self.h["zones"].append((zone, act, design))
        bad = self.h["sched"] == -1 or any(-1 in (a, d) for _, a, d in self.h["zones"])
        print("PVDL_OK: 조명 핸들 확보" if not bad else f"PVDL_WARN: 조명 핸들 실패 {self.h}", flush=True)
        return not bad

    def update(self, state, angle_now: int):
        ex = self.api.exchange
        if not ex.api_data_fully_ready(state):
            return
        if not self.ready:
            self.ready = self._get_handles(state)
            if not self.ready:
                return
        idx = -1
        if ex.kind_of_sim(state) == 3:  # RunPeriodWeather (웜업 포함, 날짜 기준 인덱스)
            idx = ((ex.day_of_year(state) - 1) * 24 + ex.hour(state)) * 6 + (ex.zone_time_step_number(state) - 1)
        sched = ex.get_variable_value(state, self.h["sched"])
        for zone, act, design in self.h["zones"]:
            col = self.table[(angle_now, zone)]
            mult = col[idx] if 0 <= idx < len(col) else 1.0
            ex.set_actuator_value(state, act, ex.get_internal_variable_value(state, design) * sched * mult)


class PVLongwaveFixedPlugin(EnergyPlusPlugin):
    """각도 고정 모델(case2)용"""

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.coupler = PVLongwaveCoupler(self.api, self.cfg)

    def on_begin_zone_timestep_before_init_heat_balance(self, state) -> int:
        self.coupler.update(state, int(self.cfg["fixed_angle"]))
        return 0

"""
eplus_winter/prepare.py
=======================
TiDE 각도 스케줄(train_tide_mm.py --export) E+ 폐루프 검증 준비 (TMYx.2011-2025, 겨울만).

1. 주광 배율 표: 학습 데이터와 같은 case2 TMYx2011 최종 실행(bipv_mismatch/case2_KS_TMYx2011_final, 반사 포함)에서
   남측 존 'Daylighting Lighting Power Multiplier' → pv_lw_daylight DaylightTableCoupler 형식
   (기존 dl_mult_FE_L400.csv 는 IWEC 기상이라 쓸 수 없음)
2. 오라클 스케줄: labels/mm_label_test_useful_lam0.05_tol0.0.csv 의 겨울 각도 + 그 외 기준안 태양추적
3. 배치 JSON: 스케줄 4개 × 1/6~1/15 (집계 1/9~1/15, 사용자 결정 겨울 일주일). 설정은 pv_lw_daylight case3 최종 실행(c3_FE_ST_lw_dl400)과 같음

출력: eplus_winter/{dl_mult_tmyx2011_L400.csv, schedules/oracle_test.csv, batch.json}
실행: python pv_lw_daylight/run_pvlw.py --batch bipv_mismatch/eplus_winter/batch.json --jobs 4
"""

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
MM = HERE.parent
ROOT = MM.parent
sys.path.insert(0, str(ROOT / "pv_lw_daylight"))
from build_daylight_table import multipliers, ZONES, N_STEPS  # noqa: E402

CASE2_RUNS = MM / "case2_KS_TMYx2011_final"
WEATHER = "data/KOR_KJ_Gwangju.471560_TMYx.2011-2025.epw"
BASELINE = "bipv_experiments/schedules/suntracking_w0s90.csv"
WINTER = [11, 12, 1, 2, 3]
PERIODS = {"wk": ("01-06", 10)}  # 2026-10-29 사용자: 겨울 일주일. 1/9(월)~1/15 집계 + 앞 3일 예열
REPORT = ("2006-01-09", "2006-01-15")  # 평일 구매·잉여가 겨울 평일 평균에 가장 가까운 주


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def main():
    # 1. 주광 배율 표
    cols = {}
    for a in range(0, 100, 10):
        w = multipliers(CASE2_RUNS / f"case2_{a}")
        if len(w) != N_STEPS:
            raise RuntimeError(f"A{a}: 타임스텝 수 {len(w)} != {N_STEPS}")
        for z in ZONES:
            cols[f"A{a:02d}_{z}"] = w[f"DLC_{z}".upper()].to_numpy()
    table = pd.DataFrame(cols)
    table.insert(0, "step", range(N_STEPS))
    dl_path = HERE / "dl_mult_tmyx2011_L400.csv"
    table.to_csv(dl_path, index=False, float_format="%.5f")
    print(f"[*] {dl_path.name}")

    # 2. 오라클 스케줄
    lab = pd.read_csv(MM / "labels" / "mm_label_test_useful_lam0.05_tol0.0.csv")
    base = pd.read_csv(ROOT / BASELINE)
    month = (pd.to_datetime(lab["timestamp"]) - pd.Timedelta(minutes=10)).dt.month
    angle = base["optimal_angle"].where(~month.isin(WINTER).to_numpy(), lab["angle"].to_numpy())
    (HERE / "schedules").mkdir(exist_ok=True)
    orc_path = HERE / "schedules" / "oracle_test.csv"
    pd.DataFrame({"timestamp": lab["timestamp"], "optimal_angle": angle.astype(int)}).to_csv(orc_path, index=False)
    print(f"[*] {orc_path.name}")

    # 3. 배치
    schedules = {
        "suntracking": BASELINE,
        "tide_strict": "bipv_mismatch/schedules/tide_mm_test_night_strict.csv",
        "tide_tie": "bipv_mismatch/schedules/tide_mm_test_night_tie.csv",
        "oracle": rel(orc_path),
    }
    jobs = []
    for sname, sched in schedules.items():
        for pname, (start, days) in PERIODS.items():
            name = f"w_{sname}_{pname}"
            jobs.append({
                "name": name, "case": "case3", "idf": "bipv_experiments/idf/case3_v3_south_fixed.idf",
                "schedule": sched, "weather": WEATHER, "start": start, "days": days,
                "lw": True, "daylight_table": rel(dl_path),
                "solar_distribution": "FullExterior",
                "ideal_sizing_from": "bipv_experiments/sizing/case2_max_over_angles.eio",
                "economizer": "DifferentialEnthalpy", "pv_bandgap": 1.25,
                "extra_outputs": ["Generator Produced DC Electricity Energy",
                                  "Zone Ideal Loads Supply Air Total Cooling Energy",
                                  "Zone Ideal Loads Supply Air Total Heating Energy"],
                "out_dir": f"bipv_mismatch/eplus_winter/runs/{name}",
            })
    (HERE / "batch.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[*] batch.json: {len(jobs)} jobs")


if __name__ == "__main__":
    main()

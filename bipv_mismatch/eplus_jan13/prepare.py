"""
eplus_jan13/prepare.py
======================
겨울 대표일(1/13, IWEC) 잉여 시간대만 90°(수평, 개방)로 두는 case3 E+ 실험 준비.

- 잉여 구간: fig41 (c3_FE_suntracking_od) 기준 10:20~14:10 → 구간 종료 라벨 10:30~14:10 (23스텝)
- 나머지 시각은 기준안 태양추적(bipv_experiments/schedules/suntracking_w0s90.csv) 그대로
- 기간 1/6~1/14: 1/6~1/12 예열(스케줄이 기준안과 같으므로 연간 실행과 일치하는지 검증용), 1/13 07시~1/14 07시 평가
- 설정은 pv_lw_daylight case3 최종 연간 실행(c3_FE_ST_lw_dl400)과 같음 → 기준안은 그 연간 결과를 그대로 쓴다

출력: eplus_jan13/{schedules/st_jan13_surplus90.csv, batch.json}
실행: python pv_lw_daylight/run_pvlw.py --batch bipv_mismatch/eplus_jan13/batch.json --jobs 1
"""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASELINE = "bipv_experiments/schedules/suntracking_w0s90.csv"
SURPLUS_START, SURPLUS_END = "2026-01-13 10:30", "2026-01-13 14:10"  # 구간 종료 라벨 기준
OPEN_ANGLE = 90


def main():
    sched = pd.read_csv(ROOT / BASELINE, parse_dates=["timestamp"])
    m = (sched["timestamp"] >= SURPLUS_START) & (sched["timestamp"] <= SURPLUS_END)
    if m.sum() != 23:
        raise ValueError(f"잉여 구간 행 {m.sum()}개 (기대 23)")
    print("기준 각도:", sched.loc[m, "optimal_angle"].value_counts().sort_index().to_dict())
    sched.loc[m, "optimal_angle"] = OPEN_ANGLE
    out = HERE / "schedules" / "st_jan13_surplus90.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    sched.to_csv(out, index=False, date_format="%Y-%m-%d %H:%M:%S")

    job = {
        "name": "jan13_surplus90", "case": "case3",
        "idf": "bipv_experiments/idf/case3_v3_south_fixed.idf",
        "schedule": str(out.relative_to(ROOT)).replace("\\", "/"),
        "start": "01-06", "days": 9,
        "lw": True, "daylight_table": "pv_lw_daylight/daylight_tables/dl_mult_FE_L400.csv",
        "solar_distribution": "FullExterior",
        "ideal_sizing_from": "bipv_experiments/sizing/case2_max_over_angles.eio",
        "economizer": "DifferentialEnthalpy", "pv_bandgap": 1.25,
        "extra_outputs": ["Zone Mean Air Temperature", "Surface Window Transmitted Solar Radiation Energy"],
        "out_dir": "bipv_mismatch/eplus_jan13/runs/jan13_surplus90",
    }
    (HERE / "batch.json").write_text(json.dumps([job], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] {out}\n[*] {HERE / 'batch.json'}")


if __name__ == "__main__":
    main()

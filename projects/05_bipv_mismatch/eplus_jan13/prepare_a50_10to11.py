"""
eplus_jan13/prepare_a50_10to11.py
=================================
jan13_surplus90 변형: 1/13 10:00~11:00 만 50°, 11:00~14:10 은 그대로 90°, 나머지는 태양추적.

- 기반 스케줄: schedules/st_jan13_surplus90.csv (prepare.py 출력, 수정하지 않음)
- 10:00~11:00 → 구간 종료 라벨 10:10~11:00 (6스텝)
- 설정은 jan13_surplus90 과 같음 (기간 1/6~1/14, lw, 주광 L400, FullExterior, Eg 1.25)

출력: eplus_jan13/{schedules/st_jan13_a50_10to11.csv, batch_a50_10to11.json}
실행: python projects/04_pv_lw_daylight/run_pvlw.py --batch projects/05_bipv_mismatch/eplus_jan13/batch_a50_10to11.json --jobs 1
"""

import json
from pathlib import Path

import pandas as pd
from shared.paths import ROOT

HERE = Path(__file__).resolve().parent
BASE = HERE / "schedules" / "st_jan13_surplus90.csv"
START, END = "2026-01-13 10:10", "2026-01-13 11:00"  # 구간 종료 라벨 기준
ANGLE = 50
NAME = "jan13_a50_10to11"


def main():
    sched = pd.read_csv(BASE, parse_dates=["timestamp"])
    m = (sched["timestamp"] >= START) & (sched["timestamp"] <= END)
    if m.sum() != 6:
        raise ValueError(f"변경 구간 행 {m.sum()}개 (기대 6)")
    print("기존 각도:", sched.loc[m, "optimal_angle"].tolist())
    sched.loc[m, "optimal_angle"] = ANGLE
    out = HERE / "schedules" / "st_jan13_a50_10to11.csv"
    sched.to_csv(out, index=False, date_format="%Y-%m-%d %H:%M:%S")

    job = json.loads((HERE / "batch.json").read_text(encoding="utf-8"))[0]
    job.update(name=NAME, schedule=out.relative_to(ROOT).as_posix(),
               out_dir=f"projects/05_bipv_mismatch/eplus_jan13/runs/{NAME}")
    batch = HERE / "batch_a50_10to11.json"
    batch.write_text(json.dumps([job], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] {out}\n[*] {batch}")


if __name__ == "__main__":
    main()

"""
bipv_experiments/analysis/build_oracle_schedule.py
==================================================
고정각 데이터셋에서 timestep별 '참' 최적 각도 스케줄을 만든다.
  --mode net  : net energy 최소 각도 (근시안적 oracle)
  --mode pv   : PV 발전 최대 각도
모든 각도가 동률인 스텝(주로 야간)은 기준 스케줄(태양추적) 각도를 쓴다.

사용 예:
  python bipv_experiments/analysis/build_oracle_schedule.py --dataset <csv> --mode net --out bipv_experiments/schedules/oracle_stepwise.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path(__file__).resolve().parents[1]
ANGLES = np.arange(0, 100, 10)
TIE_TOL = 1e-9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--mode", choices=["net", "pv"], default="net")
    ap.add_argument("--fallback", type=Path, default=EXP_DIR / "schedules" / "suntracking_w0s90.csv")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.dataset)
    fb = pd.read_csv(args.fallback)
    if args.mode == "net":
        mat = df[[f"net_energy_{a}" for a in ANGLES]].values
        best = mat.argmin(axis=1)
    else:
        mat = df[[f"pv_gen_{a}" for a in ANGLES]].values
        best = mat.argmax(axis=1)
    tie = (mat.max(axis=1) - mat.min(axis=1)) <= TIE_TOL
    sched = np.where(tie, fb["optimal_angle"].values, ANGLES[best])

    pd.DataFrame({"timestamp": fb["timestamp"], "optimal_angle": sched}).to_csv(args.out, index=False)
    print(f"[*] saved {args.out}  tie steps {tie.sum():,}  switches {(np.diff(sched) != 0).sum():,}")


if __name__ == "__main__":
    main()

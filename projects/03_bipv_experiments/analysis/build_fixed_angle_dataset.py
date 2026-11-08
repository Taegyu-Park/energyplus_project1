"""
bipv_experiments/analysis/build_fixed_angle_dataset.py
======================================================
고정각(0~90°) 연간 run 10개(runs/<prefix>A00 ~ A90)에서 timestep 데이터셋을 만든다.
컬럼 형식은 ai_model/tide 의 case2 데이터셋과 같다 (pv_gen_{a}, cool_load_{a}, heat_load_{a}, net_energy_{a}).

사용 예:
  python bipv_experiments/analysis/build_fixed_angle_dataset.py --prefix fixed_ --out bipv_experiments/analysis/case3_fixed_angle_dataset.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from sql_extract import extract_loads_pv, extract_weather

EXP_DIR = Path(__file__).resolve().parents[1]
ANGLES = list(range(0, 100, 10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True, help="runs/ 아래 고정각 run 이름 접두사 (예: fixed_)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    runs = EXP_DIR / "runs"
    df = extract_weather(runs / f"{args.prefix}A00" / "eplusout.sql")
    parts = [extract_loads_pv(runs / f"{args.prefix}A{a:02d}" / "eplusout.sql", str(a)) for a in ANGLES]
    angle_df = pd.concat(parts, axis=1)
    angle_df.index = df.index
    df = pd.concat([df, angle_df], axis=1)

    net = df[[f"net_energy_{a}" for a in ANGLES]].values
    df["optimal_angle"] = np.array(ANGLES)[net.argmin(axis=1)]
    df["optimal_net_energy"] = net.min(axis=1)
    if df.isnull().values.any():
        raise ValueError("NaN in dataset")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out)
    print(f"[*] saved {args.out} {df.shape}")
    for a in ANGLES:
        print(f"    fixed {a:>2}: net {df[f'net_energy_{a}'].sum():10.1f} kWh")


if __name__ == "__main__":
    main()

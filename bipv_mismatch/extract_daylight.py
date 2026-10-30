"""
extract_daylight.py
===================
dataset_final 의 3개 기상 폴더 × 10개 각도 SQL에서 남측 존 주광 기준점 조도를 뽑는다.
잉여 시점 각도 선택(채광 최대화) 라벨용 보조 테이블. build_dataset.py 출력은 건드리지 않는다.

- illum_{a}: DLC_BIPV_OFFICE_{1,2}_S 기준점 1 조도 평균 (lux)
- dlmult_{a}: 같은 두 존 조명 전력 배율 평균 (0.3~1)

출력: bipv_mismatch/dataset_final/daylight_{train,val,test}.csv (timestamp 는 case2_mm_*.csv 와 같은 순서)
"""

import pandas as pd
from pathlib import Path

from build_dataset import ANGLES, BASE_DIR, FINAL_SPLITS, read_vars, series

DL_VARS = ["Daylighting Reference Point 1 Illuminance", "Daylighting Lighting Power Multiplier"]


def main():
    out_dir = BASE_DIR / "dataset_final"
    for name, folder in FINAL_SPLITS.items():
        ts = pd.read_csv(out_dir / f"case2_mm_{name}.csv", usecols=["timestamp"])["timestamp"]
        cols = {}
        for a in ANGLES:
            raw = read_vars(BASE_DIR / folder / f"case2_{a}" / "eplusout.sql", DL_VARS)
            cols[f"illum_{a}"] = series(raw, DL_VARS[0], agg="mean").to_numpy()
            cols[f"dlmult_{a}"] = series(raw, DL_VARS[1], agg="mean").to_numpy()
        df = pd.DataFrame(cols)
        if len(df) != len(ts):
            raise ValueError(f"{name}: 행 수 {len(df)} ≠ {len(ts)}")
        df.insert(0, "timestamp", ts.to_numpy())
        df.to_csv(out_dir / f"daylight_{name}.csv", index=False)
        print(f"[*] {name} ({folder}) → daylight_{name}.csv")


if __name__ == "__main__":
    main()

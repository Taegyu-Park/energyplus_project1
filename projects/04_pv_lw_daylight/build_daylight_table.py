"""
pv_lw_daylight/build_daylight_table.py
=======================================================
case2 각도별 주광 실행(runs/tbl_FE_L<lx>_A<각도>)에서 남측 2개 존의 'Daylighting Lighting Power Multiplier'를 뽑아
case3 플러그인(DaylightTableCoupler)이 쓰는 표를 만든다.

- 행: 연간 10분 타임스텝 52,560개 (1/1 00:10 → 12/31 24:00, 웜업 제외)
- 열: step, A00_BIPV_office_1_S, A00_BIPV_office_2_S, ..., A90_BIPV_office_2_S
- 출력: daylight_tables/dl_mult_FE_L<lx>.csv

사용: python pv_lw_daylight/build_daylight_table.py --lx 300 400 600
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs" / "daylight_table"
OUT = HERE / "daylight_tables"
ZONES = ["BIPV_office_1_S", "BIPV_office_2_S"]
N_STEPS = 52560


def multipliers(run: Path) -> pd.DataFrame:
    conn = sqlite3.connect(run / "eplusout.sql")
    df = pd.read_sql(
        """SELECT rd.TimeIndex, d.KeyValue, rd.Value FROM ReportData rd
           JOIN ReportDataDictionary d ON rd.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
           JOIN Time t ON rd.TimeIndex = t.TimeIndex
           WHERE d.Name = 'Daylighting Lighting Power Multiplier' AND t.WarmupFlag = 0
             AND t.EnvironmentPeriodIndex = (SELECT MAX(EnvironmentPeriodIndex) FROM Time)""", conn)
    conn.close()
    wide = df.pivot(index="TimeIndex", columns="KeyValue", values="Value").sort_index()
    wide.columns = [c.upper() for c in wide.columns]
    return wide


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lx", type=int, nargs="+", default=[300, 400, 600])
    ap.add_argument("--prefix", default="tbl_FE")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for lx in args.lx:
        cols = {}
        for a in range(0, 100, 10):
            w = multipliers(RUNS / f"{args.prefix}_L{lx}_A{a:02d}")
            if len(w) != N_STEPS:
                raise RuntimeError(f"L{lx} A{a}: 타임스텝 수 {len(w)} != {N_STEPS}")
            for z in ZONES:
                cols[f"A{a:02d}_{z}"] = w[f"DLC_{z}".upper()].to_numpy()
        out = pd.DataFrame(cols)
        out.insert(0, "step", range(N_STEPS))
        path = OUT / f"dl_mult_{args.prefix.split('_', 1)[1]}_L{lx}.csv"
        out.to_csv(path, index=False, float_format="%.5f")
        day = out.iloc[:, 1:]
        print(f"{path.name}: 각도별 평균 배율(전체 시간) " +
              " ".join(f"A{a:02d}={day[[f'A{a:02d}_{z}' for z in ZONES]].to_numpy().mean():.3f}" for a in range(0, 100, 10)))


if __name__ == "__main__":
    main()

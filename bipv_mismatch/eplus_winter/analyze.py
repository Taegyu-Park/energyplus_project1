"""
eplus_winter/analyze.py
=======================
case3 폐루프 일주일 실행(prepare.py 배치) 결과를 10분 단위로 다시 계산해 비교한다.

- PV = Generator Produced DC Electricity Energy 합 (선택 각도 발전기만 발전, 데이터셋 pv_gen 과 같은 정의)
- 수요 = 냉방/3.0 + 난방/2.5 + 조명(전체 존), 구매 = max(수요 − PV, 0), 잉여(버림) = max(PV − 수요, 0)
- 조도: case3 는 주광을 직접 계산하지 않음 → case2 TMYx2011 각도별 조도(dataset_final/daylight_test.csv)에서 스케줄 각도 값
- 오프라인 추정: case2 고정각 결과(dataset_final/case2_mm_test.csv)를 스케줄 각도로 골라 붙인 값 (학습·라벨과 같은 계산)
- 집계 기간: prepare.REPORT (평일 + 일주일 전체)

출력: eplus_winter/results_week.csv, 표준 출력
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MM = HERE.parent
sys.path.insert(0, str(MM))
from prepare import REPORT  # noqa: E402

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
J_TO_KWH = 1 / 3.6e6
VARS = ["Generator Produced DC Electricity Energy", "Zone Ideal Loads Supply Air Total Cooling Energy",
        "Zone Ideal Loads Supply Air Total Heating Energy", "Zone Lights Electricity Energy"]
RUNS = {"태양추적": "w_suntracking_wk", "TiDE 엄격": "w_tide_strict_wk",
        "TiDE 야간동점": "w_tide_tie_wk", "오라클": "w_oracle_wk"}
SCHED = {"태양추적": MM.parent / "bipv_experiments/schedules/suntracking_w0s90.csv",
         "TiDE 엄격": MM / "schedules/tide_mm_test_night_strict.csv",
         "TiDE 야간동점": MM / "schedules/tide_mm_test_night_tie.csv",
         "오라클": HERE / "schedules/oracle_test.csv"}


def read_run(run: Path) -> pd.DataFrame:
    q = f"""SELECT t.Month, t.Day, t.Hour, t.Minute, d.Name, SUM(r.Value) AS v
            FROM ReportData r JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON r.TimeIndex = t.TimeIndex
            WHERE t.WarmupFlag = 0 AND d.ReportingFrequency = 'Zone Timestep' AND d.Name IN ({",".join("?" * len(VARS))})
            GROUP BY t.TimeIndex, d.Name"""
    with sqlite3.connect(run / "eplusout.sql") as c:
        df = pd.read_sql(q, c, params=VARS)
    ts = pd.to_datetime(dict(year=2006, month=df.Month, day=df.Day)) + pd.to_timedelta(df.Hour * 60 + df.Minute, "m")
    w = df.assign(ts=ts).pivot(index="ts", columns="Name", values="v").fillna(0.0) * J_TO_KWH
    out = pd.DataFrame(index=w.index)
    out["pv"] = w[VARS[0]]
    out["demand"] = w[VARS[1]] / 3.0 + w[VARS[2]] / 2.5 + w[VARS[3]]
    return out


def summarize(df: pd.DataFrame, angle: np.ndarray, illum: np.ndarray, name: str, src: str) -> list:
    purchase = (df["demand"] - df["pv"]).clip(lower=0)
    surplus = (df["pv"] - df["demand"]).clip(lower=0)
    move = np.r_[0, np.abs(np.diff(angle))]
    t = df.index - pd.Timedelta(minutes=10)
    rows = []
    for tag, m in [("평일", t.dayofweek < 5), ("일주일", np.ones(len(df), bool))]:
        m = np.asarray(m)
        nd = m.sum() / 144
        r2 = m & (surplus.to_numpy() > 0)
        rows.append({"안": name, "계산": src, "기간": tag,
                     "수요kWh": df["demand"][m].sum(), "PVkWh": df["pv"][m].sum(),
                     "구매kWh": purchase[m].sum(), "버린PVkWh": surplus[m].sum(),
                     "미스매치kWh": purchase[m].sum() + surplus[m].sum(),
                     "잉여시점조도lx": illum[r2].mean() if r2.any() else np.nan,
                     "잉여시점>1500lx%": (illum[r2] > 1500).mean() * 100 if r2.any() else np.nan,
                     "이동회/일": (move[m] > 0).sum() / nd, "이동°/일": move[m].sum() / nd})
    return rows


def main():
    lo, hi = pd.Timestamp(REPORT[0]) + pd.Timedelta(minutes=10), pd.Timestamp(REPORT[1]) + pd.Timedelta(days=1)
    c2 = pd.read_csv(MM / "dataset_final/case2_mm_test.csv", usecols=["timestamp"] + [f"{c}_{a}" for c in ["pv_gen", "demand_elec"] for a in ANGLES])
    dl = pd.read_csv(MM / "dataset_final/daylight_test.csv", usecols=["timestamp"] + [f"illum_{a}" for a in ANGLES])
    c2.index = dl.index = pd.to_datetime(c2["timestamp"])
    c2, dl = c2.loc[lo:hi], dl.loc[lo:hi]
    rows = []
    for name, run in RUNS.items():
        s = pd.read_csv(SCHED[name])
        s.index = pd.to_datetime(s["timestamp"]).map(lambda x: x.replace(year=2006))
        angle = s.loc[lo:hi, "optimal_angle"].to_numpy()
        idx = np.searchsorted(ANGLES, angle)
        r = np.arange(len(idx))
        illum = dl[[f"illum_{a}" for a in ANGLES]].to_numpy()[r, idx]
        off = pd.DataFrame({"pv": c2[[f"pv_gen_{a}" for a in ANGLES]].to_numpy()[r, idx],
                            "demand": c2[[f"demand_elec_{a}" for a in ANGLES]].to_numpy()[r, idx]}, index=c2.index)
        rows += summarize(off, angle, illum, name, "오프라인(case2)")
        p = HERE / "runs" / run / "eplusout.sql"
        if (p.parent / "summary.json").exists():  # 실행 완료된 것만 (실행 중 SQL 은 잠겨 있음)
            ep = read_run(p.parent).loc[lo:hi]
            if len(ep) != len(off):
                raise ValueError(f"{run}: 스텝 수 {len(ep)} != {len(off)}")
            rows += summarize(ep, angle, illum, name, "E+ case3")
    res = pd.DataFrame(rows)
    res.to_csv(HERE / "results_week.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    for tag in ["평일", "일주일"]:
        print(f"\n===== {REPORT[0]} ~ {REPORT[1]} {tag} =====")
        print(res[res["기간"] == tag].drop(columns="기간").set_index(["계산", "안"]).round(1).to_string())


if __name__ == "__main__":
    main()

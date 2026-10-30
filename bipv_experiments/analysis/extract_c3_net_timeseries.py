"""c3 동적 One-Diode run(태양추적, TiDE S1/S2)의 10분 단위 net energy 시계열을 CSV 한 개로 캐시한다.
출력: analysis/c3_net_timeseries_onediode.csv  (timestamp, {ST,S1,S2}_{pv,cool,heat,net}, angle_{ST,S1,S2})
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from sql_extract import extract_loads_pv

EXP = Path(__file__).resolve().parents[1]
RUNS = {"ST": "c3_FE_suntracking_od", "S1": "c3_FE_tide_s1_od", "S2": "c3_FE_tide_s2_od"}
SCHED = {"ST": "suntracking_w0s90", "S1": "tide_s1_current", "S2": "tide_s2_current"}

out = None
for k, run in RUNS.items():
    df = extract_loads_pv(EXP / "runs" / run / "eplusout.sql", suffix=k)
    print(k, len(df), flush=True)
    sch = pd.read_csv(EXP / "schedules" / f"{SCHED[k]}.csv")
    df.insert(0, "timestamp", sch["timestamp"].values[: len(df)])
    df[f"angle_{k}"] = sch["optimal_angle"].values[: len(df)]
    out = df if out is None else out.merge(df.drop(columns="timestamp"), left_index=True, right_index=True)
out.to_csv(EXP / "analysis" / "c3_net_timeseries_onediode.csv", index=False)
print(out.shape)

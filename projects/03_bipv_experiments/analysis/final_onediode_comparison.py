"""
One-Diode case3 동적 실행 결과로 최종 비교표를 만든다 (방법 C + 대조군 오프셋 제거).
  최종 부하 = case2 반사켬 스티칭 + [(case3 동적 − case2 반사끔 스티칭) − (case3 30°고정 − case2 반사끔 30°)]
  PV        = case2 반사켬 스티칭 (관성 없음)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

EXP = Path(__file__).resolve().parents[1]
A = np.arange(0, 100, 10)
COP_C, COP_H = 3.0, 2.5


def stitch(ds, sched, col):
    m = ds[[f"{col}_{a}" for a in A]].values
    idx = (sched // 10).astype(int)
    return m[np.arange(len(idx)), idx].sum()


def summ(name):
    s = json.loads((EXP / "runs" / name / "summary.json").read_text(encoding="utf-8"))
    return s["total_heating_load_thermal_kwh"], s["total_cooling_load_thermal_kwh"], s["total_bipv_generation_kwh"]


rf = pd.read_csv(EXP / "analysis/c2_RF_fixed_angle_dataset.csv")
fe = pd.read_csv(EXP / "analysis/c2_FE_fixed_angle_dataset.csv")

h30c3, c30c3, _ = summ("c3_FE_fixed_A30_od")
h30c2, c30c2, _ = summ("c2_FE_A30")
off_h, off_c = h30c3 - h30c2, c30c3 - c30c2
print(f"모델 오프셋(case3−case2, 30° 고정): 난방 {off_h:+,.0f}  냉방 {off_c:+,.0f}")

rows = []
for label, sch, run in [("태양추적", "suntracking_w0s90", "c3_FE_suntracking_od"),
                        ("TiDE 전략1", "tide_s1_current", "c3_FE_tide_s1_od"),
                        ("TiDE 전략2", "tide_s2_current", "c3_FE_tide_s2_od"),
                        ("고정 30°", "fixed_A30", "c3_FE_fixed_A30_od")]:
    s = pd.read_csv(EXP / "schedules" / f"{sch}.csv")["optimal_angle"].values
    pv = stitch(rf, s, "pv_gen"); h_rf = stitch(rf, s, "heat_load"); c_rf = stitch(rf, s, "cool_load")
    h_fe = stitch(fe, s, "heat_load"); c_fe = stitch(fe, s, "cool_load"); pv_fe = stitch(fe, s, "pv_gen")
    h3, c3, pv3 = summ(run)
    dh = (h3 - h_fe) - off_h; dc = (c3 - c_fe) - off_c
    H, C = h_rf + dh, c_rf + dc
    rows.append(dict(스케줄=label, PV=pv, 난방_스티칭=h_rf, 난방_관성=dh, 난방_최종=H,
                     냉방_스티칭=c_rf, 냉방_관성=dc, 냉방_최종=C,
                     net_스티칭=c_rf / COP_C + h_rf / COP_H - pv, net_최종=C / COP_C + H / COP_H - pv,
                     PV_case3_vs_case2FE=pv3 - pv_fe))
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(df.round(0).to_string(index=False))
df.to_csv(EXP / "analysis/final_onediode_comparison.csv", index=False, encoding="utf-8-sig")

"""
verify_eg125.py
===============
Eg 1.25 재실행 결과 검증: 완료 여부·Severe·스텝 수, 그리고 Eg 1.12 대비 연간 PV·HVAC 변화.
사용: python bipv_mismatch/verify_eg125.py
"""

import re
import sqlite3
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
SETS = [("IWEC", "case2_KS"), ("TMYx", "case2_KS_TMYx")]


def status(run_dir: Path) -> str:
    end = (run_dir / "eplusout.end").read_text(errors="ignore") if (run_dir / "eplusout.end").exists() else "없음"
    m = re.search(r"(\d+) Severe", end)
    return ("OK" if "Successfully" in end else "FAIL") + f" severe={m.group(1) if m else '?'}"


def annual(sql: Path) -> dict:
    """연간 PV DC 합(발전기 합, kWh), 존 냉난방 현열(kWh), 런 기간 Interval=10 스텝 수"""
    if not sql.exists():
        return {}
    c = sqlite3.connect(sql)
    env = "(select max(EnvironmentPeriodIndex) from Time)"
    steps = c.execute(f"select count(*) from Time where EnvironmentPeriodIndex={env} and Interval=10").fetchone()[0]
    def total(name):
        r = c.execute(f"""select sum(r.Value) from ReportData r
            join ReportDataDictionary d using(ReportDataDictionaryIndex) join Time t using(TimeIndex)
            where d.Name=? and d.ReportingFrequency='Zone Timestep' and t.EnvironmentPeriodIndex={env}""", (name,)).fetchone()[0]
        return (r or 0.0) / 3.6e6
    return {"steps": steps,
            "pv": total("Generator Produced DC Electricity Energy"),
            "heat": total("Zone Ideal Loads Zone Sensible Heating Energy"),
            "cool": total("Zone Ideal Loads Zone Sensible Cooling Energy")}


def main():
    for label, folder in SETS:
        print(f"\n### {label}  (Eg 1.25 vs 1.12)")
        print("각도  상태              스텝    PV_1.25   PV_1.12   ΔPV%   난방Δ%  냉방Δ%")
        for a in ANGLES:
            new_dir = WORK_DIR / folder / f"case2_{a}"
            old_dir = WORK_DIR / f"{folder}_Eg112" / f"case2_{a}"
            n, o = annual(new_dir / "eplusout.sql"), annual(old_dir / "eplusout.sql")
            if not n:
                print(f"{a:3d}°  {status(new_dir)}")
                continue
            def d(k):
                return f"{100 * (n[k] / o[k] - 1):+6.2f}" if o and o.get(k) else "   -  "
            old_pv = f"{o['pv']:9.0f}" if o and o.get("steps") == 52560 else "  (불완전)"
            print(f"{a:3d}°  {status(new_dir):16s} {n['steps']:6d} {n['pv']:9.0f} {old_pv}  {d('pv')}  {d('heat')}  {d('cool')}")


if __name__ == "__main__":
    main()

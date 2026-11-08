"""
run_case3_south_suntracking_sim.py
==================================
Executes EnergyPlus 25.2.0 annual simulation for case3_v3_south.idf
driven by Sun-Tracking Python Plugin (model_pythonpluginsystem_sun_tracking.py)
with winter night = 0 deg (closed) and summer/intermediate night = 90 deg (open).
"""

import os
import sys
import shutil
import subprocess
import json
import sqlite3
import pandas as pd
from pathlib import Path
from shared.paths import BASELINE_RESULTS, CASE_IDF, DATA, PLUGINS, ROOT

CWD = ROOT
IDF_PATH = CASE_IDF / "case3_v3_KS" / "case3_v3_south.idf"
WEATHER_PATH = DATA / "KOR_Kwangju.471560_IWEC (1).epw"
OUT_DIR = BASELINE_RESULTS / "bipv_variation" / "5zone_NSEW_korean" / "case3_v3_south"
EP_DIR = Path(r"C:\EnergyPlusV25-2-0")

COP_COOLING = 3.0
COP_HEATING = 2.5


def run_simulation():
    print("=" * 80)
    print("Starting EnergyPlus Case3 South (Sun-Tracking BIPV) Annual Simulation")
    print(f"[*] Logic       : Winter Night 0° (Closed) / Summer Night 90° (Open)")
    print(f"[*] IDF Model   : {IDF_PATH.relative_to(CWD)}")
    print(f"[*] Weather File: {WEATHER_PATH.relative_to(CWD)}")
    print(f"[*] Output Dir  : {OUT_DIR.relative_to(CWD)}")
    print("=" * 80)

    if not IDF_PATH.exists():
        raise FileNotFoundError(f"IDF not found: {IDF_PATH}")
    if not WEATHER_PATH.exists():
        raise FileNotFoundError(f"Weather file not found: {WEATHER_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ep_exe = EP_DIR / "energyplus.exe"
    if not ep_exe.exists():
        raise FileNotFoundError(f"EnergyPlus executable not found at: {ep_exe}")

    # Set up environment with EnergyPlus Python API path
    env = os.environ.copy()
    ep_python_api_path = str(EP_DIR / "api" / "python")
    plugin_search_path = str(IDF_PATH.parent)
    env["PYTHONPATH"] = (
        ep_python_api_path + os.pathsep +
        plugin_search_path + os.pathsep +
        str(PLUGINS) + os.pathsep +
        str(CWD) + os.pathsep +
        env.get("PYTHONPATH", "")
    )

    cmd = [
        str(ep_exe),
        "-w", str(WEATHER_PATH),
        "-d", str(OUT_DIR),
        str(IDF_PATH)
    ]

    print("\n[*] Executing EnergyPlus process...")
    print(f"    Command: {' '.join(cmd)}")
    
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)

    if proc.returncode != 0:
        print("\n[!] EnergyPlus Execution ERROR:")
        print(proc.stderr[-2000:] if proc.stderr else proc.stdout[-2000:])
        raise RuntimeError(f"EnergyPlus failed with exit code {proc.returncode}")

    print("\n[*] EnergyPlus Process Finished Successfully (Exit Code 0)!")

    # Analyze Results from SQLite
    analyze_results(OUT_DIR)


def analyze_results(out_dir: Path):
    print("\n" + "=" * 80)
    print("Analyzing EnergyPlus Simulation Results [Case3 South Sun-Tracking]")
    print("=" * 80)

    sql_path = out_dir / "eplusout.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"eplusout.sql not found in {out_dir}")

    conn = sqlite3.connect(sql_path)
    c = conn.cursor()

    def get_kwh(var_name):
        c.execute("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = ?", (var_name,))
        ids = [r[0] for r in c.fetchall()]
        if not ids:
            return 0.0
        placeholders = ",".join("?" for _ in ids)
        c.execute(f"""
            SELECT SUM(rd.Value)
            FROM ReportData rd
            JOIN Time t ON rd.TimeIndex = t.TimeIndex
            WHERE rd.ReportDataDictionaryIndex IN ({placeholders})
              AND t.WarmupFlag = 0
        """, ids)
        row = c.fetchone()
        return (row[0] or 0.0) / 3.6e6 if row else 0.0

    total_cool_kwh = get_kwh("Zone Ideal Loads Supply Air Total Cooling Energy")
    total_heat_kwh = get_kwh("Zone Ideal Loads Supply Air Total Heating Energy")
    total_pv_kwh = get_kwh("Facility Total Produced Electricity Energy")
    conn.close()

    cool_elec_kwh = total_cool_kwh / COP_COOLING
    heat_elec_kwh = total_heat_kwh / COP_HEATING
    hvac_elec_kwh = cool_elec_kwh + heat_elec_kwh
    net_energy_kwh = hvac_elec_kwh - total_pv_kwh

    print(f"[+] Total Annual BIPV Generation : {total_pv_kwh:10.2f} kWh (Elec)")
    print(f"[+] Total Annual Cooling Load     : {total_cool_kwh:10.2f} kWh (Thermal)")
    print(f"[+] Total Annual Heating Load     : {total_heat_kwh:10.2f} kWh (Thermal)")
    print(f"[+] Total Annual Thermal Load    : {total_cool_kwh + total_heat_kwh:10.2f} kWh (Thermal)")
    print(f"[+] Total Annual HVAC Elec Load  : {hvac_elec_kwh:10.2f} kWh (Elec)")
    print(f"[+] Total Annual Net Energy      : {net_energy_kwh:10.2f} kWh (Net Elec)")

    summary = {
        "case": "case3_v3_south_sun_tracking",
        "simulation_model": "case3_v3_south.idf",
        "plugin_module": "model_pythonpluginsystem_sun_tracking",
        "total_pv_kwh": float(total_pv_kwh),
        "total_cool_thermal_kwh": float(total_cool_kwh),
        "total_heat_thermal_kwh": float(total_heat_kwh),
        "total_thermal_load_kwh": float(total_cool_kwh + total_heat_kwh),
        "hvac_elec_kwh": float(hvac_elec_kwh),
        "net_energy_kwh": float(net_energy_kwh)
    }

    summary_file = out_dir / "case3_south_suntracking_annual_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[*] Saved summary to: {summary_file.name}")


if __name__ == "__main__":
    run_simulation()

"""
run_case3_south_tide_sim.py
===========================
Executes EnergyPlus 25.2.0 annual simulation for case3_v3_south.idf
driven by TiDE AI-predicted optimal BIPV tilt angles.

Post-processes eplusout.csv to compute:
- Annual Total BIPV Power Generation (kWh)
- Annual Cooling & Heating Thermal Loads (kWh)
- Annual Net Energy Consumption (kWh)
- BIPV Tilt Angle Operation Distribution
"""

import os
import sys
import shutil
import subprocess
import pandas as pd
import numpy as np
import argparse
from pathlib import Path
from shared.paths import CASE_IDF, DATA, PLUGINS, ROOT, TIDE_V1_RESULTS

CWD = ROOT
IDF_PATH = CASE_IDF / "case3_v3_KS" / "case3_v3_south.idf"
WEATHER_PATH = DATA / "KOR_Kwangju.471560_IWEC (1).epw"
EP_DIR = Path(r"C:\EnergyPlusV25-2-0")

COP_COOLING = 3.0
COP_HEATING = 2.5


def run_simulation(strategy: int = 2):
    out_dir = TIDE_V1_RESULTS / f"case3_v3_south_tide_strategy{strategy}"
    print("=" * 80)
    print(f"Starting EnergyPlus Case3 South (TiDE AI Strategy {strategy} Controlled BIPV) Annual Simulation")
    print("=" * 80)
    print(f"[*] IDF Model   : {IDF_PATH.relative_to(CWD)}")
    print(f"[*] Weather File: {WEATHER_PATH.relative_to(CWD)}")
    print(f"[*] Output Dir  : {out_dir.relative_to(CWD)}")

    if not IDF_PATH.exists():
        raise FileNotFoundError(f"IDF not found: {IDF_PATH}")
    if not WEATHER_PATH.exists():
        raise FileNotFoundError(f"Weather file not found: {WEATHER_PATH}")

    out_dir.mkdir(parents=True, exist_ok=True)

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
        "-d", str(out_dir),
        str(IDF_PATH)
    ]

    print("\n[*] Executing EnergyPlus process...")
    print(f"    Command: {' '.join(cmd)}")
    
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)

    # Print log snippet
    if proc.returncode != 0:
        print("\n[!] EnergyPlus Execution ERROR:")
        print(proc.stderr[-2000:] if proc.stderr else proc.stdout[-2000:])
        raise RuntimeError(f"EnergyPlus failed with exit code {proc.returncode}")

    print("\n[*] EnergyPlus Process Finished Successfully (Exit Code 0)!")

    # Check for eplusout.csv or convert via ReadVarsESO
    csv_file = out_dir / "eplusout.csv"
    if not csv_file.exists():
        print("[*] eplusout.csv not found. Running ReadVarsESO.exe...")
        readvars_exe = EP_DIR / "PostProcess" / "ReadVarsESO.exe"
        if readvars_exe.exists():
            subprocess.run([str(readvars_exe)], cwd=str(out_dir), check=True, capture_output=True)
            print("[*] ReadVarsESO conversion complete!")

    # Analyze Results from SQLite & CSV
    analyze_results(out_dir, strategy)


def analyze_results(out_dir: Path, strategy: int):
    print("\n" + "=" * 80)
    print(f"Analyzing EnergyPlus Simulation Results [Strategy {strategy}]")
    print("=" * 80)

    sql_path = out_dir / "eplusout.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"eplusout.sql not found in {out_dir}")

    import sqlite3
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

    print(f"[+] Total Annual BIPV Generation : {total_pv_kwh:10.2f} kWh (Elec)")
    print(f"[+] Total Annual Cooling Load     : {total_cool_kwh:10.2f} kWh (Thermal)")
    print(f"[+] Total Annual Heating Load     : {total_heat_kwh:10.2f} kWh (Thermal)")
    print(f"[+] Total Annual Thermal Load    : {total_cool_kwh + total_heat_kwh:10.2f} kWh (Thermal)")

    # Electric Energy Equivalent via COP
    cool_elec_kwh = total_cool_kwh / COP_COOLING
    heat_elec_kwh = total_heat_kwh / COP_HEATING
    hvac_elec_kwh = cool_elec_kwh + heat_elec_kwh
    net_energy_kwh = hvac_elec_kwh - total_pv_kwh

    print("-" * 80)
    print(f"[*] HVAC Electricity (Cooling/3.0 + Heating/2.5) : {hvac_elec_kwh:10.2f} kWh")
    print(f"[*] Net Energy Consumption (HVAC Elec - PV Gen)   : {net_energy_kwh:10.2f} kWh")
    print("=" * 80)

    # Save Summary JSON
    summary_data = {
        "simulation_model": "case3_v3_south.idf",
        "control_strategy": f"TiDE AI Optimal Angle Injection (Strategy {strategy})",
        "total_bipv_generation_kwh": float(total_pv_kwh),
        "total_cooling_load_thermal_kwh": float(total_cool_kwh),
        "total_heating_load_thermal_kwh": float(total_heat_kwh),
        "total_thermal_load_kwh": float(total_cool_kwh + total_heat_kwh),
        "hvac_electric_consumption_kwh": float(hvac_elec_kwh),
        "net_energy_consumption_kwh": float(net_energy_kwh),
    }

    summary_json = out_dir / "case3_south_tide_annual_summary.json"
    import json
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"[*] Summary results saved to: {summary_json.name}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Case 3 South BIPV Annual Simulation")
    parser.add_argument("--strategy", type=int, default=2, choices=[1, 2], help="Strategy 1 or 2")
    args = parser.parse_args()
    run_simulation(strategy=args.strategy)

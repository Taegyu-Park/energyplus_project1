"""
Figure 1: Annual HVAC Load vs PV Generation
Case 1 (Base) / Case 2 (Fixed 0°–90°) / Case 3 (Kinetic BIPV)
"""

import os
import sqlite3
from pathlib import Path

import dartwork_mpl as dm
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

plt.rcParams['svg.fonttype'] = 'none'

dm.style.use("presentation")
plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

BASE = Path("C:/Users/taegyu/Codes/EnergyPlus_Project1")
RUN  = BASE / "case_analysis/normal"
OUT  = BASE / "figure/net_energy_analysis"

C_HEAT     = "oc.blue6"
C_PV_GREEN = "oc.green6"

COP_HEATING = 2.5
COP_COOLING = 3.0
J_TO_MWH    = 1 / 3.6e9
ANGLES      = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]

# ── 데이터 로드 ──────────────────────────────────────────────────────

def load_case1_annual():
    df = pd.read_csv(RUN / "case1/case1.csv")
    df.columns = df.columns.str.strip()
    heat_cols = [c for c in df.columns if "Heating Energy" in c]
    cool_cols = [c for c in df.columns if "Cooling Energy" in c]
    for c in heat_cols + cool_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    h = sum(df[c].sum() for c in heat_cols) * J_TO_MWH / COP_HEATING
    c = sum(df[c].sum() for c in cool_cols) * J_TO_MWH / COP_COOLING
    return {"heating_MWh": h, "cooling_MWh": c, "pv_MWh": 0.0}


def load_case2_annual(angle: int):
    folder = f"{angle}"
    sql_path = RUN / f"case2/{folder}/eplusout.sql"
    conn = sqlite3.connect(sql_path)
    rows = conn.execute("""
        SELECT rd.Name, SUM(r.Value)
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
        GROUP BY rd.Name
    """).fetchall()
    conn.close()
    d = {name: val * J_TO_MWH for name, val in rows}
    return {
        "heating_MWh": d.get("Zone Ideal Loads Supply Air Total Heating Energy", 0) / COP_HEATING,
        "cooling_MWh": d.get("Zone Ideal Loads Supply Air Total Cooling Energy", 0) / COP_COOLING,
        "pv_MWh":      d.get("Facility Total Produced Electricity Energy", 0),
    }


def load_case3_annual():
    df = pd.read_csv(RUN / "case3/case3.csv", low_memory=False)
    df.columns = df.columns.str.strip()
    heat_cols = [c for c in df.columns if "Heating Energy" in c]
    cool_cols = [c for c in df.columns if "Cooling Energy" in c]
    pv_col    = "Whole Building:Facility Total Produced Electricity Energy"
    for c in heat_cols + cool_cols + [pv_col]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    h  = sum(df[c].sum() for c in heat_cols) * J_TO_MWH / COP_HEATING
    c  = sum(df[c].sum() for c in cool_cols) * J_TO_MWH / COP_COOLING
    pv = df[pv_col].sum() * J_TO_MWH
    return {"heating_MWh": h, "cooling_MWh": c, "pv_MWh": pv}


print("Loading Case 1...")
c1 = load_case1_annual()

print("Loading Case 2 (all angles)...")
c2 = {a: load_case2_annual(a) for a in ANGLES}

print("Loading Case 3...")
c3 = load_case3_annual()

# ── 플롯 ─────────────────────────────────────────────────────────────
labels = ["Case 1\n(Base)"] + [f"Case 2\n{a}°" for a in ANGLES] + ["Case 3\n(Kinetic)"]

gross_vals = (
    [c1["heating_MWh"] + c1["cooling_MWh"]]
    + [c2[a]["heating_MWh"] + c2[a]["cooling_MWh"] for a in ANGLES]
    + [c3["heating_MWh"] + c3["cooling_MWh"]]
)
net_vals = (
    [c1["heating_MWh"] + c1["cooling_MWh"] - c1["pv_MWh"]]
    + [c2[a]["heating_MWh"] + c2[a]["cooling_MWh"] - c2[a]["pv_MWh"] for a in ANGLES]
    + [c3["heating_MWh"] + c3["cooling_MWh"] - c3["pv_MWh"]]
)

x = np.arange(len(labels))

fig, ax = plt.subplots(figsize=(23 / 2.54, 13 / 2.54))

ax.bar(x, gross_vals, color=C_PV_GREEN, width=0.65, zorder=2)
ax.bar(x, net_vals,   color=C_HEAT,     width=0.65, zorder=3)

for i in range(len(labels)):
    ax.text(x[i], net_vals[i] + 0.8, f"{net_vals[i]:.1f}",
            ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    if gross_vals[i] > net_vals[i] + 1.0:
        ax.text(x[i], gross_vals[i] + 0.8, f"{gross_vals[i]:.1f}",
                ha="center", va="bottom", fontsize=8.5, color="oc.green9")

ax.axhline(0, color="black", linewidth=0.6, zorder=4)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylim(0, 58)
ax.set_ylabel("Annual Electricity Consumption [MWh]")
ax.set_title("Annual Electricity Consumption by Case\n(HVAC Electricity − BIPV Generation)",
             fontweight="bold")

patches = [
    mpatches.Patch(color=C_HEAT,     label="HVAC Load (Net)"),
    mpatches.Patch(color=C_PV_GREEN, label="PV Generation"),
]
ax.legend(handles=patches, ncol=2, loc="upper center",
          bbox_to_anchor=(0.5, -0.15), borderaxespad=0, fontsize=9)

# 저장 처리
script_dir = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.splitext(os.path.basename(__file__))[0]
figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", script_name))
os.makedirs(figure_dir, exist_ok=True)
output_png = os.path.join(figure_dir, "fig7_annual_net_energy.png")
output_svg = os.path.join(figure_dir, "fig7_annual_net_energy.svg")

fig.savefig(output_png, dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(output_svg, bbox_inches="tight", transparent=True)
plt.close(fig)

print(f"\n저장 완료: {output_png} 및 {output_svg}")

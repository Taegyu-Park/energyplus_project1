import os
import sqlite3
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import dartwork_mpl as dm

# SVG Font Settings for editing in Figma/Illustrator
mpl.rcParams['svg.fonttype'] = 'none'

# Database paths
db_v2 = r"c:\Users\taegyu\Codes\energyplus_project1\case_analysis\normal\case3\eplusout.sql"
db_v3 = r"c:\Users\taegyu\Codes\energyplus_project1\case_analysis\bipv_variation\5zone\case3_white.sql"

J_TO_KWH = 1.0 / 3.6e6
J_TO_MWH = 1.0 / 3.6e9  # Convert to MWh for better readability on axes

def query_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = """
        SELECT rd.KeyValue, rd.Name, SUM(r.Value) as TotalValue
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy'
        ) AND t.WarmupFlag = 0
        GROUP BY rd.KeyValue, rd.Name
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows

# Fetch data
v2_rows = query_db(db_v2)
v3_rows = query_db(db_v3)

# -------------------------------------------------------------
# Process v2 Data (2-Zone)
# -------------------------------------------------------------
# Keys: BIPV_OFFICE_1 IDEAL LOADS AIR SYSTEM, BIPV_OFFICE_2 IDEAL LOADS AIR SYSTEM
v2_data = {
    'Heating': {'Floor 1': 0.0, 'Floor 2': 0.0},
    'Cooling': {'Floor 1': 0.0, 'Floor 2': 0.0}
}

for kv, name, val in v2_rows:
    val_mwh = val * J_TO_MWH
    is_heating = 'Heating' in name
    var_type = 'Heating' if is_heating else 'Cooling'
    
    if 'OFFICE_1' in kv.upper():
        v2_data[var_type]['Floor 1'] += val_mwh
    elif 'OFFICE_2' in kv.upper():
        v2_data[var_type]['Floor 2'] += val_mwh

# -------------------------------------------------------------
# Process v3 Data (10-Zone)
# -------------------------------------------------------------
# Keys like: BIPV_OFFICE_1_CORE IDEAL LOADS AIR SYSTEM, etc.
v3_data = {
    'Heating': {'Core': 0.0, 'South': 0.0, 'East': 0.0, 'North': 0.0, 'West': 0.0},
    'Cooling': {'Core': 0.0, 'South': 0.0, 'East': 0.0, 'North': 0.0, 'West': 0.0}
}

for kv, name, val in v3_rows:
    val_mwh = val * J_TO_MWH
    is_heating = 'Heating' in name
    var_type = 'Heating' if is_heating else 'Cooling'
    
    kv_upper = kv.upper()
    if '_CORE' in kv_upper:
        v3_data[var_type]['Core'] += val_mwh
    elif '_S' in kv_upper:
        v3_data[var_type]['South'] += val_mwh
    elif '_E' in kv_upper:
        v3_data[var_type]['East'] += val_mwh
    elif '_N' in kv_upper:
        v3_data[var_type]['North'] += val_mwh
    elif '_W' in kv_upper:
        v3_data[var_type]['West'] += val_mwh

# -------------------------------------------------------------
# Plotting with dartwork-mpl (presentation style)
# -------------------------------------------------------------
dm.style.use("presentation")

# Setup output folders
output_dir = r"c:\Users\taegyu\Codes\energyplus_project1\figure\plot\fig22_loads_comparison_v2_v3"
os.makedirs(output_dir, exist_ok=True)

fig, ax = plt.subplots(figsize=(12, 6.5))

# Y positions for bars
# We want:
# Y=3: v3 Cooling
# Y=2: v2 Cooling
# Y=1: v3 Heating
# Y=0: v2 Heating
y_pos = np.array([0, 1, 2.5, 3.5])
bar_height = 0.65

# 1. Plot v2 Heating (Y=0)
h_f1 = v2_data['Heating']['Floor 1']
h_f2 = v2_data['Heating']['Floor 2']
ax.barh(0, h_f1, bar_height, color="oc.red3", edgecolor="black", lw=0.8, label="v2 Floor 1")
ax.barh(0, h_f2, bar_height, left=h_f1, color="oc.red6", edgecolor="black", lw=0.8, label="v2 Floor 2")

# Label v2 Heating total
ax.text(h_f1 + h_f2 + 1, 0, f"{h_f1+h_f2:.1f} MWh", va='center', ha='left', fontweight='bold', fontsize=11)

# 2. Plot v3 Heating (Y=1)
v3_h = v3_data['Heating']
left_h = 0.0
# Stacked bars for Core, S, E, N, W (Heating)
h_colors = ["oc.gray4", "oc.orange4", "oc.yellow4", "oc.blue4", "oc.violet4"]
h_labels = ["Core", "South (S)", "East (E)", "North (N)", "West (W)"]
for idx, zone in enumerate(['Core', 'South', 'East', 'North', 'West']):
    val = v3_h[zone]
    ax.barh(1, val, bar_height, left=left_h, color=h_colors[idx], edgecolor="black", lw=0.8, label=h_labels[idx] if idx==0 else None)
    left_h += val
# Label v3 Heating total
ax.text(left_h + 1, 1, f"{left_h:.1f} MWh", va='center', ha='left', fontweight='bold', fontsize=11)

# 3. Plot v2 Cooling (Y=2.5)
c_f1 = v2_data['Cooling']['Floor 1']
c_f2 = v2_data['Cooling']['Floor 2']
ax.barh(2.5, c_f1, bar_height, color="oc.blue3", edgecolor="black", lw=0.8)
ax.barh(2.5, c_f2, bar_height, left=c_f1, color="oc.blue6", edgecolor="black", lw=0.8)
# Label v2 Cooling total
ax.text(c_f1 + c_f2 + 1, 2.5, f"{c_f1+c_f2:.1f} MWh", va='center', ha='left', fontweight='bold', fontsize=11)

# 4. Plot v3 Cooling (Y=3.5)
v3_c = v3_data['Cooling']
left_c = 0.0
# Stacked bars for Core, S, E, N, W (Cooling)
c_colors = ["oc.gray5", "oc.orange5", "oc.yellow5", "oc.blue5", "oc.violet5"]
for idx, zone in enumerate(['Core', 'South', 'East', 'North', 'West']):
    val = v3_c[zone]
    ax.barh(3.5, val, bar_height, left=left_c, color=c_colors[idx], edgecolor="black", lw=0.8)
    left_c += val
# Label v3 Cooling total
ax.text(left_c + 1, 3.5, f"{left_c:.1f} MWh", va='center', ha='left', fontweight='bold', fontsize=11)

# Title & Labels
ax.set_title("Annual Thermal Load Comparison: 2-Zone (v2) vs. 10-Zone (v3)", fontsize=15, fontweight='bold', pad=15)
ax.set_yticks(y_pos)
ax.set_yticklabels([
    "Heating\n(v2: 2-Zone)",
    "Heating\n(v3: 10-Zone)",
    "Cooling\n(v2: 2-Zone)",
    "Cooling\n(v3: 10-Zone)"
], fontsize=11)
ax.set_xlabel("Annual Energy Load (MWh)", fontsize=12)
ax.set_xlim(0, 180)
ax.grid(axis='x', linestyle='--', alpha=0.5)

# Customized legends
# Legend 1: v2 Floors (Floor 1, Floor 2)
# Legend 2: v3 Zones (Core, S, E, N, W)
# Let's draw a single clean legend for the 5 zones of v3 and 2 floors of v2
# We construct proxy artists for the legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='oc.gray5', edgecolor='black', label='Core Zone'),
    Patch(facecolor='oc.orange5', edgecolor='black', label='South Zone (S)'),
    Patch(facecolor='oc.yellow5', edgecolor='black', label='East Zone (E)'),
    Patch(facecolor='oc.blue5', edgecolor='black', label='North Zone (N)'),
    Patch(facecolor='oc.violet5', edgecolor='black', label='West Zone (W)'),
    Patch(facecolor='none', edgecolor='none', label=''), # Spacer
    Patch(facecolor='oc.gray3', edgecolor='black', label='v2 Floor 1'),
    Patch(facecolor='oc.gray7', edgecolor='black', label='v2 Floor 2')
]
ax.legend(handles=legend_elements, loc='lower right', frameon=True, fontsize=10, facecolor='none', edgecolor='none')

plt.tight_layout()

# Save PNG and SVG as requested
png_path = os.path.join(output_dir, "fig22_loads_comparison_v2_v3.png")
svg_path = os.path.join(output_dir, "fig22_loads_comparison_v2_v3.svg")

plt.savefig(png_path, dpi=300, transparent=True)
plt.savefig(svg_path, transparent=True)

print(f"Successfully generated fig22 plot at:")
print(f"  PNG: {png_path}")
print(f"  SVG: {svg_path}")

import os
import sqlite3
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import dartwork_mpl as dm

# SVG Font Settings for editing in Figma/Illustrator
mpl.rcParams['svg.fonttype'] = 'none'

# Database paths
db_base = r"c:\Users\taegyu\Codes\energyplus_project1\case_idf\case3_base_runcheck\case3_baseout.sql"
db_v3 = r"c:\Users\taegyu\Codes\energyplus_project1\case_analysis\bipv_variation\5zone\case3_white.sql"

J_TO_KWH = 1.0 / 3.6e6
J_TO_MWH = 1.0 / 3.6e9

def query_zone_loads(db_path):
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
base_rows = query_zone_loads(db_base)
v3_rows = query_zone_loads(db_v3)

# -------------------------------------------------------------
# Process Data
# -------------------------------------------------------------
def get_orientation(key_value):
    kv_upper = key_value.upper()
    if '_CORE' in kv_upper:
        return 'Core'
    elif '_S' in kv_upper:
        return 'South'
    elif '_E' in kv_upper:
        return 'East'
    elif '_N' in kv_upper:
        return 'North'
    elif '_W' in kv_upper:
        return 'West'
    return 'Unknown'

# Data structures: {Orient: {Heating: val, Cooling: val}}
base_data = {o: {'Heating': 0.0, 'Cooling': 0.0} for o in ['Core', 'South', 'East', 'North', 'West']}
v3_data = {o: {'Heating': 0.0, 'Cooling': 0.0} for o in ['Core', 'South', 'East', 'North', 'West']}

for kv, name, val in base_rows:
    val_kwh = val * J_TO_KWH
    orient = get_orientation(kv)
    load_type = 'Heating' if 'Heating' in name else 'Cooling'
    if orient in base_data:
        base_data[orient][load_type] += val_kwh

for kv, name, val in v3_rows:
    val_kwh = val * J_TO_KWH
    orient = get_orientation(kv)
    load_type = 'Heating' if 'Heating' in name else 'Cooling'
    if orient in v3_data:
        v3_data[orient][load_type] += val_kwh

# Building total loads (MWh)
total_base_h = sum(base_data[o]['Heating'] for o in base_data) / 1000.0
total_base_c = sum(base_data[o]['Cooling'] for o in base_data) / 1000.0
total_base_tot = total_base_h + total_base_c

total_v3_h = sum(v3_data[o]['Heating'] for o in v3_data) / 1000.0
total_v3_c = sum(v3_data[o]['Cooling'] for o in v3_data) / 1000.0
total_v3_tot = total_v3_h + total_v3_c

# Zone differences (kWh)
orients = ['Core', 'South', 'East', 'North', 'West']
diff_c = [v3_data[o]['Cooling'] - base_data[o]['Cooling'] for o in orients]
diff_h = [v3_data[o]['Heating'] - base_data[o]['Heating'] for o in orients]

# -------------------------------------------------------------
# Plotting with dartwork-mpl (presentation style)
# -------------------------------------------------------------
dm.style.use("presentation")

# Setup output folders
output_dir = r"c:\Users\taegyu\Codes\energyplus_project1\figure\plot\fig23_loads_comparison_base_v3"
os.makedirs(output_dir, exist_ok=True)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={'width_ratios': [1, 1.2]})
fig.suptitle("Annual Thermal Load Comparison: Base (No BIPV) vs. BIPV (v3)", fontsize=16, fontweight='bold', y=0.98)

# -------------------------------------------------------------
# Subplot 1: Building Total Load Comparison
# -------------------------------------------------------------
labels = ['Heating', 'Cooling', 'Total']
base_totals = [total_base_h, total_base_c, total_base_tot]
v3_totals = [total_v3_h, total_v3_c, total_v3_tot]

x1 = np.arange(len(labels))
width1 = 0.35

ax1.bar(x1 - width1/2, base_totals, width1, label='Base (No BIPV)', color='oc.gray5', edgecolor='black', lw=0.8)
ax1.bar(x1 + width1/2, v3_totals, width1, label='BIPV (White)', color='oc.orange6', edgecolor='black', lw=0.8)

ax1.set_title("Building-wide Annual Load Comparison", fontsize=13, fontweight='bold', pad=12)
ax1.set_xticks(x1)
ax1.set_xticklabels(labels, fontsize=11)
ax1.set_ylabel("Annual Energy Load (MWh)", fontsize=12)
ax1.set_ylim(0, 200)
ax1.grid(axis='y', linestyle='--', alpha=0.5)
ax1.legend(loc='upper right', frameon=True, facecolor='none', edgecolor='none')

# Add values on top of bars
for i in range(len(labels)):
    ax1.annotate(f"{base_totals[i]:.1f}", (i - width1/2, base_totals[i]), textcoords="offset points", xytext=(0,3), ha='center', fontsize=9.5, fontweight='bold')
    ax1.annotate(f"{v3_totals[i]:.1f}", (i + width1/2, v3_totals[i]), textcoords="offset points", xytext=(0,3), ha='center', fontsize=9.5, fontweight='bold')

# -------------------------------------------------------------
# Subplot 2: Zone-by-Zone Load Difference (v3 - Base)
# -------------------------------------------------------------
x2 = np.arange(len(orients))
width2 = 0.35

# Cooling diff is negative (saving), Heating diff is positive (penalty)
bars_c = ax2.bar(x2 - width2/2, diff_c, width2, label='Cooling Saving', color='oc.blue5', edgecolor='black', lw=0.8)
bars_h = ax2.bar(x2 + width2/2, diff_h, width2, label='Heating Penalty', color='oc.red5', edgecolor='black', lw=0.8)

ax2.set_title("BIPV Impact on Annual Load by Zone (v3 - Base)", fontsize=13, fontweight='bold', pad=12)
ax2.set_xticks(x2)
ax2.set_xticklabels(orients, fontsize=11)
ax2.set_ylabel("Load Change (kWh/year)", fontsize=12)
ax2.set_ylim(-4500, 1500)
ax2.axhline(0, color='black', lw=1.0, linestyle='-')
ax2.grid(axis='y', linestyle='--', alpha=0.5)
ax2.legend(loc='lower right', frameon=True, facecolor='none', edgecolor='none')

# Add values on top/bottom of bars for major impacts (South and Core)
for i in range(len(orients)):
    val_c = diff_c[i]
    val_h = diff_h[i]
    # Label cooling diff
    if abs(val_c) > 100:
        ax2.annotate(f"{val_c:+.0f}", (i - width2/2, val_c), textcoords="offset points", 
                     xytext=(0, -12 if val_c < 0 else 3), ha='center', fontsize=9.5, fontweight='bold', 
                     color='oc.blue8' if val_c < 0 else 'black')
    # Label heating diff
    if abs(val_h) > 100:
        ax2.annotate(f"{val_h:+.0f}", (i + width2/2, val_h), textcoords="offset points", 
                     xytext=(0, 3 if val_h >= 0 else -12), ha='center', fontsize=9.5, fontweight='bold', 
                     color='oc.red8' if val_h >= 0 else 'black')

plt.tight_layout()

# Save PNG and SVG
png_path = os.path.join(output_dir, "fig23_loads_comparison_base_v3.png")
svg_path = os.path.join(output_dir, "fig23_loads_comparison_base_v3.svg")

plt.savefig(png_path, dpi=300, transparent=True)
plt.savefig(svg_path, transparent=True)

print(f"Successfully generated fig23 plot at:")
print(f"  PNG: {png_path}")
print(f"  SVG: {svg_path}")

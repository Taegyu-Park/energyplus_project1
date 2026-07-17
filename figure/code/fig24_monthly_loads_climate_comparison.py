import os
import sqlite3
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# Preserve SVG fonts for editing in Illustrator/Figma
mpl.rcParams['svg.fonttype'] = 'none'

# Database paths
project_root = r"c:\Users\taegyu\Codes\energyplus_project1"
bipv_dir = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone")

DB_PATHS = {
    "Helsinki": os.path.join(bipv_dir, "Helsinki", "case3_white.sql"),
    "Kwangju": os.path.join(bipv_dir, "case3_white.sql"),
    "Phoenix": os.path.join(bipv_dir, "Phoenix", "case3_white.sql")
}

J_TO_MWH = 1.0 / 3.6e9

def query_monthly_loads(db_path):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT t.Month, rd.Name, SUM(r.Value)
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy'
        ) AND t.WarmupFlag = 0
        GROUP BY t.Month, rd.Name
    """)
    rows = cur.fetchall()
    conn.close()
    
    monthly_data = {m: {'Heating': 0.0, 'Cooling': 0.0} for m in range(1, 13)}
    for month, name, val in rows:
        val_mwh = val * J_TO_MWH
        load_type = 'Heating' if 'Heating' in name else 'Cooling'
        monthly_data[month][load_type] = val_mwh
        
    return monthly_data

# Fetch data for all locations
data = {}
for loc, path in DB_PATHS.items():
    print(f"Querying monthly loads for {loc}...")
    data[loc] = query_monthly_loads(path)

# Setup output folders
output_dir = os.path.join(project_root, "figure", "plot", "fig24_monthly_loads_climate_comparison")
os.makedirs(output_dir, exist_ok=True)

# -------------------------------------------------------------
# Plotting with dartwork-mpl (presentation style)
# -------------------------------------------------------------
dm.style.use("presentation")

fig, axs = plt.subplots(1, 3, figsize=(16, 6.5), sharey=True)
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
x = np.arange(1, 13)

# Define clean colors
color_heating = "#e11d48"  # Strong red
color_cooling = "#2563eb"  # Deep blue

# Locations ordered from cold to hot
locations = ["Helsinki", "Kwangju", "Phoenix"]
titles = {
    "Helsinki": "Helsinki (Cold Climate)",
    "Kwangju": "Kwangju (Temperate Climate)",
    "Phoenix": "Phoenix (Hot & Dry Climate)"
}

for i, loc in enumerate(locations):
    ax = axs[i]
    loc_data = data[loc]
    
    heating_vals = np.array([loc_data[m]['Heating'] for m in range(1, 13)])
    cooling_vals = np.array([loc_data[m]['Cooling'] for m in range(1, 13)])
    
    # Plot stacked bars
    bars_heat = ax.bar(x, heating_vals, label="Heating Load", color=color_heating, edgecolor='black', lw=0.6)
    bars_cool = ax.bar(x, cooling_vals, bottom=heating_vals, label="Cooling Load", color=color_cooling, edgecolor='black', lw=0.6)
    
    # Subplot formatting
    ax.set_title(titles[loc], fontsize=13, fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=10, rotation=30)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Enable y-axis label only on the first subplot
    if i == 0:
        ax.set_ylabel("Monthly Energy Load (MWh)", fontsize=12, fontweight='bold')
    
    # Legend only on the middle subplot to avoid cluttering
    if i == 1:
        ax.legend(loc='upper right', frameon=True, facecolor='none', edgecolor='none', fontsize=11)

# Set common y-limit
plt.ylim(0, 45)

# Main Title
fig.suptitle("Monthly Heating and Cooling Load Comparison by Climate Location", fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout()

# Save PNG and SVG
png_path = os.path.join(output_dir, "fig24_monthly_loads_climate_comparison.png")
svg_path = os.path.join(output_dir, "fig24_monthly_loads_climate_comparison.svg")

plt.savefig(png_path, dpi=300, transparent=True)
plt.savefig(svg_path, transparent=True)

print(f"\nSuccessfully generated fig24 plots at:")
print(f"  PNG: {png_path}")
print(f"  SVG: {svg_path}")

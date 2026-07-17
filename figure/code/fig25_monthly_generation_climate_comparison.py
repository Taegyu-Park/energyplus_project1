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

CLIMATES = ["Helsinki", "Kwangju", "Phoenix"]
COLORS = ["white", "light_gray_beige", "terracotta"]

J_TO_MWH = 1.0 / 3.6e9

def query_monthly_gen(db_path):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT t.Month, SUM(r.Value)
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name = 'Facility Total Produced Electricity Energy' AND t.WarmupFlag = 0
        GROUP BY t.Month
    """)
    rows = cur.fetchall()
    conn.close()
    
    monthly_data = {m: 0.0 for m in range(1, 13)}
    for month, val in rows:
        monthly_data[month] = val * J_TO_MWH
        
    return monthly_data

# Fetch data for all locations and cases
data = {loc: {} for loc in CLIMATES}
for loc in CLIMATES:
    for col in COLORS:
        # Determine path
        if loc == "Kwangju":
            path = os.path.join(bipv_dir, f"case3_{col}.sql")
        else:
            path = os.path.join(bipv_dir, loc, f"case3_{col}.sql")
            
        print(f"Querying monthly gen for {loc} - {col}...")
        data[loc][col] = query_monthly_gen(path)

# Setup output folders
output_dir = os.path.join(project_root, "figure", "plot", "fig25_monthly_generation_climate_comparison")
os.makedirs(output_dir, exist_ok=True)

# -------------------------------------------------------------
# Plotting with dartwork-mpl (presentation style)
# -------------------------------------------------------------
dm.style.use("presentation")

fig, axs = plt.subplots(1, 3, figsize=(16, 6.5), sharey=True)
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
x = np.arange(1, 13)
width = 0.26  # width of grouped bars

# Color codes representing BIPV Panel Colors (material-inspired)
color_white = "#cfd8dc"        # Sleek White/Light Gray
color_beige = "#ffe0b2"        # Soft Light Gray Beige
color_terracotta = "#d84315"   # Authentic Terracotta Red-Orange

titles = {
    "Helsinki": "Helsinki (Cold Climate)",
    "Kwangju": "Kwangju (Temperate Climate)",
    "Phoenix": "Phoenix (Hot & Dry Climate)"
}

for i, loc in enumerate(CLIMATES):
    ax = axs[i]
    loc_data = data[loc]
    
    y_white = np.array([loc_data["white"][m] for m in range(1, 13)])
    y_beige = np.array([loc_data["light_gray_beige"][m] for m in range(1, 13)])
    y_terracotta = np.array([loc_data["terracotta"][m] for m in range(1, 13)])
    
    # Plot grouped bars
    ax.bar(x - width, y_white, width, label="White (250W)", color=color_white, edgecolor='black', lw=0.6)
    ax.bar(x, y_beige, width, label="Beige (350W)", color=color_beige, edgecolor='black', lw=0.6)
    ax.bar(x + width, y_terracotta, width, label="Terracotta (390W)", color=color_terracotta, edgecolor='black', lw=0.6)
    
    # Subplot formatting
    ax.set_title(titles[loc], fontsize=13, fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=10, rotation=30)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    if i == 0:
        ax.set_ylabel("Monthly BIPV Generation (MWh)", fontsize=12, fontweight='bold')
        
    if i == 1:
        ax.legend(loc='upper right', frameon=True, facecolor='none', edgecolor='none', fontsize=11)

# Set common y-limit
plt.ylim(0, 10)

# Main Title
fig.suptitle("Monthly BIPV Electricity Generation Comparison by Climate and Color Spec", fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout()

# Save PNG and SVG
png_path = os.path.join(output_dir, "fig25_monthly_generation_climate_comparison.png")
svg_path = os.path.join(output_dir, "fig25_monthly_generation_climate_comparison.svg")

plt.savefig(png_path, dpi=300, transparent=True)
plt.savefig(svg_path, transparent=True)

print(f"\nSuccessfully generated fig25 plots at:")
print(f"  PNG: {png_path}")
print(f"  SVG: {svg_path}")

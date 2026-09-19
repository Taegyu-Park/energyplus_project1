"""
PV Annual Generation Analysis for Case 3 Kinetic BIPV (North Facade)
====================================================================
This script parses the annual electricity generation of each PV panel (6 rows, 16 columns)
from the simulation database (eplusout.sql) for the North orientation.
It sums the values across all BIPV angles, converts the unit from Joules (J) to kWh,
saves the 6x16 matrix data, and creates a spatial heatmap.

Source Script: c:\\Users\\taegyu\\Codes\\energyplus_project1\\figure\\code\\fig12_analyze_pv_generation_north.py
Output Plots: c:\\Users\\taegyu\\Codes\\energyplus_project1\\figure\\plot\\fig12_analyze_pv_generation_north\\
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

def main():
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # Target North simulation database
    db_path = os.path.normpath(
        os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_north", "eplusout.sql")
    )
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    print(f"Connecting to North simulation database: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    print("Querying and aggregating North PV generation data...")
    c.execute("""
        SELECT ReportDataDictionaryIndex, KeyValue 
        FROM ReportDataDictionary 
        WHERE Name = 'Generator Produced DC Electricity Energy' AND KeyValue LIKE 'PV_%'
    """)
    rdd_map = {row[0]: row[1] for row in c.fetchall()}
    
    if not rdd_map:
        print("Error: No PV generation RDD entries found in the database.")
        conn.close()
        return

    rdd_ids = tuple(rdd_map.keys())
    c.execute(f"""
        SELECT ReportDataDictionaryIndex, SUM(Value) 
        FROM ReportData 
        WHERE ReportDataDictionaryIndex IN ({','.join(map(str, rdd_ids))})
        GROUP BY ReportDataDictionaryIndex
    """)
    rows_raw = c.fetchall()
    conn.close()
    
    rows = [(rdd_map[rdd_id], val_j) for rdd_id, val_j in rows_raw]
    if not rows:
        print("Error: No PV generation data found in the database.")
        return

    print(f"Retrieved {len(rows)} database records.")

    # Initialize 6x16 grid for J (Joules)
    grid_joules = np.zeros((6, 16))
    processed_panels = set()
    
    # Parse names (format: PV_Row_Angle_Col, e.g., PV_1_00_01)
    for key_value, val_j in rows:
        parts = key_value.split('_')
        if len(parts) != 4:
            continue
            
        try:
            row = int(parts[1])     # 1 to 6
            angle = int(parts[2])   # 00 to 90
            col = int(parts[3])     # 1 to 16
            
            r_idx = row - 1
            c_idx = col - 1
            
            if 0 <= r_idx < 6 and 0 <= c_idx < 16:
                grid_joules[r_idx, c_idx] += val_j
                processed_panels.add((row, col))
        except ValueError:
            print(f"Warning: Failed to parse PV KeyValue '{key_value}'")
            continue

    print(f"Aggregated data for {len(processed_panels)} unique physical North PV panel locations (expected 96).")

    # Convert Joules to kWh (1 kWh = 3.6e6 Joules)
    grid_kwh = grid_joules / 3.6e6

    # Console Summary Output
    print("\n" + "="*80)
    print(" NORTH FACADE ANNUAL PV GENERATION MATRIX (6 rows x 16 columns) - Unit: kWh ")
    print("="*80)
    
    col_headers = "Row \\ Col | " + " | ".join(f"{c:02d}" for c in range(1, 17))
    print(col_headers)
    print("-" * len(col_headers))
    
    for r in range(6):
        row_str = f"   Row {r+1}   | " + " | ".join(f"{grid_kwh[r, c]:5.1f}" for c in range(16))
        print(row_str)
    print("="*80)
    
    total_generation_kwh = np.sum(grid_kwh)
    mean_generation_kwh = np.mean(grid_kwh)
    min_generation_kwh = np.min(grid_kwh)
    max_generation_kwh = np.max(grid_kwh)
    
    print(f"Total Annual Grid North PV Generation: {total_generation_kwh:.2f} kWh ({total_generation_kwh/1000:.3f} MWh)")
    print(f"Average per Panel: {mean_generation_kwh:.2f} kWh")
    print(f"Min Generation: {min_generation_kwh:.2f} kWh (at Row {np.argmin(grid_kwh)//16 + 1}, Col {np.argmin(grid_kwh)%16 + 1})")
    print(f"Max Generation: {max_generation_kwh:.2f} kWh (at Row {np.argmax(grid_kwh)//16 + 1}, Col {np.argmax(grid_kwh)%16 + 1})")
    print("="*80)

    # Style and Font settings for SVG text preservation
    mpl.rcParams['svg.fonttype'] = 'none'
    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
    except ImportError:
        plt.style.use("default")

    fig, ax = plt.subplots(figsize=(15, 7.5))
    
    from matplotlib.colors import LinearSegmentedColormap
    yl_or_cmap = LinearSegmentedColormap.from_list("YlOr_North", ["#FFFFE3", "#87CEEB", "#1E90FF"])
    im = ax.imshow(grid_kwh, cmap=yl_or_cmap, aspect="auto")
    
    for r in range(6):
        for c in range(16):
            val = grid_kwh[r, c]
            norm_val = (val - min_generation_kwh) / (max_generation_kwh - min_generation_kwh) if (max_generation_kwh - min_generation_kwh) > 0 else 0.5
            text_color = "black" if norm_val < 0.7 else "white"
            ax.text(c, r, f"{val:.1f}", ha="center", va="center", color=text_color, fontweight="bold", fontsize=10)

    ax.set_xticks(np.arange(16))
    ax.set_xticklabels([f"{c:02d}" for c in range(1, 17)])
    ax.set_yticks(np.arange(6))
    ax.set_yticklabels([f"Row {r}" for r in range(1, 7)])
    
    ax.set_xlabel("Column", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_ylabel("Row", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title("North Facade Annual PV Panel Electricity Generation Heatmap (kWh)", fontsize=16, fontweight="bold", pad=15)
    
    ax.set_xticks(np.arange(16) - 0.5, minor=True)
    ax.set_yticks(np.arange(6) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)
    ax.tick_params(which="minor", size=0)
    
    cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.8)
    cbar.ax.set_facecolor('none')
    cbar.set_label("Annual Generation (kWh)", fontsize=11, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()
    
    print(f"Successfully generated plots:\n  PNG: {plot_png_path}\n  SVG: {plot_svg_path}")

if __name__ == "__main__":
    main()

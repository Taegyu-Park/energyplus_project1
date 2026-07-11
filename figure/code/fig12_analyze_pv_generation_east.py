"""
PV Annual Generation Analysis for Case 3 (Kinetic BIPV) - East Wall (6 rows x 9 columns)
========================================================================================
This script parses the annual electricity generation of each PV panel (6 rows, 9 columns)
from the simulation database (eplusout.sql) in the normal_east case3 directory.
It sums the values across all BIPV angles, converts the unit from Joules (J) to kWh,
saves the 6x9 matrix to a CSV file, and creates a spatial heatmap.
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt

def main():
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    db_path = os.path.normpath(os.path.join(project_root, "case_analysis", "normal_east", "case3", "eplusout.sql"))
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, "pv_annual_generation_heatmap_east.png")
    plot_svg_path = os.path.join(figure_dir, "pv_annual_generation_heatmap_east.svg")
    
    # Artifact directory for embedding in responses
    artifact_dir = r"C:\Users\taegyu\\.gemini\antigravity-ide\brain\6a656d91-dc30-4c35-bfce-a2c524e5b824"

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Query annual total (in Joules) for all PV panels
    query = """
        SELECT rdd.KeyValue, SUM(rd.Value)
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rdd.Name = 'Generator Produced DC Electricity Energy'
          AND rdd.KeyValue LIKE 'PV_%'
          AND t.WarmupFlag = 0
        GROUP BY rdd.KeyValue
    """
    
    print("Querying and aggregating PV generation data...")
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("Error: No PV generation data found in the database.")
        return

    print(f"Retrieved {len(rows)} database records.")

    # Initialize 6x9 grid for J (Joules)
    grid_joules = np.zeros((6, 9))
    processed_panels = set()
    
    # Parse names (format: PV_Row_Angle_Col, e.g., PV_1_00_01)
    for key_value, val_j in rows:
        parts = key_value.split('_')
        if len(parts) != 4:
            continue
            
        try:
            row = int(parts[1])     # 1 to 6
            angle = int(parts[2])   # 00 to 90
            col = int(parts[3])     # 1 to 9 (East wall columns)
            
            r_idx = row - 1
            c_idx = col - 1
            
            if 0 <= r_idx < 6 and 0 <= c_idx < 9:
                grid_joules[r_idx, c_idx] += val_j
                processed_panels.add((row, col))
        except ValueError:
            print(f"Warning: Failed to parse PV KeyValue '{key_value}'")
            continue

    print(f"Aggregated data for {len(processed_panels)} unique physical PV panel locations (expected 54).")

    # Convert Joules to kWh (1 kWh = 3.6e6 Joules)
    grid_kwh = grid_joules / 3.6e6

    # 1. Print formatted matrix to console
    print("\n" + "="*80)
    print(" ANNUAL PV GENERATION MATRIX (6 rows x 9 columns) - Unit: kWh ")
    print("="*80)
    
    col_headers = "Row \\ Col | " + " | ".join(f"{c:02d}" for c in range(1, 10))
    print(col_headers)
    print("-" * len(col_headers))
    
    for r in range(6):
        row_str = f"   Row {r+1}   | " + " | ".join(f"{grid_kwh[r, c]:5.1f}" for c in range(9))
        print(row_str)
    print("="*80)
    
    # Overall summary stats
    total_generation_kwh = np.sum(grid_kwh)
    mean_generation_kwh = np.mean(grid_kwh)
    min_generation_kwh = np.min(grid_kwh)
    max_generation_kwh = np.max(grid_kwh)
    
    print(f"Total Annual Grid PV Generation: {total_generation_kwh:.2f} kWh ({total_generation_kwh/1000:.3f} MWh)")
    print(f"Average per Panel: {mean_generation_kwh:.2f} kWh")
    print(f"Min Generation: {min_generation_kwh:.2f} kWh (at Row {np.argmin(grid_kwh)//9 + 1}, Col {np.argmin(grid_kwh)%9 + 1})")
    print(f"Max Generation: {max_generation_kwh:.2f} kWh (at Row {np.argmax(grid_kwh)//9 + 1}, Col {np.argmax(grid_kwh)%9 + 1})")
    print("="*80)

    # 2. Create Heatmap Plot
    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
        plt.rcParams['svg.fonttype'] = 'none'
    except ImportError:
        plt.style.use("default")

    fig, ax = plt.subplots(figsize=(12, 7.5))
    
    from matplotlib.colors import LinearSegmentedColormap
    yl_or_cmap = LinearSegmentedColormap.from_list("YlOr", ["#FFFFE3", "#FFD700", "#FFA500"])
    im = ax.imshow(grid_kwh, cmap=yl_or_cmap, aspect="auto", vmin=250, vmax=400)
    
    for r in range(6):
        for c in range(9):
            val = grid_kwh[r, c]
            norm_val = (val - 250) / (400 - 250)
            text_color = "black" if norm_val < 0.7 else "white"
            ax.text(c, r, f"{val:.1f}", ha="center", va="center", color=text_color, fontweight="bold", fontsize=10)

    # Set labels
    ax.set_xticks(np.arange(9))
    ax.set_xticklabels([f"{c:02d}" for c in range(1, 10)])
    ax.set_yticks(np.arange(6))
    ax.set_yticklabels([f"Row {r}" for r in range(1, 7)])
    
    ax.set_xlabel("Column", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_ylabel("Row", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title("Annual PV Panel Electricity Generation Heatmap - East Wall (kWh)", fontsize=16, fontweight="bold", pad=15)
    
    # Grid lines to separate cells
    ax.set_xticks(np.arange(9) - 0.5, minor=True)
    ax.set_yticks(np.arange(6) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)
    ax.tick_params(which="minor", size=0)
    
    # Add colorbar
    cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.8)
    cbar.set_label("Annual Generation (kWh)", fontsize=11, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    
    # Save a copy in the artifact directory for rendering in response
    if os.path.exists(artifact_dir):
        artifact_png = os.path.join(artifact_dir, "pv_annual_generation_heatmap_east.png")
        plt.savefig(artifact_png, dpi=200)
        print(f"Saved artifact copy to {artifact_png}")
        
    plt.close()
    
    print(f"Saved Heatmap plots to:\n  - {plot_png_path}\n  - {plot_svg_path}")
    print("Analysis completed successfully!")

if __name__ == "__main__":
    main()

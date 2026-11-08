"""
PV Annual Generation Analysis for Case 3 (Kinetic BIPV) - West Wall (6 rows x 9 columns)
========================================================================================
This script parses the annual electricity generation of each PV panel (6 rows, 9 columns)
from the simulation database (eplusout.sql) in case3_v3_west.
It maps the columns from the front-facing perspective of the West facade:
- Left (Col 01) = North side
- Right (Col 09) = South side (DB Col 01 mapped to Viewer Col 09)
Saves the 6x9 heatmap in PNG and SVG formats.
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    db_path = os.path.normpath(os.path.join(
        project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_west", "eplusout.sql"
    ))
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("PRAGMA index_list('ReportData')")
    indexes = [r[1] for r in c.fetchall()]
    if 'idx_rddi' not in indexes:
        print("Creating index on ReportData...")
        c.execute("CREATE INDEX IF NOT EXISTS idx_rddi ON ReportData(ReportDataDictionaryIndex)")
        conn.commit()

    c.execute("SELECT MIN(TimeIndex), MAX(TimeIndex) FROM Time WHERE WarmupFlag = 0")
    min_t, max_t = c.fetchone()

    query = f"""
        SELECT rdd.KeyValue, SUM(rd.Value)
        FROM ReportData rd
        JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        WHERE rdd.Name = 'Generator Produced DC Electricity Energy'
          AND rdd.KeyValue LIKE 'PV_%'
          AND rd.TimeIndex >= {min_t} AND rd.TimeIndex <= {max_t}
        GROUP BY rdd.KeyValue
    """
    
    print("Querying and aggregating West PV generation data...")
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("Error: No PV generation data found in the database.")
        return

    print(f"Retrieved {len(rows)} database records.")

    # Matrix in raw database coordinates (DB Col 1 = South side, DB Col 9 = North side)
    grid_joules_raw = np.zeros((6, 9))
    processed_panels = set()
    
    for key_value, val_j in rows:
        parts = key_value.split('_')
        if len(parts) != 4:
            continue
            
        try:
            row = int(parts[1])     # 1 to 6
            angle = int(parts[2])   # 00 to 90
            col = int(parts[3])     # 1 to 9 (1=South, 9=North)
            
            r_idx = row - 1
            c_idx = col - 1
            
            if 0 <= r_idx < 6 and 0 <= c_idx < 9:
                grid_joules_raw[r_idx, c_idx] += val_j
                processed_panels.add((row, col))
        except ValueError:
            print(f"Warning: Failed to parse PV KeyValue '{key_value}'")
            continue

    print(f"Aggregated data for {len(processed_panels)} unique physical PV panel locations (expected 54).")

    grid_kwh_raw = grid_joules_raw / 3.6e6

    # Front-facing View Alignment for West Facade (Looking East from outside):
    # Left = North side (DB Col 9), Right = South side (DB Col 1)
    # Horizontal flip: fliplr reverses column order so Viewer Col 1 = DB Col 9 (North), Viewer Col 9 = DB Col 1 (South)
    grid_kwh = np.fliplr(grid_kwh_raw)

    print("\n" + "="*80)
    print(" WEST WALL FRONT-VIEW PV GENERATION MATRIX (Left=North, Right=South) - kWh ")
    print("="*80)
    
    col_headers = "Row \\ Col | " + " | ".join(f"{c:02d}" for c in range(1, 10))
    print(col_headers)
    print("-" * len(col_headers))
    
    for r in range(6):
        row_str = f"   Row {r+1}   | " + " | ".join(f"{grid_kwh[r, c]:5.1f}" for c in range(9))
        print(row_str)
    print("="*80)
    
    total_generation_kwh = np.sum(grid_kwh)
    mean_generation_kwh = np.mean(grid_kwh)
    min_generation_kwh = np.min(grid_kwh)
    max_generation_kwh = np.max(grid_kwh)
    
    print(f"Total Annual West PV Generation: {total_generation_kwh:.2f} kWh ({total_generation_kwh/1000:.3f} MWh)")
    print(f"Average per Panel: {mean_generation_kwh:.2f} kWh")
    print(f"Min Generation: {min_generation_kwh:.2f} kWh")
    print(f"Max Generation: {max_generation_kwh:.2f} kWh")
    print("="*80)

    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
        mpl.rcParams['svg.fonttype'] = 'none'
    except ImportError:
        plt.style.use("default")

    fig, ax = plt.subplots(figsize=(12, 7.5))
    
    from matplotlib.colors import LinearSegmentedColormap
    yl_or_cmap = LinearSegmentedColormap.from_list("YlOr", ["#FFFFE3", "#FFD700", "#FFA500"])
    
    im = ax.imshow(grid_kwh, cmap=yl_or_cmap, aspect="auto", vmin=min_generation_kwh*0.95, vmax=max_generation_kwh*1.02)
    
    for r in range(6):
        for c in range(9):
            val = grid_kwh[r, c]
            norm_val = (val - min_generation_kwh) / (max_generation_kwh - min_generation_kwh) if (max_generation_kwh - min_generation_kwh) > 0 else 0.5
            text_color = "black" if norm_val < 0.7 else "white"
            ax.text(c, r, f"{val:.1f}", ha="center", va="center", color=text_color, fontweight="bold", fontsize=10)

    ax.set_xticks(np.arange(9))
    ax.set_xticklabels([f"{c:02d}" for c in range(1, 10)])
    ax.set_yticks(np.arange(6))
    ax.set_yticklabels([f"Row {r}" for r in range(1, 7)])
    
    ax.set_xlabel("Column (Left: North Side -> Right: South Side)", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_ylabel("Row", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title("Annual West Wall BIPV Panel Generation Heatmap [Front View] (kWh)", fontsize=15, fontweight="bold", pad=15)
    
    ax.set_xticks(np.arange(9) - 0.5, minor=True)
    ax.set_yticks(np.arange(6) - 0.5, minor=True)
    ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)
    ax.tick_params(which="minor", size=0)
    
    cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.8)
    cbar.set_label("Annual Generation (kWh)", fontsize=11, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()
    
    print(f"Saved Front-View West Heatmap plots to:\n  - {plot_png_path}\n  - {plot_svg_path}")

if __name__ == "__main__":
    main()

"""
FIG 34_2: Optimal 96 PV Placement Heatmap Layout from case3_v3_max Simulation
=============================================================================
- Source Script: c:\\Users\\taegyu\\Codes\\energyplus_project1\\figure\\code\\fig34_2_optimal_96_pv_heatmap_layout_max.py
- Plot Directory: c:\\Users\\taegyu\\Codes\\energyplus_project1\\figure\\plot\\fig34_2_optimal_96_pv_heatmap_layout_max\\
- Outputs: PNG and SVG formats with transparent background and non-embedded SVG fonts.
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
import dartwork_mpl as dm

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")

    db_path = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_max", "eplusout.sql")
    if not os.path.exists(db_path):
        print(f"Error: SQL database file not found at '{db_path}'")
        return

    # Facade Grid Configurations: (Rows, Cols)
    facade_dims = {
        'WEST': (6, 9),
        'SOUTH': (6, 16),
        'EAST': (6, 9)
    }

    # 1. Query Top 96 PV panel generation data directly from case3_v3_max eplusout.sql
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()

    c.execute("SELECT ReportDataDictionaryIndex, KeyValue FROM ReportDataDictionary WHERE Name = 'Generator Produced DC Electricity Energy'")
    rdd_rows = c.fetchall()
    rdd_dict = {r[0]: r[1] for r in rdd_rows}
    rdd_ids = list(rdd_dict.keys())

    q_marks = ','.join(['?'] * len(rdd_ids))
    c.execute(f"SELECT ReportDataDictionaryIndex, SUM(Value) FROM ReportData WHERE ReportDataDictionaryIndex IN ({q_marks}) GROUP BY ReportDataDictionaryIndex", rdd_ids)

    top96_data = {}
    for rdd_id, val_j in c.fetchall():
        if val_j is None:
            continue
        kv = rdd_dict[rdd_id]
        parts = kv.split('_')
        if len(parts) >= 5:
            orient_code = parts[0].upper()
            orient_map = {'S': 'SOUTH', 'E': 'EAST', 'W': 'WEST', 'N': 'NORTH'}
            orient = orient_map.get(orient_code, orient_code)
            row = int(parts[2])
            col = int(parts[4])
            val_kwh = val_j / 3.6e6
            
            loc = (orient, row, col)
            top96_data[loc] = top96_data.get(loc, 0.0) + val_kwh

    conn.close()
    print(f"Extracted {len(top96_data)} panel records from case3_v3_max SQL database.")

    # 2. Build Heatmap Matrices & Selected Masks for West, South, East
    grids = {}
    mask_selected = {}
    
    for orient, (num_r, num_c) in facade_dims.items():
        grid = np.zeros((num_r, num_c))
        selected_mask = np.zeros((num_r, num_c), dtype=bool)
        
        for r in range(1, num_r + 1):
            for c_idx in range(1, num_c + 1):
                val = top96_data.get((orient, r, c_idx), np.nan)
                if not np.isnan(val) and val > 0:
                    grid[r - 1, c_idx - 1] = val
                    selected_mask[r - 1, c_idx - 1] = True
                    
        grids[orient] = grid
        mask_selected[orient] = selected_mask

    # Style Setup
    dm.style.use("presentation")
    mpl.rcParams['svg.fonttype'] = 'none'
    mpl.rcParams['hatch.linewidth'] = 1.5
    mpl.rcParams['hatch.color'] = '#444444'

    # Layout: 3 subplots horizontally: West (6x9), South (6x16), East (6x9)
    fig, axes = plt.subplots(1, 3, figsize=(21.6, 7.5), gridspec_kw={'width_ratios': [9, 16, 9]})

    # Colormap: Yellow -> Gold -> Orange
    cmap = LinearSegmentedColormap.from_list("YlOr", ["#FFFFE3", "#FFD700", "#FFA500"])
    
    # Global Min/Max matching range (363.19 ~ 623.88 kWh)
    all_vals = list(top96_data.values())
    vmin = 363.19
    vmax = 623.88

    orient_names = {
        'WEST': ('West Facade', 9),
        'SOUTH': ('South Facade', 16),
        'EAST': ('East Facade', 9)
    }

    orient_keys = ['WEST', 'SOUTH', 'EAST']
    images = []

    for i, orient in enumerate(orient_keys):
        ax = axes[i]
        grid = grids[orient]
        sel_mask = mask_selected[orient]
        num_r, num_c = facade_dims[orient]

        # Display selected cell heatmap
        display_grid = np.where(sel_mask, grid, np.nan)
        ax.set_facecolor('#E0E0E0') # Hatching background for unselected cells
        
        im = ax.imshow(display_grid, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')
        images.append(im)

        # Annotate cell numbers & draw unselected hatching
        for r in range(num_r):
            for c_idx in range(num_c):
                val = grid[r, c_idx]
                is_sel = sel_mask[r, c_idx]
                
                if is_sel:
                    # Contrast text color calculation
                    norm_val = (val - vmin) / (vmax - vmin) if (vmax - vmin) > 0 else 0.5
                    text_color = "black" if norm_val < 0.65 else "white"
                    ax.text(c_idx, r, f"{val:.1f}", ha="center", va="center", color=text_color, fontweight="bold", fontsize=9.5)
                else:
                    # Draw unselected cell background patch
                    rect = plt.Rectangle((c_idx - 0.5, r - 0.5), 1, 1, fill=True, facecolor='#E8E8E8', 
                                         edgecolor='#000000', lw=0.8, zorder=2)
                    ax.add_patch(rect)
                    
                    # Draw explicit vector diagonal lines for 100% Figma SVG compatibility
                    for offset in np.arange(-0.8, 0.9, 0.3):
                        x1 = c_idx - 0.5
                        x2 = c_idx + 0.5
                        y1 = r - 0.5 + offset
                        y2 = r + 0.5 + offset
                        
                        xs = np.linspace(x1, x2, 10)
                        ys = xs - c_idx + r + offset
                        
                        mask = (xs >= c_idx - 0.5) & (xs <= c_idx + 0.5) & (ys >= r - 0.5) & (ys <= r + 0.5)
                        if np.any(mask):
                            ax.plot(xs[mask], ys[mask], color='#666666', lw=1.2, zorder=3)

        # Grid lines between cells
        ax.set_xticks(np.arange(num_c))
        ax.set_xticklabels([f"{c:02d}" for c in range(1, num_c + 1)])
        ax.set_yticks(np.arange(num_r))
        
        if i == 0:
            ax.set_yticklabels([f"Row {r}" for r in range(1, num_r + 1)])
            ax.set_ylabel("Row", fontsize=12, fontweight='bold')
        else:
            ax.set_yticklabels([])
            ax.set_ylabel("")

        ax.set_xticks(np.arange(num_c) - 0.5, minor=True)
        ax.set_yticks(np.arange(num_r) - 0.5, minor=True)
        ax.grid(which="minor", color="black", linestyle="-", linewidth=1.2)
        ax.tick_params(which="minor", size=0)

        title_text, total_c = orient_names[orient]
        sel_count = np.sum(sel_mask)
        ax.set_title(f"{title_text}\n({sel_count}/{num_r*num_c} Panels)", fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel("Column", fontsize=12, fontweight='bold')

    # Colorbar & Layout Adjustments
    plt.subplots_adjust(left=0.04, right=0.91, top=0.82, bottom=0.12, wspace=0.08)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.65])
    cbar = fig.colorbar(images[1], cax=cbar_ax)
    cbar.ax.set_facecolor('none')
    cbar.set_label("Annual PV Generation (kWh)", fontsize=12, fontweight='bold')

    # Main Title
    fig.suptitle("Optimal 96 Kinetic BIPV Placement Unfolded Elevation Heatmap (case3_v3_max)", 
                 fontsize=16, fontweight='bold', y=0.96)

    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()

    print("="*80)
    print(f" Successfully generated Fig 34_2 plots:")
    print(f"   PNG: {plot_png_path}")
    print(f"   SVG: {plot_svg_path}")
    print("="*80)

if __name__ == '__main__':
    main()

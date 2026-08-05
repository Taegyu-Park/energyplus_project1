"""
FIG 29: Real Model (case3) vs Simple Model (4m_cube) PV Self-Shading Impact Comparison
=======================================================================================
This script analyzes and compares the row-by-row annual PV generation (normalized to kWh per 2m panel)
between the Real Model (Case 3, 6x16 grid) and the Simple Model (4m_cube, 6x1 grid).
It generates comparison plots for both PNG and SVG formats following AGENTS.md guidelines.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams['svg.fonttype'] = 'none'

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    db_real = os.path.join(project_root, "case_analysis", "normal", "case3", "eplusout.sql")
    db_simple = os.path.join(project_root, "sim_diff", "4m_cube", "original", "eplusout.sql")
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.join(project_root, "figure", "plot", script_name)
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")

    # 1. Real Model Data Query
    conn_r = sqlite3.connect(db_real)
    query_r = """
    SELECT rdd.KeyValue, SUM(rd.Value) as TotalJ
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name = 'Generator Produced DC Electricity Energy'
      AND rdd.KeyValue LIKE 'PV_%'
      AND t.WarmupFlag = 0
    GROUP BY rdd.KeyValue
    """
    df_r = pd.read_sql_query(query_r, conn_r)
    conn_r.close()

    df_r['Row'] = df_r['KeyValue'].apply(lambda x: int(x.split('_')[1])) # Row 1=Top, Row 6=Bottom
    df_r['kWh'] = df_r['TotalJ'] / 3.6e6
    real_row_avg = df_r.groupby('Row')['kWh'].sum() / 16.0 # Average per 2m panel

    # 2. Simple Model Data Query
    conn_s = sqlite3.connect(db_simple)
    query_s = """
    SELECT rdd.KeyValue, SUM(rd.Value) as TotalJ
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name = 'Generator Produced DC Electricity Energy'
      AND t.WarmupFlag = 0
    GROUP BY rdd.KeyValue
    """
    df_s = pd.read_sql_query(query_s, conn_s)
    conn_s.close()

    def parse_s_row(kv):
        if kv.endswith('_P3'): return 6     # Bottommost in plot (Row 6)
        elif kv.endswith('_P2'): return 5
        elif kv.endswith('_P3_2'): return 3
        elif kv.endswith('_P2_2'): return 2
        elif kv.endswith('_2'): return 1    # Topmost in plot (Row 1)
        else: return 4

    df_s['PlotRow'] = df_s['KeyValue'].apply(parse_s_row)
    df_s['kWh'] = df_s['TotalJ'] / 3.6e6
    simple_row_avg = (df_s.groupby('PlotRow')['kWh'].sum() / 2.0).sort_index() # Normalized to 2m width

    # 3. Create Plot using dartwork-mpl
    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
    except ImportError:
        plt.style.use("default")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    rows = np.arange(1, 7)
    row_labels = [f"Row {r}\n({'Top' if r==1 else ('Bot' if r==6 else f'Mid-{r}')})" for r in rows]

    # Subplot 1: Real Model vs Simple Model Generation per 2m panel
    ax1.plot(rows, real_row_avg.values, marker='o', linewidth=2.5, markersize=8, color='#1f77b4', label='Real Model (case3, 32m facade)')
    ax1.plot(rows, simple_row_avg.values, marker='s', linewidth=2.5, markersize=8, color='#ff7f0e', linestyle='--', label='Simple Model (4m_cube, 4m facade)')
    
    for r, v1, v2 in zip(rows, real_row_avg.values, simple_row_avg.values):
        ax1.text(r, v1 + 15, f"{v1:.1f}", ha='center', va='bottom', fontsize=10, color='#1f77b4', fontweight='bold')
        ax1.text(r, v2 + 15, f"{v2:.1f}", ha='center', va='bottom', fontsize=10, color='#ff7f0e', fontweight='bold')

    ax1.set_xticks(rows)
    ax1.set_xticklabels(row_labels, fontsize=10)
    ax1.set_ylabel("Annual PV Generation (kWh / 2m Panel)", fontsize=12, fontweight='bold')
    ax1.set_title("Row-by-Row PV Generation (Normalized to 2m Panel)", fontsize=13, fontweight='bold', pad=12)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.set_ylim(300, 700)
    ax1.legend(framealpha=0, loc='center right')

    # Subplot 2: Relative Generation (% of Topmost Row 1)
    real_rel = (real_row_avg.values / real_row_avg.values[0]) * 100
    simple_rel = (simple_row_avg.values / simple_row_avg.values[0]) * 100

    ax2.plot(rows, real_rel, marker='o', linewidth=2.5, markersize=8, color='#1f77b4', label='Real Model (case3, -4.5% total drop)')
    ax2.plot(rows, simple_rel, marker='s', linewidth=2.5, markersize=8, color='#ff7f0e', linestyle='--', label='Simple Model (4m_cube, -36.3% total drop)')

    for r, v1, v2 in zip(rows, real_rel, simple_rel):
        ax2.text(r, v1 + 2, f"{v1:.1f}%", ha='center', va='bottom', fontsize=10, color='#1f77b4', fontweight='bold')
        ax2.text(r, v2 + 2, f"{v2:.1f}%", ha='center', va='bottom', fontsize=10, color='#ff7f0e', fontweight='bold')

    ax2.set_xticks(rows)
    ax2.set_xticklabels(row_labels, fontsize=10)
    ax2.set_ylabel("Relative Generation (% of Topmost Row)", fontsize=12, fontweight='bold')
    ax2.set_title("Self-Shading Impact Relative to Topmost Row (%)", fontsize=13, fontweight='bold', pad=12)
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.set_ylim(50, 115)
    ax2.legend(framealpha=0, loc='lower left')

    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()

    print(f"Successfully generated figure:\n  PNG: {plot_png_path}\n  SVG: {plot_svg_path}")

if __name__ == "__main__":
    main()

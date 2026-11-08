"""
FIG 31: Monthly PV Generation Comparison & Self-Shading Loss Rate (%) [case3_v3_south]
=======================================================================================
This script queries EnergyPlus simulation results from case3_v3_south (eplusout.sql),
calculates monthly PV generation per tilt angle case for Row 1 (Top) and Row 6 (Bottom), and plots:
  - Subplot 1: Monthly PV Generation Grouped Bar Chart (Y-axis: 60-120 kWh, Row 1: Orange, Row 6: Blue)
  - Subplot 2: Monthly Self-Shading Loss Rate (%) Bar Chart (Row 6 relative to Row 1)

Follows AGENTS.md guidelines for dartwork-mpl style, font handling, and transparent saving.
All value labels are formatted to 1 decimal place ({:.1f}) in black text.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

# SVG text editable setting for Figma
mpl.rcParams['svg.fonttype'] = 'none'

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir)) # c:\Users\taegyu\Codes\energyplus_project1
    
    db_path = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south", "eplusout.sql")
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.join(project_root, "figure", "plot", script_name)
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # 1. Monthly Query for Row 1 and Row 6
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        t.Month,
        SUM(CASE WHEN rdd.KeyValue LIKE 'PV_1_%' THEN rd.Value ELSE 0 END) as Row1_J,
        SUM(CASE WHEN rdd.KeyValue LIKE 'PV_6_%' THEN rd.Value ELSE 0 END) as Row6_J
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name = 'Generator Produced DC Electricity Energy'
      AND t.WarmupFlag = 0
    GROUP BY t.Month
    ORDER BY t.Month
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Convert Joules [J] per month to kWh per tilt angle case (divide by 10 tilt angles evaluated)
    # Row1_kWh ranges from 66.4 to 103.0 kWh
    df['Row1_kWh'] = df['Row1_J'] / 3.6e6 / 10.0
    df['Row6_kWh'] = df['Row6_J'] / 3.6e6 / 10.0
    df['Diff_kWh'] = df['Row1_kWh'] - df['Row6_kWh']
    df['Loss_Percent'] = (df['Row6_kWh'] - df['Row1_kWh']) / df['Row1_kWh'] * 100.0

    months = np.arange(1, 13)
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # 2. Style & Figure Setup
    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
    except ImportError:
        plt.style.use("default")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True)

    # Colors requested by user:
    # Row 1 (Top): Orange
    # Row 6 (Bottom): Blue
    color_row1 = '#ff7f0e'  # Orange
    color_row6 = '#1f77b4'  # Blue
    color_loss = '#d62728'  # Red for Loss %

    # Subplot 1: Monthly Grouped Bar Chart
    width = 0.38
    x = np.arange(len(months))

    rects1 = ax1.bar(x - width/2, df['Row1_kWh'], width, label='Row 1 (Top)', color=color_row1, alpha=0.9, edgecolor='none')
    rects2 = ax1.bar(x + width/2, df['Row6_kWh'], width, label='Row 6 (Bottom)', color=color_row6, alpha=0.9, edgecolor='none')

    # Value labels on top of bars: Black text, 1 decimal place
    for rect in rects1:
        h = rect.get_height()
        ax1.text(rect.get_x() + rect.get_width()/2., h + 0.8, f"{h:.1f}", ha='center', va='bottom', fontsize=8.5, color='black', fontweight='bold')
        
    for rect in rects2:
        h = rect.get_height()
        ax1.text(rect.get_x() + rect.get_width()/2., h + 0.8, f"{h:.1f}", ha='center', va='bottom', fontsize=8.5, color='black', fontweight='bold')

    ax1.set_ylabel("Monthly PV Generation (kWh / Row)", fontsize=12, fontweight='bold')
    ax1.set_title("Monthly PV Generation Comparison: Row 1 (Top) vs Row 6 (Bottom) [case3_v3_south]", fontsize=14, fontweight='bold', pad=12)
    
    # Y-axis range set to 60~120 as requested by user
    ax1.set_ylim(60, 120)
    ax1.legend(loc='upper right', framealpha=0, fontsize=11)
    ax1.grid(True, axis='y', linestyle=':', alpha=0.6)

    # Subplot 2: Monthly Relative Loss Rate (%) Bar Chart
    rects3 = ax2.bar(x, df['Loss_Percent'], width=0.55, color=color_loss, alpha=0.85, edgecolor='none', label='Self-Shading Loss Rate (%)')
    
    # Value labels: Black text, 1 decimal place
    for rect, loss in zip(rects3, df['Loss_Percent']):
        h = rect.get_height()
        y_pos = h - 0.5 if h < 0 else h + 0.2
        va = 'top' if h < 0 else 'bottom'
        fontweight = 'bold' if loss < -5.0 else 'normal'
        ax2.text(rect.get_x() + rect.get_width()/2., y_pos, f"{loss:.1f}%", ha='center', va=va, fontsize=9.5, color='black', fontweight=fontweight)

    ax2.axhline(0, color='black', linestyle='-', linewidth=1.0, alpha=0.8)
    ax2.set_ylabel("Self-Shading Loss Rate (%)", fontsize=12, fontweight='bold')
    ax2.set_title(r"Monthly PV Self-Shading Loss Rate ($\frac{\text{Row 6} - \text{Row 1}}{\text{Row 1}} \times 100\%$)", fontsize=13, fontweight='bold', pad=10)
    ax2.set_ylim(min(df['Loss_Percent']) * 1.25, 1.5)
    ax2.legend(loc='lower right', framealpha=0, fontsize=11)
    ax2.grid(True, axis='y', linestyle=':', alpha=0.6)

    # X-axis formatting
    ax2.set_xticks(x)
    ax2.set_xticklabels(month_labels, fontsize=11, fontweight='bold')
    ax2.set_xlabel("Month", fontsize=12, fontweight='bold')

    plt.tight_layout()

    # Save figure in both PNG and SVG with transparent background
    fig.savefig(plot_png_path, dpi=300, transparent=True, bbox_inches='tight')
    fig.savefig(plot_svg_path, transparent=True, bbox_inches='tight')
    plt.close(fig)

    print(f"Successfully generated figures:")
    print(f"  PNG: {plot_png_path}")
    print(f"  SVG: {plot_svg_path}")

if __name__ == "__main__":
    main()

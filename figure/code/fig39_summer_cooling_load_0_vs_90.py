import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import dartwork_mpl as dm

# Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

# Apply presentation style from dartwork_mpl
dm.style.use("presentation")

# Patch matplotlib font_manager for SVG export compatibility (resolves numeric font weight KeyError)
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w


def get_south_zone_cooling_day_data(sql_path, month, day):
    """SQLite DB에서 특정 월/일의 시간대별 남측 존 냉방 부하 추출"""
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    
    conn = sqlite3.connect(sql_path)
    
    # 1. Time table for the day
    df_time = pd.read_sql_query(
        f"SELECT TimeIndex, Month, Day, Hour, Minute FROM Time WHERE WarmupFlag = 0 AND Month = {month} AND Day = {day}", 
        conn
    )
    time_indices = tuple(df_time['TimeIndex'].tolist())
    time_str = f"({','.join(map(str, time_indices))})"
    
    c = conn.cursor()
    
    # 2. South Zone Cooling Indices (BIPV_OFFICE_1_S, BIPV_OFFICE_2_S)
    c.execute(
        "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary "
        "WHERE Name = 'Zone Ideal Loads Supply Air Total Cooling Energy' "
        "AND (KeyValue LIKE '%_1_S%' OR KeyValue LIKE '%_2_S%')"
    )
    s_indices = [str(r[0]) for r in c.fetchall()]
    s_idx_str = ",".join(s_indices)
    
    # Query Data
    df_s = pd.read_sql_query(
        f"SELECT TimeIndex, SUM(Value) as SouthJ FROM ReportData "
        f"WHERE TimeIndex IN {time_str} AND ReportDataDictionaryIndex IN ({s_idx_str}) "
        f"GROUP BY TimeIndex", 
        conn
    )
    
    conn.close()
    
    # Merge and calculate kWh
    df_merged = pd.merge(df_time, df_s, on="TimeIndex", how="left").fillna(0)
    df_merged['South_kWh'] = df_merged['SouthJ'] / 3.6e6
    
    # Resample to hourly (EnergyPlus 6 timesteps/hr)
    df_hourly = df_merged.groupby('Hour').agg({
        'South_kWh': 'sum'
    }).reset_index()
    
    return df_hourly


def main():
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    plot_dir     = os.path.join(project_root, "figure", "plot", "fig39_summer_cooling_load_0_vs_90")
    os.makedirs(plot_dir, exist_ok=True)
    
    base_dir = os.path.join(project_root, "case_analysis", "normal", "case2_KS")
    angles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    
    print("Loading simulation datasets for all 10 angles (0° to 90°)...")
    data_by_angle = {}
    for ang in angles:
        sql_p = os.path.join(base_dir, f"case2_{ang}", "eplusout.sql")
        df_ang = get_south_zone_cooling_day_data(sql_p, 8, 2)
        data_by_angle[ang] = df_ang
        
    hours = data_by_angle[0]['Hour'].values
    
    # Prepare Summary DataFrame
    summary_dict = {'Hour': hours}
    for ang in angles:
        summary_dict[f'Angle_{ang:02d}_kWh'] = data_by_angle[ang]['South_kWh']
    summary_df = pd.DataFrame(summary_dict)
    
    csv_path = os.path.join(plot_dir, "fig39_summer_cooling_load_all_angles_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    print(f"Summary data saved to: {csv_path}")
    
    # -------------------------------------------------------------------------
    # Plotting: Single-panel Integrated Diurnal Cooling Load Curves (0° to 90°)
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    
    # Fixed chromatic gradient palette (identical to fig35)
    # 0°: Red -> 90°: Deep Indigo Blue
    palette = [
        "#dc2626",  # 0°  - Vivid Crimson Red
        "#ea580c",  # 10° - Rust Orange
        "#d97706",  # 20° - Amber
        "#ca8a04",  # 30° - Gold
        "#65a30d",  # 40° - Olive Green
        "#0d9488",  # 50° - Teal
        "#0284c7",  # 60° - Sky Cyan
        "#2563eb",  # 70° - Royal Blue
        "#7c3aed",  # 80° - Violet
        "#4338ca",  # 90° - Deep Indigo Blue
    ]
    
    # 1. Plot lines for each angle with uniform linewidth
    lines = []
    labels = []
    
    for i, ang in enumerate(angles):
        s_kwh = data_by_angle[ang]['South_kWh'].values
        daily_sum = s_kwh.sum()
        color = palette[i]
        
        # Style definition: Uniform line width across all angles
        lw = 2.2
        alpha = 0.95
        zorder = 5
        
        if ang == 0:
            zorder = 10
            lbl = f"BIPV  0° (Daily: {daily_sum:5.1f} kWh) [Full Shading]"
        elif ang == 90:
            zorder = 10
            lbl = f"BIPV 90° (Daily: {daily_sum:5.1f} kWh) [Horizontal Overhang, Max Solar]"
        else:
            lbl = f"BIPV {ang:2d}° (Daily: {daily_sum:5.1f} kWh)"
            
        line, = ax.plot(
            hours, 
            s_kwh, 
            color=color, 
            linewidth=lw, 
            alpha=alpha, 
            zorder=zorder,
            label=lbl
        )
        lines.append(line)
        labels.append(lbl)
    

    
    # Chart Styling
    ax.set_title(
        "South Zone Diurnal Cooling Load Progression across BIPV Tilt Angles (0° to 90°)\n"
        "(Summer Representative Day: Aug 02 | Gwangju Climate)", 
        fontsize=14.5, 
        fontweight='bold', 
        pad=16
    )
    ax.set_xlabel("Hour of Day", fontsize=12.5, fontweight='bold')
    ax.set_ylabel("South Zone Cooling Load [kWh]", fontsize=12.5, fontweight='bold')
    
    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_ylim(-0.5, 25)
    ax.grid(True, linestyle=':', alpha=0.55)
    
    # Legend: 2 columns with transparent background
    ax.legend(
        lines, 
        labels, 
        loc="upper left", 
        bbox_to_anchor=(0.01, 0.98),
        ncols=2, 
        fontsize=9.5, 
        framealpha=0, 
        facecolor="none"
    )
    
    plt.tight_layout()
    
    # Save Figures (PNG & SVG with transparent backgrounds)
    png_path = os.path.join(plot_dir, "fig39_summer_cooling_load_0_vs_90.png")
    svg_path = os.path.join(plot_dir, "fig39_summer_cooling_load_0_vs_90.svg")
    
    plt.savefig(png_path, dpi=300, transparent=True, bbox_inches='tight')
    plt.savefig(svg_path, transparent=True, bbox_inches='tight')
    plt.close()
    
    print(f"\nFigures successfully updated and generated:")
    print(f" - PNG: {png_path}")
    print(f" - SVG: {svg_path}")


if __name__ == "__main__":
    main()

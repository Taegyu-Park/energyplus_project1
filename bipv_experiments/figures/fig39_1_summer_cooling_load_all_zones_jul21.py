import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

# Apply presentation style from dartwork_mpl
dm.style.use("presentation")

# Patch matplotlib font_manager for SVG export compatibility (resolves numeric font weight KeyError)
import matplotlib.font_manager as fm
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w


def get_all_zones_cooling_day_data(sql_path, month, day):
    """SQLite DB에서 특정 월/일의 시간대별 전체 존(All 10 Zones) 냉방 부하 추출"""
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
    
    # 2. All Zones Cooling Indices (1F/2F Core, East, North, South, West total 10 zones)
    c.execute(
        "SELECT ReportDataDictionaryIndex FROM ReportDataDictionary "
        "WHERE Name = 'Zone Ideal Loads Supply Air Total Cooling Energy'"
    )
    all_indices = [str(r[0]) for r in c.fetchall()]
    idx_str = ",".join(all_indices)
    
    # Query Data: Summing across all 10 zones per timestep
    df_load = pd.read_sql_query(
        f"SELECT TimeIndex, SUM(Value) as TotalJ FROM ReportData "
        f"WHERE TimeIndex IN {time_str} AND ReportDataDictionaryIndex IN ({idx_str}) "
        f"GROUP BY TimeIndex", 
        conn
    )
    
    conn.close()
    
    # Merge and calculate kWh
    df_merged = pd.merge(df_time, df_load, on="TimeIndex", how="left").fillna(0)
    df_merged['Total_kWh'] = df_merged['TotalJ'] / 3.6e6
    
    # Resample to hourly (EnergyPlus 6 timesteps/hr)
    df_hourly = df_merged.groupby('Hour').agg({
        'Total_kWh': 'sum'
    }).reset_index()
    
    return df_hourly


def main():
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))  # bipv_experiments/figures -> 저장소 루트
    plot_dir     = os.path.join(script_dir, "fig39_1_summer_cooling_load_all_zones_jul21")
    os.makedirs(plot_dir, exist_ok=True)
    
    base_dir = os.path.join(project_root, "case_analysis", "normal", "case2_KS")
    angles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    
    print("Loading simulation datasets for all 10 angles (0° to 90°) across all zones (Jul 21)...")
    data_by_angle = {}
    for ang in angles:
        sql_p = os.path.join(base_dir, f"case2_{ang}", "eplusout.sql")
        df_ang = get_all_zones_cooling_day_data(sql_p, 7, 21)
        data_by_angle[ang] = df_ang
        
    # Load Kinetic BIPV (Sun-Tracking) Case 3 South Data
    kinetic_sql_p = os.path.join(
        project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south", "eplusout.sql"
    )
    print("Loading simulation dataset for Kinetic BIPV (case3_v3_south) across all zones (Jul 21)...")
    df_kinetic = get_all_zones_cooling_day_data(kinetic_sql_p, 7, 21)
    kinetic_kwh = df_kinetic['Total_kWh'].values
    kinetic_daily = kinetic_kwh.sum()
    
    hours = data_by_angle[0]['Hour'].values
    
    # Prepare Summary DataFrame
    summary_dict = {'Hour': hours}
    for ang in angles:
        summary_dict[f'Angle_{ang:02d}_kWh'] = data_by_angle[ang]['Total_kWh']
    summary_dict['Kinetic_BIPV_kWh'] = kinetic_kwh
    summary_df = pd.DataFrame(summary_dict)
    
    csv_path = os.path.join(plot_dir, "fig39_1_summer_cooling_load_all_zones_jul21_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    print(f"Summary data saved to: {csv_path}")
    
    # -------------------------------------------------------------------------
    # Plotting: Single-panel Integrated Diurnal Cooling Load Curves (All Zones)
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    
    # Slate Gray monotone gradient palette (identical to fig35_1)
    # 0° Light Slate Gray -> 90° Deep Charcoal / Slate Black
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "gray_monotone_inv", ["#cbd5e1", "#94a3b8", "#64748b", "#334155", "#0f172a"]
    )
    palette = [mpl.colors.to_hex(cmap(i / 9)) for i in range(10)]
    
    # 1. Plot lines for each angle
    lines = []
    labels = []
    
    for i, ang in enumerate(angles):
        total_kwh = data_by_angle[ang]['Total_kWh'].values
        daily_sum = total_kwh.sum()
        color = palette[i]
        
        # Style definition: Uniform line width across all angles
        lw = 2.2
        alpha = 0.95
        zorder = 5 + i
        
        if ang == 0:
            lbl = f"BIPV  0° (Daily: {daily_sum:5.1f} kWh) [Full Shading, Min Cooling]"
        elif ang == 90:
            lbl = f"BIPV 90° (Daily: {daily_sum:5.1f} kWh) [Horizontal Overhang, Max Solar]"
        else:
            lbl = f"BIPV {ang:2d}° (Daily: {daily_sum:5.1f} kWh)"
            
        line, = ax.plot(
            hours, 
            total_kwh, 
            color=color, 
            linewidth=lw, 
            alpha=alpha, 
            zorder=zorder,
            label=lbl
        )
        lines.append(line)
        labels.append(lbl)
    
    # 2. Plot Kinetic BIPV (Sun-Tracking) in distinct Vivid Orange (identical to fig35_1)
    line_kinetic, = ax.plot(
        hours,
        kinetic_kwh,
        color="#ea580c",  # Vivid Orange 600
        linewidth=2.8,
        alpha=1.0,
        zorder=25,
        label=f"Kinetic BIPV (Sun-Tracking) (Daily: {kinetic_daily:5.1f} kWh)"
    )
    lines.append(line_kinetic)
    labels.append(f"Kinetic BIPV (Sun-Tracking) (Daily: {kinetic_daily:5.1f} kWh)")
    
    # Chart Styling
    ax.set_title(
        "Total Building (All Zones) Diurnal Cooling Load: Fixed Angles (0°–90°) vs Kinetic BIPV\n"
        "(Summer Representative Day: Jul 21 | Gwangju Climate)", 
        fontsize=14.5, 
        fontweight='bold', 
        pad=16
    )
    ax.set_xlabel("Hour of Day", fontsize=12.5, fontweight='bold')
    ax.set_ylabel("Total Building Cooling Load [kWh]", fontsize=12.5, fontweight='bold')
    
    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    # 날짜에 따라 부하 크기가 달라 고정 상한(100) 대신 데이터 최대값 기준 (범례 공간 확보용 여유 포함)
    y_max = max(np.nanmax(l.get_ydata()) for l in lines)
    ax.set_ylim(-2, np.ceil(y_max * 1.45 / 20) * 20)
    ax.grid(True, linestyle=':', alpha=0.55)
    
    # Legend: 2 columns with transparent background, placed at upper left where morning load is 0
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
    png_path = os.path.join(plot_dir, "fig39_1_summer_cooling_load_all_zones_jul21.png")
    svg_path = os.path.join(plot_dir, "fig39_1_summer_cooling_load_all_zones_jul21.svg")
    
    plt.savefig(png_path, dpi=300, transparent=True, bbox_inches='tight')
    plt.savefig(svg_path, transparent=True, bbox_inches='tight')
    plt.close()
    
    print(f"\nFigures successfully generated:")
    print(f" - PNG: {png_path}")
    print(f" - SVG: {svg_path}")


if __name__ == "__main__":
    main()

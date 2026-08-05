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

def get_day_hours(month, day):
    """Calculate 0-based start and end hour indices for a non-leap year (365 days)"""
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    start_day = sum(days_in_month[:month-1]) + (day - 1)
    start_hour = start_day * 24
    end_hour = start_hour + 24
    return start_hour, end_hour

def load_sql_south_zone_load(sql_path, var_name):
    """SQLite DB에서 건물 남측 1,2층 존(BIPV_OFFICE_1_S, BIPV_OFFICE_2_S)의 부하 추출"""
    if not os.path.exists(sql_path):
        print(f"ERROR: File not found at {sql_path}")
        return None
    conn = sqlite3.connect(sql_path)
    df_time = pd.read_sql_query("SELECT TimeIndex, Month, Day, Hour, Minute FROM Time WHERE WarmupFlag = 0", conn)
    c = conn.cursor()
    c.execute(f"SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = '{var_name}' AND (KeyValue LIKE '%_1_S%' OR KeyValue LIKE '%_2_S%')")
    indices = [r[0] for r in c.fetchall()]
    if not indices:
        conn.close()
        return None
    idx_str = ",".join(map(str, indices))
    
    df_rd = pd.read_sql_query(f"SELECT TimeIndex, SUM(Value) as TotalJ FROM ReportData WHERE ReportDataDictionaryIndex IN ({idx_str}) GROUP BY TimeIndex", conn)
    conn.close()
    
    df = pd.merge(df_time, df_rd, on="TimeIndex", how="inner")
    df['kWh'] = df['TotalJ'] / 3.6e6
    return df

def process_hourly_dataset(df_raw):
    """Resample 6 timesteps per hour -> 8760 hourly sums"""
    if df_raw is None:
        return None
    df_hourly = df_raw.groupby(df_raw.index // 6).agg({
        'Month': 'first',
        'Day': 'first',
        'Hour': 'first',
        'kWh': 'sum'
    })
    return df_hourly

def main():
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    plot_dir     = os.path.join(project_root, "figure", "plot", "fig30_south_window_solar_gain_comparison")
    
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
        
    angles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    
    cool_data = {}
    heat_data = {}

    # 1. Case 1 (Base Case - No PV)
    case1_path = os.path.join(project_root, "case_analysis", "normal", "case1_KS", "eplusout.sql")
    print(f"Loading Case 1 (Base Case - No PV)...")
    df_c1_cool = process_hourly_dataset(load_sql_south_zone_load(case1_path, 'Zone Ideal Loads Supply Air Total Cooling Energy'))
    df_c1_heat = process_hourly_dataset(load_sql_south_zone_load(case1_path, 'Zone Ideal Loads Supply Air Total Heating Energy'))
    if df_c1_cool is not None: cool_data["Base_Case1"] = df_c1_cool['kWh'].values
    if df_c1_heat is not None: heat_data["Base_Case1"] = df_c1_heat['kWh'].values

    # 2. Case 2 (Normal/case2_KS) - 10 fixed angles (0° to 90°)
    case2_base_path = os.path.join(project_root, "case_analysis", "normal", "case2_KS")
    for angle in angles:
        sql_path = os.path.join(case2_base_path, f"case2_{angle}", "eplusout.sql")
        print(f"Loading Case 2 ({angle}°)...")
        df_c2_cool = process_hourly_dataset(load_sql_south_zone_load(sql_path, 'Zone Ideal Loads Supply Air Total Cooling Energy'))
        df_c2_heat = process_hourly_dataset(load_sql_south_zone_load(sql_path, 'Zone Ideal Loads Supply Air Total Heating Energy'))
        if df_c2_cool is not None: cool_data[f"Fixed_{angle}deg"] = df_c2_cool['kWh'].values
        if df_c2_heat is not None: heat_data[f"Fixed_{angle}deg"] = df_c2_heat['kWh'].values

    # 3. Case 3 (bipv_variation/5zone_NSEW_korean/case3_v3_south) - Kinetic BIPV South
    case3_south_path = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south", "eplusout.sql")
    print(f"Loading Case 3 (Kinetic South)...")
    df_c3_cool = process_hourly_dataset(load_sql_south_zone_load(case3_south_path, 'Zone Ideal Loads Supply Air Total Cooling Energy'))
    df_c3_heat = process_hourly_dataset(load_sql_south_zone_load(case3_south_path, 'Zone Ideal Loads Supply Air Total Heating Energy'))
    if df_c3_cool is not None: cool_data["Kinetic_South"] = df_c3_cool['kWh'].values
    if df_c3_heat is not None: heat_data["Kinetic_South"] = df_c3_heat['kWh'].values

    df_cool_all = pd.DataFrame(cool_data)
    df_heat_all = pd.DataFrame(heat_data)
    
    # Save datasets to CSV
    csv_cool_path = os.path.join(plot_dir, "fig30_south_zone_cooling_hourly.csv")
    csv_heat_path = os.path.join(plot_dir, "fig30_south_zone_heating_hourly.csv")
    df_cool_all.to_csv(csv_cool_path, index=False)
    df_heat_all.to_csv(csv_heat_path, index=False)
    print(f"Saved dataset CSVs to {plot_dir}")

    # Color palette configuration
    color_base = '#dc2626'      # Distinct Red (Base Case 1 - No PV)
    color_kinetic = '#f59e0b'   # Amber/Orange (Kinetic BIPV Case 3)
    cmap = mpl.colormaps['coolwarm'].resampled(len(angles))
    angle_colors = {angle: cmap(i / (len(angles) - 1)) for i, angle in enumerate(angles)}

    # =========================================================================
    # Representative Days 24-Hour Profile Plot
    # Summer Rep Day: 8/2 (Cooling Demand)
    # Winter Rep Day: 12/28 (Heating Demand)
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    
    # 1. Summer Representative Day (8/2) - Cooling Load
    ax_sum = axes[0]
    start_h, end_h = get_day_hours(8, 2)
    time_hours = np.arange(0, 24)
    
    # Plot Case 2 Fixed Angles
    for angle in angles:
        col_name = f'Fixed_{angle}deg'
        lw = 1.3 if angle in [0, 90] else 1.1
        ls = '-' if angle in [0, 30, 60, 90] else ':'
        ax_sum.plot(time_hours, df_cool_all[col_name].iloc[start_h:end_h], 
                    color=angle_colors[angle], linestyle=ls, linewidth=lw, alpha=0.75, 
                    label=f'Fixed {angle}° (Case 2)')
        
    # Plot Case 3 Kinetic BIPV South
    ax_sum.plot(time_hours, df_cool_all['Kinetic_South'].iloc[start_h:end_h], 
                color=color_kinetic, linewidth=3.0, label='Kinetic BIPV South (Case 3)')
    
    # Plot Case 1 Base (No PV) - Bold Red Dashed Line
    ax_sum.plot(time_hours, df_cool_all['Base_Case1'].iloc[start_h:end_h], 
                color=color_base, linestyle='--', linewidth=3.2, label='Base (No PV, Case 1)')

    ax_sum.set_title('Summer Representative Day (8/02)\nSouth Zone Cooling Demand [kWh]', fontsize=14, fontweight='bold', pad=10)
    ax_sum.set_xlim(0, 23)
    ax_sum.set_xticks([0, 4, 8, 12, 16, 20, 23])
    ax_sum.set_xticklabels(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '23:00'])
    ax_sum.set_xlabel('Time of Day', fontsize=12, fontweight='bold')
    ax_sum.set_ylabel('Hourly Cooling Demand [kWh]', fontsize=12, fontweight='bold')
    ax_sum.grid(True, linestyle=':', alpha=0.6)
    ax_sum.legend(loc='upper left', framealpha=0, facecolor='none', fontsize=8.5, ncol=2)

    # 2. Winter Representative Day (12/28) - Heating Load
    ax_win = axes[1]
    start_h, end_h = get_day_hours(12, 28)
    
    # Plot Case 2 Fixed Angles
    for angle in angles:
        col_name = f'Fixed_{angle}deg'
        lw = 1.3 if angle in [0, 90] else 1.1
        ls = '-' if angle in [0, 30, 60, 90] else ':'
        ax_win.plot(time_hours, df_heat_all[col_name].iloc[start_h:end_h], 
                    color=angle_colors[angle], linestyle=ls, linewidth=lw, alpha=0.75, 
                    label=f'Fixed {angle}° (Case 2)')
        
    # Plot Case 3 Kinetic BIPV South
    ax_win.plot(time_hours, df_heat_all['Kinetic_South'].iloc[start_h:end_h], 
                color=color_kinetic, linewidth=3.0, label='Kinetic BIPV South (Case 3)')
    
    # Plot Case 1 Base (No PV) - Bold Red Dashed Line
    ax_win.plot(time_hours, df_heat_all['Base_Case1'].iloc[start_h:end_h], 
                color=color_base, linestyle='--', linewidth=3.2, label='Base (No PV, Case 1)')

    ax_win.set_title('Winter Representative Day (12/28)\nSouth Zone Heating Demand [kWh]', fontsize=14, fontweight='bold', pad=10)
    ax_win.set_xlim(0, 23)
    ax_win.set_xticks([0, 4, 8, 12, 16, 20, 23])
    ax_win.set_xticklabels(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '23:00'])
    ax_win.set_xlabel('Time of Day', fontsize=12, fontweight='bold')
    ax_win.set_ylabel('Hourly Heating Demand [kWh]', fontsize=12, fontweight='bold')
    ax_win.grid(True, linestyle=':', alpha=0.6)
    ax_win.legend(loc='upper right', framealpha=0, facecolor='none', fontsize=8.5, ncol=2)

    plt.suptitle('Diurnal South Zone (1st & 2nd Floor) Thermal Demand: Base (Case 1) vs. Fixed PV (Case 2) vs. Kinetic (Case 3)', fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    png_path = os.path.join(plot_dir, "fig30_south_window_solar_gain_comparison.png")
    svg_path = os.path.join(plot_dir, "fig30_south_window_solar_gain_comparison.svg")
    
    fig.savefig(png_path, dpi=300, transparent=True)
    fig.savefig(svg_path, transparent=True)
    plt.close(fig)
    print(f"Saved representative day diurnal plot to: {plot_dir}")

if __name__ == '__main__':
    main()

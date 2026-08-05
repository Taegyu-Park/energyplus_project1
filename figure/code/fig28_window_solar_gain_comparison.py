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

def load_sql_solar_gain(sql_path):
    """SQLite DB에서 Zone Ideal Loads Supply Air Total Cooling Energy (창면 태양 열취득 연관 부하) 추출"""
    if not os.path.exists(sql_path):
        print(f"ERROR: File not found at {sql_path}")
        return None
    conn = sqlite3.connect(sql_path)
    df_time = pd.read_sql_query("SELECT TimeIndex, Month, Day, Hour, Minute FROM Time WHERE WarmupFlag = 0", conn)
    c = conn.cursor()
    c.execute("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = 'Zone Ideal Loads Supply Air Total Cooling Energy'")
    indices = [r[0] for r in c.fetchall()]
    idx_str = ",".join(map(str, indices))
    
    df_rd = pd.read_sql_query(f"SELECT TimeIndex, SUM(Value) as TotalJ FROM ReportData WHERE ReportDataDictionaryIndex IN ({idx_str}) GROUP BY TimeIndex", conn)
    conn.close()
    
    df = pd.merge(df_time, df_rd, on="TimeIndex", how="inner")
    df['kWh'] = df['TotalJ'] / 3.6e6
    return df

def main():
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    plot_dir     = os.path.join(project_root, "figure", "plot", "fig28_window_solar_gain_comparison")
    
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
        
    angles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    data = {}

    # 1. Case 2 (normal/case2_KS) - 10 fixed angles (0° to 90°)
    case2_base_path = os.path.join(project_root, "case_analysis", "normal", "case2_KS")
    for angle in angles:
        sql_path = os.path.join(case2_base_path, f"case2_{angle}", "eplusout.sql")
        print(f"Loading Case 2 ({angle}°) from {sql_path}...")
        df_angle = load_sql_solar_gain(sql_path)
        if df_angle is not None:
            data[f"Fixed_{angle}deg"] = df_angle['kWh'].values

    # 2. Case 3 (bipv_variation/5zone_NSEW_korean/case3_v3_south) - Kinetic BIPV South
    case3_south_path = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south", "eplusout.sql")
    print(f"Loading Case 3 (South) from {case3_south_path}...")
    df_c3 = load_sql_solar_gain(case3_south_path)
    if df_c3 is not None:
        data["Kinetic_South"] = df_c3['kWh'].values

    df_all = pd.DataFrame(data)
    
    # Save processed dataset to fig28_data.csv for reference
    data_csv_path = os.path.join(plot_dir, "fig28_data.csv")
    df_all.to_csv(data_csv_path, index=False)
    print(f"Saved processed dataset to {data_csv_path}")

    # Resample to hourly data (52,560 timesteps -> 8,760 hours)
    df_hourly = df_all.groupby(df_all.index // 6).sum()
    df_hourly.index = pd.date_range("2026-01-01 00:00:00", periods=8760, freq="h")
        
    # Colors setup: sleek colormap for the 10 fixed angles (0° to 90°)
    cmap = mpl.colormaps['coolwarm'].resampled(len(angles))
    angle_colors = {angle: cmap(i / (len(angles) - 1)) for i, angle in enumerate(angles)}
    color_kinetic = '#f59e0b' # Amber/Orange (Kinetic BIPV)

    # =========================================================================
    # 1. 대표일(여름/겨울) 시간대별 프로파일 그래프 (Diurnal Profiles Plot)
    # =========================================================================
    rep_days = {
        'Summer': (8, 2, "Summer Representative Day (8/02)"),
        'Winter': (12, 28, "Winter Representative Day (12/28)")
    }
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), sharey=True)
    
    for i, season in enumerate(['Summer', 'Winter']):
        ax = axes[i]
        month, day, title_label = rep_days[season]
        start_h, end_h = get_day_hours(month, day)
        
        day_df = df_hourly.iloc[start_h:end_h]
        time_hours = np.arange(0, 24)
        
        # 1. Plot All 10 Fixed Angles (Case 2: 0° to 90°)
        for angle in angles:
            col_name = f'Fixed_{angle}deg'
            lw = 1.3 if angle in [0, 90] else 1.1
            ls = '-' if angle in [0, 30, 60, 90] else ':'
            ax.plot(time_hours, day_df[col_name], color=angle_colors[angle], linestyle=ls, linewidth=lw, alpha=0.85, label=f'Fixed {angle}° (Case 2)')
            
        # 2. Plot Kinetic BIPV South (Case 3)
        ax.plot(time_hours, day_df['Kinetic_South'], color=color_kinetic, linewidth=3.2, label='Kinetic BIPV South (Case 3)')
        
        ax.set_title(title_label, fontsize=14, fontweight='bold', pad=10)
        ax.set_xlim(0, 23)
        ax.set_xticks([0, 4, 8, 12, 16, 20, 23])
        ax.set_xticklabels(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '23:00'])
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.set_xlabel('Time of Day', fontsize=12, fontweight='bold')
        
        if i == 0:
            ax.set_ylabel('Hourly Solar Heat Gain / Cooling Energy [kWh]', fontsize=12, fontweight='bold')
            
        ax.legend(loc='upper right', framealpha=0, facecolor='none', fontsize=9.5, ncol=2)

    plt.suptitle('Diurnal Window Solar Heat Gain & Cooling Energy: Fixed Angles (Case 2) vs. Kinetic (Case 3)', fontsize=17, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    png_diurnal_path = os.path.join(plot_dir, "fig28_window_solar_gain_comparison_diurnal.png")
    svg_diurnal_path = os.path.join(plot_dir, "fig28_window_solar_gain_comparison_diurnal.svg")
    
    fig.savefig(png_diurnal_path, dpi=300, transparent=True)
    fig.savefig(svg_diurnal_path, transparent=True)
    plt.close(fig)
    print(f"Saved diurnal comparison plots (0° to 90°) to: {plot_dir}")

    # =========================================================================
    # 2. 월별 누적 일사/냉방 부하 그래프 (Monthly Cumulative Plot)
    # =========================================================================
    monthly_df = df_hourly.groupby(df_hourly.index.month).sum()
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    months = np.arange(1, 13)
    num_bars = len(angles) + 1  # 10 angles + Kinetic (Base Case Excluded)
    width = 0.8 / num_bars
    
    # Plot 10 Fixed Angles bars (Case 2)
    for idx, angle in enumerate(angles):
        col_name = f'Fixed_{angle}deg'
        ax.bar(months - (num_bars/2 - 0.5 - idx) * width, monthly_df[col_name], width, label=f'Fixed {angle}° (Case 2)', color=angle_colors[angle])
        
    # Plot Kinetic BIPV bar (Case 3)
    ax.bar(months + (num_bars/2 - 0.5) * width, monthly_df['Kinetic_South'], width, label='Kinetic BIPV South (Case 3)', color=color_kinetic)
    
    ax.set_title('Monthly Cumulative Solar Heat Gain & Cooling Energy (Fixed Angles Case 2 vs. Kinetic Case 3)', fontsize=16, fontweight='bold', pad=15)
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Solar Heat Gain / Cooling Energy [kWh]', fontsize=12, fontweight='bold')
    ax.set_xticks(months)
    ax.set_xticklabels([f'{m}M' for m in months])
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='upper right', framealpha=0, facecolor='none', fontsize=9.5, ncol=3)
    
    plt.tight_layout()
    
    png_monthly_path = os.path.join(plot_dir, "fig28_window_solar_gain_comparison_monthly.png")
    svg_monthly_path = os.path.join(plot_dir, "fig28_window_solar_gain_comparison_monthly.svg")
    
    fig.savefig(png_monthly_path, dpi=300, transparent=True)
    fig.savefig(svg_monthly_path, transparent=True)
    plt.close(fig)
    print(f"Saved monthly comparison plots to: {plot_dir}")

if __name__ == '__main__':
    main()

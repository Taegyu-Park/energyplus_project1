import os
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

def parse_ep_datetime(df):
    dt_str = df['Date/Time'].str.strip()
    parts = dt_str.str.split(expand=True)
    date_parts = parts[0].str.split('/', expand=True)
    time_parts = parts[1].str.split(':', expand=True)
    
    df['Month'] = date_parts[0].astype(int)
    df['Day'] = date_parts[1].astype(int)
    df['Hour'] = time_parts[0].astype(int)
    df['Minute'] = time_parts[1].astype(int)
    return df

def main():
    # ── 경로 설정 ────────────────────────────────────────────────────────
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    data_dir     = os.path.join(project_root, "case_analysis", "bipv_variation")
    
    # ── 데이터 파일 ───────────────────────────────────────────────────────
    files = {
        "South": os.path.join(data_dir, "case3_terracotta.csv"),
        "East": os.path.join(data_dir, "case3_v3_east_terracotta.csv"),
        "North": os.path.join(data_dir, "case3_v3_north_terracotta.csv"),
        "West": os.path.join(data_dir, "case3_v3_west_terracotta.csv")
    }
    
    # Representative days
    rep_days = {
        'Winter': (12, 23, "Winter Representative Day (12/23)"),
        'Spring': (4, 21, "Spring Representative Day (4/21)"),
        'Summer': (8, 2, "Summer Representative Day (8/02)"),
        'Autumn': (9, 29, "Autumn Representative Day (9/29)")
    }
    
    # Load and process data
    data_by_orientation = {}
    for name, path in files.items():
        print(f"Loading {name} data...")
        cols = [
            'Date/Time',
            'Whole Building:Facility Net Purchased Electricity Energy [J](TimeStep)',
            'Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)'
        ]
        df = pd.read_csv(path, usecols=cols)
        df = parse_ep_datetime(df)
        
        # Calculate Power in kW (Energy in J / 600 seconds / 1000)
        df['Load_kW'] = (df['Whole Building:Facility Net Purchased Electricity Energy [J](TimeStep)'] + 
                         df['Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)']) / 6.0e5
        df['Gen_kW'] = df['Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)'] / 6.0e5
        
        # Time in hours (0 to 24)
        # Note: EnergyPlus 24:00 corresponds to hour 24.
        # We can map each timestep to a fraction of a day: (hour * 60 + minute) / 60
        # Since the timestep represents the end of the interval, 00:10 is 10 mins, 24:00 is 24 hours.
        # Let's handle 24:00 as 24.0.
        df['Time_Hours'] = df.apply(lambda r: 24.0 if r['Hour'] == 24 else (r['Hour'] + r['Minute'] / 60.0), axis=1)
        
        data_by_orientation[name] = df
        
    # ── 시각화 스타일 설정 ──────────────────────────────────────────────────
    dm.style.use("presentation")
    
    # Colors for orientations and load
    colors = {
        'Load': '#64748b',       # Muted slate gray
        'South': '#ef4444',      # Vibrant Red
        'East': '#f59e0b',       # Orange/Amber (Sun rises in the east)
        'West': '#3b82f6',       # Blue (Sun sets in the west)
        'North': '#10b981'       # Emerald Green
    }
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True)
    axes_flat = axes.flatten()
    
    seasons = ['Winter', 'Spring', 'Summer', 'Autumn']
    
    for i, season in enumerate(seasons):
        ax = axes_flat[i]
        month, day, label = rep_days[season]
        
        # Plot Building Load (Load is identical, so we use South as load reference)
        ref_df = data_by_orientation['South']
        day_ref = ref_df[(ref_df['Month'] == month) & (ref_df['Day'] == day)].sort_values('Time_Hours')
        
        # Area fill for load to represent demand baseline
        ax.fill_between(day_ref['Time_Hours'], day_ref['Load_kW'], color=colors['Load'], alpha=0.15, label='Building Load')
        ax.plot(day_ref['Time_Hours'], day_ref['Load_kW'], color=colors['Load'], linestyle='--', linewidth=1.5)
        
        # Plot BIPV Generation for each orientation
        for name in ['South', 'East', 'West', 'North']:
            df = data_by_orientation[name]
            day_data = df[(df['Month'] == month) & (df['Day'] == day)].sort_values('Time_Hours')
            ax.plot(day_data['Time_Hours'], day_data['Gen_kW'], color=colors[name], linewidth=2.5, label=f'{name} BIPV Gen')
            
        ax.set_title(label, fontsize=14, fontweight='bold', pad=10)
        ax.set_xlim(0, 24)
        ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
        ax.set_xticklabels(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'])
        ax.grid(True, linestyle=':', alpha=0.6)
        
        if i in [0, 2]:
            ax.set_ylabel('Power [kW]', fontweight='bold', fontsize=12)
        if i in [2, 3]:
            ax.set_xlabel('Time of Day', fontweight='bold', fontsize=12)
            
        # Transparent legend
        ax.legend(loc='upper right', framealpha=0, fontsize=10)
        
    plt.suptitle('Diurnal Load and BIPV Generation Mismatch by Orientation', fontsize=18, fontweight='bold', y=0.96)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # ── 결과 저장 ────────────────────────────────────────────────────────
    output_dir = os.path.join(project_root, "figure", "plot", "fig26_seasonal_mismatch_analysis")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    png_path = os.path.join(output_dir, "fig26_seasonal_mismatch_analysis.png")
    svg_path = os.path.join(output_dir, "fig26_seasonal_mismatch_analysis.svg")
    
    fig.savefig(png_path, dpi=300, transparent=True)
    fig.savefig(svg_path, transparent=True)
    
    print(f"Saved PNG to: {png_path}")
    print(f"Saved SVG to: {svg_path}")

if __name__ == '__main__':
    main()

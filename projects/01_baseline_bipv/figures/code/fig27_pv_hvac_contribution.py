import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

def load_data_from_sql(sql_path):
    """SQLite DB에서 HVAC 부하와 PV 발전량을 timestep 단위로 쿼리하여 DataFrame으로 반환"""
    if not os.path.exists(sql_path):
        print(f"File not found: {sql_path}")
        return None
        
    conn = sqlite3.connect(sql_path)
    
    # 1. 냉난방 부하 합산 쿼리 (10개 존의 Heating & Cooling Energy 합산)
    hvac_query = """
    SELECT 
        t.Month, 
        t.Day, 
        t.Hour, 
        t.Minute, 
        SUM(rd.Value) as HVAC_Energy_J
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name IN ('Zone Ideal Loads Supply Air Total Heating Energy', 'Zone Ideal Loads Supply Air Total Cooling Energy')
    GROUP BY t.Month, t.Day, t.Hour, t.Minute
    """
    df_hvac = pd.read_sql_query(hvac_query, conn)
    
    # 2. PV 발전량 쿼리 (Facility Total Produced Electricity Energy)
    gen_query = """
    SELECT 
        t.Month, 
        t.Day, 
        t.Hour, 
        t.Minute, 
        rd.Value as Gen_Energy_J
    FROM ReportData rd
    JOIN ReportDataDictionary rdd ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rdd.Name = 'Facility Total Produced Electricity Energy'
    """
    df_gen = pd.read_sql_query(gen_query, conn)
    
    conn.close()
    
    # 두 데이터프레임 병합
    df = pd.merge(df_hvac, df_gen, on=['Month', 'Day', 'Hour', 'Minute'])
    
    # 에너지 [J] -> 전력 [kW] 변환 (10분 timestep = 600초)
    # Power = Energy / 600 / 1000
    df['HVAC_kW'] = df['HVAC_Energy_J'] / 6.0e5
    df['Gen_kW'] = df['Gen_Energy_J'] / 6.0e5
    
    # BIPV 발전량 중 냉난방 부하를 직접 해결하는 데 기여한 전력량 계산 (Self-Consumed Power for HVAC)
    df['Contribution_kW'] = np.minimum(df['Gen_kW'], df['HVAC_kW'])
    
    # 시간 변환 (0.0 to 24.0)
    df['Time_Hours'] = df.apply(lambda r: 24.0 if r['Hour'] == 24 else (r['Hour'] + r['Minute'] / 60.0), axis=1)
    
    return df

def main():
    # ── 경로 설정 ────────────────────────────────────────────────────────
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    data_dir     = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean")
    
    orientations = {
        "South": os.path.join(data_dir, "case3_v3_south", "eplusout.sql"),
        "East": os.path.join(data_dir, "case3_v3_east", "eplusout.sql"),
        "North": os.path.join(data_dir, "case3_v3_north", "eplusout.sql"),
        "West": os.path.join(data_dir, "case3_v3_west", "eplusout.sql")
    }
    
    # 계절별 대표일 정의
    rep_days = {
        'Winter': (12, 28, "Winter Representative Day (12/28)"),
        'Spring': (4, 21, "Spring Representative Day (4/21)"),
        'Summer': (8, 2, "Summer Representative Day (8/02)"),
        'Autumn': (9, 29, "Autumn Representative Day (9/29)")
    }
    
    # 데이터 로드
    data_by_orientation = {}
    for name, path in orientations.items():
        print(f"Loading and processing {name} data from SQL...")
        df = load_data_from_sql(path)
        if df is not None:
            data_by_orientation[name] = df
            
    # ── 시각화 스타일 설정 ──────────────────────────────────────────────────
    dm.style.use("presentation")
    
    # Colors for BIPV orientations and HVAC load
    colors = {
        'Load': '#64748b',       # Muted slate gray
        'South': '#ef4444',      # Vibrant Red
        'East': '#f59e0b',       # Orange/Amber
        'West': '#3b82f6',       # Blue
        'North': '#10b981'       # Emerald Green
    }
    
    # ── Y축 스케일 통일을 위한 최댓값 계산 ─────────────────────────────────────
    max_val = 0.0
    for season, (month, day, _) in rep_days.items():
        # 1. HVAC 부하 최댓값 체크 (South 기준)
        if 'South' in data_by_orientation:
            df = data_by_orientation['South']
            day_data = df[(df['Month'] == month) & (df['Day'] == day)]
            if not day_data.empty:
                max_val = max(max_val, day_data['HVAC_kW'].max())
        # 2. 각 BIPV 발전량 최댓값 체크
        for name, df in data_by_orientation.items():
            day_data = df[(df['Month'] == month) & (df['Day'] == day)]
            if not day_data.empty:
                max_val = max(max_val, day_data['Gen_kW'].max())
    
    # 상단 마진 10% 추가
    y_max = max_val * 1.1 if max_val > 0 else 10.0

    fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True, sharey=True)
    axes_flat = axes.flatten()
    
    seasons = ['Winter', 'Spring', 'Summer', 'Autumn']
    
    for i, season in enumerate(seasons):
        ax = axes_flat[i]
        month, day, label = rep_days[season]
        
        # 1. 건물 총 냉난방 부하 (HVAC Load) - South 기준으로 대표 플로팅
        if 'South' in data_by_orientation:
            ref_df = data_by_orientation['South']
            day_ref = ref_df[(ref_df['Month'] == month) & (ref_df['Day'] == day)].sort_values('Time_Hours')
            ax.fill_between(
                day_ref['Time_Hours'], 
                day_ref['HVAC_kW'], 
                color=colors['Load'], 
                alpha=0.15, 
                label='HVAC Load'
            )
            ax.plot(
                day_ref['Time_Hours'], 
                day_ref['HVAC_kW'], 
                color=colors['Load'], 
                linestyle='--', 
                linewidth=1.5
            )
        
        # 2. 각 방위별 BIPV 발전량 (PV Generation)
        for name in ['South', 'East', 'West', 'North']:
            if name in data_by_orientation:
                df = data_by_orientation[name]
                day_data = df[(df['Month'] == month) & (df['Day'] == day)].sort_values('Time_Hours')
                ax.plot(
                    day_data['Time_Hours'], 
                    day_data['Gen_kW'], 
                    color=colors[name], 
                    linewidth=2.5, 
                    label=f'{name} BIPV Gen'
                )
                
        ax.set_title(label, fontsize=14, fontweight='bold', pad=10)
        ax.set_xlim(0, 24)
        ax.set_ylim(0, y_max)
        ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
        ax.set_xticklabels(['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'])
        ax.grid(True, linestyle=':', alpha=0.6)
        
        if i in [0, 2]:
            ax.set_ylabel('Power [kW]', fontweight='bold', fontsize=12)
        if i in [2, 3]:
            ax.set_xlabel('Time of Day', fontweight='bold', fontsize=12)
            
        # Transparent legend
        ax.legend(loc='upper right', framealpha=0, facecolor='none', fontsize=10)
        
    plt.suptitle('Diurnal HVAC Load and BIPV Generation Comparison by Orientation', fontsize=18, fontweight='bold', y=0.96)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # ── 결과 저장 ────────────────────────────────────────────────────────
    output_dir = os.path.join(project_root, "figure", "plot", "fig27_pv_hvac_contribution")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    png_path = os.path.join(output_dir, "fig27_pv_hvac_contribution.png")
    svg_path = os.path.join(output_dir, "fig27_pv_hvac_contribution.svg")
    
    fig.savefig(png_path, dpi=300, transparent=True)
    fig.savefig(svg_path, transparent=True)
    
    print(f"Saved PNG to: {png_path}")
    print(f"Saved SVG to: {svg_path}")

if __name__ == '__main__':
    main()

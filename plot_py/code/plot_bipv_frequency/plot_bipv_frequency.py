import os
import sqlite3
import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import dartwork_mpl as dm

def get_best_angle(sun_alt):
    if sun_alt <= 0:
        return 0
    angles = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    return min(angles, key=lambda x: abs(x - sun_alt))

def main():
    # -------------------------------------------------------------------------
    # 1. 데이터 베이스 로드 및 고성능 단일 스캔 데이터 추출
    # -------------------------------------------------------------------------
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    db_path = os.path.join(project_root, "run_analysis", "case3", "eplusout.sql")
    
    if not os.path.exists(db_path):
        print(f"[Error] Database not found at: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Site Solar Altitude Angle 의 ReportDataDictionaryIndex 조회
    c.execute("""
        SELECT ReportDataDictionaryIndex 
        FROM ReportDataDictionary 
        WHERE KeyValue = 'Environment' AND Name = 'Site Solar Altitude Angle' AND ReportingFrequency = 'Zone Timestep'
    """)
    alt_dict_idx = c.fetchone()[0]

    # Facility Total Produced Electricity Energy 의 ReportDataDictionaryIndex 조회 (건물 전체 발전량)
    c.execute("""
        SELECT ReportDataDictionaryIndex 
        FROM ReportDataDictionary 
        WHERE KeyValue = 'Whole Building' AND Name = 'Facility Total Produced Electricity Energy' AND ReportingFrequency = 'Zone Timestep'
    """)
    pv_dict_idx = c.fetchone()[0]

    # Time 테이블에서 실제 런타임 타임스텝 정보 조회 (Warmup 제외)
    c.execute("""
        SELECT TimeIndex, Month, Day, Hour, Minute 
        FROM Time 
        WHERE WarmupFlag = 0 
        ORDER BY TimeIndex
    """)
    time_rows = c.fetchall()

    # ReportData 테이블에서 태양 고도 데이터 스캔 (단 1회 풀 스캔)
    c.execute("""
        SELECT TimeIndex, Value 
        FROM ReportData 
        WHERE ReportDataDictionaryIndex = ?
    """, (alt_dict_idx,))
    val_rows = c.fetchall()
    val_map = {time_idx: val for time_idx, val in val_rows}

    # ReportData 테이블에서 발전량 데이터 스캔 (단 1회 풀 스캔)
    c.execute("""
        SELECT TimeIndex, Value 
        FROM ReportData 
        WHERE ReportDataDictionaryIndex = ?
    """, (pv_dict_idx,))
    pv_rows = c.fetchall()
    pv_map = {time_idx: val for time_idx, val in pv_rows}
    
    conn.close()

    # -------------------------------------------------------------------------
    # 2. T-1 지연 복원 로직 및 발전 필터링을 적용한 BIPV 각도 시퀀스 생성
    # -------------------------------------------------------------------------
    timesteps_data = []
    angles_list = []
    pv_gen_list = []
    
    for i, (time_idx, month, day, hour, minute) in enumerate(time_rows):
        sun_alt = val_map.get(time_idx, 0.0)
        pv_gen = pv_map.get(time_idx, 0.0)
        
        # T-1 시점의 고도 사용 (첫 스텝은 0.0)
        prev_sun_alt = timesteps_data[i-1]['SunAlt'] if i > 0 else 0.0
        angle = get_best_angle(prev_sun_alt)
        
        data_item = {
            'TimeIndex': time_idx,
            'Month': month,
            'Day': day,
            'Hour': hour,
            'Minute': minute,
            'SunAlt': sun_alt,
            'Angle': angle,
            'PVGen': pv_gen
        }
        timesteps_data.append(data_item)
        angles_list.append(angle)
        pv_gen_list.append(pv_gen)

    total_timesteps = len(timesteps_data)
    print(f"[Info] Successfully processed {total_timesteps} timesteps.")
    
    # 발전이 있을 때(PVGen > 100J)만 각도 리스트를 생성, 없을 때는 NaN 처리 (Carpet Plot 용)
    angles_float = np.array(angles_list, dtype=float)
    for i, data in enumerate(timesteps_data):
        if data['PVGen'] <= 100.0:
            angles_float[i] = np.nan

    if total_timesteps != 52560:
        print(f"[Warning] Timesteps count is {total_timesteps}, expected 52560.")
        num_days = total_timesteps // 144
        angles_2d = angles_float[:num_days * 144].reshape(num_days, 144)
    else:
        angles_2d = angles_float.reshape(365, 144)

    # -------------------------------------------------------------------------
    # 3. 색상 및 스타일 정의
    # -------------------------------------------------------------------------
    # 오렌지 그라데이션 및 야간 0도 슬레이트 그레이 컬러 매핑
    colors = [
        "#64748b",      # 0°: Slate Gray
        "#ffe8cc",      # 10°: oc.orange1
        "#ffd8a8",      # 20°: oc.orange2
        "#ffc078",      # 30°: oc.orange3
        "#ffa94d",      # 40°: oc.orange4
        "#ff922b",      # 50°: oc.orange5
        "#fd7e14",      # 60°: oc.orange6
        "#f76707",      # 70°: oc.orange7 (대표 오렌지)
        "#e8590c",      # 80°: oc.orange8
        "#d9480f"       # 90°: oc.orange9 (딥 오렌지-레드)
    ]
    cmap = mcolors.ListedColormap(colors)
    cmap.set_bad(color='#f1f5f9') # 발전량이 없을 때는 연한 슬레이트 회색 백그라운드로 처리
    
    bounds = np.arange(-5, 105, 10)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # 출력 폴더 생성
    output_dir = os.path.join(project_root, "plot_py", "figure", "plot_bipv_frequency")
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # Graph 1: Timestep Resolution (Carpet Plot)
    # -------------------------------------------------------------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    fig, ax = plt.subplots(figsize=dm.figsize('23cm', '14cm'))
    
    im = ax.imshow(
        angles_2d.T, 
        aspect='auto', 
        origin='lower', 
        extent=[1, 365, 0, 24], 
        cmap=cmap, 
        norm=norm
    )
    
    # 1월부터 12월까지의 월 경계 표시 수직선 추가
    month_starts = [32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    for m_start in month_starts:
        ax.axvline(x=m_start, color='#ffffff', linestyle='--', linewidth=0.5, alpha=0.6)
        
    ax.set_title("BIPV Tilt Angle Carpet Plot (Power Generating Timesteps Only)", fontsize=15.5, fontweight='bold', pad=12)
    ax.set_xlabel("Day of Year")
    ax.set_ylabel("Hour of Day")
    ax.set_xlim(1, 365)
    ax.set_ylim(0, 24)
    ax.set_yticks(np.arange(0, 25, 4))
    
    # 컬러바 추가 (세로형)
    cbar = fig.colorbar(im, ax=ax, ticks=np.arange(0, 91, 10), pad=0.03)
    cbar.set_ticklabels([f"{a}°" for a in range(0, 91, 10)])
    cbar.set_label("Selected BIPV Angle")
    
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bipv_frequency_carpet.png"), dpi=300, transparent=True)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_carpet.svg"), transparent=True)
    plt.close(fig)

    # -------------------------------------------------------------------------
    # Graph 2: Hourly Resolution (Diurnal Line Profile)
    # -------------------------------------------------------------------------
    winter_days = []
    summer_days = []
    shoulder_days = []
    
    for day_idx in range(365):
        first_step_idx = day_idx * 144
        if first_step_idx >= len(timesteps_data):
            break
        month = timesteps_data[first_step_idx]['Month']
        day_angles = angles_list[first_step_idx : first_step_idx + 144]
        day_gens = pv_gen_list[first_step_idx : first_step_idx + 144]
        
        # 발전량이 있을 때만 각도 기록, 없으면 NaN
        day_angles_filtered = [ang if gen > 100.0 else np.nan for ang, gen in zip(day_angles, day_gens)]
        
        if month in [12, 1, 2]:
            winter_days.append(day_angles_filtered)
        elif month in [6, 7, 8]:
            summer_days.append(day_angles_filtered)
        else:
            shoulder_days.append(day_angles_filtered)
            
    # nanmean 경고 메시지 무시 처리 (야간 시간대에는 모두 nan 이므로 경고가 발생함)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        winter_avg = np.nanmean(winter_days, axis=0) if winter_days else np.zeros(144)
        summer_avg = np.nanmean(summer_days, axis=0) if summer_days else np.zeros(144)
        shoulder_avg = np.nanmean(shoulder_days, axis=0) if shoulder_days else np.zeros(144)
    
    time_x = np.arange(144) * 10 / 60.0 # 0.0 ~ 23.833
    
    fig, ax = plt.subplots(figsize=dm.figsize('20cm', '12cm'))
    
    # lines will only draw where not nan
    ax.plot(time_x, winter_avg, color="oc.indigo7", label="Winter (Dec-Feb)", lw=dm.lw(1.2))
    ax.plot(time_x, shoulder_avg, color="oc.teal7", label="Spring/Autumn", lw=dm.lw(1.2))
    ax.plot(time_x, summer_avg, color="oc.orange7", label="Summer (Jun-Aug)", lw=dm.lw(1.2))
    
    ax.set_title("Diurnal BIPV Angle Tracking Profile (Generating Hours Only)", fontsize=15.5, fontweight='bold', pad=12)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Average BIPV Angle [°]")
    ax.set_xlim(0, 24)
    ax.set_ylim(-2, 92)
    ax.set_xticks(np.arange(0, 25, 3))
    ax.set_yticks(np.arange(0, 91, 10))
    
    ax.grid(True, axis='both', linewidth=0.3, color='#e2e8f0')
    ax.legend(loc="upper left")
    
    dm.simple_layout(fig)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_hourly.png"), dpi=300, transparent=True)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_hourly.svg"), transparent=True)
    plt.close(fig)

    # -------------------------------------------------------------------------
    # Graph 3: Daily Resolution (100% Stacked Area Chart)
    # -------------------------------------------------------------------------
    daily_counts = np.zeros((365, 10))
    daily_total_gen_steps = np.zeros(365)
    
    for day_idx in range(365):
        first_step_idx = day_idx * 144
        if first_step_idx >= len(timesteps_data):
            break
        day_angles = angles_list[first_step_idx : first_step_idx + 144]
        day_gens = pv_gen_list[first_step_idx : first_step_idx + 144]
        for ang, gen in zip(day_angles, day_gens):
            if gen > 100.0:
                ang_idx = int(ang // 10)
                daily_counts[day_idx, ang_idx] += 1
                daily_total_gen_steps[day_idx] += 1
                
    # 일일 백분율 계산 (발전량이 전혀 없는 날은 이전 날의 비율로 보간 처리하여 그래프 끊김 방지)
    daily_pct = np.zeros((365, 10))
    for day_idx in range(365):
        t_steps = daily_total_gen_steps[day_idx]
        if t_steps > 0:
            daily_pct[day_idx, :] = (daily_counts[day_idx, :] / t_steps) * 100.0
        else:
            if day_idx > 0:
                daily_pct[day_idx, :] = daily_pct[day_idx - 1, :]
            else:
                daily_pct[day_idx, 0] = 100.0  # 첫 날이 발전 없을 경우 예외 처리
                
    day_x = np.arange(1, 366)
    y_stack = [daily_pct[:, i] for i in range(10)]
    
    fig, ax = plt.subplots(figsize=dm.figsize('22cm', '13cm'))
    
    ax.stackplot(
        day_x, 
        y_stack, 
        labels=[f"{a}°" for a in range(0, 91, 10)], 
        colors=colors, 
        alpha=0.95
    )
    
    # 월 구분을 위한 선 추가 및 틱 라벨 설정
    month_ticks = [15, 45, 75, 105, 135, 166, 196, 227, 258, 288, 319, 349]
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    for m_start in month_starts:
        ax.axvline(x=m_start, color='#ffffff', linestyle='-', linewidth=0.8, alpha=0.8)
        
    ax.set_title("Daily BIPV Angle Selection Share (Generating Hours Only)", fontsize=15.5, fontweight='bold', pad=12)
    ax.set_xlabel("Month")
    ax.set_ylabel("Selection Ratio [%]")
    ax.set_xlim(1, 365)
    ax.set_ylim(0, 100)
    ax.set_xticks(month_ticks)
    ax.set_xticklabels(month_labels)
    
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=12)
    
    dm.simple_layout(fig)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_daily.png"), dpi=300, transparent=True)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_daily.svg"), transparent=True)
    plt.close(fig)

    # -------------------------------------------------------------------------
    # Graph 4: Monthly Resolution (Stacked Column Bar Chart)
    # -------------------------------------------------------------------------
    monthly_hours = np.zeros((12, 10))
    for i, data in enumerate(timesteps_data):
        month = data['Month']
        ang = data['Angle']
        pv_gen = data['PVGen']
        ang_idx = int(ang // 10)
        
        # 발전이 있는 10분만 적산
        if pv_gen > 100.0:
            monthly_hours[month - 1, ang_idx] += 1.0 / 6.0
        
    fig, ax = plt.subplots(figsize=dm.figsize('21cm', '14cm'))
    
    x = np.arange(12)
    bar_width = 0.55
    bottom = np.zeros(12)
    
    for i in range(10):
        ax.bar(
            x, 
            monthly_hours[:, i], 
            bottom=bottom, 
            width=bar_width, 
            color=colors[i], 
            label=f"{i*10}°", 
            alpha=0.9
        )
        bottom += monthly_hours[:, i]
        
    ax.set_title("Monthly BIPV Angle Cumulative Operation Hours", fontsize=17, fontweight='bold', pad=12)
    ax.set_xlabel("Month")
    ax.set_ylabel("Operation Hours [h]")
    ax.set_xticks(x)
    ax.set_xticklabels(month_labels)
    ax.set_xlim(-0.6, 11.6)
    
    # Y축 범위 자동 설정 (발전 시간으로만 한정하므로 동적 범위 설정)
    max_monthly_hours = np.max(np.sum(monthly_hours, axis=1))
    ax.set_ylim(0, max_monthly_hours * 1.15)
    
    ax.grid(True, axis='y', linewidth=0.3, color='#e2e8f0')
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=12)
    
    dm.simple_layout(fig)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_monthly.png"), dpi=300, transparent=True)
    fig.savefig(os.path.join(output_dir, "bipv_frequency_monthly.svg"), transparent=True)
    plt.close(fig)

    print(f"\n[Success] Frequency plots successfully saved to: {output_dir}")

if __name__ == "__main__":
    main()

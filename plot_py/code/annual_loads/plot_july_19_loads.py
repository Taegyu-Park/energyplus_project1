import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

def parse_case_daily_loads(csv_path, target_date="07/19"):
    times = []
    heating_raw = []
    cooling_raw = []
    is_hourly = False
    
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        headers = next(reader)
        
        heating_cols = []
        cooling_cols = []
        for i, h in enumerate(headers):
            h_lower = h.lower()
            if "ideal loads" in h_lower:
                if "heating" in h_lower:
                    heating_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                    
        if not heating_cols or not cooling_cols:
            heating_cols = []
            cooling_cols = []
            for i, h in enumerate(headers):
                h_lower = h.lower()
                if "heating" in h_lower:
                    heating_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                    
        for row in reader:
            if not row:
                continue
            
            # Date/Time 컬럼은 대개 0번 컬럼이며, 앞뒤 공백 제거 후 비교
            date_time_str = row[0].strip()
            # 포맷 예: "07/19  00:10:00" -> 첫 단어가 target_date와 일치하는지 확인
            if date_time_str.startswith(target_date) or (len(date_time_str.split()) > 0 and date_time_str.split()[0] == target_date):
                time_str = date_time_str.split()[-1] # "00:10:00"
                times.append(time_str)
                
                h_sum = 0.0
                for idx in heating_cols:
                    if idx < len(row) and row[idx].strip():
                        h_sum += float(row[idx].strip())
                
                c_sum = 0.0
                for idx in cooling_cols:
                    if idx < len(row) and row[idx].strip():
                        c_sum += float(row[idx].strip())
                
                heating_raw.append(h_sum)
                cooling_raw.append(c_sum)
                
    # Joules 단위를 Rate (kW) 단위로 변환
    if is_hourly:
        # Hourly data: 1시간 동안 누적된 에너지 (J)
        # 1시간 평균 전력 (kW) = 누적 에너지 (J) / 3600초 / 1000 W/kW = 에너지 (J) / 3.6e6
        n_steps = len(heating_raw)
        heating_kw = np.zeros(n_steps)
        cooling_kw = np.zeros(n_steps)
        
        # 시간당 타임스텝 수 계산 (보통 6개)
        timesteps_per_hour = n_steps // 24 if n_steps >= 24 else 1
        
        for hr in range(24):
            start_idx = hr * timesteps_per_hour
            end_idx = start_idx + timesteps_per_hour
            if end_idx <= n_steps:
                # 에너지는 시간의 마지막 타임스텝에 기록됨
                h_joules = heating_raw[end_idx - 1]
                c_joules = cooling_raw[end_idx - 1]
                
                h_kw = h_joules / 3.6e6
                c_kw = c_joules / 3.6e6
                
                heating_kw[start_idx:end_idx] = h_kw
                cooling_kw[start_idx:end_idx] = c_kw
    else:
        # Timestep data: 10분 동안의 에너지 (J)
        # Power (kW) = Energy (J) / (10 minutes * 60 seconds) / 1000 = Energy (J) / 6.0e5
        heating_kw = np.array(heating_raw) / 6.0e5
        cooling_kw = np.array(cooling_raw) / 6.0e5
    
    return times, heating_kw, cooling_kw

def main():
    import json
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 파일 경로 설정
    case1_path = os.path.join(project_root, "run_analysis", "case1", "case1.csv")
    case2_path = os.path.join(project_root, "run_analysis", "case2", "90", "case2_90.csv")
    case3_path = os.path.join(project_root, "run_analysis", "case3", "case3.csv")
    
    # 2. 7월 19일 데이터 파싱
    times, c1_h, c1_c = parse_case_daily_loads(case1_path, "07/19")
    _, c2_h, c2_c = parse_case_daily_loads(case2_path, "07/19")
    _, c3_h, c3_c = parse_case_daily_loads(case3_path, "07/19")
    
    if not times:
        print("Error: Target date 07/19 not found in CSV files!")
        return
        
    print(f"Parsed {len(times)} timesteps for July 19th.")
    print(f"Case 1 Max Cooling: {np.max(c1_c):.2f} kW")
    print(f"Case 2 Max Cooling: {np.max(c2_c):.2f} kW")
    print(f"Case 3 Max Cooling: {np.max(c3_c):.2f} kW")
    print(f"Case 1 Max Heating: {np.max(c1_h):.2f} kW")
    print(f"Case 2 Max Heating: {np.max(c2_h):.2f} kW")
    print(f"Case 3 Max Heating: {np.max(c3_h):.2f} kW")

    # pv_angles.json 로드
    json_path = os.path.join(script_dir, "pv_angles.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            pv_data = json.load(f)
    else:
        pv_data = {}
    pv_angles = pv_data.get("07/19")

    # 3. dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 가로형 그래프 크기 정의
    fig, ax = plt.subplots(figsize=dm.figsize('23cm', '13cm'))
    
    # 시간 인덱스를 0부터 24시간 범위로 매핑 (144개 타임스텝)
    time_hours = np.linspace(0, 24, len(times), endpoint=False)
    
    # 7월 19일은 여름철이므로 난방 부하가 0일 가능성이 큽니다.
    # 만약 난방 부하가 존재한다면 점선으로 함께 표현하고, 없으면 냉방 부하만 표시합니다.
    has_heating = np.max(c1_h) > 0.01 or np.max(c2_h) > 0.01 or np.max(c3_h) > 0.01
    
    # 0 값을 NaN으로 처리하여 플로팅에서 제외
    c1_c = np.where(c1_c <= 0.001, np.nan, c1_c)
    c2_c = np.where(c2_c <= 0.001, np.nan, c2_c)
    c3_c = np.where(c3_c <= 0.001, np.nan, c3_c)
    c1_h = np.where(c1_h <= 0.001, np.nan, c1_h)
    c2_h = np.where(c2_h <= 0.001, np.nan, c2_h)
    c3_h = np.where(c3_h <= 0.001, np.nan, c3_h)
    
    # 냉방 부하 실선 플롯
    mask1_c = ~np.isnan(c1_c)
    mask2_c = ~np.isnan(c2_c)
    mask3_c = ~np.isnan(c3_c)
    ax.plot(time_hours[mask1_c], c1_c[mask1_c], color="oc.gray6", label="Case 1 (No Shade) - Cooling", lw=dm.lw(1.2))
    ax.plot(time_hours[mask2_c], c2_c[mask2_c], color="oc.blue6", label="Case 2 (Fixed-90°) - Cooling", lw=dm.lw(1.2))
    ax.plot(time_hours[mask3_c], c3_c[mask3_c], color="oc.orange7", label="Case 3 (Kinetic) - Cooling", lw=dm.lw(1.2))
    
    # 난방 부하 점선 플롯 (있는 경우만)
    if has_heating:
        mask1_h = ~np.isnan(c1_h)
        mask2_h = ~np.isnan(c2_h)
        mask3_h = ~np.isnan(c3_h)
        ax.plot(time_hours[mask1_h], c1_h[mask1_h], color="oc.gray6", linestyle="--", label="Case 1 - Heating", lw=dm.lw(1.0))
        ax.plot(time_hours[mask2_h], c2_h[mask2_h], color="oc.blue6", linestyle="--", label="Case 2 - Heating", lw=dm.lw(1.0))
        ax.plot(time_hours[mask3_h], c3_h[mask3_h], color="oc.orange7", linestyle="--", label="Case 3 - Heating", lw=dm.lw(1.0))
        
    # 그래프 축 및 라벨 설정
    ax.set_ylabel("Cooling Load [kW]" if not has_heating else "Thermal Load [kW]")
    ax.set_xlabel("Time of Day [Hour]")
    ax.set_title("Hourly Load Profile on July 19th (Timestep Level)", fontsize=15.5, fontweight="bold")
    
    # X축 범위를 0 ~ 24로 고정하고 2시간 단위 눈금 설정
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    
    # Y축 최하단을 0으로 고정
    ax.set_ylim(bottom=0)
    
    # PV 각도 보조축 설정
    if pv_angles is not None:
        ax2 = ax.twinx()
        # None 및 0 값을 NaN으로 처리하여 플로팅에서 제외
        angles_clean = [a if (a is not None and a != 0.0) else np.nan for a in pv_angles]
        ax2.step(time_hours, angles_clean, where="post", color="oc.orange4", linestyle="-.", lw=dm.lw(1.0), label="Case 3 PV Angle")
        ax2.set_ylabel("PV Tilt Angle [°]")
        ax2.set_ylim(-5, 95)
        ax2.set_yticks([0, 30, 60, 90])
        
        # 범례 병합
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")
        ax2.grid(False)
    else:
        ax.legend(loc="upper right")
        
    ax.grid(True)
    
    # 레이아웃 조정 및 저장
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "july_19_loads_comparison.png")
    output_svg = os.path.join(figure_dir, "july_19_loads_comparison.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"Saved daily loads comparison plots to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()

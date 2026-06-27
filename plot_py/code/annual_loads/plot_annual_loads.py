import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

def parse_case_hourly_loads(csv_path):
    heating_raw = []
    cooling_raw = []
    
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
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    
        if not heating_cols or not cooling_cols:
            for i, h in enumerate(headers):
                h_lower = h.lower()
                if "heating" in h_lower:
                    heating_cols.append(i)
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    
        for row in reader:
            if not row:
                continue
            
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
            
    heating_arr = np.array(heating_raw)
    cooling_arr = np.array(cooling_raw)
    
    # 52560행(10분 단위)이면 6개씩 묶어 합산하여 8760시간 단위로 변환
    if len(heating_arr) == 52560:
        heating_arr = heating_arr.reshape(8760, 6).sum(axis=1)
        cooling_arr = cooling_arr.reshape(8760, 6).sum(axis=1)
        
    heating_kwh = heating_arr / 3.6e6
    cooling_kwh = cooling_arr / 3.6e6
    
    return heating_kwh, cooling_kwh

def main():
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    
    # 데이터 경로
    case1_path = os.path.join(project_root, "run_analysis", "case1", "case1.csv")
    case2_path = os.path.join(project_root, "run_analysis", "case2", "90", "case2_90.csv")
    case3_path = os.path.join(project_root, "run_analysis", "case3", "case3.csv")
    
    # 8760 시간별 데이터 파싱 (자동 컬럼 매핑 및 타임스텝 누계 처리)
    c1_h, c1_c = parse_case_hourly_loads(case1_path)
    c2_h, c2_c = parse_case_hourly_loads(case2_path)
    c3_h, c3_c = parse_case_hourly_loads(case3_path)
    
    # 365일 일일 합계로 리샘플링 (8760 -> 365, 24시간 단위 합산)
    c1_h_daily = c1_h.reshape(365, 24).sum(axis=1)
    c1_c_daily = c1_c.reshape(365, 24).sum(axis=1)
    
    c2_h_daily = c2_h.reshape(365, 24).sum(axis=1)
    c2_c_daily = c2_c.reshape(365, 24).sum(axis=1)
    
    c3_h_daily = c3_h.reshape(365, 24).sum(axis=1)
    c3_c_daily = c3_c.reshape(365, 24).sum(axis=1)
    
    days = np.arange(1, 366)
    
    # 2. dartwork-mpl 스타일 적용하여 서브플롯 생성
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 2행 1열 subplots 생성 (상단: 난방, 하단: 냉방)
    # width: 21cm, height: 23cm (TALL 비율)
    fig, (ax_heating, ax_cooling) = plt.subplots(2, 1, figsize=dm.figsize('21cm', '23cm'), sharex=True)
    
    # X축 월별 눈금 위치 설정 (누적 일수 기반)
    month_starts = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # --- 상단: 1년 전체 일별 난방 부하 비교 ---
    ax_heating.plot(days, c1_h_daily, color="oc.gray6", label="Case 1 (No Shade)", lw=dm.lw(0.3), alpha=0.85)
    ax_heating.plot(days, c2_h_daily, color="oc.blue6", label="Case 2 (Fixed-90°)", lw=dm.lw(0.3), alpha=0.85)
    ax_heating.plot(days, c3_h_daily, color="oc.orange7", label="Case 3 (Kinetic)", lw=dm.lw(0.3), alpha=0.85)
    
    ax_heating.set_ylabel("Daily Heating Load [kWh/day]")
    ax_heating.set_title("Annual Daily Heating Energy Consumption")
    ax_heating.set_xlim(1, 365)
    ax_heating.set_ylim(bottom=0)
    ax_heating.legend(loc="upper right")
    
    # --- 하단: 1년 전체 일별 냉방 부하 비교 ---
    ax_cooling.plot(days, c1_c_daily, color="oc.gray6", label="Case 1 (No Shade)", lw=dm.lw(0.3), alpha=0.85)
    ax_cooling.plot(days, c2_c_daily, color="oc.blue6", label="Case 2 (Fixed-90°)", lw=dm.lw(0.3), alpha=0.85)
    ax_cooling.plot(days, c3_c_daily, color="oc.orange7", label="Case 3 (Kinetic)", lw=dm.lw(0.3), alpha=0.85)
    
    ax_cooling.set_ylabel("Daily Cooling Load [kWh/day]")
    ax_cooling.set_xlabel("Time [Month]")
    ax_cooling.set_title("Annual Daily Cooling Energy Consumption")
    ax_cooling.set_xlim(1, 365)
    ax_cooling.set_ylim(bottom=0)
    
    # sharex=True 이므로 하단 subplots에만 눈금 적용
    ax_cooling.set_xticks(month_starts)
    ax_cooling.set_xticklabels(month_labels)
    ax_cooling.legend(loc="upper right")
    
    # 3. 저장 처리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "annual_loads.png")
    output_svg = os.path.join(figure_dir, "annual_loads.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    print(f"\nAnnual loads plot saved to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()

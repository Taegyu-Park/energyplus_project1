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
    
    # 난방 부하와 냉방 부하 합산하여 시간별 총 열부하 계산 (8760 시간 단위)
    c1_total = c1_h + c1_c
    c2_total = c2_h + c2_c
    c3_total = c3_h + c3_c
    
    hours = np.arange(1, 8761)
    
    # 2. dartwork-mpl 스타일 적용하여 플롯 생성
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 단일 plot 생성 (총 부하이므로 1행 1열)
    # width: 21cm, height: 13cm (가로형 레이아웃)
    fig, ax = plt.subplots(figsize=dm.figsize('21cm', '13cm'))
    
    # X축 월별 눈금 위치 설정 (누적 시간 기반: 일수 * 24)
    month_starts_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    month_starts_hours = [d * 24 for d in month_starts_days]
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # --- 1년 전체 시간별 총 열부하 비교 ---
    # 8760개 포인트이므로 선 굵기를 얇게(lw=0.1) 지정하여 가독성을 높입니다.
    ax.plot(hours, c1_total, color="oc.gray6", label="Case 1 (No Shade)", lw=dm.lw(0.1), alpha=0.75)
    ax.plot(hours, c2_total, color="oc.blue6", label="Case 2 (Fixed-90°)", lw=dm.lw(0.1), alpha=0.75)
    ax.plot(hours, c3_total, color="oc.orange7", label="Case 3 (Kinetic)", lw=dm.lw(0.1), alpha=0.75)
    
    ax.set_ylabel("Hourly Total Thermal Load [kWh]")
    ax.set_xlabel("Time [Month]")
    ax.set_title("Annual Hourly Total Thermal Load (Heating + Cooling)")
    ax.set_xlim(1, 8760)
    ax.set_ylim(bottom=0)
    
    ax.set_xticks(month_starts_hours)
    ax.set_xticklabels(month_labels)
    ax.legend(loc="upper right")
    
    # 3. 저장 처리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "annual_total_loads.png")
    output_svg = os.path.join(figure_dir, "annual_total_loads.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    print(f"\nAnnual total loads plot saved to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()

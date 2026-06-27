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

def hourly_to_monthly(hourly_arr):
    days_in_months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    monthly_arr = []
    current_idx = 0
    for days in days_in_months:
        hours = days * 24
        monthly_arr.append(np.sum(hourly_arr[current_idx : current_idx + hours]))
        current_idx += hours
    return np.array(monthly_arr)

def main():
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    
    # 1. 데이터 경로 설정
    case1_path = os.path.join(project_root, "run_analysis", "case1", "case1.csv")
    case2_path = os.path.join(project_root, "run_analysis", "case2", "90", "case2_90.csv")
    case3_path = os.path.join(project_root, "run_analysis", "case3", "case3.csv")
    
    # 2. 데이터 파싱 (Hourly)
    c1_h_hour, c1_c_hour = parse_case_hourly_loads(case1_path)
    c2_h_hour, c2_c_hour = parse_case_hourly_loads(case2_path)
    c3_h_hour, c3_c_hour = parse_case_hourly_loads(case3_path)
    
    # 3. 월별 합계 변환 및 MWh 단위 환산
    c1_h = hourly_to_monthly(c1_h_hour) / 1000.0
    c1_c = hourly_to_monthly(c1_c_hour) / 1000.0
    c2_h = hourly_to_monthly(c2_h_hour) / 1000.0
    c2_c = hourly_to_monthly(c2_c_hour) / 1000.0
    c3_h = hourly_to_monthly(c3_h_hour) / 1000.0
    c3_c = hourly_to_monthly(c3_c_hour) / 1000.0
    
    months = np.arange(1, 13)
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)

    # ----------------------------------------------------
    # [대안 A] 냉난방 분리형 2단 시계열 라인 그래프 (2x1 Subplots)
    # ----------------------------------------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    fig_a, (ax_h, ax_c) = plt.subplots(2, 1, figsize=dm.figsize('23cm', '20cm'), sharex=True)
    
    # 상단: 난방 부하
    ax_h.plot(months, c1_h, color="oc.gray6", marker="o", label="Case 1 (No Shade)", lw=dm.lw(1.2), markersize=4)
    ax_h.plot(months, c2_h, color="oc.blue6", marker="s", label="Case 2 (Fixed-90°)", lw=dm.lw(1.2), markersize=4)
    ax_h.plot(months, c3_h, color="oc.orange7", marker="^", label="Case 3 (Kinetic)", lw=dm.lw(1.2), markersize=4)
    ax_h.set_ylabel("Heating Load [MWh]")
    ax_h.set_title("Monthly Heating Load Comparison", fontsize=14, fontweight="bold")
    ax_h.legend(loc="upper right")
    ax_h.grid(True)
    
    # 하단: 냉방 부하
    ax_c.plot(months, c1_c, color="oc.gray6", marker="o", label="Case 1 (No Shade)", lw=dm.lw(1.2), markersize=4)
    ax_c.plot(months, c2_c, color="oc.blue6", marker="s", label="Case 2 (Fixed-90°)", lw=dm.lw(1.2), markersize=4)
    ax_c.plot(months, c3_c, color="oc.orange7", marker="^", label="Case 3 (Kinetic)", lw=dm.lw(1.2), markersize=4)
    ax_c.set_ylabel("Cooling Load [MWh]")
    ax_c.set_xlabel("Month")
    ax_c.set_title("Monthly Cooling Load Comparison", fontsize=14, fontweight="bold")
    ax_c.set_xticks(months)
    ax_c.set_xticklabels(month_labels)
    ax_c.legend(loc="upper right")
    ax_c.grid(True)
    
    dm.simple_layout(fig_a)
    fig_a.savefig(os.path.join(figure_dir, "monthly_loads_subplots.png"), dpi=300, transparent=True)
    fig_a.savefig(os.path.join(figure_dir, "monthly_loads_subplots.svg"), transparent=True)
    plt.close(fig_a)
    print("Generated monthly_loads_subplots.png/svg successfully.")
    
    # ----------------------------------------------------
    # [대안 B] 월별 그룹-적층 막대 그래프 (Grouped-Stacked Bar Chart)
    # ----------------------------------------------------
    fig_b, ax = plt.subplots(figsize=dm.figsize('29cm', '14cm'))
    
    bar_width = 0.24
    
    # 각 대안별 12개월 막대 시각화 (동일 월 내에 3개 막대 나란히 배치)
    # Case 1: 왼쪽 막대
    b1_h = ax.bar(months - bar_width, c1_h, bar_width, color="oc.red3", edgecolor="oc.red4", label="Case 1 Heating", alpha=0.85)
    b1_c = ax.bar(months - bar_width, c1_c, bar_width, bottom=c1_h, color="oc.blue3", edgecolor="oc.blue4", label="Case 1 Cooling", alpha=0.85)
    
    # Case 2: 가운데 막대
    b2_h = ax.bar(months, c2_h, bar_width, color="oc.red6", edgecolor="oc.red7", label="Case 2 Heating", alpha=0.85)
    b2_c = ax.bar(months, c2_c, bar_width, bottom=c2_h, color="oc.blue6", edgecolor="oc.blue7", label="Case 2 Cooling", alpha=0.85)
    
    # Case 3: 오른쪽 막대
    b3_h = ax.bar(months + bar_width, c3_h, bar_width, color="oc.red9", edgecolor="oc.red9", label="Case 3 Heating", alpha=0.85)
    b3_c = ax.bar(months + bar_width, c3_c, bar_width, bottom=c3_h, color="oc.blue9", edgecolor="oc.blue9", label="Case 3 Cooling", alpha=0.85)
    
    ax.set_ylabel("Monthly Thermal Load [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly Stacked Thermal Load Comparison (Heating + Cooling)", fontsize=15.5, fontweight="bold")
    ax.set_xticks(months)
    ax.set_xticklabels(month_labels)
    
    # 범례 정리 (순서 조정 및 중복 제거)
    handles, labels = ax.get_legend_handles_labels()
    # 범례 가시성을 위해 정렬: [C1 H, C1 C, C2 H, C2 C, C3 H, C3 C]
    # 가독성을 높이기 위해 2행 3열 범례 구성
    ax.legend(handles, labels, loc="upper right", ncol=3, fontsize=12)
    ax.grid(True, axis='y')
    
    dm.simple_layout(fig_b)
    fig_b.savefig(os.path.join(figure_dir, "monthly_stacked_loads.png"), dpi=300, transparent=True)
    fig_b.savefig(os.path.join(figure_dir, "monthly_stacked_loads.svg"), transparent=True)
    plt.close(fig_b)
    print("Generated monthly_stacked_loads.png/svg successfully.")

if __name__ == "__main__":
    main()

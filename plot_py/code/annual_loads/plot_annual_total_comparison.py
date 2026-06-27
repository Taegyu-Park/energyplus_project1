import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

def parse_case_annual_totals(csv_path):
    if not os.path.exists(csv_path):
        return None, None
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
        
    heating_kwh = heating_arr.sum() / 3.6e6
    cooling_kwh = cooling_arr.sum() / 3.6e6
    
    return heating_kwh, cooling_kwh

def main():
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    
    cases = []
    heating = []
    cooling = []
    
    # 1. Case 1 (No Shade)
    c1_path = os.path.join(project_root, "run_analysis", "case1", "case1.csv")
    h1, c1 = parse_case_annual_totals(c1_path)
    if h1 is not None:
        cases.append('Case 1\n(No Shade)')
        heating.append(h1)
        cooling.append(c1)
        
    # 2. Case 2 (Fixed Angles 0 to 90)
    for angle in range(0, 100, 10):
        folder_name = f"{angle}_v2" if angle == 0 else f"{angle}"
        c2_path = os.path.join(project_root, "run_analysis", "case2", folder_name, f"case2_{angle}.csv")
        h2, c2 = parse_case_annual_totals(c2_path)
        if h2 is not None:
            cases.append(f'Fixed-{angle}°')
            heating.append(h2)
            cooling.append(c2)
            
    # 3. Case 3 (Kinetic)
    c3_path = os.path.join(project_root, "run_analysis", "case3", "case3.csv")
    h3, c3 = parse_case_annual_totals(c3_path)
    if h3 is not None:
        cases.append('Case 3\n(Kinetic)')
        heating.append(h3)
        cooling.append(c3)
        
    heating = [h / 1000.0 for h in heating]
    cooling = [c / 1000.0 for c in cooling]
    totals = [h + c for h, c in zip(heating, cooling)]
    
    # dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 1행 1열 plot 생성 (수평 가로폭 확장: width: 29cm, height: 16cm)
    fig, ax = plt.subplots(figsize=dm.figsize('29cm', '16cm'))
    
    # 막대 두께 설정
    bar_width = 0.6
    
    # 누적 막대그래프 그리기 (아래: Heating, 위: Cooling)
    bars_heating = ax.bar(cases, heating, color="oc.red4", label="Heating Load", width=bar_width, alpha=0.85)
    bars_cooling = ax.bar(cases, cooling, bottom=heating, color="oc.blue4", label="Cooling Load", width=bar_width, alpha=0.85)
    
    # 각 막대 위에 총합 값 표시
    for i, total in enumerate(totals):
        ax.text(
            i, 
            total + 3.0, 
            f"Total:\n{total:.1f}", 
            ha='center', 
            va='bottom', 
            fontsize=11,
            fontweight='bold',
            color='black'
        )
        
    # 각 막대 안에 개별 Heating / Cooling 부하 값 표시
    for i in range(len(cases)):
        # Heating (빨간 막대 중앙)
        h_val = heating[i]
        ax.text(
            i,
            h_val / 2,
            f"H:\n{h_val:.1f}",
            ha='center',
            va='center',
            color='white',
            fontsize=14,
            fontweight='bold'
        )
        
        # Cooling (파란 막대 중앙)
        c_val = cooling[i]
        ax.text(
            i,
            h_val + c_val / 2,
            f"C:\n{c_val:.1f}",
            ha='center',
            va='center',
            color='white',
            fontsize=14,
            fontweight='bold'
        )
        
    # Y축 라벨 및 타이틀 설정
    ax.set_ylabel("Annual Cumulative Load [MWh]")
    ax.set_title("Annual Thermal Load Comparison (Heating + Cooling)", fontsize=17, fontweight = 'bold')
    
    # Y축 최댓값 범위 설정 (최댓값 대비 라벨 공간 확보)
    ax.set_ylim(0, 165)
    
    # 천 단위 쉼표 적용하는 Y축 포맷터 (정수 형태로 표현)
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,.0f}".format(x)))
    
    # 범례 설정
    ax.legend(loc="upper right")
    
    # 저장 처리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "annual_total_comparison.png")
    output_svg = os.path.join(figure_dir, "annual_total_comparison.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"Comparison plot saved to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()


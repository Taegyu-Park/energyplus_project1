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
    
    # 1. 파일 경로 및 컬럼 인덱스 설정 (이전 조사 결과 바탕)
    case1_path = os.path.join(project_root, "run_analysis", "model_realscale_case1", "case1.csv")
    case2_path = os.path.join(project_root, "run_analysis", "model_realscale_case2", "model_realscale_90", "case2_90.csv")
    case3_path = os.path.join(project_root, "run_analysis", "model_realscale_case3", "case3.csv")
    
    # 8760 시간별 데이터 파싱 (자동 컬럼 매핑 및 타임스텝 누계 처리)
    c1_h, c1_c = parse_case_hourly_loads(case1_path)
    c2_h, c2_c = parse_case_hourly_loads(case2_path)
    c3_h, c3_c = parse_case_hourly_loads(case3_path)
    
    # 데이터 행 수 검증 (모두 8760이어야 함)
    print(f"Data lengths check:")
    print(f"  Case 1 -> Heating: {len(c1_h)}, Cooling: {len(c1_c)}")
    print(f"  Case 2 -> Heating: {len(c2_h)}, Cooling: {len(c2_c)}")
    print(f"  Case 3 -> Heating: {len(c3_h)}, Cooling: {len(c3_c)}")
    
    # 2. 대표 겨울 주간과 여름 주간 슬라이싱
    # 겨울 대표 주간 (가장 난방 부하 편차가 큰 주간): 1월 29일 00:00 ~ 2월 4일 23:00 (시간 index: 672 ~ 840)
    # 여름 대표 주간: 8월 1일 00:00 ~ 8월 7일 23:00 (213일째~219일째, 시간 index: 5088 ~ 5256)
    w_start, w_end = 672, 840
    s_start, s_end = 5088, 5256
    
    time_hours = np.arange(168)  # 1주일 = 168시간
    
    # 3. dartwork-mpl 스타일 적용하여 서브플롯 생성
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 상하로 겨울(난방)과 여름(냉방) 시계열을 그리기 위해 2행 1열 subplots 생성
    # width: 20cm, height: 23cm (TALL 비율)
    fig, (ax_winter, ax_summer) = plt.subplots(2, 1, figsize=dm.figsize('20cm', '23cm'), sharex=False)
    
    # --- 상단: 겨울철 난방 부하 비교 (Heating Load) ---
    ax_winter.plot(time_hours, c1_h[w_start:w_end], color="oc.gray6", label="Case 1 (No Shade)", lw=dm.lw(0.5))
    ax_winter.plot(time_hours, c2_h[w_start:w_end], color="oc.blue6", label="Case 2 (Fixed-90°)", lw=dm.lw(0.5))
    ax_winter.plot(time_hours, c3_h[w_start:w_end], color="oc.orange7", label="Case 3 (Kinetic)", lw=dm.lw(0.5))
    
    ax_winter.set_ylabel("Heating Load [kWh]")
    ax_winter.set_title("Winter Typical Week (Jan 29 - Feb 4) Heating Load", fontweight="bold")
    ax_winter.set_xlim(0, 167)
    ax_winter.set_ylim(bottom=0)
    # 24시간 간격으로 눈금 설정 (일 단위)
    ax_winter.set_xticks(np.arange(0, 169, 24))
    ax_winter.set_xticklabels(["Jan 29", "Jan 30", "Jan 31", "Feb 1", "Feb 2", "Feb 3", "Feb 4", "Feb 5"])
    ax_winter.legend(loc="upper right")
    
    # --- 하단: 여름철 냉방 부하 비교 (Cooling Load) ---
    ax_summer.plot(time_hours, c1_c[s_start:s_end], color="oc.gray6", label="Case 1 (No Shade)", lw=dm.lw(0.5))
    ax_summer.plot(time_hours, c2_c[s_start:s_end], color="oc.blue6", label="Case 2 (Fixed-90°)", lw=dm.lw(0.5))
    ax_summer.plot(time_hours, c3_c[s_start:s_end], color="oc.orange7", label="Case 3 (Kinetic)", lw=dm.lw(0.5))
    
    ax_summer.set_ylabel("Cooling Load [kWh]")
    ax_summer.set_title("Summer Typical Week (Aug 1 - Aug 7) Cooling Load", fontweight="bold")
    ax_summer.set_xlim(0, 167)
    ax_summer.set_ylim(bottom=0)
    ax_summer.set_xticks(np.arange(0, 169, 24))
    ax_summer.set_xticklabels(["Aug 1", "Aug 2", "Aug 3", "Aug 4", "Aug 5", "Aug 6", "Aug 7", "Aug 8"])
    ax_summer.legend(loc="upper left")
    
    # 두 그래프의 X축 틱 라벨 스타일(폰트 굵기 등) 통일 (겨울철의 가벼운 굵기인 300/light로 고정)
    for label in ax_winter.get_xticklabels():
        label.set_fontweight('light')
    for label in ax_summer.get_xticklabels():
        label.set_fontweight('light')
    
    # 4. 저장 처리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "runs_comparison"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "runs_comparison.png")
    output_svg = os.path.join(figure_dir, "runs_comparison.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    print(f"\nRuns comparison plot saved to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()

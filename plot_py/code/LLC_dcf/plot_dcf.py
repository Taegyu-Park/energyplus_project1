import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

def parse_val(text):
    text = text.strip()
    if not text or text == "-":
        return 0.0
    return float(text.replace('"', '').replace(',', ''))

def main():
    # 1. 경로 설정
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    csv_1_path = os.path.join(project_root, "economy_analysis_1.csv")
    csv_2_path = os.path.join(project_root, "economy_analysis_2.csv")
    csv_3_path = os.path.join(project_root, "economy_analysis_3.csv")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 데이터 파싱
    # 2.1. CAPEX 데이터 파싱 (csv_1)
    capex_items = []
    capex_values = []
    with open(csv_1_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        in_capex = False
        for row in reader:
            if not row:
                continue
            first_cell = row[0].strip()
            if "초기투자비 CAPEX" in first_cell:
                in_capex = True
                continue
            if in_capex:
                if "총 CAPEX" in first_cell or "운영비" in first_cell or not first_cell or first_cell.startswith("—"):
                    break
                item_kr = first_cell
                # 한글 항목을 영문으로 매핑 (Roboto 폰트의 한글 깨짐 방지 및 학술용 시각화 통일)
                label_map = {
                    "태양광 모듈": "PV Modules",
                    "액추에이터 (추종 구동)": "Actuators",
                    "구조·프레임": "Structure & Frame",
                    "인버터·전력변환": "Inverters & Converters",
                    "추종 제어시스템": "Tracking Control System",
                    "전기 BOS (배선·보호·계측)": "Electrical BOS",
                    "설치·시운전": "Installation & Commissioning",
                    "설계·인허가": "Design & Permitting"
                }
                item_en = label_map.get(item_kr, item_kr)
                val = parse_val(row[1])
                capex_items.append(item_en)
                capex_values.append(val)
                
    # 2.2. 연도별 현금흐름 데이터 파싱 (csv_2)
    years = []
    net_cf = []          # 순현금흐름
    discounted_cf = []   # 할인현금흐름
    cum_discounted = []  # 누적할인현금흐름
    
    with open(csv_2_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # 타이틀 줄 건너뛰기
        next(reader)  # 빈 줄 건너뛰기
        headers = next(reader)
        
        for row in reader:
            if not row or not row[0].strip().isdigit():
                continue
            years.append(int(row[0].strip()))
            net_cf.append(parse_val(row[8]))
            discounted_cf.append(parse_val(row[10]))
            cum_discounted.append(parse_val(row[11]))
            
    # 단위를 백만 원으로 변환하여 가독성 향상
    net_cf_mkrw = [val / 1e6 for val in net_cf]
    discounted_cf_mkrw = [val / 1e6 for val in discounted_cf]
    cum_discounted_mkrw = [val / 1e6 for val in cum_discounted]
    capex_values_mkrw = [val / 1e6 for val in capex_values]
    
    # 3. dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "LLC_dcf"))
    os.makedirs(figure_dir, exist_ok=True)

    # ----------------------------------------------------
    # [그래프 1] 누적 할인 현금흐름 및 투자 회수기간 (NPV Trajectory)
    # ----------------------------------------------------
    fig1, ax1 = plt.subplots(figsize=dm.figsize('26cm', '14cm'))
    
    # 누적 곡선 그리기
    ax1.plot(years, cum_discounted_mkrw, color="oc.blue7", lw=dm.lw(1.5), label="Cumulative Discounted Cash Flow")
    
    # 손익분기 기준선 (Y=0)
    ax1.axhline(0, color="oc.gray5", linestyle="--", lw=dm.lw(0.8))
    
    # 할인 회수기간 (12.6년) 교점 강조
    payback_year = 12.6
    ax1.axvline(payback_year, color="oc.red6", linestyle=":", lw=dm.lw(1.0))
    ax1.plot(payback_year, 0, marker="o", color="oc.red6", markersize=6)
    ax1.text(payback_year + 0.6, -3.0, f"Discounted Payback Period: {payback_year} Years", 
             color="oc.red8", fontsize=12.5, fontweight="bold", va="center")
             
    # 12년차 액추에이터 교체 지점 강조 (교체비 발생으로 인한 기울기 변화)
    ax1.plot(12, cum_discounted_mkrw[12], marker="x", color="oc.orange7", markersize=8, mew=2)
    ax1.text(12 - 0.5, cum_discounted_mkrw[12] - 3.0, "Actuator Replacement\n(Year 12)", 
             color="oc.orange9", fontsize=11, ha="right", va="top")
             
    # 그래프 서식 설정
    ax1.set_xlabel("Project Timeline [Years]")
    ax1.set_ylabel("Cumulative NPV [Million KRW]")
    ax1.set_title("Cumulative Discounted Cash Flow & Payback Period", fontsize=15.5, fontweight="bold")
    ax1.set_xlim(0, 25)
    ax1.set_xticks(range(0, 26, 5))
    ax1.legend(loc="lower right")
    
    # 레이아웃 조정 및 저장
    dm.simple_layout(fig1)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow.png"), dpi=300, transparent=True)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow.svg"), transparent=True)
    plt.close(fig1)
    
    # ----------------------------------------------------
    # [그래프 2] 연도별 명목 순현금흐름 vs 할인 현금흐름 비교 막대그래프
    # ----------------------------------------------------
    fig2, ax2 = plt.subplots(figsize=dm.figsize('26cm', '14cm'))
    
    # 연도 1부터 25까지 시각화 (초기 CAPEX가 발생하는 0년차는 제외하여 연도별 절감액 가치 체감 극대화)
    bar_years = np.array(years[1:])
    bar_width = 0.35
    
    rects1 = ax2.bar(bar_years - bar_width/2, net_cf_mkrw[1:], bar_width, 
                     color="oc.gray5", label="Nominal Cash Flow", alpha=0.85)
    rects2 = ax2.bar(bar_years + bar_width/2, discounted_cf_mkrw[1:], bar_width, 
                     color="oc.blue6", label="Discounted Cash Flow (PV)", alpha=0.85)
                     
    # 12년차에 교체비로 급감하는 지점 강조 표시
    ax2.text(12, net_cf_mkrw[12] + 0.3, "Actuator Replacement\nin Year 12",
             color="oc.orange9", fontsize=11, fontweight="bold", ha="center", va="bottom")
             
    # 그래프 서식 설정
    ax2.set_xlabel("Project Timeline [Years]")
    ax2.set_ylabel("Annual Cash Flow [Million KRW]")
    ax2.set_title("Annual Nominal vs. Discounted Cash Flows (Year 1 - 25)", fontsize=15.5, fontweight="bold")
    ax2.set_xlim(0.5, 25.5)
    ax2.set_xticks(range(1, 26, 2))
    ax2.legend(loc="upper left")
    
    # 레이아웃 조정 및 저장
    dm.simple_layout(fig2)
    fig2.savefig(os.path.join(figure_dir, "2_annual_cash_flows_comparison.png"), dpi=300, transparent=True)
    fig2.savefig(os.path.join(figure_dir, "2_annual_cash_flows_comparison.svg"), transparent=True)
    plt.close(fig2)
    
    # ----------------------------------------------------
    # [그래프 3] 초기 투자비 (CAPEX) 구성 비율 도넛 차트
    # ----------------------------------------------------
    fig3, ax3 = plt.subplots(figsize=dm.figsize('21cm', '14cm'))
    
    # Open Color 팔레트를 조화롭게 적용
    colors = ["oc.blue7", "oc.cyan6", "oc.teal6", "oc.green6", "oc.yellow6", "oc.orange6", "oc.red6", "oc.grape6"]
    
    wedges, texts, autotexts = ax3.pie(
        capex_values_mkrw, 
        labels=capex_items, 
        autopct='%1.1f%%',
        startangle=140, 
        colors=colors,
        textprops=dict(color="black", fontsize=11),
        pctdistance=0.75
    )
    
    # 도넛 구멍 만들기 (중앙에 흰색 원 추가)
    centre_circle = plt.Circle((0,0), 0.55, fc='white')
    ax3.add_artist(centre_circle)
    
    # 내부 비율 텍스트 폰트 설정
    plt.setp(autotexts, size=8, weight="bold")
    ax3.set_title("CAPEX Breakdown for Kinetic BIPV (Total: 40.91M KRW)", fontsize=15.5, fontweight="bold")
    
    # 레이아웃 조정 및 저장
    dm.simple_layout(fig3)
    fig3.savefig(os.path.join(figure_dir, "3_capex_breakdown.png"), dpi=300, transparent=True)
    fig3.savefig(os.path.join(figure_dir, "3_capex_breakdown.svg"), transparent=True)
    plt.close(fig3)
    
    print("All economic analysis plots generated successfully inside LLC_dcf directory.")

if __name__ == "__main__":
    main()

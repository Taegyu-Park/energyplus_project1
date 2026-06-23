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
    
    total_om_pv = 0.0
    total_replace_pv = 0.0
    
    with open(csv_2_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # 타이틀
        next(reader)  # 빈줄
        headers = next(reader)
        
        for row in reader:
            if not row or not row[0].strip().isdigit():
                continue
            year = int(row[0].strip())
            years.append(year)
            net_cf.append(parse_val(row[8]))
            discounted_cf.append(parse_val(row[10]))
            cum_discounted.append(parse_val(row[11]))
            
            if year > 0:
                om_nominal = parse_val(row[6])
                replace_nominal = parse_val(row[7])
                df = parse_val(row[9])
                
                total_om_pv += om_nominal * df
                total_replace_pv += replace_nominal * df
                
    # LCOE 파싱 (csv_3)
    lcoe_val = 128.5 # 기본값 설정 (파싱 실패 대비)
    with open(csv_3_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if "LCOE" in row[0]:
                lcoe_val = parse_val(row[1])
                break

    # 단위 변환
    net_cf_mkrw = [val / 1e6 for val in net_cf]
    discounted_cf_mkrw = [val / 1e6 for val in discounted_cf]
    cum_discounted_mkrw = [val / 1e6 for val in cum_discounted]
    capex_values_mkrw = [val / 1e6 for val in capex_values]
    
    total_capex = sum(capex_values)
    
    # 3. dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "LLC_dcf"))
    os.makedirs(figure_dir, exist_ok=True)

    # ----------------------------------------------------
    # [그래프 1] 누적 할인 현금흐름 및 투자 회수기간
    # ----------------------------------------------------
    fig1, ax1 = plt.subplots(figsize=dm.figsize('26cm', '14cm'))
    ax1.plot(years, cum_discounted_mkrw, color="oc.blue7", lw=dm.lw(1.5), label="Cumulative Discounted Cash Flow")
    ax1.axhline(0, color="oc.gray5", linestyle="--", lw=dm.lw(0.8))
    
    payback_year = 12.6
    ax1.axvline(payback_year, color="oc.red6", linestyle=":", lw=dm.lw(1.0))
    ax1.plot(payback_year, 0, marker="o", color="oc.red6", markersize=6)
    ax1.text(payback_year + 0.6, -3.0, f"Discounted Payback Period: {payback_year} Years", 
             color="oc.red8", fontsize=12.5, fontweight="bold", va="center")
             
    ax1.plot(12, cum_discounted_mkrw[12], marker="x", color="oc.orange7", markersize=8, mew=2)
    ax1.text(12 - 0.5, cum_discounted_mkrw[12] - 3.0, "Actuator Replacement\n(Year 12)", 
             color="oc.orange9", fontsize=11, ha="right", va="top")
             
    ax1.set_xlabel("Project Timeline [Years]")
    ax1.set_ylabel("Cumulative NPV [Million KRW]")
    ax1.set_title("Cumulative Discounted Cash Flow & Payback Period", fontsize=15.5, fontweight="bold")
    ax1.set_xlim(0, 25)
    ax1.set_xticks(range(0, 26, 5))
    ax1.legend(loc="lower right")
    
    dm.simple_layout(fig1)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow.png"), dpi=300, transparent=True)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow.svg"), transparent=True)
    plt.close(fig1)
    
    # ----------------------------------------------------
    # [그래프 2] 연도별 명목 순현금흐름 vs 할인 현금흐름 비교
    # ----------------------------------------------------
    fig2, ax2 = plt.subplots(figsize=dm.figsize('26cm', '14cm'))
    bar_years = np.array(years[1:])
    bar_width = 0.35
    
    ax2.bar(bar_years - bar_width/2, net_cf_mkrw[1:], bar_width, 
             color="oc.gray5", label="Nominal Cash Flow", alpha=0.85)
    ax2.bar(bar_years + bar_width/2, discounted_cf_mkrw[1:], bar_width, 
             color="oc.blue6", label="Discounted Cash Flow (PV)", alpha=0.85)
                     
    ax2.text(12, net_cf_mkrw[12] + 0.3, "Actuator Replacement\nin Year 12",
             color="oc.orange9", fontsize=11, fontweight="bold", ha="center", va="bottom")
             
    ax2.set_xlabel("Project Timeline [Years]")
    ax2.set_ylabel("Annual Cash Flow [Million KRW]")
    ax2.set_title("Annual Nominal vs. Discounted Cash Flows (Year 1 - 25)", fontsize=15.5, fontweight="bold")
    ax2.set_xlim(0.5, 25.5)
    ax2.set_xticks(range(1, 26, 2))
    ax2.legend(loc="upper left")
    
    dm.simple_layout(fig2)
    fig2.savefig(os.path.join(figure_dir, "2_annual_cash_flows_comparison.png"), dpi=300, transparent=True)
    fig2.savefig(os.path.join(figure_dir, "2_annual_cash_flows_comparison.svg"), transparent=True)
    plt.close(fig2)
    
    # ----------------------------------------------------
    # [그래프 3] 초기 투자비 (CAPEX) 구성 비율 도넛 차트
    # ----------------------------------------------------
    fig3, ax3 = plt.subplots(figsize=dm.figsize('21cm', '14cm'))
    colors_capex = ["oc.blue7", "oc.cyan6", "oc.teal6", "oc.green6", "oc.yellow6", "oc.orange6", "oc.red6", "oc.grape6"]
    
    wedges, texts, autotexts = ax3.pie(
        capex_values_mkrw, 
        labels=capex_items, 
        autopct='%1.1f%%',
        startangle=140, 
        colors=colors_capex,
        textprops=dict(color="black", fontsize=11),
        pctdistance=0.75
    )
    centre_circle = plt.Circle((0,0), 0.55, fc='white')
    ax3.add_artist(centre_circle)
    
    plt.setp(autotexts, size=8, weight="bold")
    ax3.set_title(f"CAPEX Breakdown for Kinetic BIPV\n(Total: {total_capex/1e6:.2f} Million KRW)", fontsize=15.5, fontweight="bold")
    
    dm.simple_layout(fig3)
    fig3.savefig(os.path.join(figure_dir, "3_capex_breakdown.png"), dpi=300, transparent=True)
    fig3.savefig(os.path.join(figure_dir, "3_capex_breakdown.svg"), transparent=True)
    plt.close(fig3)

    # ----------------------------------------------------
    # [그래프 4] 생애주기비용 (LCC, Life Cycle Cost) 도넛 차트
    # ----------------------------------------------------
    fig4, ax4 = plt.subplots(figsize=dm.figsize('21cm', '14cm'))
    
    lcc_items = ["Initial CAPEX", "O&M (Present Value)", "Actuator Replacement (PV)"]
    lcc_values = [total_capex / 1e6, total_om_pv / 1e6, total_replace_pv / 1e6]
    total_lcc = sum(lcc_values)
    colors_lcc = ["oc.blue7", "oc.teal6", "oc.orange6"]
    
    wedges, texts, autotexts = ax4.pie(
        lcc_values, 
        labels=lcc_items, 
        autopct='%1.1f%%',
        startangle=120, 
        colors=colors_lcc,
        textprops=dict(color="black", fontsize=12),
        pctdistance=0.7
    )
    centre_circle = plt.Circle((0,0), 0.5, fc='white')
    ax4.add_artist(centre_circle)
    
    plt.setp(autotexts, size=8.5, weight="bold")
    ax4.set_title(f"25-Year Life Cycle Cost (LCC) Breakdown\n(Total LCC: {total_lcc:.2f} Million KRW)", fontsize=15.5, fontweight="bold")
    
    dm.simple_layout(fig4)
    fig4.savefig(os.path.join(figure_dir, "4_lcc_breakdown.png"), dpi=300, transparent=True)
    fig4.savefig(os.path.join(figure_dir, "4_lcc_breakdown.svg"), transparent=True)
    plt.close(fig4)

    # ----------------------------------------------------
    # [그래프 5] LCOE vs. Grid 전기요금 (그리드 패리티 비교)
    # ----------------------------------------------------
    fig5, ax5 = plt.subplots(figsize=dm.figsize('21cm', '13cm'))
    
    categories = [
        "Summer Tariff\n(June-August)",
        "Winter Tariff\n(November-February)",
        "Weighted Avg Tariff\n(Annual Average)",
        "Kinetic BIPV LCOE\n(Cost of Generation)",
        "Spring/Autumn Tariff\n(March-May, Sept-Oct)"
    ]
    prices = [165.0, 149.9, 138.7, lcoe_val, 119.3]
    
    # 순서 정렬 (가격이 높은 순으로 그리기 위해 인덱스 조정)
    # LCOE는 강조색(오렌지)을 입히고, 나머지는 그라데이션 블루 또는 그레이 처리
    colors_gp = ["oc.blue8", "oc.blue5", "oc.blue3", "oc.orange7", "oc.gray6"]
    
    bars = ax5.barh(categories, prices, color=colors_gp, height=0.6, alpha=0.9)
    
    # 각 막대 끝에 단가 텍스트 표시
    for bar in bars:
        width = bar.get_width()
        ax5.text(width + 2, bar.get_y() + bar.get_height()/2, f"{width:.1f} KRW", 
                 va="center", ha="left", fontsize=12.5, fontweight="bold")
                 
    # LCOE 기준 수직 점선 (그리드 패리티 기준선)
    ax5.axvline(lcoe_val, color="oc.orange7", linestyle="--", lw=dm.lw(1.2))
    ax5.text(lcoe_val + 1, len(categories) - 0.7, "Grid Parity Line (LCOE)", 
             color="oc.orange9", fontsize=12, fontweight="bold", ha="left", va="bottom")
             
    ax5.set_xlabel("Electricity Cost [KRW / kWh]")
    ax5.set_title("LCOE vs. Grid Electricity Tariffs (Grid Parity Analysis)", fontsize=15.5, fontweight="bold")
    ax5.set_xlim(0, 195)
    
    dm.simple_layout(fig5)
    fig5.savefig(os.path.join(figure_dir, "5_grid_parity_comparison.png"), dpi=300, transparent=True)
    fig5.savefig(os.path.join(figure_dir, "5_grid_parity_comparison.svg"), transparent=True)
    plt.close(fig5)
    
    print("All economic analysis plots (1-5) generated successfully in plot_py/LLC_dcf/ folder!")

if __name__ == "__main__":
    main()

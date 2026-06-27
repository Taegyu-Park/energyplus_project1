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

def solve_irr(cash_flows):
    r = 0.1
    for _ in range(100):
        npv = sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))
        d_npv = sum(-t * cf / ((1 + r) ** (t + 1)) for t, cf in enumerate(cash_flows))
        if d_npv == 0:
            break
        new_r = r - npv / d_npv
        if abs(new_r - r) < 1e-6:
            return new_r * 100
        r = new_r
    return 10.0

def main():
    # 1. 경로 설정
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    csv_1_path = os.path.join(project_root, "economy_analysis_1.csv")
    csv_2_path = os.path.join(project_root, "economy_analysis_2.csv")
    csv_3_path = os.path.join(project_root, "economy_analysis_3.csv")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "LLC_dcf"))
    os.makedirs(figure_dir, exist_ok=True)

    # ----------------------------------------------------
    # Case 3 데이터 파싱
    # ----------------------------------------------------
    years = []
    c3_tariffs = []
    c3_savings = []
    c3_om = []
    c3_replace = []
    c3_net_cf = []
    c3_discount_factors = []
    c3_discounted_cf = []
    c3_cum_discounted = []
    
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
            if year == 0:
                c3_tariffs.append(0.0)
                c3_savings.append(0.0)
                c3_om.append(0.0)
                c3_replace.append(0.0)
                c3_net_cf.append(parse_val(row[8]))
                c3_discount_factors.append(1.0)
                c3_discounted_cf.append(parse_val(row[10]))
                c3_cum_discounted.append(parse_val(row[11]))
            else:
                c3_tariffs.append(parse_val(row[4]))
                c3_savings.append(parse_val(row[5]))
                c3_om.append(parse_val(row[6]))
                c3_replace.append(parse_val(row[7]))
                c3_net_cf.append(parse_val(row[8]))
                c3_discount_factors.append(parse_val(row[9]))
                c3_discounted_cf.append(parse_val(row[10]))
                c3_cum_discounted.append(parse_val(row[11]))

    # Case 3 결과 요약
    c3_capex = 40912000.0
    c3_npv = c3_cum_discounted[-1]
    c3_lcoe = 128.5
    c3_payback = 12.6
    
    # ----------------------------------------------------
    # Case 2 (Fixed-90°) 경제성 연산 및 모델 수립
    # ----------------------------------------------------
    # CAPEX 구성
    c2_capex_dict = {
        "PV Modules": 9312000.0,
        "Actuators": 0.0,
        "Structure & Frame": 3500000.0,
        "Inverters & Converters": 5000000.0,
        "Tracking Control System": 0.0,
        "Electrical BOS": 3000000.0,
        "Installation & Commissioning": 4000000.0,
        "Design & Permitting": 1500000.0
    }
    c2_capex = sum(c2_capex_dict.values()) # 26,312,000 원
    
    # 발전량 및 절감액 연산
    # Case 2 90° 발전량 비율: 18.177 MWh (Case 3는 35.471 MWh) -> 17,935.2 kWh (Year 1)
    c2_pv_gen_y1 = 35000.0 * (18.177 / 35.471) # 17,935.2 kWh
    
    c2_net_cf = [-c2_capex]
    c2_discounted_cf = [-c2_capex]
    c2_cum_discounted = [-c2_capex]
    
    c2_savings = [0.0]
    c2_om = [0.0]
    c2_replace = [0.0]
    
    total_c2_om_pv = 0.0
    total_c2_replace_pv = 0.0
    total_c2_gen_discounted = 0.0
    
    # 연도별 현금흐름 시뮬레이션 (1~25년)
    for year in range(1, 26):
        # 1) 발전량 (연간 0.5% 열화)
        gen = c2_pv_gen_y1 * ((1 - 0.005) ** (year - 1))
        # 2) 단가 (동일 요금제 단가 사용)
        tariff = c3_tariffs[year]
        # 3) 절감액
        saving = gen * tariff
        c2_savings.append(saving)
        # 4) O&M (CAPEX의 1.0% 기준, 물가상승률 2.5% 반영)
        om_cost = (c2_capex * 0.01) * ((1 + 0.025) ** (year - 1))
        c2_om.append(om_cost)
        # 5) 교체비 (고정식은 0)
        replace_cost = 0.0
        c2_replace.append(replace_cost)
        
        # 6) 순 현금흐름
        net_cf = saving - om_cost
        c2_net_cf.append(net_cf)
        
        # 7) 할인 현금흐름
        df = c3_discount_factors[year]
        discounted = net_cf * df
        c2_discounted_cf.append(discounted)
        
        # 8) 누적 할인 현금흐름
        c2_cum_discounted.append(c2_cum_discounted[-1] + discounted)
        
        # LCOE용 누계 계산
        total_c2_om_pv += om_cost * df
        total_c2_replace_pv += replace_cost * df
        total_c2_gen_discounted += gen * df

    c2_npv = c2_cum_discounted[-1]
    
    # IRR 계산
    c2_irr = solve_irr(c2_net_cf)
        
    # LCOE 계산: (초기투자비 + O&M PV + 교체비 PV) / 할인발전량 누계
    c2_lcoe = (c2_capex + total_c2_om_pv) / total_c2_gen_discounted
    
    # 회수기간 계산 (할인현금흐름 기준 0을 돌파하는 시점 보간)
    c2_payback = 25.0
    for y in range(1, 26):
        if c2_cum_discounted[y-1] < 0 and c2_cum_discounted[y] >= 0:
            c2_payback = (y-1) + (-c2_cum_discounted[y-1]) / (c2_cum_discounted[y] - c2_cum_discounted[y-1])
            break

    print(f"Case 2 (Fixed-90°) Economic Summary:")
    print(f"  CAPEX: {c2_capex:,.0f} 원")
    print(f"  NPV: {c2_npv:,.0f} 원")
    print(f"  IRR: {c2_irr:.2f} %")
    print(f"  LCOE: {c2_lcoe:.2f} 원/kWh")
    print(f"  Discounted Payback: {c2_payback:.2f} 년")

    # 3. dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    
    # ----------------------------------------------------
    # [그래프 1] 누적 할인 현금흐름 비교 (NPV Trajectory Comparison)
    # ----------------------------------------------------
    fig1, ax1 = plt.subplots(figsize=dm.figsize('26cm', '14cm'))
    
    ax1.plot(years, [val/1e6 for val in c3_cum_discounted], color="oc.orange7", lw=dm.lw(1.5), label="Case 3 (Kinetic BIPV)")
    ax1.plot(years, [val/1e6 for val in c2_cum_discounted], color="oc.blue7", lw=dm.lw(1.5), label="Case 2 (Fixed-90° BIPV)")
    ax1.axhline(0, color="oc.gray5", linestyle="--", lw=dm.lw(0.8))
    
    # 회수기간 교점 표시
    ax1.plot(c3_payback, 0, marker="o", color="oc.orange9", markersize=6)
    ax1.text(c3_payback + 0.5, 3.0, f"Case 3 Payback: {c3_payback:.1f} Yrs", color="oc.orange9", fontsize=12, fontweight="bold")
    
    ax1.plot(c2_payback, 0, marker="o", color="oc.blue9", markersize=6)
    ax1.text(c2_payback - 0.5, -4.5, f"Case 2 Payback: {c2_payback:.1f} Yrs", color="oc.blue9", fontsize=12, fontweight="bold", ha="right")
    
    # 최종 NPV 텍스트 표시
    ax1.text(25.2, c3_cum_discounted[-1]/1e6, f"Case 3 NPV:\n{c3_npv/1e6:.2f}M KRW", color="oc.orange9", fontsize=11, fontweight="bold", va="center")
    ax1.text(25.2, c2_cum_discounted[-1]/1e6, f"Case 2 NPV:\n{c2_npv/1e6:.2f}M KRW", color="oc.blue9", fontsize=11, fontweight="bold", va="center")
    
    ax1.set_xlabel("Project Timeline [Years]")
    ax1.set_ylabel("Cumulative NPV [Million KRW]")
    ax1.set_title("NPV Trajectory & Payback Period Comparison", fontsize=15.5, fontweight="bold")
    ax1.set_xlim(0, 29) # 텍스트 공간 확보
    ax1.set_xticks(range(0, 26, 5))
    ax1.legend(loc="lower right")
    ax1.grid(True, alpha=0.3)
    
    dm.simple_layout(fig1)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow_comparison.png"), dpi=300, transparent=True)
    fig1.savefig(os.path.join(figure_dir, "1_cum_discounted_cash_flow_comparison.svg"), transparent=True)
    plt.close(fig1)
    
    # ----------------------------------------------------
    # [그래프 2] LCC (Life Cycle Cost) 비교 막대그래프
    # ----------------------------------------------------
    fig2, ax2 = plt.subplots(figsize=dm.figsize('20cm', '14cm'))
    
    # 각 케이스별 비용 구성 요소 (백만 원 단위)
    # LCC = CAPEX + Discounted O&M + Discounted Replacement
    c3_lcc_vals = [c3_capex / 1e6, sum(c3_om[1:]) * 0.948 / 1e6, sum(c3_replace) * 0.526 / 1e6] # O&M과 교체비 PV 대략치 사용 또는 실제 데이터 집계
    # 실제 연산 데이터 사용
    c3_total_om_pv = sum(c3_om[y] * c3_discount_factors[y] for y in range(1, 26))
    c3_total_replace_pv = sum(c3_replace[y] * c3_discount_factors[y] for y in range(1, 26))
    
    categories = ["Case 2 (Fixed-90°)", "Case 3 (Kinetic)"]
    capex_vals = np.array([c2_capex / 1e6, c3_capex / 1e6])
    om_vals = np.array([total_c2_om_pv / 1e6, c3_total_om_pv / 1e6])
    replace_vals = np.array([0.0, c3_total_replace_pv / 1e6])
    
    # 누적 막대 그래프 그리기
    width = 0.45
    b1 = ax2.bar(categories, capex_vals, width, label="Initial CAPEX", color="oc.blue7")
    b2 = ax2.bar(categories, om_vals, width, bottom=capex_vals, label="O&M (Present Value)", color="oc.teal6")
    b3 = ax2.bar(categories, replace_vals, width, bottom=capex_vals+om_vals, label="Equipment Replacement (PV)", color="oc.orange6")
    
    # 총 LCC 값 라벨 추가
    total_lccs = capex_vals + om_vals + replace_vals
    for idx, total in enumerate(total_lccs):
        ax2.text(idx, total + 1.0, f"{total:.2f}M KRW", ha="center", va="bottom", fontsize=12.5, fontweight="bold")
        
    ax2.set_ylabel("Total Life Cycle Cost [Million KRW]")
    ax2.set_title("25-Year Life Cycle Cost (LCC) Comparison", fontsize=15.5, fontweight="bold")
    ax2.set_ylim(0, max(total_lccs) + 8.0)
    ax2.legend(loc="upper left")
    
    dm.simple_layout(fig2)
    fig2.savefig(os.path.join(figure_dir, "2_lcc_comparison.png"), dpi=300, transparent=True)
    fig2.savefig(os.path.join(figure_dir, "2_lcc_comparison.svg"), transparent=True)
    plt.close(fig2)

    # ----------------------------------------------------
    # [그래프 3] LCOE 및 전기요금 그리드 패리티 비교
    # ----------------------------------------------------
    fig3, ax3 = plt.subplots(figsize=dm.figsize('23cm', '13cm'))
    
    labels_gp = [
        "Summer Tariff (June-August)",
        "Winter Tariff (Nov-Feb)",
        "Weighted Avg Tariff (Annual)",
        "Case 2 LCOE (Fixed-90°)",
        "Case 3 LCOE (Kinetic BIPV)",
        "Spring/Autumn Tariff (Mar-May, Sept-Oct)"
    ]
    prices_gp = [165.0, 149.9, 138.7, c2_lcoe, c3_lcoe, 119.3]
    colors_gp = ["oc.blue8", "oc.blue5", "oc.blue3", "oc.blue7", "oc.orange7", "oc.gray6"]
    
    bars = ax3.barh(labels_gp, prices_gp, color=colors_gp, height=0.6, alpha=0.9)
    for bar in bars:
        width = bar.get_width()
        ax3.text(width + 2, bar.get_y() + bar.get_height()/2, f"{width:.1f} KRW", 
                 va="center", ha="left", fontsize=12.5, fontweight="bold")
                 
    # 그리드 패리티 라인 추가
    ax3.axvline(c3_lcoe, color="oc.orange7", linestyle="--", lw=dm.lw(1.2))
    ax3.axvline(c2_lcoe, color="oc.blue7", linestyle=":", lw=dm.lw(1.2))
    
    ax3.set_xlabel("Electricity Cost [KRW / kWh]")
    ax3.set_title("LCOE vs. Grid Electricity Tariffs (Economic Feasibility)", fontsize=15.5, fontweight="bold")
    ax3.set_xlim(0, 195)
    
    dm.simple_layout(fig3)
    fig3.savefig(os.path.join(figure_dir, "3_lcoe_comparison.png"), dpi=300, transparent=True)
    fig3.savefig(os.path.join(figure_dir, "3_lcoe_comparison.svg"), transparent=True)
    plt.close(fig3)

    # ----------------------------------------------------
    # [그래프 4] CAPEX 구성 비교 그래프
    # ----------------------------------------------------
    fig4, ax4 = plt.subplots(figsize=dm.figsize('23cm', '14cm'))
    
    # 두 케이스의 CAPEX 구성 대조 막대 그래프
    items_capex = list(c2_capex_dict.keys())
    c2_capex_vals = [c2_capex_dict[item]/1e6 for item in items_capex]
    
    c3_capex_dict = {
        "PV Modules": 9312000.0,
        "Actuators": 3600000.0,
        "Structure & Frame": 7000000.0,
        "Inverters & Converters": 5000000.0,
        "Tracking Control System": 3500000.0,
        "Electrical BOS": 3000000.0,
        "Installation & Commissioning": 7000000.0,
        "Design & Permitting": 2500000.0
    }
    c3_capex_vals = [c3_capex_dict[item]/1e6 for item in items_capex]
    
    y_pos = np.arange(len(items_capex))
    height = 0.35
    
    ax4.barh(y_pos + height/2, c3_capex_vals, height, label="Case 3 (Kinetic)", color="oc.orange6", alpha=0.9)
    ax4.barh(y_pos - height/2, c2_capex_vals, height, label="Case 2 (Fixed-90°)", color="oc.blue6", alpha=0.9)
    
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(items_capex)
    ax4.set_xlabel("CAPEX Cost [Million KRW]")
    ax4.set_title("CAPEX Breakdown Comparison", fontsize=15.5, fontweight="bold")
    ax4.legend(loc="upper right")
    ax4.grid(True, alpha=0.3)
    
    dm.simple_layout(fig4)
    fig4.savefig(os.path.join(figure_dir, "4_capex_comparison.png"), dpi=300, transparent=True)
    fig4.savefig(os.path.join(figure_dir, "4_capex_comparison.svg"), transparent=True)
    plt.close(fig4)

    print("All comparison economic analysis plots generated inside LLC_dcf directory.")

if __name__ == "__main__":
    main()

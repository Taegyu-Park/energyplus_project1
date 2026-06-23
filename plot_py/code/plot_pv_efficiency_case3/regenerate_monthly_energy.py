import os
import matplotlib.pyplot as plt
import numpy as np
import dartwork_mpl as dm

def main():
    # 데이터 설정 (SVG 분석을 통해 획득한 실제 월별 MWh 발전량)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    energy = [2.71, 2.86, 3.44, 3.79, 3.69, 2.80, 2.63, 2.85, 3.15, 3.59, 2.89, 2.54]
    annual_total = 36.9 # SVG에 표시된 Annual total 값
    
    # dartwork-mpl 스타일 적용
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 1행 1열 subplots 생성 (가로형 발표자료용 비율)
    fig, ax = plt.subplots(figsize=dm.figsize('21cm', '12cm'))
    
    # 막대 색상: 세련되고 차분한 단일 블루 색상 (#4574b3)
    bar_color = '#4574b3'
    bar_width = 0.55
    
    # 막대 그래프 그리기
    bars = ax.bar(months, energy, color=bar_color, width=bar_width, alpha=0.9)
    
    # 각 막대 위에 월별 수치값 표시
    for bar in bars:
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.08, 
            f"{yval:.2f}", 
            ha='center', 
            va='bottom', 
            fontsize=11, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # 데코레이션 설정
    ax.set_ylabel("Energy [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly PV Generation (Case 3)")
    
    # Y축 범위 조정 (상단 텍스트 마진 확보)
    ax.set_ylim(0, 4.4)
    
    # 연간 총합 정보를 그래프 좌측 상단에 텍스트 상자로 기입
    ax.text(
        0.05, 
        0.93, 
        f"Annual total: {annual_total:.1f} MWh", 
        transform=ax.transAxes, 
        fontsize=12.5, 
        fontweight='bold', 
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#f8fafc', edgecolor='#e2e8f0', alpha=0.8),
        color='#1e293b'
    )
    
    # 저장 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "plot_pv_efficiency_case3"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "pv_case3_2_monthly_energy.png")
    output_svg = os.path.join(figure_dir, "pv_case3_2_monthly_energy.svg")
    
    # 레이아웃 간소화 및 투명 저장
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"Successfully generated monthly energy plots to:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

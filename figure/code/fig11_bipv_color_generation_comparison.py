"""
Monthly BIPV Generation Comparison by Color (White, Light Gray Beige, Terracotta)
컬러 BIPV 세 케이스(White, Light Gray Beige, Terracotta)의 월간 발전량 비교 분석
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm
plt.rcParams['svg.fonttype'] = 'none'

def load_monthly_generation_mwh(file_path):
    """
    Reads the EnergyPlus CSV file, parses Date/Time to extract month, 
    and returns monthly sum of facility total produced electricity in MWh.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found: {file_path}")
        
    df = pd.read_csv(file_path, usecols=['Date/Time', 'Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)'])
    
    # Extract Month from Date/Time (e.g. ' 01/01  00:10:00' -> 1)
    df['Month'] = df['Date/Time'].apply(lambda x: int(x.strip().split('/')[0]))
    
    # Group by Month and sum produced energy (Joules -> MWh)
    # 1 MWh = 3.6e9 Joules
    monthly_sum_j = df.groupby('Month')['Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)'].sum()
    monthly_mwh = monthly_sum_j / 3.6e9
    
    # Reindex to ensure all months (1-12) are represented
    monthly_mwh = monthly_mwh.reindex(range(1, 13), fill_value=0.0)
    return monthly_mwh.values

def main():
    # ── 경로 설정 ────────────────────────────────────────────────────────
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    data_dir     = os.path.join(project_root, "case_analysis", "bipv_variation")
    
    # ── 데이터 로드 ───────────────────────────────────────────────────────
    cases = {
        "White": {
            "file": os.path.join(data_dir, "case3_white.csv"),
            "color": "#f8fafc",  # Clean slate white
        },
        "Light Gray Beige": {
            "file": os.path.join(data_dir, "case3_light_gray_beige.csv"),
            "color": "#d4cdc3",  # Light gray-beige
        },
        "Terracotta": {
            "file": os.path.join(data_dir, "case3_terracotta.csv"),
            "color": "#c2593f",  # Terracotta brick orange-red
        }
    }
    
    gen_data = {}
    annual_totals = {}
    for name, info in cases.items():
        print(f"Loading and processing {name}...")
        mwh_vals = load_monthly_generation_mwh(info["file"])
        gen_data[name] = mwh_vals
        annual_totals[name] = sum(mwh_vals)
        print(f"  Annual Total: {annual_totals[name]:.2f} MWh")
        
    # ── 스타일 및 레이아웃 설정 ──────────────────────────────────────────
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    
    fig, ax = plt.subplots(figsize=(26 / 2.54, 13 / 2.54))
    
    # X axis positions and labels
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    x = np.arange(len(months_labels)) * 1.6  # Spacing out groups
    width = 0.5  # Bar width
    
    # Plotting grouped bars with borders for clarity on transparent background
    bars_white = ax.bar(x - width, gen_data["White"], width=width, color=cases["White"]["color"], edgecolor='#cbd5e1', linewidth=0.8, alpha=0.9, label="White (10.51%)")
    bars_beige = ax.bar(x, gen_data["Light Gray Beige"], width=width, color=cases["Light Gray Beige"]["color"], edgecolor='#b7ab9f', linewidth=0.8, alpha=0.9, label="Light Gray Beige (14.71%)")
    bars_terra = ax.bar(x + width, gen_data["Terracotta"], width=width, color=cases["Terracotta"]["color"], edgecolor='#9a3412', linewidth=0.8, alpha=0.9, label="Terracotta (16.39%)")
    
    # Add values on top of each bar (dark slate color for readability)
    for bar in bars_white:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.08, f"{yval:.2f}", ha='center', va='bottom', fontsize=10.5, color='#1e293b', fontweight='bold')
        
    for bar in bars_beige:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.08, f"{yval:.2f}", ha='center', va='bottom', fontsize=10.5, color='#1e293b', fontweight='bold')
        
    for bar in bars_terra:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.08, f"{yval:.2f}", ha='center', va='bottom', fontsize=10.5, color='#1e293b', fontweight='bold')
        
    # Labels and formatting
    ax.set_xlabel("Month", fontweight="bold", labelpad=10)
    ax.set_ylabel("PV Generation [MWh]", fontweight="bold", labelpad=10)
    ax.set_title("Monthly PV Generation Comparison by BIPV Color (Case 3)", fontsize=16, fontweight="bold", pad=20)
    
    ax.set_xticks(x)
    ax.set_xticklabels(months_labels)
    ax.set_ylim(0, 6.8)
    
    # Legend
    ax.legend(loc="upper right", framealpha=0.8)
    
    # Summary info box (Annual Total MWh)
    info_text = (
        "Annual Total Generation:\n"
        f"• Terracotta: {annual_totals['Terracotta']:.2f} MWh\n"
        f"• Light Gray Beige: {annual_totals['Light Gray Beige']:.2f} MWh\n"
        f"• White: {annual_totals['White']:.2f} MWh"
    )
    # Light theme translucent box background
    ax.text(
        0.02, 0.82, info_text, 
        transform=ax.transAxes, 
        fontsize=11, 
        fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#f8fafc', edgecolor='#cbd5e1', alpha=0.85),
        color='#1e293b'
    )
    
    # ── 이미지 저장 처리 ─────────────────────────────────────────────────
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    output_png = os.path.join(figure_dir, f"{script_name}.png")
    output_svg = os.path.join(figure_dir, f"{script_name}.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    plt.close(fig)
    
    print(f"\nSaved Code   → {__file__}")
    print(f"Saved Plot   → {output_png}")
    print(f"Saved Plot   → {output_svg}")

if __name__ == "__main__":
    main()

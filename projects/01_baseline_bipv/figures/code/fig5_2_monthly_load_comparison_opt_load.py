import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

plt.rcParams['svg.fonttype'] = 'none'

def parse_case2_monthly_loads(csv_path):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    
    # Identify heating and cooling columns
    heat_cols = [c for c in df.columns if 'Ideal Loads' in c and 'Heating' in c]
    cool_cols = [c for c in df.columns if 'Ideal Loads' in c and 'Cooling' in c]
    
    if not heat_cols or not cool_cols:
        heat_cols = [c for c in df.columns if 'Heating' in c]
        cool_cols = [c for c in df.columns if 'Cooling' in c]
        
    df['Month'] = df['Date/Time'].apply(lambda x: int(x.strip().split()[0].split('/')[0]))
    
    df['Heating_Sum'] = df[heat_cols].sum(axis=1)
    df['Cooling_Sum'] = df[cool_cols].sum(axis=1)
    
    # Group by Month and sum, convert to MWh (J / 3.6e9)
    monthly = df.groupby('Month')[['Heating_Sum', 'Cooling_Sum']].sum()
    monthly['Heating_MWh'] = monthly['Heating_Sum'] / 3.6e9
    monthly['Cooling_MWh'] = monthly['Cooling_Sum'] / 3.6e9
    monthly['Total_Load_MWh'] = monthly['Heating_MWh'] + monthly['Cooling_MWh']
    
    return monthly['Total_Load_MWh'].to_dict()

def parse_case3_monthly_loads(csv_path):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    
    heat_cols = [c for c in df.columns if 'Ideal Loads' in c and 'Heating' in c]
    cool_cols = [c for c in df.columns if 'Ideal Loads' in c and 'Cooling' in c]
    
    df['Month'] = df['Date/Time'].apply(lambda x: int(x.strip().split()[0].split('/')[0]))
    
    df['Heating_Sum'] = df[heat_cols].sum(axis=1)
    df['Cooling_Sum'] = df[cool_cols].sum(axis=1)
    
    monthly = df.groupby('Month')[['Heating_Sum', 'Cooling_Sum']].sum()
    monthly['Heating_MWh'] = monthly['Heating_Sum'] / 3.6e9
    monthly['Cooling_MWh'] = monthly['Cooling_Sum'] / 3.6e9
    monthly['Total_Load_MWh'] = monthly['Heating_MWh'] + monthly['Cooling_MWh']
    
    return monthly['Total_Load_MWh'].to_dict()

def main():
    # Detect directories relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # ------------------
    # Data for Case 2 (Load-Minimizing BIPV Angle & Load)
    # ------------------
    # BIPV 각도 정의:
    # - 0°: 외벽과 평행한 수직 밀폐 상태 (창문을 덮어 여름철 일사 차단에 유리)
    # - 90°: 외벽과 수직인 수평 차양 상태 (완전히 열려 겨울철 일사 획득에 유리)
    case2_dir = os.path.join(project_root, "case_analysis", "normal", "case2")
    angles = list(range(0, 100, 10))
    angle_results = {}
    
    # Extract data for all BIPV angles
    for angle in angles:
        folder_name = "0_v2" if angle == 0 else f"{angle}"
        csv_filename = f"case2_{angle}.csv"
        csv_path = os.path.join(case2_dir, folder_name, csv_filename)
        
        # Fallback to folder "0" for angle 0 if needed
        if angle == 0 and not os.path.exists(csv_path):
            csv_path = os.path.join(case2_dir, "0", csv_filename)
            
        monthly_load = parse_case2_monthly_loads(csv_path)
        if monthly_load:
            angle_results[angle] = monthly_load
            
    if not angle_results:
        print("Error: No simulation CSV files found for Case 2!")
        return

    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    best_angles = []
    case2_loads = []
    
    # For each month, find the angle that MINIMIZES the total thermal load
    for m in range(1, 13):
        best_angle = None
        min_val = float('inf')
        for angle in angles:
            if angle in angle_results:
                val = angle_results[angle].get(m, float('inf'))
                if val < min_val:
                    min_val = val
                    best_angle = angle
        best_angles.append(best_angle)
        case2_loads.append(min_val)
        
    case2_annual_total = sum(case2_loads)
    
    # ------------------
    # Data for Case 3 (Monthly HVAC Load)
    # ------------------
    case3_csv_path = os.path.join(project_root, "case_analysis", "normal", "case3", "case3.csv")
    case3_load_dict = parse_case3_monthly_loads(case3_csv_path)
    if not case3_load_dict:
        print("Error: Case 3 CSV file not found!")
        return
        
    case3_loads = [case3_load_dict.get(m, 0.0) for m in range(1, 13)]
    case3_annual_total = sum(case3_loads)

    # ------------------
    # Plotting using dartwork-mpl
    # ------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # Create single subplot (stretched horizontally to 26cm)
    fig, ax = plt.subplots(figsize=(26 / 2.54, 12 / 2.54))
    
    # Space out x positions by 1.4 to create a visible gap between months
    x = np.arange(len(months_labels)) * 1.4
    width = 0.5  # width of each bar
    
    # Case 2: Left bar in each month group
    left_color = 'oc.blue6'  # Cool blue
    bars_left = ax.bar(x - width/2, case2_loads, width=width, color=left_color, alpha=0.9, label='Case 2 (Opt BIPV Load)')
    
    # Case 3: Right bar in each month group
    right_color = 'oc.orange7'  # Warm orange
    bars_right = ax.bar(x + width/2, case3_loads, width=width, color=right_color, alpha=0.9, label='Case 3 (Kinetic BIPV)')
    
    # Annotate Case 2 (Load value near top, Optimal Angle inside bar near bottom)
    for bar, angle in zip(bars_left, best_angles):
        yval = bar.get_height()
        # Load value on top of the bar
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.5, 
            f"{yval:.2f}", 
            ha='center', 
            va='bottom', 
            fontsize=10.0, 
            fontweight='bold',
            color='#1e293b'
        )
        # Optimal BIPV angle inside the bar (near the bottom)
        # Place it at a fixed height of 1.5 MWh if yval > 4.0, else inside near the middle
        user_angle = 90 - angle
        text_y = 1.5 if yval > 4.0 else yval / 2.0
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            text_y, 
            f"{user_angle}°", 
            ha='center', 
            va='center', 
            fontsize=10.0, 
            fontweight='bold',
            color='#ffffff' if yval > 4.0 else '#1e293b'
        )
        
    # Annotate Case 3 (Load value)
    for bar in bars_right:
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.5, 
            f"{yval:.2f}", 
            ha='center', 
            va='bottom', 
            fontsize=10.0, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # Set labels, ticks, title, limits
    ax.set_ylabel("HVAC Load [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly HVAC Load Comparison (Optimal Load Angle for Case 2)", fontsize=17, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(months_labels)
    ax.set_ylim(0, 36.0)
    
    # Add Legend
    ax.legend(loc="upper right")
    
    # Add Annual total information in a nice text box on the upper left
    info_text = (
        f"Annual Total:\n"
        f"• Case 2 (Opt): {case2_annual_total:.2f} MWh\n"
        f"• Case 3 (Kinetic): {case3_annual_total:.2f} MWh"
    )
    ax.text(
        0.03, 
        0.83, 
        info_text, 
        transform=ax.transAxes, 
        fontsize=11, 
        fontweight='bold', 
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#f8fafc', edgecolor='#e2e8f0', alpha=0.85),
        color='#1e293b'
    )
    
    # Save files
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, f"{script_name}.png")
    output_svg = os.path.join(figure_dir, f"{script_name}.svg")
    
    # Apply layout cleanups
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"\nSuccessfully generated combined monthly HVAC load plot:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

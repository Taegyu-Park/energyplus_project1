import os
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
import dartwork_mpl as dm

def get_monthly_pv(db_path):
    if not os.path.exists(db_path):
        return None
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Get dictionary index for Facility Total Produced Electricity Energy
    c.execute("""
        SELECT ReportDataDictionaryIndex 
        FROM ReportDataDictionary 
        WHERE KeyValue = 'Whole Building' AND Name = 'Facility Total Produced Electricity Energy' AND ReportingFrequency = 'Zone Timestep'
    """)
    res = c.fetchone()
    if not res:
        # Fallback search
        c.execute("""
            SELECT ReportDataDictionaryIndex 
            FROM ReportDataDictionary 
            WHERE Name LIKE 'Facility Total Produced Electricity Energy%' AND ReportingFrequency = 'Zone Timestep'
        """)
        res = c.fetchone()
        
    if not res:
        conn.close()
        return None
        
    dict_idx = res[0]
    
    # 2. Query monthly totals in Joules
    c.execute("""
        SELECT t.Month, SUM(rd.Value)
        FROM ReportData rd
        INNER JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rd.ReportDataDictionaryIndex = ?
        GROUP BY t.Month
        ORDER BY t.Month
    """, (dict_idx,))
    
    monthly_data = {}
    for month, total_j in c.fetchall():
        # Convert Joules to MWh (J / 3.6e9)
        monthly_data[month] = total_j / 3.6e9
        
    conn.close()
    return monthly_data

def main():
    # Detect directories relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    
    # ------------------
    # Data for Left Plot: Case 2 (Optimal BIPV Angle & PV Generation)
    # ------------------
    case2_dir = os.path.join(project_root, "run_analysis", "model_realscale_case2")
    angles = list(range(0, 100, 10))
    angle_results = {}
    
    # Extract data for all BIPV angles
    for angle in angles:
        folder_name = f"model_realscale_{angle}_v2" if angle == 0 else f"model_realscale_{angle}"
        db_path = os.path.join(case2_dir, folder_name, "eplusout.sql")
        monthly_pv = get_monthly_pv(db_path)
        if monthly_pv:
            angle_results[angle] = monthly_pv
            
    if not angle_results:
        print("Error: No simulation database files found for Case 2!")
        return

    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    best_angles = []
    case2_generations = []
    
    for m in range(1, 13):
        best_angle = None
        max_val = -1.0
        for angle in angles:
            val = angle_results[angle].get(m, 0.0)
            if val > max_val:
                max_val = val
                best_angle = angle
        best_angles.append(best_angle)
        case2_generations.append(max_val)
        
    case2_annual_total = sum(case2_generations)
    
    # ------------------
    # Data for Right Plot: Case 3 (Monthly PV Generation)
    # ------------------
    # Hardcoded values from regenerate_monthly_energy.py to match pv_case3_2_monthly_energy.svg exactly
    case3_generations = [2.71, 2.86, 3.44, 3.79, 3.69, 2.80, 2.63, 2.85, 3.15, 3.59, 2.89, 2.54]
    case3_annual_total = 36.9  # SVG에 표시된 Annual total 값

    # ------------------
    # Plotting using dartwork-mpl
    # ------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # Create single subplot (stretched horizontally to 26cm)
    fig, ax = plt.subplots(figsize=dm.figsize('26cm', '12cm'))
    
    # Space out x positions by 1.4 to create a visible gap between months
    x = np.arange(len(months_labels)) * 1.4
    width = 0.5  # width of each bar
    
    # Case 2: Left bar in each month group
    left_color = 'oc.blue6'  # Cool blue
    bars_left = ax.bar(x - width/2, case2_generations, width=width, color=left_color, alpha=0.9, label='Case 2 (Opt BIPV)')
    
    # Case 3: Right bar in each month group
    right_color = 'oc.orange7'  # Warm orange
    bars_right = ax.bar(x + width/2, case3_generations, width=width, color=right_color, alpha=0.9, label='Case 3 (Kinetic BIPV)')
    
    # Annotate Case 2 (Generation inside near top, Optimal Angle inside near bottom)
    for bar, angle in zip(bars_left, best_angles):
        yval = bar.get_height()
        # Generation value inside the bar (near the top)
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.15, 
            f"{yval:.2f}", 
            ha='center', 
            va='center', 
            fontsize=10.5, 
            fontweight='bold',
            color='#1e293b'
        )
        # Optimal BIPV angle inside the bar (near the bottom)
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval - 0.35, 
            f"{angle}°", 
            ha='center', 
            va='center', 
            fontsize=10.5, 
            fontweight='bold',
            color='#ffffff'
        )
        
    # Annotate Case 3 (Generation)
    for bar in bars_right:
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.05, 
            f"{yval:.2f}", 
            ha='center', 
            va='bottom', 
            fontsize=10.5, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # Set labels, ticks, title, limits
    ax.set_ylabel("PV Generation [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly PV Generation Comparison", fontsize=17, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(months_labels)
    ax.set_ylim(0, 4.6)
    
    # Add Legend
    ax.legend(loc="upper right")
    
    # Add Annual total information in a nice text box on the upper left
    info_text = (
        f"Annual Total:\n"
        f"• Case 2 (Opt): {case2_annual_total:.2f} MWh\n"
        f"• Case 3 (Kinetic): {case3_annual_total:.1f} MWh"
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
    
    # Define output files
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "combind_monthly_pv"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "combined_monthly_pv.png")
    output_svg = os.path.join(figure_dir, "combined_monthly_pv.svg")
    
    # Apply layout cleanups
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"\nSuccessfully generated combined monthly energy plot (grouped):")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

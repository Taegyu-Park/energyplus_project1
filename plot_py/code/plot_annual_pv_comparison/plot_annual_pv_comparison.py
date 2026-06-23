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
    # Data for Case 2 (Fixed BIPV at each angle)
    # ------------------
    case2_dir = os.path.join(project_root, "run_analysis", "model_realscale_case2")
    angles = list(range(0, 100, 10))
    case2_annual = []
    
    for angle in angles:
        folder_name = f"model_realscale_{angle}_v2" if angle == 0 else f"model_realscale_{angle}"
        db_path = os.path.join(case2_dir, folder_name, "eplusout.sql")
        monthly_pv = get_monthly_pv(db_path)
        if monthly_pv:
            annual_sum = sum(monthly_pv.values())
            case2_annual.append(annual_sum)
            print(f"Angle {angle}°: Annual PV Gen = {annual_sum:.3f} MWh")
        else:
            case2_annual.append(0.0)
            print(f"Angle {angle}°: Database not found!")

    # ------------------
    # Data for Case 3 (Kinetic BIPV)
    # ------------------
    case3_db = os.path.join(project_root, "run_analysis", "model_realscale_case3", "eplusout.sql")
    case3_monthly = get_monthly_pv(case3_db)
    if case3_monthly:
        case3_annual = sum(case3_monthly.values())
        print(f"Case 3 (Kinetic): Annual PV Gen = {case3_annual:.3f} MWh")
    else:
        case3_annual = 0.0
        print("Case 3: Database not found!")

    # ------------------
    # Plotting using dartwork-mpl
    # ------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    fig, ax = plt.subplots(figsize=dm.figsize('21cm', '12cm'))
    
    # 11 bars: 10 for Fixed angles, 1 for Kinetic at the end
    x = np.arange(len(angles) + 1)
    bar_width = 0.65
    
    # Colors (Switched as requested: Case 2 is blue, Case 3 is orange)
    case2_color = 'oc.blue6'
    case3_color = 'oc.orange7'
    
    # Plot Case 2 as bars (x = 0 to 9)
    bars_case2 = ax.bar(x[:-1], case2_annual, color=case2_color, width=bar_width, alpha=0.9, label='Case 2 (Fixed BIPV)')
    
    # Plot Case 3 as a single bar at the end (x = 10)
    bar_case3 = ax.bar(x[-1], [case3_annual], color=case3_color, width=bar_width, alpha=0.9, label='Case 3 (Kinetic BIPV)')
    
    # Annotate each bar of Case 2
    for bar in bars_case2:
        yval = bar.get_height()
        if yval > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0, 
                yval + 0.6, 
                f"{yval:.2f}", 
                ha='center', 
                va='bottom', 
                fontsize=10.5, 
                fontweight='bold',
                color='#1e293b'
            )
            
    # Annotate Case 3 bar
    for bar in bar_case3:
        yval = bar.get_height()
        if yval > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0, 
                yval + 0.6, 
                f"{yval:.2f}", 
                ha='center', 
                va='bottom', 
                fontsize=10.5, 
                fontweight='bold',
                color='#1e293b'
            )
            
    # Set titles and labels
    ax.set_title("Annual PV Generation Comparison", fontsize=17, fontweight='bold')
    ax.set_xlabel("BIPV Installation Case")
    ax.set_ylabel("Annual PV Generation [MWh]")
    
    # X-axis ticks
    xtick_labels = [f"{a}°" for a in angles] + ['Kinetic']
    ax.set_xticks(x)
    ax.set_xticklabels(xtick_labels)
    
    # Y-axis range
    ax.set_ylim(0, max(max(case2_annual), case3_annual) + 5.0)
    
    # Grid and legend
    ax.grid(True, axis='both', linewidth=0.3, color='#e2e8f0')
    ax.legend(loc="upper left")
    
    # Save files
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "plot_annual_pv_comparison"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "plot_annual_pv_comparison.png")
    output_svg = os.path.join(figure_dir, "plot_annual_pv_comparison.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"\nPlotting complete. Saved files:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

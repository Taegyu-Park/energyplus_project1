import os
import sqlite3
import matplotlib.pyplot as plt
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
        print("Error: No simulation database files found!")
        return

    # Find the optimal BIPV angle and max generation for each month
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    best_angles = []
    max_generations = []
    
    print("Monthly optimal BIPV angle search results:")
    print("-" * 55)
    for m in range(1, 13):
        best_angle = None
        max_val = -1.0
        for angle in angles:
            val = angle_results[angle].get(m, 0.0)
            if val > max_val:
                max_val = val
                best_angle = angle
        best_angles.append(best_angle)
        max_generations.append(max_val)
        print(f"  Month {m:2d} ({months_labels[m-1]}): Best BIPV Angle = {best_angle:2d}°, Generation = {max_val:.3f} MWh")
        
    annual_total = sum(max_generations)
    print("-" * 55)
    print(f"Annual Max PV Generation Total: {annual_total:.3f} MWh")

    # 3. Apply dartwork-mpl style and plot
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # Create subplot (widescreen presentation aspect ratio)
    fig, ax = plt.subplots(figsize=dm.figsize('21cm', '12cm'))
    
    # Sleek dark teal color palette for PV generation
    bar_color = '#0f766e' 
    bar_width = 0.55
    
    # Plot bars
    bars = ax.bar(months_labels, max_generations, color=bar_color, width=bar_width, alpha=0.9)
    
    # Annotate optimal BIPV angles and generation values on top of each bar
    for bar, angle, val in zip(bars, best_angles, max_generations):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0, 
            yval + 0.05, 
            f"{angle}°\n{yval:.2f}", 
            ha='center', 
            va='bottom', 
            fontsize=11, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # Decoration setting
    ax.set_ylabel("PV Generation [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Optimal Monthly BIPV Angle and PV Generation (Case 2)")
    
    # Set y-axis range to accommodate the annotations neatly
    ax.set_ylim(0, 3.2)
    
    # Display the annual sum of the optimal configurations in a text box
    ax.text(
        0.05, 
        0.93, 
        f"Annual total (Opt): {annual_total:.2f} MWh", 
        transform=ax.transAxes, 
        fontsize=12.5, 
        fontweight='bold', 
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#f8fafc', edgecolor='#e2e8f0', alpha=0.8),
        color='#1e293b'
    )
    
    # Define output file names
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "fixed_monthly_best_pv_generation"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "monthly_best_bipv_angle.png")
    output_svg = os.path.join(figure_dir, "monthly_best_bipv_angle.svg")
    
    # Save with transparent background
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"\nPlotting complete. Saved output files:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

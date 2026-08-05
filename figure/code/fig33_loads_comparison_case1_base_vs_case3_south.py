"""
Heating and Cooling Loads Comparison:
Case A: case1_KS (Base Model - No PV, No Shading)
Case B: case3_v3_south (South Wall Kinetic BIPV Shading Model)
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

def get_monthly_metric(c, var_name):
    c.execute("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = ?", (var_name,))
    ids = [r[0] for r in c.fetchall()]
    if not ids:
        return {m: 0.0 for m in range(1, 13)}, 0.0
    placeholders = ",".join("?" for _ in ids)
    query = f"""
        SELECT t.Month, SUM(rd.Value)
        FROM ReportData rd
        JOIN Time t ON rd.TimeIndex = t.TimeIndex
        WHERE rd.ReportDataDictionaryIndex IN ({placeholders})
          AND t.WarmupFlag = 0
        GROUP BY t.Month
    """
    c.execute(query, ids)
    res = {m: 0.0 for m in range(1, 13)}
    for m, val in c.fetchall():
        res[m] = (val or 0.0) / 3.6e6
    total = sum(res.values())
    return res, total

def get_case_loads(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    heat_m, heat_tot = get_monthly_metric(c, 'Zone Ideal Loads Supply Air Total Heating Energy')
    cool_m, cool_tot = get_monthly_metric(c, 'Zone Ideal Loads Supply Air Total Cooling Energy')
    
    conn.close()
    
    monthly_data = {
        m: {
            'Heating': heat_m[m],
            'Cooling': cool_m[m],
            'Total': heat_m[m] + cool_m[m]
        } for m in range(1, 13)
    }
    
    return {
        'heat_kwh': heat_tot,
        'cool_kwh': cool_tot,
        'hvac_kwh': heat_tot + cool_tot,
        'monthly': monthly_data
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    dir_case1 = os.path.join(project_root, "case_analysis", "normal", "case1_KS")
    dir_case3 = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south")
    
    db_case1 = os.path.join(dir_case1, "eplusout.sql")
    db_case3 = os.path.join(dir_case3, "eplusout.sql")
    
    print("Extracting loads for case1_KS...")
    res_case1 = get_case_loads(db_case1)
    print("Extracting loads for case3_v3_south...")
    res_case3 = get_case_loads(db_case3)
    
    # Print Empirical Results
    print("\n" + "="*85)
    print(" EMPIRICAL LOADS COMPARISON (case1_KS vs case3_v3_south)")
    print("="*85)
    print(f"{'Metric (kWh)':<25} | {'case1_KS (Base)':<18} | {'case3_v3_south':<18} | {'Diff (b-a)':<12} | {'Diff (%)':<10}")
    print("-" * 85)
    
    metrics = [
        ('Heating Load', 'heat_kwh'),
        ('Cooling Load', 'cool_kwh'),
        ('Total HVAC Load', 'hvac_kwh')
    ]
    
    for label, key in metrics:
        val_a = res_case1[key]
        val_b = res_case3[key]
        diff = val_b - val_a
        pct = (diff / val_a * 100) if val_a != 0 else 0.0
        print(f"{label:<25} | {val_a:18.2f} | {val_b:18.2f} | {diff:+12.2f} | {pct:+9.2f}%")
        
    print("="*85)
    
    # Monthly Breakdown Table
    print("\nMONTHLY BREAKDOWN (kWh):")
    print("-" * 85)
    print(f"{'Month':<6} | {'Heat (Base)':<12} | {'Heat (South)':<12} | {'Cool (Base)':<12} | {'Cool (South)':<12} | {'Total (Base)':<12} | {'Total (South)':<12}")
    print("-" * 85)
    for m in range(1, 13):
        m_a = res_case1['monthly'][m]
        m_b = res_case3['monthly'][m]
        print(f"{m:02d}     | {m_a['Heating']:12.1f} | {m_b['Heating']:12.1f} | {m_a['Cooling']:12.1f} | {m_b['Cooling']:12.1f} | {m_a['Total']:12.1f} | {m_b['Total']:12.1f}")
    print("="*85)

    # Visualization
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, f"{script_name}.png")
    plot_svg_path = os.path.join(figure_dir, f"{script_name}.svg")
    
    try:
        import dartwork_mpl as dm
        dm.style.use("presentation")
        mpl.rcParams['svg.fonttype'] = 'none'
    except ImportError:
        plt.style.use("default")
        
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    months = np.arange(1, 13)
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Color palette
    color_a = '#7f8c8d'  # Gray for Base (case1_KS)
    color_b = '#2ecc71'  # Green for Kinetic BIPV South (case3_v3_south)
    
    # 1. Annual Summary Comparison Bar Chart
    categories = ['Heating Load', 'Cooling Load', 'Total HVAC Load']
    x = np.arange(len(categories))
    width = 0.35
    vals_a = [res_case1[k] for _, k in metrics]
    vals_b = [res_case3[k] for _, k in metrics]
    
    rects1 = axes[0].bar(x - width/2, vals_a, width, label='case1_KS (Base)', color=color_a)
    rects2 = axes[0].bar(x + width/2, vals_b, width, label='case3_v3_south', color=color_b)
    axes[0].set_ylabel('Energy Load (kWh)', fontsize=11, fontweight='bold')
    axes[0].set_title('Annual HVAC Load Comparison', fontsize=13, fontweight='bold', pad=10)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(categories, fontsize=9, fontweight='bold')
    axes[0].legend(framealpha=0)
    axes[0].grid(axis='y', linestyle='--', alpha=0.5)
    
    for rect in rects1:
        height = rect.get_height()
        axes[0].annotate(f'{height:.0f}', xy=(rect.get_x() + rect.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')
    for rect in rects2:
        height = rect.get_height()
        axes[0].annotate(f'{height:.0f}', xy=(rect.get_x() + rect.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 2. Monthly Heating Load
    heat_m_a = [res_case1['monthly'][m]['Heating'] for m in months]
    heat_m_b = [res_case3['monthly'][m]['Heating'] for m in months]
    
    axes[1].plot(months, heat_m_a, marker='o', linewidth=2.5, label='case1_KS (Base)', color=color_a)
    axes[1].plot(months, heat_m_b, marker='s', linewidth=2.5, label='case3_v3_south', color=color_b)
    axes[1].set_xlabel('Month', fontsize=11, fontweight='bold')
    axes[1].set_ylabel('Heating Load (kWh)', fontsize=11, fontweight='bold')
    axes[1].set_title('Monthly Heating Load Profile', fontsize=13, fontweight='bold', pad=10)
    axes[1].set_xticks(months)
    axes[1].set_xticklabels(month_labels, fontsize=9)
    axes[1].legend(framealpha=0)
    axes[1].grid(True, linestyle='--', alpha=0.5)
    
    # 3. Monthly Cooling Load
    cool_m_a = [res_case1['monthly'][m]['Cooling'] for m in months]
    cool_m_b = [res_case3['monthly'][m]['Cooling'] for m in months]
    
    axes[2].plot(months, cool_m_a, marker='o', linewidth=2.5, label='case1_KS (Base)', color=color_a)
    axes[2].plot(months, cool_m_b, marker='s', linewidth=2.5, label='case3_v3_south', color=color_b)
    axes[2].set_xlabel('Month', fontsize=11, fontweight='bold')
    axes[2].set_ylabel('Cooling Load (kWh)', fontsize=11, fontweight='bold')
    axes[2].set_title('Monthly Cooling Load Profile', fontsize=13, fontweight='bold', pad=10)
    axes[2].set_xticks(months)
    axes[2].set_xticklabels(month_labels, fontsize=9)
    axes[2].legend(framealpha=0)
    axes[2].grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()
    
    print(f"\nSaved plots to:\n  - {plot_png_path}\n  - {plot_svg_path}")

if __name__ == "__main__":
    main()

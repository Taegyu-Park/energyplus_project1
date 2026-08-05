"""
Comparison of PV Generation and Heating/Cooling Loads:
Case A: case3_v3_south_noshading
Case B: case3_v3_south_old_periodic30
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

def get_rdd_ids(c, var_name):
    c.execute("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = ?", (var_name,))
    return [r[0] for r in c.fetchall()]

def get_total_sum(c, rdd_ids):
    if not rdd_ids:
        return 0.0
    placeholders = ",".join("?" for _ in rdd_ids)
    c.execute(f"SELECT SUM(Value) FROM ReportData WHERE ReportDataDictionaryIndex IN ({placeholders})", rdd_ids)
    val = c.fetchone()[0] or 0.0
    return val / 3.6e6  # Joules to kWh

def get_monthly_sums(c, rdd_ids, month_ranges):
    if not rdd_ids:
        return {m: 0.0 for m in range(1, 13)}
    placeholders = ",".join("?" for _ in rdd_ids)
    res = {}
    for m, min_t, max_t in month_ranges:
        c.execute(f"SELECT SUM(Value) FROM ReportData WHERE ReportDataDictionaryIndex IN ({placeholders}) AND TimeIndex >= {min_t} AND TimeIndex <= {max_t}", rdd_ids)
        res[m] = (c.fetchone()[0] or 0.0) / 3.6e6
    return res

def get_case_metrics(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get month boundaries from Time table (fast, only 52k rows)
    c.execute("SELECT Month, MIN(TimeIndex), MAX(TimeIndex) FROM Time WHERE WarmupFlag = 0 GROUP BY Month ORDER BY Month")
    month_ranges = c.fetchall()
    
    # RDD IDs
    pv_ids = get_rdd_ids(c, 'Generator Produced DC Electricity Energy')
    heat_ids = get_rdd_ids(c, 'Zone Ideal Loads Supply Air Total Heating Energy')
    cool_ids = get_rdd_ids(c, 'Zone Ideal Loads Supply Air Total Cooling Energy')
    
    # Annual totals
    pv_tot = get_total_sum(c, pv_ids)
    heat_tot = get_total_sum(c, heat_ids)
    cool_tot = get_total_sum(c, cool_ids)
    
    # Monthly profiles
    pv_m = get_monthly_sums(c, pv_ids, month_ranges)
    heat_m = get_monthly_sums(c, heat_ids, month_ranges)
    cool_m = get_monthly_sums(c, cool_ids, month_ranges)
    
    conn.close()
    
    monthly_data = {
        m: {
            'PV': pv_m[m],
            'Heating': heat_m[m],
            'Cooling': cool_m[m]
        } for m in range(1, 13)
    }
    
    return {
        'pv_kwh': pv_tot,
        'heat_kwh': heat_tot,
        'cool_kwh': cool_tot,
        'hvac_kwh': heat_tot + cool_tot,
        'monthly': monthly_data
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    dir_noshading = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south_noshading")
    dir_periodic30 = os.path.join(project_root, "case_analysis", "bipv_variation", "5zone_NSEW_korean", "case3_v3_south_old_periodic30")
    
    db_noshading = os.path.join(dir_noshading, "eplusout.sql")
    db_periodic30 = os.path.join(dir_periodic30, "eplusout.sql")
    
    print("Extracting data for case3_v3_south_noshading...")
    res_noshading = get_case_metrics(db_noshading)
    print("Extracting data for case3_v3_south_old_periodic30...")
    res_periodic30 = get_case_metrics(db_periodic30)
    
    # Print Empirical Results
    print("\n" + "="*85)
    print(" EMPIRICAL COMPARISON RESULTS (case3_v3_south_noshading vs case3_v3_south_old_periodic30)")
    print("="*85)
    print(f"{'Metric (kWh)':<30} | {'noshading':<18} | {'old_periodic30':<18} | {'Diff (b-a)':<12} | {'Diff (%)':<10}")
    print("-" * 85)
    
    metrics = [
        ('PV Generation', 'pv_kwh'),
        ('Heating Load', 'heat_kwh'),
        ('Cooling Load', 'cool_kwh'),
        ('Total HVAC Load', 'hvac_kwh')
    ]
    
    for label, key in metrics:
        val_a = res_noshading[key]
        val_b = res_periodic30[key]
        diff = val_b - val_a
        pct = (diff / val_a * 100) if val_a != 0 else 0.0
        print(f"{label:<30} | {val_a:18.2f} | {val_b:18.2f} | {diff:+12.2f} | {pct:+9.2f}%")
        
    print("="*85)
    
    # Monthly Breakdown Table
    print("\nMONTHLY BREAKDOWN (kWh):")
    print("-" * 85)
    print(f"{'Month':<6} | {'PV (NoSh)':<10} | {'PV (Per30)':<10} | {'Heat (NoSh)':<11} | {'Heat (Per30)':<12} | {'Cool (NoSh)':<11} | {'Cool (Per30)':<12}")
    print("-" * 85)
    for m in range(1, 13):
        m_a = res_noshading['monthly'][m]
        m_b = res_periodic30['monthly'][m]
        print(f"{m:02d}     | {m_a['PV']:10.1f} | {m_b['PV']:10.1f} | {m_a['Heating']:11.1f} | {m_b['Heating']:12.1f} | {m_a['Cooling']:11.1f} | {m_b['Cooling']:12.1f}")
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
        
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    months = np.arange(1, 13)
    month_labels = [f"{m}월" for m in months]
    
    # Color palette
    color_a = '#3498db'
    color_b = '#e74c3c'
    
    # 1. Monthly PV Generation
    pv_m_a = [res_noshading['monthly'][m]['PV'] for m in months]
    pv_m_b = [res_periodic30['monthly'][m]['PV'] for m in months]
    
    axes[0, 0].plot(months, pv_m_a, marker='o', linewidth=2.5, label='No Shading', color=color_a)
    axes[0, 0].plot(months, pv_m_b, marker='s', linewidth=2.5, label='Old Periodic 30°', color=color_b)
    axes[0, 0].set_xlabel('Month', fontsize=11, fontweight='bold')
    axes[0, 0].set_ylabel('PV Generation (kWh)', fontsize=11, fontweight='bold')
    axes[0, 0].set_title('Monthly PV Generation Profile', fontsize=13, fontweight='bold', pad=10)
    axes[0, 0].set_xticks(months)
    axes[0, 0].set_xticklabels(month_labels, fontsize=9)
    axes[0, 0].legend(framealpha=0)
    axes[0, 0].grid(True, linestyle='--', alpha=0.5)
    
    # 2. Annual Performance Comparison Bar Chart
    categories = ['PV Generation', 'Heating Load', 'Cooling Load', 'Total HVAC']
    x = np.arange(len(categories))
    width = 0.35
    vals_a = [res_noshading[k] for _, k in metrics]
    vals_b = [res_periodic30[k] for _, k in metrics]
    
    rects1 = axes[0, 1].bar(x - width/2, vals_a, width, label='No Shading', color=color_a)
    rects2 = axes[0, 1].bar(x + width/2, vals_b, width, label='Old Periodic 30°', color=color_b)
    axes[0, 1].set_ylabel('Energy (kWh)', fontsize=11, fontweight='bold')
    axes[0, 1].set_title('Annual Performance Summary', fontsize=13, fontweight='bold', pad=10)
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(categories, fontsize=9, fontweight='bold')
    axes[0, 1].legend(framealpha=0)
    axes[0, 1].grid(axis='y', linestyle='--', alpha=0.5)
    
    for rect in rects1:
        height = rect.get_height()
        axes[0, 1].annotate(f'{height:.0f}', xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')
    for rect in rects2:
        height = rect.get_height()
        axes[0, 1].annotate(f'{height:.0f}', xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 3. Monthly Heating Load
    heat_m_a = [res_noshading['monthly'][m]['Heating'] for m in months]
    heat_m_b = [res_periodic30['monthly'][m]['Heating'] for m in months]
    
    axes[1, 0].plot(months, heat_m_a, marker='o', linewidth=2.5, label='No Shading', color=color_a)
    axes[1, 0].plot(months, heat_m_b, marker='s', linewidth=2.5, label='Old Periodic 30°', color=color_b)
    axes[1, 0].set_xlabel('Month', fontsize=11, fontweight='bold')
    axes[1, 0].set_ylabel('Heating Load (kWh)', fontsize=11, fontweight='bold')
    axes[1, 0].set_title('Monthly Heating Load Profile', fontsize=13, fontweight='bold', pad=10)
    axes[1, 0].set_xticks(months)
    axes[1, 0].set_xticklabels(month_labels, fontsize=9)
    axes[1, 0].legend(framealpha=0)
    axes[1, 0].grid(True, linestyle='--', alpha=0.5)
    
    # 4. Monthly Cooling Load
    cool_m_a = [res_noshading['monthly'][m]['Cooling'] for m in months]
    cool_m_b = [res_periodic30['monthly'][m]['Cooling'] for m in months]
    
    axes[1, 1].plot(months, cool_m_a, marker='o', linewidth=2.5, label='No Shading', color=color_a)
    axes[1, 1].plot(months, cool_m_b, marker='s', linewidth=2.5, label='Old Periodic 30°', color=color_b)
    axes[1, 1].set_xlabel('Month', fontsize=11, fontweight='bold')
    axes[1, 1].set_ylabel('Cooling Load (kWh)', fontsize=11, fontweight='bold')
    axes[1, 1].set_title('Monthly Cooling Load Profile', fontsize=13, fontweight='bold', pad=10)
    axes[1, 1].set_xticks(months)
    axes[1, 1].set_xticklabels(month_labels, fontsize=9)
    axes[1, 1].legend(framealpha=0)
    axes[1, 1].grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(plot_png_path, dpi=300, transparent=True)
    plt.savefig(plot_svg_path, format='svg', transparent=True)
    plt.close()
    
    print(f"\nSaved plots to:\n  - {plot_png_path}\n  - {plot_svg_path}")

if __name__ == "__main__":
    main()

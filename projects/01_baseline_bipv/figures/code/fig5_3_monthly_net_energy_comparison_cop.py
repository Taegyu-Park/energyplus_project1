import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

plt.rcParams['svg.fonttype'] = 'none'

COP_HEATING = 2.5
COP_COOLING = 3.0

def extract_monthly_data(sql_path):
    if not os.path.exists(sql_path):
        return None
    conn = sqlite3.connect(sql_path)
    
    query_dict = """
    SELECT ReportDataDictionaryIndex, Name, KeyValue 
    FROM ReportDataDictionary
    WHERE (Name = 'Zone Ideal Loads Supply Air Total Heating Energy' AND KeyValue LIKE 'BIPV_OFFICE_%')
       OR (Name = 'Zone Ideal Loads Supply Air Total Cooling Energy' AND KeyValue LIKE 'BIPV_OFFICE_%')
       OR (Name = 'Facility Total Produced Electricity Energy' AND KeyValue = 'Whole Building');
    """
    df_dict = pd.read_sql_query(query_dict, conn)
    
    if df_dict.empty:
        conn.close()
        return None
        
    def get_label(row):
        name = row['Name']
        key = row['KeyValue']
        if 'Heating' in name:
            zone = 'Office_1' if 'OFFICE_1' in key else 'Office_2'
            return f'Heating_{zone}'
        elif 'Cooling' in name:
            zone = 'Office_1' if 'OFFICE_1' in key else 'Office_2'
            return f'Cooling_{zone}'
        elif 'Produced' in name:
            return 'PV_Generation'
        return 'Unknown'
    
    df_dict['Label'] = df_dict.apply(get_label, axis=1)
    idx_to_label = dict(zip(df_dict['ReportDataDictionaryIndex'], df_dict['Label']))
    
    query_data = """
    SELECT rd.TimeIndex, rd.ReportDataDictionaryIndex, rd.Value, t.Month
    FROM ReportData rd
    JOIN Time t ON rd.TimeIndex = t.TimeIndex
    WHERE rd.ReportDataDictionaryIndex IN ({})
      AND t.WarmupFlag = 0;
    """.format(','.join(map(str, idx_to_label.keys())))
    
    df_data = pd.read_sql_query(query_data, conn)
    df_data['Label'] = df_data['ReportDataDictionaryIndex'].map(idx_to_label)
    
    monthly = df_data.groupby(['Month', 'Label'])['Value'].sum().unstack(fill_value=0)
    for col in monthly.columns:
        monthly[col] = monthly[col] / 3.6e9  # Joules to MWh
        
    monthly['Heating_Total'] = monthly.get('Heating_Office_1', 0) + monthly.get('Heating_Office_2', 0)
    monthly['Cooling_Total'] = monthly.get('Cooling_Office_1', 0) + monthly.get('Cooling_Office_2', 0)
    
    conn.close()
    return monthly

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # ------------------
    # Data for Case 2 (Angles 0-90)
    # ------------------
    case2_dir = os.path.join(project_root, "case_analysis", "normal", "case2")
    angles = list(range(0, 100, 10))
    angle_results = {}
    
    for angle in angles:
        # Use folder "0" for angle 0 to avoid the empty 0_v2 database
        folder = "0" if (angle == 0) else f"{angle}"
        db_path = os.path.join(case2_dir, folder, "eplusout.sql")
        res = extract_monthly_data(db_path)
        if res is not None:
            angle_results[angle] = res
            
    if not angle_results:
        print("Error: No databases found for Case 2!")
        return

    # Load Case 3
    db_path_c3 = os.path.join(project_root, "case_analysis", "normal", "case3", "eplusout.sql")
    df_case3 = extract_monthly_data(db_path_c3)
    if df_case3 is None:
        print("Error: Case 3 database not found!")
        return

    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # We will find the optimal angle for Case 2 in each month that minimizes net electricity consumption
    best_angles = []
    case2_net = []
    
    for m in range(1, 13):
        best_angle = None
        min_net = float('inf')
        
        for angle in angles:
            if angle in angle_results:
                h = angle_results[angle].loc[m, 'Heating_Total']
                c = angle_results[angle].loc[m, 'Cooling_Total']
                pv = angle_results[angle].loc[m, 'PV_Generation']
                
                # Net Electricity = (Heating/COP_heating) + (Cooling/COP_cooling) - PV
                net_val = (h / COP_HEATING) + (c / COP_COOLING) - pv
                if net_val < min_net:
                    min_net = net_val
                    best_angle = angle
                    
        best_angles.append(best_angle)
        case2_net.append(min_net)

    # Case 3 values
    case3_net = []
    
    for m in range(1, 13):
        h = df_case3.loc[m, 'Heating_Total']
        c = df_case3.loc[m, 'Cooling_Total']
        pv = df_case3.loc[m, 'PV_Generation']
        
        net_val = (h / COP_HEATING) + (c / COP_COOLING) - pv
        case3_net.append(net_val)

    # Convert to numpy arrays for calculation
    case2_net = np.array(case2_net)
    case3_net = np.array(case3_net)

    # ------------------
    # Plotting using dartwork-mpl
    # ------------------
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    fig, ax = plt.subplots(figsize=(26 / 2.54, 14 / 2.54))
    
    x = np.arange(len(months_labels)) * 1.5
    
    # 1. Net Electricity Line Plots (Centered at x for identical coordinates)
    # Case 2 Net as blue line with diamonds
    ax.plot(x, case2_net, color='oc.blue6', marker='D', markersize=7, linewidth=2.0, zorder=5, label='Case 2 (Opt BIPV)')
    # Case 3 Net as orange line with circles
    ax.plot(x, case3_net, color='oc.orange7', marker='o', markersize=8, linewidth=2.0, zorder=5, label='Case 3 (Kinetic BIPV)')

    # Formatting
    ax.axhline(0, color='black', linewidth=0.8, zorder=4)
    ax.set_ylabel("Net Electricity Consumption [MWh]")
    ax.set_xlabel("Month")
    ax.set_title("Monthly Net Electricity Consumption Comparison\n(HVAC Electricity − BIPV PV Generation, COP_heat=2.5, COP_cool=3.0)", fontsize=16, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(months_labels)
    ax.set_ylim(-5.0, 12.0)
    
    # Legend
    ax.legend(loc='upper right', fontsize=10, ncol=2)
    
    # Add Info Box for annual totals
    c2_annual_net = case2_net.sum()
    c3_annual_net = case3_net.sum()
    info_text = (
        f"Annual Net Electricity:\n"
        f"• Case 2 (Opt): {c2_annual_net:.2f} MWh\n"
        f"• Case 3 (Kinetic): {c3_annual_net:.2f} MWh\n"
        f"• Savings: {c2_annual_net - c3_annual_net:.2f} MWh"
    )
    ax.text(
        0.03, 
        0.75, 
        info_text, 
        transform=ax.transAxes, 
        fontsize=10.5, 
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
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    
    print(f"\nSuccessfully generated combined monthly net electricity consumption plot:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

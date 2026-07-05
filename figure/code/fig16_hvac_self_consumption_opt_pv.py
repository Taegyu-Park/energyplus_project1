"""
Figure 16: Monthly HVAC Self-Consumption Rate (SCR) and Self-Sufficiency Rate (SSR) Comparison
Comparing Case 2 (Optimized for PV Generation per month) and Case 3 (Kinetic BIPV)
"""

import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import dartwork_mpl as dm

plt.rcParams['svg.fonttype'] = 'none'

# Constants
COP_HEATING = 2.5
COP_COOLING = 3.0
J_TO_KWH = 1.0 / 3.6e6

def get_monthly_details(db_path):
    """
    Connects to the EnergyPlus output database, retrieves 10-minute timestep data
    for HVAC heating/cooling energy and facility total produced electricity,
    converts them to electricity energy in kWh, and computes monthly sums
    as well as timestep self-consumption.
    """
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT t.Month, r.TimeIndex, rd.Name, r.Value
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
    """
    
    df_raw = pd.read_sql_query(query, conn)
    conn.close()
    
    # Pivot to align variables at the same timestep
    df = df_raw.pivot_table(index=['Month', 'TimeIndex'], columns='Name', values='Value', aggfunc='sum').fillna(0.0)
    df.columns = df.columns.str.strip()
    
    # Ensure all columns are present
    for col in ['Zone Ideal Loads Supply Air Total Heating Energy', 
                'Zone Ideal Loads Supply Air Total Cooling Energy', 
                'Facility Total Produced Electricity Energy']:
        if col not in df.columns:
            df[col] = 0.0
            
    # Unit conversion: Joules to kWh (and apply COP to thermal loads)
    df['PV_kWh'] = df['Facility Total Produced Electricity Energy'] * J_TO_KWH
    df['Heating_Elec_kWh'] = (df['Zone Ideal Loads Supply Air Total Heating Energy'] * J_TO_KWH) / COP_HEATING
    df['Cooling_Elec_kWh'] = (df['Zone Ideal Loads Supply Air Total Cooling Energy'] * J_TO_KWH) / COP_COOLING
    df['HVAC_Elec_kWh'] = df['Heating_Elec_kWh'] + df['Cooling_Elec_kWh']
    
    # Calculate self-consumed PV electricity at each timestep
    df['Self_Consumed_kWh'] = np.minimum(df['PV_kWh'], df['HVAC_Elec_kWh'])
    
    # Group by Month to aggregate
    monthly = df.groupby('Month').agg({
        'PV_kWh': 'sum',
        'HVAC_Elec_kWh': 'sum',
        'Self_Consumed_kWh': 'sum'
    })
    
    # Calculate monthly SCR and SSR in %
    monthly['SCR_%'] = (monthly['Self_Consumed_kWh'] / monthly['PV_kWh'].replace(0, np.nan)) * 100.0
    monthly['SSR_%'] = (monthly['Self_Consumed_kWh'] / monthly['HVAC_Elec_kWh'].replace(0, np.nan)) * 100.0
    monthly['Net_Energy_kWh'] = monthly['HVAC_Elec_kWh'] - monthly['PV_kWh']
    
    return monthly.fillna(0.0)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    
    # 1. Load Case 3 Monthly Data
    case3_db = os.path.join(project_root, "case_analysis", "normal", "case3", "eplusout.sql")
    print("Loading Case 3 data...")
    c3_monthly = get_monthly_details(case3_db)
    
    # 2. Load Case 2 Data for all angles (0, 10, ..., 90)
    angles = list(range(0, 100, 10))
    c2_monthly_by_angle = {}
    for angle in angles:
        print(f"Loading Case 2 - {angle}° data...")
        db_path = os.path.join(project_root, "case_analysis", "normal", "case2", f"{angle}", "eplusout.sql")
        res = get_monthly_details(db_path)
        if res is not None:
            c2_monthly_by_angle[angle] = res
            
    # 3. Find the Case 2 angle that maximizes PV generation for each month
    best_angles = []
    c2_opt_pv = pd.DataFrame(index=range(1, 13), columns=['Angle', 'PV_kWh', 'HVAC_Elec_kWh', 'Self_Consumed_kWh', 'SCR_%', 'SSR_%'])
    
    for m in range(1, 13):
        best_angle = None
        max_pv = -1.0
        for angle in angles:
            if angle in c2_monthly_by_angle:
                pv = c2_monthly_by_angle[angle].loc[m, 'PV_kWh']
                if pv > max_pv:
                    max_pv = pv
                    best_angle = angle
        best_angles.append(best_angle)
        
        # Save the row corresponding to the best angle for month m
        row = c2_monthly_by_angle[best_angle].loc[m]
        c2_opt_pv.loc[m] = [best_angle, row['PV_kWh'], row['HVAC_Elec_kWh'], row['Self_Consumed_kWh'], row['SCR_%'], row['SSR_%']]
        
    print("\nCase 2 Optimal (Max PV Gen) Angles and Monthly Results:")
    print(c2_opt_pv.to_string())
    
    print("\nCase 3 Monthly Results:")
    print(c3_monthly.to_string())
    # 4. Plotting using dartwork-mpl
    dm.style.use("presentation")
    plt.rcParams.update({
        "xtick.labelsize": 12, 
        "ytick.labelsize": 12,
        "svg.fonttype": "none"  # Keep text as text objects in SVG for Figma/Illustrator editability
    })
    
    # Create a single plot with dual-axis
    fig, ax_bar = plt.subplots(figsize=(24 / 2.54, 14 / 2.54))
    ax_line = ax_bar.twinx()
    
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    x = np.arange(len(months_labels)) * 1.5
    width = 0.38  # width of each bar
    
    # Color definitions (using open colors matching fig5)
    color_c2_bar  = 'oc.blue6'    # Cool Blue for Case 2 Bar
    color_c2_line = 'oc.blue3'    # Light Blue for Case 2 Line
    color_c3_bar  = 'oc.orange7'  # Warm Orange for Case 3 Bar
    color_c3_line = 'oc.orange4'  # Light Orange for Case 3 Line
    
    # Text colors for line labels (always dark for readability)
    color_c2_txt  = 'oc.blue8'
    color_c3_txt  = 'oc.orange9'
    
    # 1. Bar Chart (Left Y-axis) - Actual BIPV-to-HVAC Direct Supply in MWh
    b_c2 = ax_bar.bar(x - width/2, c2_opt_pv['Self_Consumed_kWh'] / 1000.0, width=width, color=color_c2_bar, alpha=0.9, label='Case 2 (Opt BIPV) Direct Supply')
    b_c3 = ax_bar.bar(x + width/2, c3_monthly['Self_Consumed_kWh'] / 1000.0, width=width, color=color_c3_bar, alpha=0.9, label='Case 3 (Kinetic BIPV) Direct Supply')
    
    # 2. Line Chart (Right Y-axis) - Self-Consumption Rate (SCR) in %
    l_c2, = ax_line.plot(x, c2_opt_pv['SCR_%'], color=color_c2_line, linewidth=2.5, marker='o', markersize=6, label='Case 2 (Opt BIPV) SCR')
    l_c3, = ax_line.plot(x, c3_monthly['SCR_%'], color=color_c3_line, linewidth=2.5, marker='s', markersize=6, label='Case 3 (Kinetic BIPV) SCR')
    
    # Titles and labels
    ax_bar.set_ylabel("Monthly BIPV-to-HVAC Direct Supply [MWh]", fontweight='bold', fontsize=12)
    ax_line.set_ylabel("Self-Consumption Rate (SCR) [%]", fontweight='bold', fontsize=12)
    ax_bar.set_xlabel("Month", fontweight='bold', fontsize=12)
    ax_bar.set_title("Monthly BIPV-to-HVAC Direct Supply & Self-Consumption Rate (SCR)", fontsize=15, fontweight='bold', pad=25)
    
    # Ranges
    ax_bar.set_ylim(0, 3.0)
    ax_line.set_ylim(0, 110)
    
    # # Annotate Case 2 optimal angles inside or above Case 2 bar
    # for bar, val, angle in zip(b_c2, c2_opt_pv['Self_Consumed_kWh'] / 1000.0, best_angles):
    #     y_pos = 0.02 if val < 0.30 else 0.08
    #     color_text = 'oc.blue8' if val < 0.30 else '#ffffff'
    #     ax_bar.text(
    #         bar.get_x() + bar.get_width() / 2.0, 
    #         y_pos, 
    #         f"{angle}°", 
    #         ha='center', 
    #         va='bottom', 
    #         fontsize=8.5, 
    #         fontweight='bold',
    #         color=color_text
    #     )
        
    # Annotate SCR line values (prevent overlap using smart positioning)
    for tx, val2, val3 in zip(x, c2_opt_pv['SCR_%'], c3_monthly['SCR_%']):
        if abs(val2 - val3) < 8.0:
            if val2 > val3:
                va2, off2 = 'bottom', 2.0
                va3, off3 = 'top', -4.5
            else:
                va2, off2 = 'top', -4.5
                va3, off3 = 'bottom', 2.0
        else:
            va2, off2 = 'bottom', 2.0
            va3, off3 = 'bottom', 2.0
            
        ax_line.text(tx, val2 + off2, f"{val2:.1f}%", ha='center', va=va2, fontsize=9.0, color=color_c2_txt, fontweight='bold')
        ax_line.text(tx, val3 + off3, f"{val3:.1f}%", ha='center', va=va3, fontsize=9.0, color=color_c3_txt, fontweight='bold')
        
    # Split Legends (Left and Right)
    ax_bar.legend(handles=[b_c2, b_c3], labels=['Case 2 Direct Supply', 'Case 3 Direct Supply'], 
                  loc="upper left", framealpha=0.9, fontsize=9.5)
    ax_line.legend(handles=[l_c2, l_c3], labels=['Case 2 SCR', 'Case 3 SCR'], 
                   loc="upper right", framealpha=0.9, fontsize=9.5)
    
    # Configure X-axis
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(months_labels)
    
    for label in ax_bar.get_xticklabels():
        label.set_fontweight('normal')
        
    # Grids
    ax_bar.grid(True, axis='y', linewidth=0.3, color='#e2e8f0')
    
    # Output file paths
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", "fig16_hvac_self_consumption_opt_pv"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "hvac_self_consumption_comparison_opt_pv.png")
    output_svg = os.path.join(figure_dir, "hvac_self_consumption_comparison_opt_pv.svg")
    
    # Save figure
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    plt.close(fig)
    
    print(f"\nSuccessfully generated SCR & Direct Supply comparison plot (Max PV Angle, Single Axis):")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

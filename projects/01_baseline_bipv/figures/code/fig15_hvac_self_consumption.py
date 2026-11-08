"""
Figure 15: Monthly HVAC Self-Consumption Rate (SCR) and Self-Sufficiency Rate (SSR) Comparison
Comparing Case 2 (Optimized for SCR per month) and Case 3 (Kinetic BIPV)
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
            
    # 3. Find the Case 2 angle that maximizes SCR for each month
    best_angles = []
    c2_opt_scr = pd.DataFrame(index=range(1, 13), columns=['Angle', 'PV_kWh', 'HVAC_Elec_kWh', 'Self_Consumed_kWh', 'SCR_%', 'SSR_%'])
    
    for m in range(1, 13):
        best_angle = None
        max_scr = -1.0
        for angle in angles:
            if angle in c2_monthly_by_angle:
                scr = c2_monthly_by_angle[angle].loc[m, 'SCR_%']
                if scr > max_scr:
                    max_scr = scr
                    best_angle = angle
        best_angles.append(best_angle)
        
        # Save the row corresponding to the best angle for month m
        row = c2_monthly_by_angle[best_angle].loc[m]
        c2_opt_scr.loc[m] = [best_angle, row['PV_kWh'], row['HVAC_Elec_kWh'], row['Self_Consumed_kWh'], row['SCR_%'], row['SSR_%']]
        
    print("\nCase 2 Optimal (Max SCR) Angles and Monthly Results:")
    print(c2_opt_scr.to_string())
    
    print("\nCase 3 Monthly Results:")
    print(c3_monthly.to_string())
    
    # 4. Plotting using dartwork-mpl
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    
    # Create two subplots: Top for SCR, Bottom for SSR
    fig, (ax_scr, ax_ssr) = plt.subplots(2, 1, figsize=(26 / 2.54, 22 / 2.54), sharex=True)
    
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    x = np.arange(len(months_labels)) * 1.5
    width = 0.55  # width of each bar
    
    color_c2 = 'oc.blue6'      # Cool blue for Case 2 (Optimized)
    color_c3 = 'oc.orange7'    # Warm orange for Case 3 (Kinetic BIPV)
    
    # ------------------
    # Top Plot: HVAC Self-Consumption Rate (SCR)
    # ------------------
    bars_scr_c2 = ax_scr.bar(x - width/2, c2_opt_scr['SCR_%'], width=width, color=color_c2, alpha=0.9, label='Case 2 (Opt BIPV)')
    bars_scr_c3 = ax_scr.bar(x + width/2, c3_monthly['SCR_%'], width=width, color=color_c3, alpha=0.9, label='Case 3 (Kinetic BIPV)')
    
    ax_scr.set_ylabel("HVAC Self-Consumption Rate (SCR) [%]", fontweight='bold', fontsize=12)
    ax_scr.set_title("Monthly HVAC Self-Consumption Rate (SCR) Comparison", fontsize=15, fontweight='bold')
    ax_scr.set_ylim(0, 115)
    ax_scr.grid(True, axis='y', linewidth=0.3, color='#e2e8f0')
    ax_scr.legend(loc="upper right", framealpha=0.9)
    
    # Annotate SCR values and Case 2 optimal angles
    for bar, val, angle in zip(bars_scr_c2, c2_opt_scr['SCR_%'], best_angles):
        # Value on top of bar
        ax_scr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            val + 1.5, 
            f"{val:.1f}%", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#1e293b'
        )
        # Optimal angle inside the bar (near the bottom)
        y_pos = 1.0 if val < 10 else 4.0
        ax_scr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            y_pos, 
            f"{angle}°", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#ffffff'
        )
        
    for bar, val in zip(bars_scr_c3, c3_monthly['SCR_%']):
        ax_scr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            val + 1.5, 
            f"{val:.1f}%", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # ------------------
    # Bottom Plot: HVAC Self-Sufficiency Rate (SSR)
    # ------------------
    bars_ssr_c2 = ax_ssr.bar(x - width/2, c2_opt_scr['SSR_%'], width=width, color=color_c2, alpha=0.9, label='Case 2 (Opt BIPV)')
    bars_ssr_c3 = ax_ssr.bar(x + width/2, c3_monthly['SSR_%'], width=width, color=color_c3, alpha=0.9, label='Case 3 (Kinetic BIPV)')
    
    ax_ssr.set_ylabel("HVAC Self-Sufficiency Rate (SSR) [%]", fontweight='bold', fontsize=12)
    ax_ssr.set_title("Monthly HVAC Self-Sufficiency Rate (SSR) Comparison", fontsize=15, fontweight='bold')
    ax_ssr.set_xlabel("Month", fontweight='bold', fontsize=12)
    ax_ssr.set_ylim(0, 115)
    ax_ssr.grid(True, axis='y', linewidth=0.3, color='#e2e8f0')
    ax_ssr.legend(loc="upper right", framealpha=0.9)
    
    # Annotate SSR values and Case 2 optimal angles
    for bar, val, angle in zip(bars_ssr_c2, c2_opt_scr['SSR_%'], best_angles):
        # Value on top of bar
        ax_ssr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            val + 1.5, 
            f"{val:.1f}%", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#1e293b'
        )
        # Optimal angle inside the bar (near the bottom)
        y_pos = 1.0 if val < 10 else 4.0
        ax_ssr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            y_pos, 
            f"{angle}°", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#ffffff'
        )
        
    for bar, val in zip(bars_ssr_c3, c3_monthly['SSR_%']):
        ax_ssr.text(
            bar.get_x() + bar.get_width() / 2.0, 
            val + 1.5, 
            f"{val:.1f}%", 
            ha='center', 
            va='bottom', 
            fontsize=9.5, 
            fontweight='bold',
            color='#1e293b'
        )
        
    # Configure X-axis
    ax_ssr.set_xticks(x)
    ax_ssr.set_xticklabels(months_labels)
    
    # Align labels font weight
    for label in ax_scr.get_xticklabels():
        label.set_fontweight('light')
    for label in ax_ssr.get_xticklabels():
        label.set_fontweight('light')
        
    # Output file paths
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", "fig15_hvac_self_consumption"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "hvac_self_consumption_comparison.png")
    output_svg = os.path.join(figure_dir, "hvac_self_consumption_comparison.svg")
    
    # Save figure
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    plt.close(fig)
    
    print(f"\nSuccessfully generated self-consumption comparison plots:")
    print(f"  PNG: {output_png}")
    print(f"  SVG: {output_svg}")

if __name__ == "__main__":
    main()

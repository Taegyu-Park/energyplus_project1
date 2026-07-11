"""
Figure 18: Timestep-level PV Generation Efficiency Analysis for Case 3 (Kinetic BIPV)
====================================================================================
This script calculates the PV generation efficiency at each 10-minute timestep 
for Case 3 (Kinetic BIPV). It plots:
1) An annual heatmap of PV efficiency by hour of day and day of year.
2) Representative Summer (Aug 1) and Winter (Jan 29) daily profiles showing 
   the relationship between PV efficiency and cell temperature.
"""

import os
import sqlite3
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import dartwork_mpl as dm

# Save SVGs as vector paths for Illustrator/Figma editability
plt.rcParams['svg.fonttype'] = 'none'

# Constants
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
PV_ACTIVE_AREA = 2.186184  # m2 per panel
NUM_PANELS = 96
TOTAL_PV_AREA = PV_ACTIVE_AREA * NUM_PANELS  # 209.87366 m2
NOCT_AMB = 20.0
NOCT_CELL = 45.0
NOCT_RAD = 800.0
NOCT_COEFF = (NOCT_CELL - NOCT_AMB) / NOCT_RAD  # 25 / 800 = 0.03125

def get_best_angle(sun_alt):
    if sun_alt <= 0:
        return 0
    return min(ANGLES, key=lambda x: abs(x - sun_alt))

def get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg):
    tilt_rad = math.radians(tilt_deg)
    alt_rad = math.radians(sun_alt)
    azi_rad = math.radians(sun_azi)

    cos_theta = (math.sin(alt_rad) * math.cos(tilt_rad) +
                 math.cos(alt_rad) * math.sin(tilt_rad) * math.cos(azi_rad - math.pi))
    cos_theta = max(0.0, cos_theta)
    
    # Incident direct solar
    i_beam = dn_rad * cos_theta
    
    # Diffuse solar on tilted surface (isotropic sky model)
    i_diff = df_rad * (1.0 + math.cos(tilt_rad)) / 2.0
    
    # Ground-reflected solar on tilted surface (albedo = 0.2)
    total_horiz = dn_rad * math.sin(alt_rad) + df_rad
    i_ground = total_horiz * 0.2 * (1.0 - math.cos(tilt_rad)) / 2.0

    return i_beam + i_diff + i_ground

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    db_path = os.path.join(project_root, "case_analysis", "normal", "case3", "eplusout.sql")
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    plot_png_path = os.path.join(figure_dir, "pv_efficiency_analysis.png")
    plot_svg_path = os.path.join(figure_dir, "pv_efficiency_analysis.svg")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        return

    print("Connecting to database and loading variables...")
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT t.Month, t.Day, t.Hour, t.Minute, t.TimeIndex, rd.Name, r.Value
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Site Direct Solar Radiation Rate per Area',
            'Site Diffuse Solar Radiation Rate per Area',
            'Site Solar Altitude Angle',
            'Site Solar Azimuth Angle',
            'Site Outdoor Air Drybulb Temperature',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
    """
    
    df_raw = pd.read_sql_query(query, conn)
    conn.close()
    
    print("Pivoting data table...")
    df = df_raw.pivot_table(index=['Month', 'Day', 'Hour', 'Minute', 'TimeIndex'], 
                            columns='Name', 
                            values='Value').reset_index()
    df.columns = [c.strip() for c in df.columns]

    print("Calculating incident radiation, cell temperature, and efficiency...")
    eff_list = []
    inc_solar_list = []
    best_angle_list = []
    t_cell_list = []

    for idx, row in df.iterrows():
        sun_alt = row.get('Site Solar Altitude Angle', 0.0)
        sun_azi = row.get('Site Solar Azimuth Angle', 0.0)
        dn_rad = row.get('Site Direct Solar Radiation Rate per Area', 0.0)
        df_rad = row.get('Site Diffuse Solar Radiation Rate per Area', 0.0)
        out_temp = row.get('Site Outdoor Air Drybulb Temperature', 0.0)
        pv_gen_joules = row.get('Facility Total Produced Electricity Energy', 0.0)
        
        best_angle = get_best_angle(sun_alt)
        best_angle_list.append(best_angle)
        
        if sun_alt <= 0:
            inc_solar = 0.0
            t_cell = out_temp
            eff = np.nan
        else:
            tilt_deg = 90.0 - best_angle
            inc_solar = get_incident_solar_val(sun_alt, sun_azi, dn_rad, df_rad, tilt_deg)
            t_cell = out_temp + inc_solar * NOCT_COEFF
            
            # PV power in Watts (Joules / 600s)
            pv_power_w = pv_gen_joules / 600.0
            total_inc_rad_w = inc_solar * TOTAL_PV_AREA
            
            # We calculate efficiency only when solar radiation is significant and power is generated
            if total_inc_rad_w > 10.0 and pv_power_w > 1.0:
                eff = pv_power_w / total_inc_rad_w
                # Clamp efficiency to realistic physical bounds (e.g., 0% to 25%)
                if eff > 0.25:
                    eff = np.nan
            else:
                eff = np.nan
                
        inc_solar_list.append(inc_solar)
        t_cell_list.append(t_cell)
        eff_list.append(eff)

    df['Best_Angle'] = best_angle_list
    df['Incident_Solar_Rate'] = inc_solar_list
    df['Cell_Temperature'] = t_cell_list
    df['PV_Efficiency'] = eff_list

    # Map datetime index for timeseries operations (assuming year 2026 to match fig13)
    df.index = pd.date_range(start='2026-01-01 00:10:00', periods=len(df), freq='10min') - pd.Timedelta(minutes=10)

    # ------------------
    # Plotting using dartwork-mpl
    # ------------------
    dm.style.use("presentation")
    plt.rcParams.update({
        "xtick.labelsize": 11, 
        "ytick.labelsize": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13
    })
    
    fig, (ax_eff, ax_solar) = plt.subplots(2, 1, figsize=(26 / 2.54, 16 / 2.54), 
                                           sharex=True, gridspec_kw={"hspace": 0.28})

    color_eff = '#e8590c'      # Orange for efficiency
    color_solar = '#1c7ed6'    # Blue for solar irradiance

    # 1. Plot Efficiency Line Plot
    # We plot the 10-minute timestep values. matplolib automatically leaves gaps where y is NaN (nighttime).
    ax_eff.plot(df.index, df['PV_Efficiency'] * 100.0, color=color_eff, linewidth=0.35, alpha=0.8)
    
    ax_eff.set_title("Annual BIPV PV Generation Efficiency [%] (Timestep Level)", fontweight='bold', pad=10)
    ax_eff.set_ylabel("PV Efficiency [%]", fontweight='bold')
    ax_eff.set_ylim(6.0, 16.0)
    ax_eff.grid(True, linestyle="--", alpha=0.4)

    # 2. Plot Solar Radiation Line Plot
    ax_solar.plot(df.index, df['Incident_Solar_Rate'], color=color_solar, linewidth=0.35, alpha=0.8)
    
    ax_solar.set_title("Annual BIPV Incident Solar Radiation [W/m²] (Timestep Level)", fontweight='bold', pad=10)
    ax_solar.set_xlabel("Month", fontweight='bold')
    ax_solar.set_ylabel("Incident Solar Irradiance [W/m²]", fontweight='bold')
    ax_solar.set_ylim(0.0, 1100.0)
    ax_solar.grid(True, linestyle="--", alpha=0.4)
    
    # Format X-axis with monthly ticks
    ax_solar.xaxis.set_major_locator(mdates.MonthLocator())
    ax_solar.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

    plt.suptitle("Case 3 (Kinetic BIPV) Timestep Efficiency and Incident Solar Radiation Analysis", 
                 fontsize=15, fontweight='bold', y=0.98)
    
    # Save plots
    plt.savefig(plot_png_path, dpi=300, bbox_inches='tight', transparent=True)
    plt.savefig(plot_svg_path, format='svg', bbox_inches='tight', transparent=True)
    print(f"Figures successfully saved at:\n- {plot_png_path}\n- {plot_svg_path}")

if __name__ == '__main__':
    main()

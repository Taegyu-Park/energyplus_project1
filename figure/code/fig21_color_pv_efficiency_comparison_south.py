"""
Figure 21: BIPV PV Efficiency Comparison by Panel Color (Case 3: Kinetic)
========================================================================
This script calculates the PV generation efficiency at each 10-minute timestep 
for three color variations of Case 3 (Kinetic BIPV):
- Case 3 — White (10.51% operational efficiency)
- Case 3 — Light Gray Beige (14.40% operational efficiency)
- Case 3 — Terracotta (15.85% operational efficiency)

It plots:
1) 1-year time series of daily PV efficiency (with 14-day moving average).
"""

import os
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

def load_and_calculate_efficiency(file_path):
    print(f"Reading and analyzing {os.path.basename(file_path)}...")
    df = pd.read_csv(file_path)
    
    # Parse Date/Time to extract month and day
    df['Month'] = df['Date/Time'].apply(lambda x: int(x.strip().split('/')[0]))
    df['Day'] = df['Date/Time'].apply(lambda x: int(x.strip().split('/')[1].split()[0]))
    
    # Map datetime index (assuming year 2026 to match other figures)
    df.index = pd.date_range(start='2026-01-01 00:10:00', periods=len(df), freq='10min') - pd.Timedelta(minutes=10)
    
    sun_alt = df['Environment:Site Solar Altitude Angle [deg](TimeStep)'].values
    sun_azi = df['Environment:Site Solar Azimuth Angle [deg](TimeStep)'].values
    dn_rad = df['Environment:Site Direct Solar Radiation Rate per Area [W/m2](TimeStep)'].values
    df_rad = df['Environment:Site Diffuse Solar Radiation Rate per Area [W/m2](TimeStep)'].values
    pv_gen_j = df['Whole Building:Facility Total Produced Electricity Energy [J](TimeStep)'].values
    
    inc_solar_rate = []
    for i in range(len(df)):
        alt = sun_alt[i]
        if alt <= 0:
            inc_solar_rate.append(0.0)
        else:
            best_angle = get_best_angle(alt)
            tilt_deg = 90.0 - best_angle
            inc_solar_rate.append(get_incident_solar_val(alt, sun_azi[i], dn_rad[i], df_rad[i], tilt_deg))
            
    df['Incident_Solar_Rate'] = inc_solar_rate
    df['Incident_Solar_Energy_J'] = df['Incident_Solar_Rate'] * TOTAL_PV_AREA * 600.0
    
    # Timestep-level efficiency (threshold check matching fig18)
    eff_list = []
    for i in range(len(df)):
        inc_e = df['Incident_Solar_Energy_J'].values[i]
        pv_j = pv_gen_j[i]
        if inc_e > 10.0 * 600.0 and pv_j > 1.0:
            eff = pv_j / inc_e
            if eff <= 0.25:
                eff_list.append(eff)
            else:
                eff_list.append(np.nan)
        else:
            eff_list.append(np.nan)
            
    df['PV_Efficiency'] = eff_list
    
    # Daily average efficiency for time series
    daily_eff = df['PV_Efficiency'].resample('D').mean() * 100.0
    
    return daily_eff

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    data_dir = os.path.join(project_root, "case_analysis", "bipv_variation")
    
    # Figure directory (named matching script filename)
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(project_root, "figure", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    # Artifact directory for embedding in the response
    artifact_dir = r"C:\Users\taegyu\\.gemini\antigravity-ide\brain\6a656d91-dc30-4c35-bfce-a2c524e5b824"
    
    # Load cases
    cases = {
        "White": {
            "file": os.path.join(data_dir, "case3_white_south.csv"),
            "line_color": "#475569",     # Slate grey
            "efficiency": "10.51%"
        },
        "Light Gray Beige": {
            "file": os.path.join(data_dir, "case3_light_gray_beige_south.csv"),
            "line_color": "#78350f",     # Warm brown
            "efficiency": "14.71%"
        },
        "Terracotta": {
            "file": os.path.join(data_dir, "case3_terracotta_south.csv"),
            "line_color": "#b91c1c",     # Strong red
            "efficiency": "16.39%"
        }
    }
    
    daily_data = {}
    
    for name, info in cases.items():
        daily_eff = load_and_calculate_efficiency(info["file"])
        daily_data[name] = daily_eff
        
    # Plotting using dartwork-mpl style
    dm.style.use("presentation")
    plt.rcParams.update({
        "xtick.labelsize": 11, 
        "ytick.labelsize": 11,
        "axes.labelsize": 12,
        "legend.fontsize": 10.5
    })
    
    fig, ax = plt.subplots(figsize=(11, 5.5))
    
    # ── Annual Time Series (Daily + 14-day rolling) ───────────────────
    for name, info in cases.items():
        daily = daily_data[name]
        rolling = daily.rolling(window=14, center=True, min_periods=1).mean()
        
        # Plot daily faint line
        ax.plot(daily.index, daily, color=info["line_color"], alpha=0.18, linewidth=0.5)
        # Plot rolling mean thick line
        ax.plot(rolling.index, rolling, color=info["line_color"], alpha=0.95, linewidth=1.8, label=f"{name} ({info['efficiency']})")
        
    ax.set_xlabel("Date", fontweight="bold", labelpad=8)
    ax.set_ylabel("PV Efficiency [%]", fontweight="bold", labelpad=8)
    ax.set_title("1-Year Time Series of Daily PV Efficiency by Panel Color (Case 3: Kinetic, South Wall, 14-day Moving Average)", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylim(5.0, 25.0)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    plt.tight_layout()
    
    # Save plots
    png_path = os.path.join(figure_dir, "fig21_color_pv_efficiency_comparison_south.png")
    svg_path = os.path.join(figure_dir, "fig21_color_pv_efficiency_comparison_south.svg")
    plt.savefig(png_path, dpi=300, bbox_inches='tight', transparent=True)
    plt.savefig(svg_path, bbox_inches='tight', transparent=True)
    print(f"Saved figure to {png_path} and {svg_path}")
    
    # Save a copy in the artifact directory
    if os.path.exists(artifact_dir):
        artifact_png = os.path.join(artifact_dir, "fig21_color_pv_efficiency_comparison_south.png")
        plt.savefig(artifact_png, dpi=200, bbox_inches='tight')
        print(f"Saved artifact copy to {artifact_png}")

if __name__ == "__main__":
    main()

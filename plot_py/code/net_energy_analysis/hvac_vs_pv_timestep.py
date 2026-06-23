"""
Timestep HVAC vs PV Coverage Analysis for Extreme Days
- Case 2: Static BIPV at 90° (Fixed)
- Case 3: Kinetic BIPV (Solar tracking)

Generates a 2x2 grid comparing:
- Left Column: Max PV Surplus Day (April 22nd)
- Right Column: Max HVAC Deficit Day (July 28th)
- Top Row: Case 2 (Fixed-90°)
- Bottom Row: Case 3 (Kinetic)
"""

import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import dartwork_mpl as dm

dm.style.use("presentation")
plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

# ── paths ──────────────────────────────────────────────────────────────────────
BASE = Path("C:/Users/taegyu/Codes/EnergyPlus_Project1")
RUN  = BASE / "run_analysis"
OUT  = BASE / "plot_py/figure/net_energy_analysis"

COP_HEATING = 2.5
COP_COOLING = 3.0

# ── data loader ────────────────────────────────────────────────────────────────
def load_timestep_sql(sql_path: Path) -> pd.DataFrame:
    """
    Load 10-minute timestep Heating, Cooling, and PV data from SQLite database.
    """
    print(f"Loading data from {sql_path.name}...")
    conn = sqlite3.connect(sql_path)
    
    query = """
        SELECT t.TimeIndex, t.Month, t.Day, t.Hour, t.Minute, t.SimulationDays, rd.Name, r.Value
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
    
    # Pivot
    df = df_raw.pivot_table(
        index=['TimeIndex', 'Month', 'Day', 'Hour', 'Minute', 'SimulationDays'],
        columns='Name',
        values='Value',
        aggfunc='sum'
    ).reset_index().fillna(0)
    
    # Standardize column names
    col_mapping = {
        'Zone Ideal Loads Supply Air Total Heating Energy': 'heating_J',
        'Zone Ideal Loads Supply Air Total Cooling Energy': 'cooling_J',
        'Facility Total Produced Electricity Energy': 'pv_J'
    }
    df = df.rename(columns=col_mapping)
    
    for col in ['heating_J', 'cooling_J', 'pv_J']:
        if col not in df.columns:
            df[col] = 0.0

    # 10-minute timestep power (kW)
    # Energy (J) to Power (kW): P = E / 6.0e5
    scale_factor = 1 / 6.0e5
    df["heating_kW"] = df["heating_J"] * scale_factor
    df["cooling_kW"] = df["cooling_J"] * scale_factor
    df["hvac_thermal_kW"] = df["heating_kW"] + df["cooling_kW"]
    df["pv_elec_kW"] = df["pv_J"] * scale_factor
    
    # Calculate PV equivalent thermal power
    df["cop"] = np.where(df["heating_kW"] > df["cooling_kW"], COP_HEATING, COP_COOLING)
    df["pv_thermal_kW"] = df["pv_elec_kW"] * df["cop"]
    
    return df

# ── load all data ──────────────────────────────────────────────────────────────
c2_sql = RUN / "model_realscale_case2/model_realscale_90/eplusout.sql"
c3_sql = RUN / "model_realscale_case3/eplusout.sql"

c2 = load_timestep_sql(c2_sql)
c3 = load_timestep_sql(c3_sql)


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTTING: 2x2 Grid for Extreme Days Comparison
# ═══════════════════════════════════════════════════════════════════════════════
print("\nPlotting 2x2 Grid for Extreme Days...")

# ── plotting panel helper ──────────────────────────────────────────────────────
def plot_timestep_panel(ax, df, day_num, title, ylim=95):
    # Filter day
    df_day = df[df["SimulationDays"] == day_num].copy()
    if df_day.empty:
        print(f"Warning: No data for day {day_num}")
        return
        
    x = df_day["Hour"].values + df_day["Minute"].values / 60.0
    hvac = df_day["hvac_thermal_kW"].values
    pv = df_day["pv_thermal_kW"].values
    
    # Plot HVAC Load area
    ax.fill_between(x, 0, hvac, color="oc.gray4", alpha=0.3, label="HVAC Thermal Load")
    
    # Plot PV Equivalent line
    ax.plot(x, pv, color="oc.green7", lw=1.2, label="PV Thermal Equivalent")
    
    # Fill surplus (PV >= HVAC)
    ax.fill_between(x, hvac, pv, where=(pv >= hvac), color="oc.green5", alpha=0.45,
                    interpolate=True, linewidth=0, label="PV Surplus (Export)")
    
    # Fill deficit (PV < HVAC)
    ax.fill_between(x, pv, hvac, where=(pv < hvac), color="oc.red5", alpha=0.25,
                    interpolate=True, linewidth=0, label="HVAC Deficit (Grid)")
    
    # Axis formatting
    ax.set_xlim(0, 24)
    ax.set_ylim(0, ylim)
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
    ax.set_xticklabels(["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"], fontsize=9)
    
    # Calculate daily statistics (integrated over 10-min intervals)
    E_hvac = hvac.sum() / 6.0
    E_pv = pv.sum() / 6.0
    E_surplus = np.maximum(0, pv - hvac).sum() / 6.0
    E_deficit = np.maximum(0, hvac - pv).sum() / 6.0
    
    surplus_pct = (E_surplus / E_pv * 100) if E_pv > 0 else 0
    
    # Stats Text Box
    stats_text = (
        f"PV Equivalent: {E_pv:.1f} kWh\n"
        f"HVAC Load: {E_hvac:.1f} kWh\n"
        f"PV Surplus: {E_surplus:.1f} kWh ({surplus_pct:.1f}%)\n"
        f"HVAC Deficit: {E_deficit:.1f} kWh"
    )
    
    ax.text(0.03, 0.95, stats_text, transform=ax.transAxes, va="top", ha="left", fontsize=8.5,
            fontweight="bold", bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#cbd5e1", alpha=0.92))
    
    # Panel Title
    ax.text(0.97, 0.95, title, transform=ax.transAxes, va="top", ha="right", fontsize=10.5,
            fontweight="bold")


# ═══════════════════════════════════════════════════════════════════════════════
# PLOT 1: Extreme Days (2x2 Grid)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nPlotting Plot 1: Extreme Days...")
fig, axes = plt.subplots(2, 2, figsize=dm.figsize("23cm", "16cm"), sharex=True, sharey=True)

DAY_SURPLUS = 112  # April 22
DAY_DEFICIT = 209  # July 28

# Row 1: Case 2 (Fixed-90°)
plot_timestep_panel(axes[0, 0], c2, DAY_SURPLUS, "Fixed-90° | April 22", ylim=240)
plot_timestep_panel(axes[0, 1], c2, DAY_DEFICIT, "Fixed-90° | July 28", ylim=240)

# Row 2: Case 3 (Kinetic)
plot_timestep_panel(axes[1, 0], c3, DAY_SURPLUS, "Kinetic BIPV | April 22", ylim=240)
plot_timestep_panel(axes[1, 1], c3, DAY_DEFICIT, "Kinetic BIPV | July 28", ylim=240)

# Labels
axes[0, 0].set_ylabel("Thermal Power [kW]")
axes[1, 0].set_ylabel("Thermal Power [kW]")
axes[1, 0].set_xlabel("Time of Day")
axes[1, 1].set_xlabel("Time of Day")

axes[0, 0].set_title("Maximum PV Surplus Day (April 22nd)\n[Mild Season: High PV, Low HVAC]", fontsize=12.5, fontweight="bold", pad=8)
axes[0, 1].set_title("Maximum HVAC Deficit Day (July 28th)\n[Peak Summer: Moderate PV, Extreme Cooling]", fontsize=12.5, fontweight="bold", pad=8)

handles, labels_leg = axes[0, 0].get_legend_handles_labels()
by_label = dict(zip(labels_leg, handles))
fig.legend(by_label.values(), by_label.keys(), loc="lower center", ncol=4, fontsize=10,
           frameon=True, edgecolor="#cbd5e1", bbox_to_anchor=(0.5, -0.03))

fig.suptitle("Real-time (10-min Timestep) HVAC Thermal Load vs. PV Thermal Equivalent\n(Extreme Surplus Day vs. Extreme Deficit Day)", y=1.03, fontsize=14.5, fontweight="bold")
fig.tight_layout(rect=[0, 0.03, 1, 1])

fig1_png = OUT / "hvac_vs_pv_extreme_days.png"
fig1_svg = OUT / "hvac_vs_pv_extreme_days.svg"
fig.savefig(fig1_png, dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(fig1_svg, bbox_inches="tight", transparent=True)
plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# PLOT 2: Typical Days (2x3 Grid)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nPlotting Plot 2: Typical Seasonal Days...")
fig, axes = plt.subplots(2, 3, figsize=dm.figsize("29cm", "14cm"), sharex=True, sharey=True)

DAY_WINTER = 19   # January 19
DAY_SUMMER = 200  # July 19
DAY_AUTUMN = 292  # October 19

# Row 1: Case 2 (Fixed-90°)
plot_timestep_panel(axes[0, 0], c2, DAY_WINTER, "Fixed-90° | Jan 19", ylim=120)
plot_timestep_panel(axes[0, 1], c2, DAY_SUMMER, "Fixed-90° | Jul 19", ylim=120)
plot_timestep_panel(axes[0, 2], c2, DAY_AUTUMN, "Fixed-90° | Oct 19", ylim=120)

# Row 2: Case 3 (Kinetic)
plot_timestep_panel(axes[1, 0], c3, DAY_WINTER, "Kinetic | Jan 19", ylim=120)
plot_timestep_panel(axes[1, 1], c3, DAY_SUMMER, "Kinetic | Jul 19", ylim=120)
plot_timestep_panel(axes[1, 2], c3, DAY_AUTUMN, "Kinetic | Oct 19", ylim=120)

# Labels
axes[0, 0].set_ylabel("Thermal Power [kW]")
axes[1, 0].set_ylabel("Thermal Power [kW]")
for i in range(3):
    axes[1, i].set_xlabel("Time of Day")

axes[0, 0].set_title("Typical Winter Day (Jan 19th)\n[Heating Dominant]", fontsize=12, fontweight="bold", pad=8)
axes[0, 1].set_title("Typical Summer Day (Jul 19th)\n[Cooling Dominant]", fontsize=12, fontweight="bold", pad=8)
axes[0, 2].set_title("Typical Spring/Autumn Day (Oct 19th)\n[Mild Season]", fontsize=12, fontweight="bold", pad=8)

handles, labels_leg = axes[0, 0].get_legend_handles_labels()
by_label = dict(zip(labels_leg, handles))
fig.legend(by_label.values(), by_label.keys(), loc="lower center", ncol=4, fontsize=10,
           frameon=True, edgecolor="#cbd5e1", bbox_to_anchor=(0.5, -0.04))

fig.suptitle("Real-time (10-min Timestep) HVAC Thermal Load vs. PV Thermal Equivalent\n(Typical Seasonal Days Comparison)", y=1.03, fontsize=14, fontweight="bold")
fig.tight_layout(rect=[0, 0.03, 1, 1])

fig2_png = OUT / "hvac_vs_pv_typical_days.png"
fig2_svg = OUT / "hvac_vs_pv_typical_days.svg"
fig.savefig(fig2_png, dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(fig2_svg, bbox_inches="tight", transparent=True)
plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# PLOT 3: July 19th Only (2x1 Grid)
# ═══════════════════════════════════════════════════════════════════════════════
print("\nPlotting Plot 3: July 19th Only...")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=dm.figsize("16cm", "14cm"), sharex=True, sharey=True)

DAY_SUMMER = 200  # July 19

# Top panel: Case 2
plot_timestep_panel(ax1, c2, DAY_SUMMER, "Fixed-90° | July 19", ylim=120)

# Bottom panel: Case 3
plot_timestep_panel(ax2, c3, DAY_SUMMER, "Kinetic BIPV | July 19", ylim=120)

# Labels
ax1.set_ylabel("Thermal Power [kW]")
ax2.set_ylabel("Thermal Power [kW]")
ax2.set_xlabel("Time of Day")

# Unified legend
handles, labels_leg = ax1.get_legend_handles_labels()
by_label = dict(zip(labels_leg, handles))
fig.legend(by_label.values(), by_label.keys(), loc="lower center", ncol=2, fontsize=10,
           frameon=True, edgecolor="#cbd5e1", bbox_to_anchor=(0.5, -0.04))

fig.suptitle("July 19th Timestep (10-min) HVAC vs. PV Comparison\n(Peak Summer Cooling Mismatch)", y=1.03, fontsize=14, fontweight="bold")
fig.tight_layout(rect=[0, 0.05, 1, 1])

fig3_png = OUT / "hvac_vs_pv_july_19.png"
fig3_svg = OUT / "hvac_vs_pv_july_19.svg"
fig.savefig(fig3_png, dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(fig3_svg, bbox_inches="tight", transparent=True)
plt.close()

print(f"\n완료!\n생성된 이미지:\n  - {fig1_png.name}\n  - {fig2_png.name}\n  - {fig3_png.name}\n저장 위치: {OUT}")



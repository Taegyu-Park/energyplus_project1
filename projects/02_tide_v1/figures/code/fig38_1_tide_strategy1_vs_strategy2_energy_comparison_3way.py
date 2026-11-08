import os
import json
from pathlib import Path
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import dartwork_mpl as dm

# 1. Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

# 2. Apply presentation style from dartwork_mpl
dm.style.use("presentation")

# Patch matplotlib font_manager for SVG export compatibility (resolves numeric font weight KeyError)
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

# 3. Path Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig38_1_tide_strategy1_vs_strategy2_energy_comparison_3way"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

PATH_STRATEGY1 = PROJECT_ROOT / "case_analysis" / "case3_v3_south_tide" / "case3_south_tide_annual_summary.json"
PATH_STRATEGY2 = PROJECT_ROOT / "case_analysis" / "case3_v3_south_tide_strategy2" / "case3_south_tide_annual_summary.json"
PATH_BASELINE_SQL = PROJECT_ROOT / "case_analysis" / "bipv_variation" / "5zone_NSEW_korean" / "case3_v3_south" / "eplusout.sql"

# 4. Load Data
# Baseline: Sun-Tracking Model (case3_v3_south)
if PATH_BASELINE_SQL.exists():
    import sqlite3
    conn = sqlite3.connect(PATH_BASELINE_SQL)
    c = conn.cursor()
    def get_sql_kwh(name):
        c.execute("SELECT ReportDataDictionaryIndex FROM ReportDataDictionary WHERE Name = ?", (name,))
        ids = [r[0] for r in c.fetchall()]
        if not ids: return 0.0
        p = ",".join("?" for _ in ids)
        c.execute(f"SELECT SUM(rd.Value) FROM ReportData rd JOIN Time t ON rd.TimeIndex = t.TimeIndex WHERE rd.ReportDataDictionaryIndex IN ({p}) AND t.WarmupFlag = 0", ids)
        row = c.fetchone()
        return (row[0] or 0.0) / 3.6e6 if row else 0.0
    base_cooling = get_sql_kwh("Zone Ideal Loads Supply Air Total Cooling Energy")
    base_heating = get_sql_kwh("Zone Ideal Loads Supply Air Total Heating Energy")
    base_pv = get_sql_kwh("Facility Total Produced Electricity Energy")
    conn.close()
    base_hvac = (base_cooling / 3.0) + (base_heating / 2.5)
    base_net = base_hvac - base_pv
else:
    base_heating = 38065.60
    base_cooling = 54568.40
    base_pv = 38074.11
    base_hvac = 33415.71
    base_net = -4658.40

# Strategy 1 (TiDE Net Energy Optimization)
with open(PATH_STRATEGY1, "r", encoding="utf-8") as f:
    data1 = json.load(f)["annual_results"]

# Extract metrics
s1_heating = data1["heating_load_thermal_kwh"]
s1_cooling = data1["cooling_load_thermal_kwh"]
s1_pv = data1["pv_power_generation_elec_kwh"]
s1_hvac = data1["hvac_electricity_kwh"]
s1_net = data1["net_energy_elec_kwh"]

# Strategy 2 (TiDE component-wise prediction)
with open(PATH_STRATEGY2, "r", encoding="utf-8") as f:
    data2 = json.load(f)
s2_heating = data2["total_heating_load_thermal_kwh"]
s2_cooling = data2["total_cooling_load_thermal_kwh"]
s2_pv = data2["total_bipv_generation_kwh"]
s2_hvac = data2["hvac_electric_consumption_kwh"]
s2_net = data2["net_energy_consumption_kwh"]

categories = [
    "Heating Load\n(Thermal)",
    "Cooling Load\n(Thermal)",
    "PV Generation\n(Electric)",
    "HVAC Electricity\n(Electric)",
    "Net Energy\n(HVAC - PV)"
]

values_base = [base_heating, base_cooling, base_pv, base_hvac, base_net]
values_tide = [s1_heating, s1_cooling, s1_pv, s1_hvac, s1_net]
values_st2 = [s2_heating, s2_cooling, s2_pv, s2_hvac, s2_net]

# 5. Visualization
fig, ax = plt.subplots(figsize=(17, 8), dpi=300)

x = np.arange(len(categories))
bar_width = 0.26

# Color scheme (Harmonized with fig37):
# Baseline (Sun-Tracking) = Amber Orange (#f59e0b), TiDE (Net Energy AI) = Royal Blue (#2563eb)
COLOR_BASE = "#f59e0b"  # Amber 500 (Sun-Tracking, matching fig37)
COLOR_ST2 = "#10b981"  # Emerald (TiDE Strategy 2)
COLOR_TIDE = "#2563eb"  # Royal Blue 600 (AI Optimal, matching fig37)

rects_base = ax.bar(
    x - bar_width,
    values_base,
    bar_width,
    label="Baseline (Sun-Tracking)",
    color=COLOR_BASE,
    alpha=0.92,
    edgecolor="none"
)

rects_tide = ax.bar(
    x,
    values_tide,
    bar_width,
    label="TiDE Strategy 1 (End-to-End)",
    color=COLOR_TIDE,
    alpha=0.92,
    edgecolor="none"
)

rects_st2 = ax.bar(
    x + bar_width,
    values_st2,
    bar_width,
    label="TiDE Strategy 2 (Component-wise)",
    color=COLOR_ST2,
    alpha=0.92,
    edgecolor="none"
)

# Reference zero line
ax.axhline(0, color="#64748b", linestyle="-", linewidth=1.2, alpha=0.8)

# 6. Data Labels
for i in range(len(categories)):
    v_base = values_base[i]
    v_tide = values_tide[i]

    # Label for Baseline
    offset_base = 1200 if v_base >= 0 else -2000
    va_base = "bottom" if v_base >= 0 else "top"
    ax.annotate(
        f"{v_base:,.0f} kWh",
        (x[i] - bar_width, v_base + offset_base),
        ha="center",
        va=va_base,
        fontsize=9,
        fontweight="bold",
        color="#b45309"
    )

    v_st2 = values_st2[i]
    ax.annotate(
        f"{v_st2:,.0f} kWh",
        (x[i] + bar_width, v_st2 + (1200 if v_st2 >= 0 else -2000)),
        ha="center",
        va="bottom" if v_st2 >= 0 else "top",
        fontsize=9,
        fontweight="bold",
        color="#047857"
    )

    # Label for TiDE
    offset_tide = 1200 if v_tide >= 0 else -2000
    va_tide = "bottom" if v_tide >= 0 else "top"
    ax.annotate(
        f"{v_tide:,.0f} kWh",
        (x[i], v_tide + offset_tide),
        ha="center",
        va=va_tide,
        fontsize=9,
        fontweight="bold",
        color="#1d4ed8"
    )

# 7. Axes & Layout Styling
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=12, fontweight="medium")
ax.set_ylabel("Annual Energy (kWh / year)", fontsize=13, fontweight="bold", labelpad=12)
ax.set_ylim(-9000, 68000)

# Title & Subtitle
ax.set_title(
    "Annual Energy Performance Comparison: Sun-Tracking vs TiDE Strategy 1 vs Strategy 2 (South BIPV)",
    fontsize=14.5,
    fontweight="bold",
    pad=24
)

# Legend configuration
legend = ax.legend(
    loc="upper right",
    frameon=True,
    framealpha=0,
    fontsize=11,
    ncols=3
)

# Grid styling
ax.grid(axis="y", linestyle="--", alpha=0.35)
ax.set_axisbelow(True)

plt.tight_layout()

# 8. Save PNG & SVG
out_png = PLOT_DIR / "fig38_1_tide_strategy1_vs_strategy2_energy_comparison_3way.png"
out_svg = PLOT_DIR / "fig38_1_tide_strategy1_vs_strategy2_energy_comparison_3way.svg"

fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)

print(f"[OK] Successfully generated figure:")
print(f"    PNG: {out_png}")
print(f"    SVG: {out_svg}")

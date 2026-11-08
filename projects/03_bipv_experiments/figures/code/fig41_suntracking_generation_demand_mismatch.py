"""fig41: case3 sun-tracking BIPV -- hourly generation vs HVAC electricity demand on extreme days.

Resolution: native 10-min timestep (kWh per 10 min, no hourly aggregation)
Data (One-Diode, final run c3_FE_suntracking_od): bipv_experiments/analysis/c3_net_timeseries_onediode.csv
Demand = cooling/3.0 + heating/2.5 (HVAC electricity, ideal loads)  [kWh]
Representative days = lowest / highest daily-mean outdoor temperature among weekdays
  winter: 01/13 (mean -6.2 C), summer: 08/08 (mean 29.0 C)
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import dartwork_mpl as dm

mpl.rcParams["svg.fonttype"] = "none"
dm.style.use("presentation")
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig41_suntracking_generation_demand_mismatch"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
EXP = PROJECT_ROOT / "bipv_experiments"
sys.path.insert(0, str(EXP / "analysis"))
from sql_extract import COP_COOLING, COP_HEATING  # noqa: E402

C_PV = "#f59e0b"       # PV generation (Amber)
C_DEM = "#1e293b"      # HVAC demand (Slate)
C_SURPLUS = "#10b981"  # PV > demand (export)
C_DEFICIT = "#dc2626"  # demand > PV (grid purchase)

DAYS = [("2026-01-13", "Extreme cold day", "Jan 13"), ("2026-08-08", "Extreme hot day", "Aug 8")]

d = pd.read_csv(EXP / "analysis" / "c3_net_timeseries_onediode.csv", parse_dates=["timestamp"])
d["t"] = d["timestamp"] - pd.Timedelta(minutes=10)  # interval-ending -> interval-start label
d["demand"] = d["cool_load_ST"] / COP_COOLING + d["heat_load_ST"] / COP_HEATING
d = d.set_index("t")

fig = plt.figure(figsize=(15, 6.8))
gs = fig.add_gridspec(1, 2, wspace=0.16)

top_axes = []
for col, (day, label, short) in enumerate(DAYS):
    h = d.loc[day:day]
    pv, dem = h["pv_gen_ST"].values, h["demand"].values

    ax = fig.add_subplot(gs[0, col])
    top_axes.append(ax)

    # step-shaped 10-min profiles (x in hours, 144 intervals)
    xs = np.r_[np.arange(len(pv)), len(pv)] / 6.0
    pv_s, dem_s = np.r_[pv, pv[-1]], np.r_[dem, dem[-1]]
    ax.step(xs, pv_s, where="post", color=C_PV, lw=1.4)
    ax.step(xs, dem_s, where="post", color=C_DEM, lw=1.0)
    top = np.maximum(pv_s, dem_s)  # no `where=`: it leaves gaps at step transitions
    ax.fill_between(xs, dem_s, top, step="post", color=C_SURPLUS, alpha=0.45, lw=0)
    ax.fill_between(xs, pv_s, top, step="post", color=C_DEFICIT, alpha=0.28, lw=0)

    ax.set_title(f"{label} — {short}",
                 fontsize=13.5, fontweight="bold", loc="left", pad=8)
    ax.set_ylim(0, 8)
    ax.grid(axis="y", ls="--", alpha=0.3)
    if col == 0:
        ax.set_ylabel("Energy [kWh / 10 min]", fontsize=12)
    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 3))
    ax.set_xticklabels([f"{k:02d}:00" for k in range(0, 25, 3)])
    ax.set_xlabel("Hour of day", fontsize=12)

handles = [
    Line2D([], [], color=C_PV, lw=1.4, label="BIPV generation (sun-tracking)"),
    Line2D([], [], color=C_DEM, lw=1.0, label=f"HVAC electricity demand (cool/{COP_COOLING:.1f} + heat/{COP_HEATING:.1f})"),
    Patch(fc=C_SURPLUS, alpha=0.6, label="Surplus"),
    Patch(fc=C_DEFICIT, alpha=0.4, label="Deficit"),
]
top_axes[0].legend(handles=handles, loc="upper right", ncol=2, fontsize=10.5, frameon=False)
fig.suptitle("Case 3 sun-tracking BIPV: mismatch between generation and HVAC demand on extreme days",
             fontsize=15.5, fontweight="bold", y=0.975)

out_png = PLOT_DIR / "fig41_suntracking_generation_demand_mismatch.png"
out_svg = PLOT_DIR / "fig41_suntracking_generation_demand_mismatch.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)
print(f"[OK] {out_png}")

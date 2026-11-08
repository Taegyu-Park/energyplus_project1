"""fig41_1: weekly extension of fig41 -- 10-min generation vs HVAC electricity demand
for a winter week (weekdays Mon-Fri only) where every weekday has both deficit and surplus.

Week selection (Dec-Feb, Mon-Fri, sun-tracking, PV>0 hours): daily deficit > 5 kWh and
daily surplus > 5 kWh on all 5 weekdays, pick the week with the largest min(daily deficit, daily surplus)
  -> Jan 30 ~ Feb 3 (min daily deficit 28.1 kWh, min daily surplus 41.3 kWh)
  (previous version used the Jan 13 week; one weekday there had no surplus)

Resolution: native 10-min timestep (kWh per 10 min, no hourly aggregation)
Data (One-Diode, final run c3_FE_suntracking_od): bipv_experiments/analysis/c3_net_timeseries_onediode.csv
Day-of-week follows the simulation calendar (eplusout.sql Time.DayType; Jan 1 = Sunday),
not the 2026 label in the CSV timestamps.
Demand = cooling/3.0 + heating/2.5 (HVAC electricity, ideal loads)  [kWh]
"""
import sqlite3
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
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig41_1_suntracking_generation_demand_mismatch_week"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
EXP = PROJECT_ROOT / "bipv_experiments"
RUN_SQL = EXP / "runs" / "c3_FE_suntracking_od" / "eplusout.sql"
sys.path.insert(0, str(EXP / "analysis"))
from sql_extract import COP_COOLING, COP_HEATING  # noqa: E402

C_PV = "#f59e0b"       # PV generation (Amber)
C_DEM = "#1e293b"      # HVAC demand (Slate)
C_SURPLUS = "#10b981"  # PV > demand (export)
C_DEFICIT = "#dc2626"  # demand > PV (grid purchase)

DAY, LABEL = "2026-01-30", "Winter weekdays"  # any day in the target week
N_DAYS = 5  # Mon-Fri
DOW_IDX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}

d = pd.read_csv(EXP / "analysis" / "c3_net_timeseries_onediode.csv", parse_dates=["timestamp"])
d["t"] = d["timestamp"] - pd.Timedelta(minutes=10)  # interval-ending -> interval-start label
d["demand"] = d["cool_load_ST"] / COP_COOLING + d["heat_load_ST"] / COP_HEATING
d = d.set_index("t")

con = sqlite3.connect(RUN_SQL)
dow = {(m, dd): DOW_IDX[t] for m, dd, t in
       con.execute("SELECT DISTINCT Month, Day, DayType FROM Time WHERE Hour = 12 AND DayType IN "
                   "('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')")}
con.close()

ts = pd.Timestamp(DAY)
start = ts - pd.Timedelta(days=dow[(ts.month, ts.day)])
end = start + pd.Timedelta(days=N_DAYS)

fig, ax = plt.subplots(1, 1, figsize=(16, 4.8))

w = d.loc[start:end - pd.Timedelta(minutes=10)]
pv, dem = w["pv_gen_ST"].values, w["demand"].values
n = len(pv)
xs = np.r_[np.arange(n), n] / 144.0  # x in days
pv_s, dem_s = np.r_[pv, pv[-1]], np.r_[dem, dem[-1]]

ax.step(xs, pv_s, where="post", color=C_PV, lw=1.4)
ax.step(xs, dem_s, where="post", color=C_DEM, lw=0.9)
top = np.maximum(pv_s, dem_s)
ax.fill_between(xs, dem_s, top, step="post", color=C_SURPLUS, alpha=0.45, lw=0)
ax.fill_between(xs, pv_s, top, step="post", color=C_DEFICIT, alpha=0.28, lw=0)

end_lbl = end - pd.Timedelta(days=1)
ax.set_title(f"{LABEL} — {start:%b} {start.day} ~ {end_lbl:%b} {end_lbl.day}",
             fontsize=13.5, fontweight="bold", loc="left", pad=8)
ax.set_ylim(0, max(8, np.ceil(top.max())))
ax.set_xlim(0, N_DAYS)
ax.set_xticks(np.arange(N_DAYS) + 0.5)
ax.set_xticklabels([f"{(start + pd.Timedelta(days=k)):%b} {(start + pd.Timedelta(days=k)).day}\n"
                    f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][k]}" for k in range(N_DAYS)])
ax.set_xticks(np.arange(N_DAYS + 1), minor=True)
ax.tick_params(axis="x", which="major", length=0)
ax.grid(axis="x", which="minor", ls="-", alpha=0.25)
ax.grid(axis="y", ls="--", alpha=0.3)
ax.set_ylabel("Energy [kWh / 10 min]", fontsize=12)

handles = [
    Line2D([], [], color=C_PV, lw=1.4, label="BIPV generation (sun-tracking)"),
    Line2D([], [], color=C_DEM, lw=1.0, label=f"HVAC electricity demand (cool/{COP_COOLING:.1f} + heat/{COP_HEATING:.1f})"),
    Patch(fc=C_SURPLUS, alpha=0.6, label="Surplus"),
    Patch(fc=C_DEFICIT, alpha=0.4, label="Deficit"),
]
ax.legend(handles=handles, loc="upper right", ncol=2, fontsize=10.5, frameon=False)

fig.suptitle("Case 3 sun-tracking BIPV: mismatch between generation and HVAC demand over winter weekdays",
             fontsize=15.5, fontweight="bold", y=1.04)
out_png = PLOT_DIR / "fig41_1_suntracking_generation_demand_mismatch_week.png"
out_svg = PLOT_DIR / "fig41_1_suntracking_generation_demand_mismatch_week.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)
print(f"[OK] {out_png}")

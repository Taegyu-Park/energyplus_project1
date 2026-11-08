"""fig42: annual daily generation-demand mismatch of case3 sun-tracking BIPV (weekdays only).

Data (One-Diode, final run c3_FE_suntracking_od): bipv_experiments/analysis/c3_net_timeseries_onediode.csv
Weekday follows the simulation calendar (eplusout.sql Time.DayType; Jan 1 = Sunday).
Demand = cooling/3.0 + heating/2.5 (HVAC electricity, ideal loads)  [kWh]
Per 10-min step: surplus = max(PV - demand, 0), deficit = max(demand - PV, 0); summed per day.
Daily surplus (+) / deficit (-)
"""
import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from matplotlib.patches import Patch
import dartwork_mpl as dm

mpl.rcParams["svg.fonttype"] = "none"
dm.style.use("presentation")
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig42_suntracking_daily_mismatch_annual"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
EXP = PROJECT_ROOT / "bipv_experiments"
RUN_SQL = EXP / "runs" / "c3_FE_suntracking_od" / "eplusout.sql"
sys.path.insert(0, str(EXP / "analysis"))
from sql_extract import COP_COOLING, COP_HEATING  # noqa: E402

C_SURPLUS = "#10b981"  # PV > demand (export)
C_DEFICIT = "#dc2626"  # demand > PV (grid purchase)

d = pd.read_csv(EXP / "analysis" / "c3_net_timeseries_onediode.csv", parse_dates=["timestamp"])
d["t"] = d["timestamp"] - pd.Timedelta(minutes=10)  # interval-ending -> interval-start label
d["demand"] = d["cool_load_ST"] / COP_COOLING + d["heat_load_ST"] / COP_HEATING
d["surplus"] = (d["pv_gen_ST"] - d["demand"]).clip(lower=0)
d["deficit"] = (d["demand"] - d["pv_gen_ST"]).clip(lower=0)
d["date"] = d["t"].dt.normalize()

con = sqlite3.connect(RUN_SQL)
daytype = {(m, dd): t for m, dd, t in
           con.execute("SELECT DISTINCT Month, Day, DayType FROM Time WHERE Hour = 12 AND DayType IN "
                       "('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')")}
con.close()

g = d.groupby("date")[["pv_gen_ST", "demand", "surplus", "deficit"]].sum()
g = g[[daytype[(t.month, t.day)] not in ("Saturday", "Sunday") for t in g.index]]

fig, ax1 = plt.subplots(figsize=(16, 5.6))

# daily surplus / deficit
ax1.bar(g.index, g["surplus"], width=1.0, color=C_SURPLUS, alpha=0.75, lw=0)
ax1.bar(g.index, -g["deficit"], width=1.0, color=C_DEFICIT, alpha=0.55, lw=0)
ax1.axhline(0, color="#334155", lw=0.8)
ax1.set_ylabel("Daily energy [kWh]", fontsize=12)
ax1.grid(axis="y", ls="--", alpha=0.3)
ax1.set_title("Daily surplus and deficit", fontsize=13.5, fontweight="bold", loc="left", pad=8)
ax1.legend(handles=[Patch(fc=C_SURPLUS, alpha=0.75, label="Surplus (PV > demand)"),
                    Patch(fc=C_DEFICIT, alpha=0.55, label="Deficit (demand > PV)")],
           loc="upper right", ncol=2, fontsize=10.5, frameon=False)

ax1.set_xlim(pd.Timestamp("2026-01-01"), pd.Timestamp("2027-01-01"))
ax1.xaxis.set_major_locator(mdates.MonthLocator())
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax1.grid(axis="x", which="major", ls="-", alpha=0.25)

fig.suptitle("Case 3 sun-tracking BIPV: daily generation-demand mismatch over the year (weekdays)",
             fontsize=15.5, fontweight="bold", y=1.0)
out_png = PLOT_DIR / "fig42_suntracking_daily_mismatch_annual.png"
out_svg = PLOT_DIR / "fig42_suntracking_daily_mismatch_annual.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)
g.round(3).to_csv(PLOT_DIR / "fig42_daily_weekday.csv")
print(f"[OK] {out_png}  ({len(g)} weekdays)")

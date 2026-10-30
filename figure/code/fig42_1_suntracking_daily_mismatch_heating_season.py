"""fig42_1: fig42 with only the heating season (Nov 1 ~ Mar 31) in color; other months in grey.

Annual daily generation-demand mismatch of case3 sun-tracking BIPV (weekdays only).

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
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig42_1_suntracking_daily_mismatch_heating_season"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
EXP = PROJECT_ROOT / "bipv_experiments"
RUN_SQL = EXP / "runs" / "c3_FE_suntracking_od" / "eplusout.sql"
sys.path.insert(0, str(EXP / "analysis"))
from sql_extract import COP_COOLING, COP_HEATING  # noqa: E402

C_SURPLUS = "#10b981"  # PV > demand (export)
C_DEFICIT = "#dc2626"  # demand > PV (grid purchase)
C_GREY_SUR = "#9ca3af"  # surplus outside the highlighted season
C_GREY_DEF = "#cbd5e1"  # deficit outside the highlighted season

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
hl = (g.index.month >= 11) | (g.index.month <= 3)  # Nov 1 ~ Mar 31
for m, c_sur, a_sur, c_def, a_def in [(hl, C_SURPLUS, 0.75, C_DEFICIT, 0.55),
                                       (~hl, C_GREY_SUR, 0.6, C_GREY_DEF, 0.8)]:
    ax1.bar(g.index[m], g["surplus"][m], width=1.0, color=c_sur, alpha=a_sur, lw=0)
    ax1.bar(g.index[m], -g["deficit"][m], width=1.0, color=c_def, alpha=a_def, lw=0)
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
out_png = PLOT_DIR / "fig42_1_suntracking_daily_mismatch_heating_season.png"
out_svg = PLOT_DIR / "fig42_1_suntracking_daily_mismatch_heating_season.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)
print(f"[OK] {out_png}  ({len(g)} weekdays)")

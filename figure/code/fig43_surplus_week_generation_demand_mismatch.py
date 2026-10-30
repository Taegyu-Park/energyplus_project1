"""fig43: fig41_1 format -- 10-min generation vs HVAC electricity demand, weekdays (Mon-Fri) only.

  Top   : summer weekdays Aug 7 ~ 11 (demand >> PV, PV fully absorbed, deficit only)
  Bottom: autumn weekdays Oct 2 ~ 6 (PV covers daytime demand on all 5 days, surplus only)
Data (One-Diode, final run c3_FE_suntracking_od, IWEC): bipv_experiments/analysis/c3_net_timeseries_onediode.csv
  -- same sun-tracking baseline as fig41 / fig41_1
Resolution: native 10-min timestep (kWh per 10 min)
Demand = cooling/3.0 + heating/2.5 (HVAC electricity, ideal loads)  [kWh]
Calendar: simulation calendar (Jan 1 = Sunday = 2006); the CSV's 2026 labels are shifted to 2006
(both non-leap, same row order) so pandas weekdays match eplusout.sql DayType. Interval-start labels.
"""
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
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig43_surplus_week_generation_demand_mismatch"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
DATA = PROJECT_ROOT / "bipv_experiments" / "analysis" / "c3_net_timeseries_onediode.csv"

COP_COOLING = 3.0
COP_HEATING = 2.5

C_PV = "#f59e0b"       # PV generation (Amber)
C_DEM = "#1e293b"      # HVAC demand (Slate)
C_SURPLUS = "#10b981"  # PV > demand (export)
C_DEFICIT = "#dc2626"  # demand > PV (grid purchase)

WEEKS = [("2006-08-07", "Summer weekdays"), ("2006-10-02", "Autumn weekdays")]  # Mondays
N_DAYS = 5  # Mon-Fri

d = pd.read_csv(DATA, usecols=["timestamp", "pv_gen_ST", "cool_load_ST", "heat_load_ST"], parse_dates=["timestamp"])
assert (d["timestamp"].iloc[0] == pd.Timestamp("2026-01-01 00:10")) and len(d) == 52560
d["t"] = d["timestamp"] - pd.DateOffset(years=20) - pd.Timedelta(minutes=10)  # -> 2006 calendar, interval-start
d["pv"] = d["pv_gen_ST"]
d["demand"] = d["cool_load_ST"] / COP_COOLING + d["heat_load_ST"] / COP_HEATING
d = d.set_index("t")

# 두 패널 공통 y축 (여름 수요가 8 kWh를 넘을 수 있음)
y_max = max(8, np.ceil(max(
    d.loc[pd.Timestamp(m):pd.Timestamp(m) + pd.Timedelta(days=N_DAYS, minutes=-10),
          ["pv", "demand"]].to_numpy().max() for m, _ in WEEKS)))

fig, axes = plt.subplots(2, 1, figsize=(16, 9.6))
fig.subplots_adjust(hspace=0.25)

for ax, (monday, label) in zip(axes, WEEKS):
    start = pd.Timestamp(monday)
    assert start.dayofweek == 0, monday
    end = start + pd.Timedelta(days=N_DAYS)
    w = d.loc[start:end - pd.Timedelta(minutes=10)]
    pv, dem = w["pv"].values, w["demand"].values
    n = len(pv)
    xs = np.r_[np.arange(n), n] / 144.0  # x in days
    pv_s, dem_s = np.r_[pv, pv[-1]], np.r_[dem, dem[-1]]

    ax.step(xs, pv_s, where="post", color=C_PV, lw=1.4)
    ax.step(xs, dem_s, where="post", color=C_DEM, lw=0.9)
    top = np.maximum(pv_s, dem_s)
    ax.fill_between(xs, dem_s, top, step="post", color=C_SURPLUS, alpha=0.45, lw=0)
    ax.fill_between(xs, pv_s, top, step="post", color=C_DEFICIT, alpha=0.28, lw=0)

    end_lbl = end - pd.Timedelta(days=1)
    ax.set_title(f"{label} — {start:%b} {start.day} ~ {end_lbl:%b} {end_lbl.day}",
                 fontsize=13.5, fontweight="bold", loc="left", pad=8)
    ax.set_ylim(0, y_max)
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
axes[1].legend(handles=handles, loc="upper right", ncol=2, fontsize=10.5, frameon=False)

out_png = PLOT_DIR / "fig43_surplus_week_generation_demand_mismatch.png"
out_svg = PLOT_DIR / "fig43_surplus_week_generation_demand_mismatch.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)
print(f"[OK] {out_png}")

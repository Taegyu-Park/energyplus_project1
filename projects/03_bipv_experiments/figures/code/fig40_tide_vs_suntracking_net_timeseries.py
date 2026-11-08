"""fig40: TiDE vs sun-tracking net energy time series -- where does the TiDE angle choice go wrong?

Data (One-Diode, final runs): bipv_experiments/analysis/c3_net_timeseries_onediode.csv
  (cached by bipv_experiments/analysis/extract_c3_net_timeseries.py)
Expected gain (no inertia) = stitching the fixed-angle dataset c2_RF_fixed_angle_dataset.csv with each schedule.
net energy = cooling/3.0 + heating/2.5 - PV  [kWh]  (lower is better)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig40_tide_vs_suntracking_net_timeseries"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
EXP = PROJECT_ROOT / "bipv_experiments"

C_ST, C_S1, C_S2 = "#f59e0b", "#2563eb", "#10b981"
C_BAD, C_GOOD = "#dc2626", "#0d9488"
WEEK = ("2026-07-21", "2026-07-28")  # Jul 21-27: contains the best day (7/21) and two worst days (7/24, 7/27)

d = pd.read_csv(EXP / "analysis" / "c3_net_timeseries_onediode.csv", parse_dates=["timestamp"])
d["t"] = d["timestamp"] - pd.Timedelta(minutes=10)  # interval-ending -> interval-start label

# expected (inertia-free) gain from the fixed-angle dataset
A = np.arange(0, 100, 10)
fx = pd.read_csv(EXP / "analysis" / "c2_RF_fixed_angle_dataset.csv")
net_fx = fx[[f"net_energy_{a}" for a in A]].values


def stitched(angles):
    return net_fx[np.arange(len(angles)), (angles // 10).astype(int)]


d["exp_S1"] = stitched(d["angle_S1"].values) - stitched(d["angle_ST"].values)
d["exp_S2"] = stitched(d["angle_S2"].values) - stitched(d["angle_ST"].values)
d["real_S1"] = d["net_energy_S1"] - d["net_energy_ST"]
d["real_S2"] = d["net_energy_S2"] - d["net_energy_ST"]

# hourly view of the representative week
w = d[(d["t"] >= WEEK[0]) & (d["t"] < WEEK[1])].copy()
w["hour"] = w["t"].dt.floor("h")
hr = w.groupby("hour").agg(ST=("net_energy_ST", "sum"), S1=("net_energy_S1", "sum"),
                           aST=("angle_ST", "mean"), aS1=("angle_S1", "mean")).reset_index()
hr["delta"] = hr["S1"] - hr["ST"]

fig = plt.figure(figsize=(14, 15))
gs = fig.add_gridspec(4, 1, height_ratios=[2.3, 1.6, 1.4, 2.6], hspace=0.24)
ax1 = fig.add_subplot(gs[0])
axd = fig.add_subplot(gs[1], sharex=ax1)
ax2 = fig.add_subplot(gs[2], sharex=ax1)
ax3 = fig.add_subplot(gs[3])

# ---- (a) net energy lines with highlighted differences
x = hr["hour"].values
ax1.plot(x, hr["ST"], color=C_ST, lw=2.0, label="Sun-tracking")
ax1.plot(x, hr["S1"], color=C_S1, lw=2.0, label="TiDE Strategy 1")
ax1.axhline(0, color="#64748b", lw=0.9, alpha=0.8)
ax1.set_ylabel("Net energy [kWh / h]", fontsize=12)
ax1.set_title("Net energy, July 21–27 (hourly): the two schedules look almost identical",
              fontsize=14.5, fontweight="bold", loc="left", pad=10)
ax1.grid(axis="y", ls="--", alpha=0.3)

# ---- (b) hourly difference as bars: this is where the gap is visible
dl = hr["delta"].values
axd.bar(x, dl, width=np.timedelta64(50, "m"), align="edge",
        color=np.where(dl > 0, C_BAD, C_GOOD), alpha=0.9, lw=0)
axd.axhline(0, color="#64748b", lw=0.9)
axd.set_ylabel("TiDE − sun-tracking\n[kWh / h]", fontsize=12)
axd.set_title("Hourly difference: red = TiDE uses more net energy", fontsize=13.5, fontweight="bold", loc="left", pad=6)
axd.grid(axis="y", ls="--", alpha=0.3)
picked = []
for _, r in hr.nlargest(12, "delta").iterrows():
    if all(abs((r["hour"] - q).total_seconds()) > 8 * 3600 for q in picked) and len(picked) < 2:
        picked.append(r["hour"])
        axd.annotate(f"+{r['delta']:.1f} kWh  ({r['hour']:%m/%d %H}h)", (r["hour"] + pd.Timedelta(minutes=25), r["delta"]),
                     xytext=(0, 14), textcoords="offset points", ha="center", fontsize=10, color=C_BAD, fontweight="bold",
                     arrowprops=dict(arrowstyle="-", color=C_BAD, lw=0.9))
axd.set_ylim(min(dl.min() * 1.3, -0.3), dl.max() * 1.55)
tot_bad, tot_good = hr["delta"].clip(lower=0).sum(), hr["delta"].clip(upper=0).sum()
axd.text(0.005, 0.97, f"week: worse +{tot_bad:.1f} kWh · better {tot_good:.1f} kWh · net {tot_bad + tot_good:+.1f} kWh",
         transform=axd.transAxes, ha="left", va="top", fontsize=10.5, fontweight="bold", color="#334155")
plt.setp(axd.get_xticklabels(), visible=False)
ax1.legend(handles=[Line2D([], [], color=C_ST, lw=2.2, label="Sun-tracking"),
                    Line2D([], [], color=C_S1, lw=2.2, label="TiDE Strategy 1")],
           loc="upper right", ncol=2, fontsize=10, frameon=False)
plt.setp(ax1.get_xticklabels(), visible=False)

# ---- (b) chosen angles, with the red windows repeated
ax2.step(x, hr["aST"], where="post", color=C_ST, lw=1.8, label="Sun-tracking")
ax2.step(x, hr["aS1"], where="post", color=C_S1, lw=1.8, label="TiDE Strategy 1")
bad = hr["delta"].values > 0
for i in np.where(bad)[0]:
    ax2.axvspan(x[i], x[i] + np.timedelta64(1, "h"), color=C_BAD, alpha=0.14, lw=0)
ax2.set_ylim(-3, 93)
ax2.set_yticks([0, 30, 60, 90])
ax2.set_ylabel("Angle [°]", fontsize=12)
ax2.set_title("Chosen angle (red band = hours where TiDE is worse)", fontsize=13.5, fontweight="bold", loc="left", pad=6)
ax2.grid(axis="y", ls="--", alpha=0.3)
ax2.xaxis.set_major_locator(mdates.DayLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
ax2.legend(loc="upper right", ncol=2, fontsize=10, frameon=False)

# ---- (c) annual cumulative difference: expected (fixed-angle data) vs realised (simulation)
tt = d["t"]
for k, c, lab in [("S1", C_S1, "TiDE Strategy 1"), ("S2", C_S2, "TiDE Strategy 2")]:
    ax3.plot(tt, d[f"real_{k}"].cumsum(), color=c, lw=2.2, label=f"{lab} · realised (simulation)")
ax3.plot(tt, d["exp_S1"].cumsum(), color=C_S1, lw=2.0, ls="--", label="TiDE Strategy 1 · expected (fixed-angle data, no inertia)")
ax3.fill_between(tt, d["exp_S1"].cumsum(), d["real_S1"].cumsum(), color=C_BAD, alpha=0.22, lw=0,
                 label="gap = gain lost to inertia and switching")
ax3.axhline(0, color="#64748b", lw=0.9)
ax3.axvspan(pd.Timestamp(WEEK[0]), pd.Timestamp(WEEK[1]), color="#94a3b8", alpha=0.35, lw=0)
ax3.text(pd.Timestamp("2026-07-24"), ax3.get_ylim()[1], "week shown above", ha="center", va="top", fontsize=9, color="#475569")
end = tt.iloc[-1]
for val, c, dy in [(d["exp_S1"].sum(), C_S1, -2), (d["real_S1"].sum(), C_S1, 2), (d["real_S2"].sum(), C_S2, -14)]:
    ax3.annotate(f"{val:,.0f}", (end, val), xytext=(6, dy), textcoords="offset points", fontsize=10,
                 fontweight="bold", color=c, va="center", annotation_clip=False)
ax3.set_ylabel("Cumulative net-energy difference\nTiDE − sun-tracking [kWh]", fontsize=12)
ax3.set_title("Over the year: the expected gain shrinks once the schedule runs in the simulation",
              fontsize=14.5, fontweight="bold", loc="left", pad=10)
ax3.xaxis.set_major_locator(mdates.MonthLocator())
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax3.grid(axis="y", ls="--", alpha=0.3)
ax3.legend(loc="lower left", fontsize=9.5, frameon=False)
ax3.set_xlim(tt.iloc[0], tt.iloc[-1] + pd.Timedelta(days=12))

fig.suptitle("TiDE vs sun-tracking BIPV: net energy = cooling/3.0 + heating/2.5 − PV (lower is better)",
             fontsize=15.5, fontweight="bold", y=0.93)
out_png = PLOT_DIR / "fig40_tide_vs_suntracking_net_timeseries.png"
out_svg = PLOT_DIR / "fig40_tide_vs_suntracking_net_timeseries.svg"
fig.savefig(out_png, dpi=300, transparent=False, facecolor="white", bbox_inches="tight")
fig.savefig(out_svg, format="svg", facecolor="white", bbox_inches="tight")
plt.close(fig)

print("annual real S1/S2, expected S1:", round(d["real_S1"].sum()), round(d["real_S2"].sum()), round(d["exp_S1"].sum()))
print(f"[OK] {out_png}")

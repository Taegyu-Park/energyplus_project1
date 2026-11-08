import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import dartwork_mpl as dm

mpl.rcParams['svg.fonttype'] = 'none'
dm.style.use("presentation")
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PLOT_DIR = SCRIPT_DIR.parent / "plot" / "fig38_2_tide_representative_weeks_energy_comparison"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

CA = PROJECT_ROOT / "case_analysis"
SQL_PATHS = {
    "Kinetic (Sun-Tracking)": CA / "bipv_variation" / "5zone_NSEW_korean" / "case3_v3_south" / "eplusout.sql",
    "TiDE Strategy 1": CA / "case3_v3_south_tide" / "eplusout.sql",
    "TiDE Strategy 2": CA / "case3_v3_south_tide_strategy2" / "eplusout.sql",
}
COLORS = {
    "Kinetic (Sun-Tracking)": "#f59e0b",
    "TiDE Strategy 1": "#2563eb",
    "TiDE Strategy 2": "#10b981",
}
# Representative weeks (7 days each) containing the fig37 days (12/26, 7/21)
WEEKS = [
    ("Winter week (12/23 - 12/29)", 12, 23, 29),
    ("Summer week (7/18 - 7/24)", 7, 18, 24),
]
VARS = {
    "Zone Ideal Loads Supply Air Total Cooling Energy": "cool",
    "Zone Ideal Loads Supply Air Total Heating Energy": "heat",
    "Facility Total Produced Electricity Energy": "pv",
}
COP_COOL, COP_HEAT = 3.0, 2.5


def load_week(sql_path, month, d0, d1):
    names = ",".join(f"'{n}'" for n in VARS)
    q = f"""
    SELECT t.Month m, t.Day d, t.Hour h, t.Minute mi, dd.Name n, SUM(r.Value) / 3.6e6 v
    FROM ReportData r
    JOIN ReportDataDictionary dd USING (ReportDataDictionaryIndex)
    JOIN Time t USING (TimeIndex)
    WHERE dd.Name IN ({names}) AND t.WarmupFlag = 0
      AND t.Month = {month} AND t.Day BETWEEN {d0} AND {d1}
    GROUP BY 1, 2, 3, 4, 5
    """
    con = sqlite3.connect(f"file:{sql_path}?mode=ro", uri=True)
    df = pd.read_sql(q, con)
    con.close()
    df["n"] = df["n"].map(VARS)
    wide = df.pivot_table(index=["m", "d", "h", "mi"], columns="n", values="v", aggfunc="sum").fillna(0.0).reset_index()
    # E+ timestamps mark the END of each 10-min interval -> bin into hours by interval end
    wide["t"] = pd.to_datetime(dict(year=2026, month=wide.m, day=wide.d)) + pd.to_timedelta(wide.h * 60 + wide.mi, unit="min")
    wide = wide.sort_values("t").set_index("t")[["cool", "heat", "pv"]]
    wide = wide.resample("1h", label="right", closed="right").sum()
    wide = wide.iloc[:168]
    wide["hvac"] = wide["cool"] / COP_COOL + wide["heat"] / COP_HEAT
    wide["net"] = wide["hvac"] - wide["pv"]
    return wide


data = {(w[0], k): load_week(p, w[1], w[2], w[3]) for w in WEEKS for k, p in SQL_PATHS.items()}

fig, axes = plt.subplots(2, 2, figsize=(18, 10), dpi=300, gridspec_kw={"width_ratios": [2.3, 1]})

cats = ["Heating\n(Thermal)", "Cooling\n(Thermal)", "PV Gen.", "HVAC Elec.", "Net Energy"]
keys = ["heat", "cool", "pv", "hvac", "net"]

for r, (title, month, d0, d1) in enumerate(WEEKS):
    ax_ts, ax_bar = axes[r]
    for k in SQL_PATHS:
        df = data[(title, k)]
        ax_ts.plot(df.index, df["net"], color=COLORS[k], linewidth=1.5, alpha=0.9, label=k)
    ax_ts.axhline(0, color="#64748b", linewidth=1.0, alpha=0.8)
    ax_ts.set_title(f"{title}: Hourly Net Energy (HVAC Elec. - PV)", fontsize=13.5, fontweight="bold", pad=10)
    ax_ts.set_ylabel("Net Energy [kWh/h]", fontsize=12, fontweight="bold")
    ax_ts.xaxis.set_major_locator(mdates.DayLocator())
    ax_ts.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax_ts.grid(True, linestyle=":", alpha=0.45)
    if r == 0:
        ax_ts.legend(loc="upper right", fontsize=10.5, framealpha=0, ncols=3)

    x = np.arange(len(cats))
    bw = 0.26
    for i, k in enumerate(SQL_PATHS):
        df = data[(title, k)]
        vals = [df[c].sum() for c in keys]
        pos = x + (i - 1) * bw
        ax_bar.bar(pos, vals, bw, color=COLORS[k], alpha=0.92, edgecolor="none", label=k)
        for p, v in zip(pos, vals):
            ax_bar.annotate(f"{v:,.0f}", (p, v), xytext=(0, 3 if v >= 0 else -3), textcoords="offset points",
                            ha="center", va="bottom" if v >= 0 else "top", fontsize=7.5, fontweight="bold", color=COLORS[k])
    ax_bar.axhline(0, color="#64748b", linewidth=1.0, alpha=0.8)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(cats, fontsize=9.5)
    ax_bar.set_title(f"{title}: Weekly Totals [kWh]", fontsize=13.5, fontweight="bold", pad=10)
    ax_bar.grid(axis="y", linestyle="--", alpha=0.35)
    ax_bar.set_axisbelow(True)

fig.suptitle("Representative Weeks: Kinetic (Sun-Tracking) vs TiDE Strategy 1 vs Strategy 2 (South BIPV)",
             fontsize=15.5, fontweight="bold", y=1.0)
plt.tight_layout()

out_png = PLOT_DIR / "fig38_2_tide_representative_weeks_energy_comparison.png"
out_svg = PLOT_DIR / "fig38_2_tide_representative_weeks_energy_comparison.svg"
fig.savefig(out_png, dpi=300, transparent=True, bbox_inches="tight")
fig.savefig(out_svg, format="svg", transparent=True, bbox_inches="tight")
plt.close(fig)

for (title, k), df in data.items():
    print(title, k, len(df), {c: round(df[c].sum()) for c in keys})
print(f"[OK] {out_png}")

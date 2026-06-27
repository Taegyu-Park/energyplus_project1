"""
Net Energy Analysis for BIPV Simulation Cases
- Case 1: Base model (no shading, no BIPV)
- Case 2: Static BIPV at 0-90 deg (10 deg intervals)
- Case 3: Kinetic BIPV (solar altitude tracking)

Net Energy = Heating + Cooling - PV Generation
"""

import sqlite3
from pathlib import Path

import dartwork_mpl as dm
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

dm.style.use("presentation")
plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

# ── paths ──────────────────────────────────────────────────────────────────────
BASE = Path("C:/Users/taegyu/Codes/EnergyPlus_Project1")
RUN = BASE / "run_analysis"
OUT = BASE / "plot_py/figure/net_energy_analysis"

# ── colors (dartwork-mpl palette) ──────────────────────────────────────────────
C_HEAT = "oc.blue6"
C_COOL = "oc.yellow6"
C_PV   = "oc.orange7"
C_NET  = "oc.red6"
C_BASE = "oc.gray6"
C_PV_GREEN = "oc.green6"

# ── COPs for EHP system ────────────────────────────────────────────────────────
COP_HEATING = 2.5
COP_COOLING = 3.0

ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
J_TO_MWH = 1 / 3.6e9

MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


# ── data loaders ───────────────────────────────────────────────────────────────

def parse_datetime(series: pd.Series) -> pd.Series:
    """Convert EnergyPlus ' MM/DD  HH:MM:SS' strings to datetime."""
    cleaned = series.str.strip()
    # EnergyPlus uses 24:00:00 for midnight next day – fix before parsing
    cleaned = cleaned.str.replace(r"\s+24:00:00", " 00:00:00", regex=True)
    return pd.to_datetime("2023/" + cleaned, format="%Y/%m/%d  %H:%M:%S", errors="coerce")


def load_case1_monthly():
    """Monthly heating, cooling (MWh) for case1. PV=0."""
    df = pd.read_csv(RUN / "case1/case1.csv", skiprows=0)
    df.columns = df.columns.str.strip()
    dt_col = df.columns[0]
    df["dt"] = parse_datetime(df[dt_col])
    df = df.dropna(subset=["dt"])
    df["month"] = df["dt"].dt.month

    heat_cols = [c for c in df.columns if "Heating Energy" in c]
    cool_cols = [c for c in df.columns if "Cooling Energy" in c]

    monthly = df.groupby("month").agg(
        heating=pd.NamedAgg(column=heat_cols[0], aggfunc="sum"),
        heating2=pd.NamedAgg(column=heat_cols[1], aggfunc="sum"),
        cooling=pd.NamedAgg(column=cool_cols[0], aggfunc="sum"),
        cooling2=pd.NamedAgg(column=cool_cols[1], aggfunc="sum"),
    ).reset_index()
    monthly["heating_MWh"] = (monthly["heating"] + monthly["heating2"]) * J_TO_MWH / COP_HEATING
    monthly["cooling_MWh"] = (monthly["cooling"] + monthly["cooling2"]) * J_TO_MWH / COP_COOLING
    monthly["pv_MWh"] = 0.0
    monthly["net_MWh"] = monthly["heating_MWh"] + monthly["cooling_MWh"]
    return monthly[["month", "heating_MWh", "cooling_MWh", "pv_MWh", "net_MWh"]]


def load_case2_annual_from_sql(angle: int):
    """Annual totals (MWh) for one case2 angle via SQLite."""
    folder_map = {0: "0_v2"}
    folder = folder_map.get(angle, f"{angle}")
    sql_path = RUN / f"case2/{folder}/eplusout.sql"

    conn = sqlite3.connect(sql_path)
    rows = conn.execute("""
        SELECT rd.Name, SUM(r.Value)
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
        GROUP BY rd.Name
    """).fetchall()
    conn.close()

    data = {name: val * J_TO_MWH for name, val in rows}
    heating = data.get("Zone Ideal Loads Supply Air Total Heating Energy", 0) / COP_HEATING
    cooling = data.get("Zone Ideal Loads Supply Air Total Cooling Energy", 0) / COP_COOLING
    pv = data.get("Facility Total Produced Electricity Energy", 0)
    return {"heating_MWh": heating, "cooling_MWh": cooling, "pv_MWh": pv,
            "net_MWh": heating + cooling - pv}


def load_case2_monthly_from_sql(angle: int):
    """Monthly totals (MWh) for one case2 angle via SQLite."""
    folder_map = {0: "0_v2"}
    folder = folder_map.get(angle, f"{angle}")
    sql_path = RUN / f"case2/{folder}/eplusout.sql"

    conn = sqlite3.connect(sql_path)
    rows = conn.execute("""
        SELECT t.Month, rd.Name, SUM(r.Value)
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
        GROUP BY t.Month, rd.Name
    """).fetchall()
    conn.close()

    records = {}
    for month, name, val in rows:
        if month not in records:
            records[month] = {"heating_MWh": 0, "cooling_MWh": 0, "pv_MWh": 0}
        if "Heating" in name:
            records[month]["heating_MWh"] += val * J_TO_MWH / COP_HEATING
        elif "Cooling" in name:
            records[month]["cooling_MWh"] += val * J_TO_MWH / COP_COOLING
        elif "Produced" in name:
            records[month]["pv_MWh"] += val * J_TO_MWH

    monthly = []
    for m in range(1, 13):
        r = records.get(m, {"heating_MWh": 0, "cooling_MWh": 0, "pv_MWh": 0})
        r["month"] = m
        r["net_MWh"] = r["heating_MWh"] + r["cooling_MWh"] - r["pv_MWh"]
        monthly.append(r)
    return pd.DataFrame(monthly)


def load_case3_monthly():
    """Monthly heating, cooling, PV (MWh) for case3 from eplusout.csv."""
    csv_path = RUN / "case3/eplusout.csv"
    df = pd.read_csv(csv_path, skiprows=0, low_memory=False)
    df.columns = df.columns.str.strip()

    # skip first 4 metadata columns (Latitude, Day of Sim, etc.)
    dt_col = df.columns[0]
    df["dt"] = parse_datetime(df[dt_col])
    df = df.dropna(subset=["dt"])
    df["month"] = df["dt"].dt.month

    heat_cols = [c for c in df.columns if "Heating Energy" in c]
    cool_cols = [c for c in df.columns if "Cooling Energy" in c]
    pv_col = "Whole Building:Facility Total Produced Electricity Energy"

    for col in heat_cols + cool_cols + [pv_col]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    monthly = df.groupby("month").apply(
        lambda g: pd.Series({
            "heating_MWh": sum(g[c].sum() for c in heat_cols) * J_TO_MWH / COP_HEATING,
            "cooling_MWh": sum(g[c].sum() for c in cool_cols) * J_TO_MWH / COP_COOLING,
            "pv_MWh": g[pv_col].sum() * J_TO_MWH,
        })
    ).reset_index()
    monthly["net_MWh"] = monthly["heating_MWh"] + monthly["cooling_MWh"] - monthly["pv_MWh"]
    return monthly


# ── load all data ──────────────────────────────────────────────────────────────
print("Loading Case 1...")
c1_monthly = load_case1_monthly()

print("Loading Case 2 (all angles)...")
c2_annual = {}
c2_monthly_data = {}
for ang in ANGLES:
    print(f"  angle {ang}°")
    c2_annual[ang] = load_case2_annual_from_sql(ang)
    c2_monthly_data[ang] = load_case2_monthly_from_sql(ang)

print("Loading Case 3...")
c3_monthly = load_case3_monthly()

# Annual aggregates
c1_annual = {
    "heating_MWh": c1_monthly["heating_MWh"].sum(),
    "cooling_MWh": c1_monthly["cooling_MWh"].sum(),
    "pv_MWh": 0,
    "net_MWh": c1_monthly["net_MWh"].sum(),
}
c3_annual = {
    "heating_MWh": c3_monthly["heating_MWh"].sum(),
    "cooling_MWh": c3_monthly["cooling_MWh"].sum(),
    "pv_MWh": c3_monthly["pv_MWh"].sum(),
    "net_MWh": c3_monthly["net_MWh"].sum(),
}

# Find best (minimum net) angle in case2
best_angle = min(c2_annual, key=lambda a: c2_annual[a]["net_MWh"])
print(f"\nBest Case2 angle: {best_angle}° "
      f"(net {c2_annual[best_angle]['net_MWh']:.1f} MWh)")
print(f"Case1 net: {c1_annual['net_MWh']:.1f} MWh")
print(f"Case3 net: {c3_annual['net_MWh']:.1f} MWh")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 1: Annual Net Energy – all cases
# ═══════════════════════════════════════════════════════════════════════════════
print("\nPlotting Figure 1: Annual Net Energy...")

fig, ax = plt.subplots(figsize=dm.figsize('23cm', '13cm'))

labels = ["Case 1\n(Base)"] + [f"Case 2\n{a}°" for a in ANGLES] + ["Case 3\n(Kinetic)"]
gross_vals = (
    [c1_annual["heating_MWh"] + c1_annual["cooling_MWh"]]
    + [c2_annual[a]["heating_MWh"] + c2_annual[a]["cooling_MWh"] for a in ANGLES]
    + [c3_annual["heating_MWh"] + c3_annual["cooling_MWh"]]
)
net_vals = (
    [c1_annual["net_MWh"]]
    + [c2_annual[a]["net_MWh"] for a in ANGLES]
    + [c3_annual["net_MWh"]]
)

x = np.arange(len(labels))

# 1. 발전량 제외 전 (Gross HVAC) 바 — PV Generation 색
bars_gross = ax.bar(x, gross_vals, color=C_PV_GREEN, width=0.65, zorder=2)

# 2. 순 소비 바 — 모두 Case 2 색(C_HEAT) 통일
bars_net = ax.bar(x, net_vals, color=C_HEAT, width=0.65, zorder=3)

# 수치 표시 레이블
for i in range(len(labels)):
    g_val = gross_vals[i]
    n_val = net_vals[i]

    ax.text(x[i], n_val + 0.8, f"{n_val:.1f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    if g_val > n_val + 1.0:
        ax.text(x[i], g_val + 0.8, f"{g_val:.1f}", ha="center", va="bottom", fontsize=8.5, color="oc.green9")

ax.axhline(0, color="black", linewidth=0.6, zorder=4)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylim(0, 58)
ax.set_ylabel("Annual Electricity Consumption [MWh]")
ax.set_title("Annual Electricity Consumption by Case\n(HVAC Electricity − BIPV Generation)", fontweight="bold")

patches = [
    mpatches.Patch(color=C_HEAT,     label="HVAC Load (Net)"),
    mpatches.Patch(color=C_PV_GREEN, label="PV Generation"),
]
ax.legend(handles=patches, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.15), borderaxespad=0, fontsize=9)

fig.savefig(OUT / "fig1_annual_net_energy.png", dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(OUT / "fig1_annual_net_energy.svg", bbox_inches="tight", transparent=True)
plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 2: Energy Decomposition (Heating / Cooling / PV)
# ═══════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 2: Energy Decomposition...")

fig, ax = plt.subplots(figsize=dm.figsize('23cm', '13cm'))

case_labels = ["Case 1\n(Base)"] + [f"Case 2\n{a}°" for a in ANGLES] + ["Case 3\n(Kinetic)"]
x = np.arange(len(case_labels))
w = 0.65

heating_vals = (
    [c1_annual["heating_MWh"]]
    + [c2_annual[a]["heating_MWh"] for a in ANGLES]
    + [c3_annual["heating_MWh"]]
)
cooling_vals = (
    [c1_annual["cooling_MWh"]]
    + [c2_annual[a]["cooling_MWh"] for a in ANGLES]
    + [c3_annual["cooling_MWh"]]
)
pv_vals = (
    [0]
    + [c2_annual[a]["pv_MWh"] for a in ANGLES]
    + [c3_annual["pv_MWh"]]
)

ax.bar(x, heating_vals, width=w, label="Heating Load", color=C_HEAT, zorder=3)
ax.bar(x, cooling_vals, width=w, bottom=heating_vals,
       label="Cooling Load", color=C_COOL, zorder=3)
ax.bar(x, [-v for v in pv_vals], width=w,
       label="PV Generation", color=C_PV_GREEN, zorder=3)

# net energy dots
net_vals2 = [h + c - p for h, c, p in zip(heating_vals, cooling_vals, pv_vals)]
ax.scatter(x, net_vals2, color=C_NET, s=18, zorder=5, label="Net Energy")
ax.plot(x, net_vals2, color=C_NET, linewidth=0.8, zorder=4, linestyle="--")

ax.axhline(0, color="black", linewidth=0.5, zorder=4)
ax.set_xticks(x)
ax.set_xticklabels(case_labels, fontsize=9)
ax.set_ylabel("Energy [MWh]")
ax.set_title("Annual Heating, Cooling and PV Energy Decomposition")
ax.legend(fontsize=9, loc="upper right")

fig.savefig(OUT / "fig2_energy_decomposition.png", dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(OUT / "fig2_energy_decomposition.svg", bbox_inches="tight", transparent=True)
plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 3: Monthly Net Energy – Case1 vs Case2 vs Case3
# ═══════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 3: Monthly Net Energy Comparison...")

fig, ax = plt.subplots(figsize=dm.figsize('23cm', '13cm'))

months = np.arange(1, 13)
c2_90_monthly = c2_monthly_data[90]

ax.plot(months, c1_monthly["net_MWh"], marker="o", markersize=3.5,
        color=C_BASE, linewidth=1.2, label="Case 1 (Base)")
ax.plot(months, c2_90_monthly["net_MWh"], marker="s", markersize=3.5,
        color=C_HEAT, linewidth=1.2, label="Case 2 (Fixed-90°)")
ax.plot(months, c3_monthly["net_MWh"], marker="^", markersize=3.5,
        color=C_PV, linewidth=1.2, label="Case 3 (Kinetic BIPV)")

ax.fill_between(months, c1_monthly["net_MWh"], c3_monthly["net_MWh"],
                alpha=0.08, color=C_PV, label="_nolegend_")

ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
ax.set_xticks(months)
ax.set_xticklabels(MONTH_LABELS)
ax.set_ylabel("Net Energy [MWh]")
ax.set_title("Monthly Net Energy Comparison\n(Thermal Load − BIPV Generation)")
ax.legend(fontsize=9)

fig.savefig(OUT / "fig3_monthly_net_energy.png", dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(OUT / "fig3_monthly_net_energy.svg", bbox_inches="tight", transparent=True)
plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 4: Monthly Stacked Breakdown – 3 key cases side-by-side
# ═══════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 4: Monthly stacked breakdown...")

fig, axes = plt.subplots(1, 3, figsize=dm.figsize('23cm', '10cm'))

cases = {
    "Case 1\n(Base)": c1_monthly,
    "Case 2\n(Fixed-90°)": c2_90_monthly,
    "Case 3\n(Kinetic)": c3_monthly,
}

for ax, (title, mdf) in zip(axes, cases.items()):
    months_x = np.arange(12)
    ax.bar(months_x, mdf["heating_MWh"], color=C_HEAT, label="Heating", width=0.8)
    ax.bar(months_x, mdf["cooling_MWh"], bottom=mdf["heating_MWh"],
           color=C_COOL, label="Cooling", width=0.8)
    ax.bar(months_x, -mdf["pv_MWh"], color=C_PV_GREEN, label="PV Generation", width=0.8)
    ax.plot(months_x, mdf["net_MWh"], color=C_NET, linewidth=1.0,
            marker="o", markersize=2.5, label="Net Energy")
    ax.axhline(0, color="black", linewidth=0.4, linestyle="--")
    ax.set_xticks(months_x)
    ax.set_xticklabels(["J","F","M","A","M","J","J","A","S","O","N","D"], fontsize=8.5)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel("Energy [MWh]" if ax is axes[0] else "")

axes[0].legend(fontsize=7.5, loc="upper right")
fig.suptitle("Monthly Energy Decomposition Comparison (HVAC Electricity & BIPV Generation)", y=1.02)

fig.savefig(OUT / "fig4_monthly_breakdown.png", dpi=300, bbox_inches="tight", transparent=True)
fig.savefig(OUT / "fig4_monthly_breakdown.svg", bbox_inches="tight", transparent=True)
plt.close()

print("\n완료! 저장 위치:", OUT)
print("생성 파일:")
for f in sorted(OUT.glob("*.png")):
    print(f"  {f.name}")


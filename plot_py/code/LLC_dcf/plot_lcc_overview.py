"""
Kinetic BIPV Life Cycle Cost (LCC) Analysis — DCF-based
2-panel figure:
  Left  : Cumulative NPV trajectory (연도별 누적 할인 현금흐름)
  Right : Present-value cost/benefit waterfall (비용 구성 분해)
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import dartwork_mpl as dm

# ── 경로 ────────────────────────────────────────────────────────────
script_dir   = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(script_dir, "..", "..", ".."))
figure_dir   = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "LLC_dcf"))
csv2_path    = os.path.join(project_root, "economy_analysis_2.csv")
os.makedirs(figure_dir, exist_ok=True)

# ── CSV 파싱 ─────────────────────────────────────────────────────────
def pv(text):
    t = text.strip().replace('"', '').replace(',', '')
    if not t or t == '-':
        return 0.0
    try:
        return float(t)
    except ValueError:
        return 0.0

years, cum_disc = [], []
savings_disc = 0.0
om_disc      = 0.0
rep_disc     = 0.0
capex        = 0.0

with open(csv2_path, encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader); next(reader); next(reader)   # title / blank / header
    for row in reader:
        yr_str = row[0].strip().lstrip('﻿')
        if not yr_str.isdigit():
            continue
        yr = int(yr_str)
        years.append(yr)
        cum_disc.append(pv(row[11]))

        if yr == 0:
            capex = abs(pv(row[8]))            # CAPEX (양수로)
        else:
            df = pv(row[9])
            savings_disc += pv(row[5]) * df
            om_disc      += pv(row[6]) * df
            rep_disc     += pv(row[7]) * df

years        = np.array(years)
cum_disc_M   = np.array(cum_disc) / 1e6       # Million KRW
capex_M      = capex      / 1e6
savings_M    = savings_disc / 1e6
om_M         = om_disc     / 1e6
rep_M        = rep_disc    / 1e6
npv_M        = cum_disc_M[-1]                  # 25년 최종 NPV

# 할인 회수기간 보간
pb_yr = None
for i in range(1, len(years)):
    if cum_disc_M[i - 1] < 0 <= cum_disc_M[i]:
        t0, t1 = years[i - 1], years[i]
        v0, v1 = cum_disc_M[i - 1], cum_disc_M[i]
        pb_yr = t0 + abs(v0) / (v1 - v0)
        break

print(f"CAPEX          = {capex_M:.2f} M KRW")
print(f"PV(savings)    = {savings_M:.2f} M KRW")
print(f"PV(O&M)        = {om_M:.2f} M KRW")
print(f"PV(replacement)= {rep_M:.2f} M KRW")
print(f"25yr NPV       = {npv_M:.2f} M KRW")
print(f"Payback period = {pb_yr:.2f} years")

# ── 스타일 ──────────────────────────────────────────────────────────
dm.style.use("presentation")
plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

fig, (ax_l, ax_r) = plt.subplots(
    1, 2,
    figsize=dm.figsize("29cm", "15cm"),
    gridspec_kw={"width_ratios": [1.6, 1], "wspace": 0.38},
)

# ══════════════════════════════════════════════════════════════════
# 왼쪽: 누적 할인 현금흐름 (NPV Trajectory)
# ══════════════════════════════════════════════════════════════════
C_LINE  = "oc.blue7"
C_NEG   = "oc.red3"
C_POS   = "oc.blue2"
C_ZERO  = "oc.gray5"
C_PB    = "oc.red6"
C_REP   = "oc.orange7"

ax_l.fill_between(years, cum_disc_M, 0,
                  where=(cum_disc_M < 0), color=C_NEG, alpha=0.12, linewidth=0)
ax_l.fill_between(years, cum_disc_M, 0,
                  where=(cum_disc_M >= 0), color=C_POS, alpha=0.18, linewidth=0)

ax_l.plot(years, cum_disc_M, color=C_LINE, lw=dm.lw(2.0), zorder=3,
          label="Cumulative Discounted Cash Flow")
ax_l.axhline(0, color=C_ZERO, linestyle="--", lw=dm.lw(0.8), zorder=2)

# 회수기간 마커
if pb_yr is not None:
    ax_l.axvline(pb_yr, color=C_PB, linestyle=":", lw=dm.lw(1.2), zorder=2)
    ax_l.plot(pb_yr, 0, marker="o", color=C_PB, markersize=7, zorder=4)
    ax_l.text(pb_yr + 0.5, cum_disc_M.min() * 0.15,
              f"Discounted\nPayback: {pb_yr:.1f} yr",
              color=C_PB, fontsize=10.5, fontweight="bold", va="bottom")

# 12년차 교체 이벤트
yr12_idx = list(years).index(12)
ax_l.plot(12, cum_disc_M[yr12_idx], marker="x", color=C_REP,
          markersize=9, mew=2, zorder=4)
ax_l.annotate("Actuator\nReplacement\n(Year 12)",
              xy=(12, cum_disc_M[yr12_idx]),
              xytext=(9.5, cum_disc_M[yr12_idx] - 8),
              fontsize=9.5, color=C_REP, ha="right",
              arrowprops=dict(arrowstyle="->", color=C_REP, lw=1.2))

# 25년 최종 NPV 주석
ax_l.annotate(f"25-yr NPV\n= +{npv_M:.1f} M KRW",
              xy=(25, npv_M),
              xytext=(21.5, npv_M - 7),
              fontsize=10.5, color=C_LINE, fontweight="bold",
              arrowprops=dict(arrowstyle="->", color=C_LINE, lw=1.2))

ax_l.set_xlabel("Project Timeline [Years]")
ax_l.set_ylabel("Cumulative NPV [Million KRW]")
ax_l.set_title("Cumulative Discounted Cash Flow\n& Discounted Payback Period",
               fontweight="bold")
ax_l.set_xlim(0, 25)
ax_l.set_xticks(range(0, 26, 5))
ax_l.legend(loc="lower right", fontsize=10)

# ══════════════════════════════════════════════════════════════════
# 오른쪽: 현재가치 구성 분해 (Waterfall — costs → savings → net NPV)
# ══════════════════════════════════════════════════════════════════
labels = [
    "Initial\nCAPEX",
    "O&M\n(PV)",
    "Actuator\nReplacement\n(PV)",
    "Electricity\nSavings (PV)",
    "Net NPV\n(25 yr)",
]
values   = [-capex_M, -om_M, -rep_M, savings_M, npv_M]
colors_w = ["oc.red7", "oc.orange6", "oc.orange4", "oc.teal6", "oc.blue7"]

# 워터폴: 누적 시작점 계산
bottoms = [0.0] * len(values)
running = 0.0
for i, v in enumerate(values[:-1]):
    if v < 0:
        bottoms[i] = running + v
    else:
        bottoms[i] = running
    running += v
# 마지막 바 (Net NPV)는 항상 0에서 시작
bottoms[-1] = min(running, 0.0) if npv_M < 0 else 0.0

bars = ax_r.bar(
    range(len(labels)),
    [abs(v) if i < len(values) - 1 else v for i, v in enumerate(values)],
    bottom=[b for b in bottoms],
    color=colors_w,
    width=0.55,
    edgecolor="white",
    linewidth=0.8,
)

# 각 바 위/아래에 값 표시
for i, (bar, v) in enumerate(zip(bars, values)):
    y_top = bar.get_y() + bar.get_height()
    y_bot = bar.get_y()
    sign  = "+" if v >= 0 else "−"
    label_y = y_top + 0.5 if v >= 0 else y_bot - 0.5
    va      = "bottom"  if v >= 0 else "top"
    ax_r.text(bar.get_x() + bar.get_width() / 2, label_y,
              f"{sign}{abs(v):.1f}",
              ha="center", va=va, fontsize=10.5, fontweight="bold",
              color=colors_w[i])

# 구분선 (Net NPV 앞)
ax_r.axvline(len(values) - 1.5, color="oc.gray4",
             linestyle=":", lw=dm.lw(0.8))

ax_r.axhline(0, color=C_ZERO, linestyle="--", lw=dm.lw(0.8))
ax_r.set_xticks(range(len(labels)))
ax_r.set_xticklabels(labels, fontsize=9.5)
ax_r.set_ylabel("Present Value [Million KRW]")
ax_r.set_title("LCC Component Breakdown\n(Discounted to Year 0, r = 5.5%)",
               fontweight="bold")

# 범례 패치
legend_patches = [
    mpatches.Patch(color="oc.red7",    label=f"CAPEX  {capex_M:.1f} M"),
    mpatches.Patch(color="oc.orange6", label=f"O&M    {om_M:.1f} M"),
    mpatches.Patch(color="oc.orange4", label=f"Replacement  {rep_M:.1f} M"),
    mpatches.Patch(color="oc.teal6",   label=f"Savings  {savings_M:.1f} M"),
]
ax_r.legend(handles=legend_patches, loc="lower right",
            fontsize=9, handlelength=1.2)

# ── 저장 ─────────────────────────────────────────────────────────
dm.simple_layout(fig)
fig.savefig(os.path.join(figure_dir, "lcc_dcf_overview.png"), dpi=300, transparent=True)
fig.savefig(os.path.join(figure_dir, "lcc_dcf_overview.svg"), transparent=True)
plt.close(fig)
print(f"\nSaved: {figure_dir}/lcc_dcf_overview.{{png,svg}}")

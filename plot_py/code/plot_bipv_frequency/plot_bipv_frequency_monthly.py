"""
BIPV Monthly Operation Hours — Stacked Bar Chart
Case 3 Kinetic BIPV: 각도별 월간 운전 시간 적산
"""

import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# ── 경로 ────────────────────────────────────────────────────────────
project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
db_path      = os.path.join(project_root, "run_analysis", "model_realscale_case3", "eplusout.sql")
output_dir   = os.path.join(project_root, "plot_py", "figure", "plot_bipv_frequency")
os.makedirs(output_dir, exist_ok=True)

# ── DB 로드 ─────────────────────────────────────────────────────────
conn = sqlite3.connect(db_path)
c    = conn.cursor()

c.execute("""
    SELECT ReportDataDictionaryIndex FROM ReportDataDictionary
    WHERE KeyValue='Environment' AND Name='Site Solar Altitude Angle'
      AND ReportingFrequency='Zone Timestep'
""")
alt_idx = c.fetchone()[0]

c.execute("""
    SELECT ReportDataDictionaryIndex FROM ReportDataDictionary
    WHERE KeyValue='Whole Building'
      AND Name='Facility Total Produced Electricity Energy'
      AND ReportingFrequency='Zone Timestep'
""")
pv_idx = c.fetchone()[0]

c.execute("""
    SELECT TimeIndex, Month, Hour, Minute FROM Time
    WHERE WarmupFlag=0 ORDER BY TimeIndex
""")
time_rows = c.fetchall()

val_map = dict(c.execute("SELECT TimeIndex, Value FROM ReportData WHERE ReportDataDictionaryIndex=?", (alt_idx,)))
pv_map  = dict(c.execute("SELECT TimeIndex, Value FROM ReportData WHERE ReportDataDictionaryIndex=?", (pv_idx,)))
conn.close()

# ── 각도 계산 (T-1 지연, 발전 중인 스텝만) ──────────────────────────
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]

def get_best_angle(sun_alt):
    if sun_alt <= 0:
        return 0
    return min(ANGLES, key=lambda x: abs(x - sun_alt))

prev_alt = 0.0
monthly_hours = np.zeros((12, 10))

for time_idx, month, hour, minute in time_rows:
    pv_gen = pv_map.get(time_idx, 0.0)
    if pv_gen > 100.0:
        angle   = get_best_angle(prev_alt)
        ang_idx = int(angle // 10)
        monthly_hours[month - 1, ang_idx] += 1.0 / 6.0   # 10분 → 시간
    prev_alt = val_map.get(time_idx, 0.0)

print(f"총 처리 타임스텝: {len(time_rows)}")
print(f"월별 총 운전시간: {np.sum(monthly_hours, axis=1).astype(int)} h")

# ── 색상 ────────────────────────────────────────────────────────────
colors = [
    "#64748b",  # 0°
    "#ffe8cc",  # 10°
    "#ffd8a8",  # 20°
    "#ffc078",  # 30°
    "#ffa94d",  # 40°
    "#ff922b",  # 50°
    "#fd7e14",  # 60°
    "#f76707",  # 70°
    "#e8590c",  # 80°
    "#d9480f",  # 90°
]

# ── 플롯 ────────────────────────────────────────────────────────────
dm.style.use("presentation")
plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

fig, ax = plt.subplots(figsize=dm.figsize("21cm", "14cm"))

month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
x      = np.arange(12)
bottom = np.zeros(12)

for i in range(10):
    ax.bar(x, monthly_hours[:, i], bottom=bottom,
           width=0.55, color=colors[i], label=f"{i*10}°", alpha=0.9)
    bottom += monthly_hours[:, i]

ax.set_title("Monthly BIPV Angle Cumulative Operation Hours",
             fontsize=17, fontweight="bold", pad=12)
ax.set_xlabel("Month")
ax.set_ylabel("Operation Hours [h]")
ax.set_xticks(x)
ax.set_xticklabels(month_labels)
ax.set_xlim(-0.6, 11.6)
ax.set_ylim(0, np.max(np.sum(monthly_hours, axis=1)) * 1.15)
ax.grid(True, axis="y", linewidth=0.3, color="#e2e8f0")
ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=12)

dm.simple_layout(fig)
fig.savefig(os.path.join(output_dir, "bipv_frequency_monthly.png"), dpi=300, transparent=True)
fig.savefig(os.path.join(output_dir, "bipv_frequency_monthly.svg"), transparent=True)
plt.close(fig)

print(f"\n저장 완료: {output_dir}/bipv_frequency_monthly.{{png,svg}}")

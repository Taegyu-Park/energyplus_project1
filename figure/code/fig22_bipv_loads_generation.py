import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os

# Set SVG font type to keep text editable in Figma
mpl.rcParams['svg.fonttype'] = 'none'

# Set font for clean academic look
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.unicode_minus'] = False

# Data for Subplot 1: Zone Loads
zones = ['Core', 'South', 'East', 'North', 'West']
f1_heating = [1694.0, 2540.3, 2632.8, 7127.3, 2668.1]
f1_cooling = [7200.6, 13972.7, 9251.4, 10214.4, 8610.7]
f2_heating = [6156.7, 8048.7, 5381.3, 12463.3, 5488.1]
f2_cooling = [9752.4, 15833.8, 10405.3, 12921.9, 8912.9]

# Data for Subplot 2: PV & HVAC Electricity
colors = ['White\n(250W)', 'Light Gray Beige\n(350W)', 'Terracotta\n(390W)']
pv_generation = [35470.7, 50275.1, 55520.3]
hvac_electricity = 57372.3 # Constant across all cases
net_electricity = [hvac_electricity - pv for pv in pv_generation]

# Create figure with 2 subplots side-by-side
fig, axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.3, 1]})
fig.suptitle('Annual Energy Analysis for 10-Zone Dynamic BIPV Model', fontsize=16, fontweight='bold', y=0.98)

# -------------------------------------------------------------
# Subplot 1: Heating & Cooling Loads by Zone
# -------------------------------------------------------------
ax1 = axes[0]
x = np.arange(len(zones))
width = 0.2

# Grouped bar chart for Floor 1 and Floor 2
ax1.bar(x - 1.5*width, f1_heating, width, label='F1 Heating', color='#ff9999', edgecolor='black', linewidth=0.7)
ax1.bar(x - 0.5*width, f1_cooling, width, label='F1 Cooling', color='#99ccff', edgecolor='black', linewidth=0.7)
ax1.bar(x + 0.5*width, f2_heating, width, label='F2 Heating', color='#cc3333', edgecolor='black', linewidth=0.7)
ax1.bar(x + 1.5*width, f2_cooling, width, label='F2 Cooling', color='#3366cc', edgecolor='black', linewidth=0.7)

ax1.set_title('Heating & Cooling Loads by Zone (All Cases)', fontsize=13, fontweight='bold', pad=10)
ax1.set_xticks(x)
ax1.set_xticklabels(zones)
ax1.set_xlabel('Zone Orientation')
ax1.set_ylabel('Thermal Load (kWh/year)')
ax1.grid(axis='y', linestyle='--', alpha=0.5)
ax1.legend(loc='upper right')

# Add values on top of bars for highlights (e.g. North and South peaks)
for i in range(len(zones)):
    # Highlight F2 North heating
    if zones[i] == 'North':
        ax1.annotate(f"{f2_heating[i]:,.0f}", (i + 0.5*width, f2_heating[i]), 
                     textcoords="offset points", xytext=(0,3), ha='center', fontsize=9, fontweight='bold')
    # Highlight F2 South cooling
    if zones[i] == 'South':
        ax1.annotate(f"{f2_cooling[i]:,.0f}", (i + 1.5*width, f2_cooling[i]), 
                     textcoords="offset points", xytext=(0,3), ha='center', fontsize=9, fontweight='bold')

# -------------------------------------------------------------
# Subplot 2: PV Generation and HVAC Net Electricity
# -------------------------------------------------------------
ax2 = axes[1]
x2 = np.arange(len(colors))
bar_width = 0.45

# Draw HVAC electricity demand as a background target line
ax2.axhline(y=hvac_electricity, color='#7f8c8d', linestyle='--', linewidth=1.5, label='HVAC Electricity Demand')

# Draw PV Generation bars
pv_colors = ['#bdc3c7', '#e0dbcd', '#d35400'] # White, Beige, Terracotta
bars = ax2.bar(x2, pv_generation, bar_width, color=pv_colors, edgecolor='black', linewidth=0.7, label='BIPV PV Generation')

# Draw Net Electricity consumption
line = ax2.plot(x2, net_electricity, color='#2c3e50', marker='o', linewidth=2, markersize=8, label='Net Electricity Consumption')

# Add values on top of bars
for bar in bars:
    height = bar.get_height()
    ax2.annotate(f"{height:,.0f} kWh",
                 xy=(bar.get_x() + bar.get_width() / 2, height),
                 xytext=(0, 3),  # 3 points vertical offset
                 textcoords="offset points",
                 ha='center', va='bottom', fontsize=9, fontweight='bold')

# Add values for Net Electricity line
for i, val in enumerate(net_electricity):
    ax2.annotate(f"{val:,.0f} kWh",
                 xy=(i, val),
                 xytext=(0, -15),  # 15 points vertical offset below marker
                 textcoords="offset points",
                 ha='center', va='top', color='#2c3e50', fontsize=10, fontweight='bold')

ax2.set_title('BIPV Generation vs Net Electricity Consumption', fontsize=13, fontweight='bold', pad=10)
ax2.set_xticks(x2)
ax2.set_xticklabels(colors)
ax2.set_ylabel('Electricity Energy (kWh/year)')
ax2.set_ylim(0, hvac_electricity * 1.15)
ax2.grid(axis='y', linestyle='--', alpha=0.5)
ax2.legend(loc='upper right')

plt.tight_layout()

# Save figure in plot directory matching the rules
output_dir = r"c:\Users\taegyu\Codes\energyplus_project1\figure\plot\fig22_bipv_loads_generation"
os.makedirs(output_dir, exist_ok=True)

png_path = os.path.join(output_dir, "fig22_bipv_loads_generation.png")
svg_path = os.path.join(output_dir, "fig22_bipv_loads_generation.svg")

plt.savefig(png_path, dpi=300, transparent=True)
plt.savefig(svg_path, transparent=True)
print(f"Figures successfully saved to:\n- {png_path}\n- {svg_path}")

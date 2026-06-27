import os
import re
import matplotlib.pyplot as plt
import dartwork_mpl as dm

# 1. Parse .eso file (from compare_eso.py logic)
def parse_eso_totals(eso_path):
    if not os.path.exists(eso_path):
        print(f"Warning: {eso_path} does not exist.")
        return None

    var_map = {}
    with open(eso_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line == "End of Data Dictionary":
                break
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    code = parts[0].strip()
                    num_vars = int(parts[1].strip())
                    if num_vars == 1:
                        if len(parts) >= 4:
                            key_val = parts[2].strip()
                            var_name = parts[3].strip()
                            full_name = f"{key_val}:{var_name}"
                        else:
                            var_name = parts[2].strip()
                            full_name = var_name
                        
                        if "!" in full_name:
                            full_name = full_name.split("!")[0].strip()
                            
                        lower_name = full_name.lower()
                        category = None
                        
                        if "ideal loads" in lower_name and "heating energy" in lower_name:
                            category = "heating"
                        elif "ideal loads" in lower_name and "cooling energy" in lower_name:
                            category = "cooling"
                        elif "produced electricity" in lower_name:
                            category = "pv_produced"
                        elif "generator produced dc electricity energy" in lower_name:
                            category = "pv_produced_dc"
                            
                        if category:
                            var_map[code] = {"category": category, "sum": 0.0}
                except ValueError:
                    continue

    # Accumulate values
    with open(eso_path, 'r', encoding='utf-8', errors='ignore') as f:
        # Skip dictionary
        for line in f:
            if line.strip() == "End of Data Dictionary":
                break
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            code = parts[0].strip()
            if code in var_map:
                try:
                    val = float(parts[1].strip())
                    var_map[code]["sum"] += val
                except (IndexError, ValueError):
                    pass

    # Convert to kWh (J -> kWh by dividing by 3.6e6)
    totals = {"heating": 0.0, "cooling": 0.0, "pv": 0.0}
    for code, info in var_map.items():
        kwh = info["sum"] / 3.6e6
        cat = info["category"]
        if cat == "pv_produced":
            # Accumulate PV (Facility Total Produced Electricity Energy)
            totals["pv"] += kwh
        elif cat == "pv_produced_dc":
            pass
        else:
            totals[cat] += kwh
            
    return totals

def main():
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    
    # 0도~90도 데이터 수집
    angles = list(range(0, 100, 10))
    angle_results = []
    
    for angle in angles:
        folder_name = f"model_realscale_{angle}_v2" if angle == 0 else f"model_realscale_{angle}"
        eso_path = os.path.join(project_root, "run_analysis", "model_realscale_case2", folder_name, "eplusout.eso")
        res = parse_eso_totals(eso_path)
        if res:
            res["angle"] = angle
            angle_results.append(res)
            
    # base 모델 데이터 수집
    base_eso_path = os.path.join(project_root, "run_analysis", "model_realscale_case1", "eplusout.eso")
    base_res = parse_eso_totals(base_eso_path)
    
    if not angle_results:
        print("Error: No data found for fixed angles!")
        return

    # 데이터 정리
    x_angles = [r["angle"] for r in angle_results]
    heating_vals = [r["heating"] for r in angle_results]
    cooling_vals = [r["cooling"] for r in angle_results]
    total_loads = [r["heating"] + r["cooling"] for r in angle_results]
    pv_vals = [r["pv"] for r in angle_results]
    
    print("Data summary for fixed angles:")
    for r in angle_results:
        print(f"  Angle {r['angle']}°: Heating={r['heating']:.2f} kWh, Cooling={r['cooling']:.2f} kWh, PV={r['pv']:.2f} kWh")
        
    if base_res:
        print(f"  Base (No Shade/PV): Heating={base_res['heating']:.2f} kWh, Cooling={base_res['cooling']:.2f} kWh")

    # 2. dartwork-mpl 스타일 적용하여 플롯 생성
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # physical width: 18cm, aspect ratio: golden (~1.618)
    fig, ax = plt.subplots(figsize=dm.figsize('18cm', '11.1cm'))
    
    # Plot lines with curated OKLCH colors
    # Use oc.blue5 for cooling, oc.red5 for heating, oc.green5 for PV, and oc.purple5 for total
    ax.plot(x_angles, cooling_vals, color="oc.blue5", marker="o", label="Cooling Load", lw=dm.lw(0.5))
    ax.plot(x_angles, heating_vals, color="oc.red5", marker="s", label="Heating Load", lw=dm.lw(0.5))
    ax.plot(x_angles, total_loads, color="oc.purple5", marker="^", label="Total Thermal Load", lw=dm.lw(0.5))
    ax.plot(x_angles, pv_vals, color="oc.green5", marker="D", label="PV Production", lw=dm.lw(0.5))
    
    # Base model levels as horizontal dashed lines (no PV for base)
    if base_res:
        ax.axhline(base_res["cooling"], color="oc.blue5", linestyle="--", alpha=0.6, label="Cooling (Base)")
        ax.axhline(base_res["heating"], color="oc.red5", linestyle="--", alpha=0.6, label="Heating (Base)")
        ax.axhline(base_res["heating"] + base_res["cooling"], color="oc.purple5", linestyle="--", alpha=0.6, label="Total Load (Base)")

    ax.set_xlabel("BIPV Shading Angle [Degrees]")
    ax.set_ylabel("Annual Energy [kWh]")
    ax.set_title("Annual Energy Consumption and Generation by BIPV Angle")
    ax.set_xticks(angles)
    
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    
    # Output path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "plot_fixed_angles"))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "bipv_angle_comparison.png")
    output_svg = os.path.join(figure_dir, "bipv_angle_comparison.svg")
    
    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    print(f"\nPlot saved to: {output_png} and {output_svg}")

if __name__ == "__main__":
    main()

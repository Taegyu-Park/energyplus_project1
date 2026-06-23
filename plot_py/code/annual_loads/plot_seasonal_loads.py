"""
봄 (4월 19일) 및 가을 (10월 19일) 대표일에 대한
Case 1, 2, 3의 timestep별 냉난방 부하 비교 플롯.
july_19_loads_comparison.svg와 동일한 스타일 적용.
"""
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm


def parse_case_daily_loads(csv_path, target_date):
    times = []
    heating_raw = []
    cooling_raw = []
    is_hourly = False

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        headers = next(reader)

        heating_cols = []
        cooling_cols = []
        for i, h in enumerate(headers):
            h_lower = h.lower()
            if "ideal loads" in h_lower:
                if "heating" in h_lower:
                    heating_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True

        if not heating_cols or not cooling_cols:
            heating_cols = []
            cooling_cols = []
            for i, h in enumerate(headers):
                h_lower = h.lower()
                if "heating" in h_lower:
                    heating_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True
                elif "cooling" in h_lower:
                    cooling_cols.append(i)
                    if "hourly" in h_lower:
                        is_hourly = True

        for row in reader:
            if not row:
                continue
            date_time_str = row[0].strip()
            if date_time_str.startswith(target_date) or (
                len(date_time_str.split()) > 0 and date_time_str.split()[0] == target_date
            ):
                time_str = date_time_str.split()[-1]
                times.append(time_str)

                h_sum = 0.0
                for idx in heating_cols:
                    if idx < len(row) and row[idx].strip():
                        h_sum += float(row[idx].strip())

                c_sum = 0.0
                for idx in cooling_cols:
                    if idx < len(row) and row[idx].strip():
                        c_sum += float(row[idx].strip())

                heating_raw.append(h_sum)
                cooling_raw.append(c_sum)

    if is_hourly:
        n_steps = len(heating_raw)
        heating_kw = np.zeros(n_steps)
        cooling_kw = np.zeros(n_steps)
        timesteps_per_hour = n_steps // 24 if n_steps >= 24 else 1
        for hr in range(24):
            start_idx = hr * timesteps_per_hour
            end_idx = start_idx + timesteps_per_hour
            if end_idx <= n_steps:
                h_kw = heating_raw[end_idx - 1] / 3.6e6
                c_kw = cooling_raw[end_idx - 1] / 3.6e6
                heating_kw[start_idx:end_idx] = h_kw
                cooling_kw[start_idx:end_idx] = c_kw
    else:
        # Timestep: 10분 에너지(J) → 평균 전력(kW)
        heating_kw = np.array(heating_raw) / 6.0e5
        cooling_kw = np.array(cooling_raw) / 6.0e5

    return times, heating_kw, cooling_kw


def plot_day(case1_path, case2_path, case3_path, pv_angles, target_date, date_label, output_stem, script_dir):
    times, c1_h, c1_c = parse_case_daily_loads(case1_path, target_date)
    _, c2_h, c2_c = parse_case_daily_loads(case2_path, target_date)
    _, c3_h, c3_c = parse_case_daily_loads(case3_path, target_date)

    if not times:
        print(f"[Error] {target_date} 데이터를 찾을 수 없습니다.")
        return

    n = len(times)
    print(f"\n[{date_label}] Parsed {n} timesteps.")
    print(f"  Case 1 Max Cooling: {np.max(c1_c):.2f} kW  |  Max Heating: {np.max(c1_h):.2f} kW")
    print(f"  Case 2 Max Cooling: {np.max(c2_c):.2f} kW  |  Max Heating: {np.max(c2_h):.2f} kW")
    print(f"  Case 3 Max Cooling: {np.max(c3_c):.2f} kW  |  Max Heating: {np.max(c3_h):.2f} kW")

    time_hours = np.linspace(0, 24, n, endpoint=False)
    has_heating = np.max(c1_h) > 0.01 or np.max(c2_h) > 0.01 or np.max(c3_h) > 0.01

    # 0 값을 NaN으로 처리하여 플로팅에서 제외
    c1_c = np.where(c1_c <= 0.001, np.nan, c1_c)
    c2_c = np.where(c2_c <= 0.001, np.nan, c2_c)
    c3_c = np.where(c3_c <= 0.001, np.nan, c3_c)
    c1_h = np.where(c1_h <= 0.001, np.nan, c1_h)
    c2_h = np.where(c2_h <= 0.001, np.nan, c2_h)
    c3_h = np.where(c3_h <= 0.001, np.nan, c3_h)

    fig, ax = plt.subplots(figsize=dm.figsize('23cm', '13cm'))

    # 냉방 부하 실선
    mask1_c = ~np.isnan(c1_c)
    mask2_c = ~np.isnan(c2_c)
    mask3_c = ~np.isnan(c3_c)
    ax.plot(time_hours[mask1_c], c1_c[mask1_c], color="oc.gray6",   label="Case 1 (No Shade) — Cooling",  lw=dm.lw(1.2))
    ax.plot(time_hours[mask2_c], c2_c[mask2_c], color="oc.blue6",   label="Case 2 (Fixed-90°) — Cooling", lw=dm.lw(1.2))
    ax.plot(time_hours[mask3_c], c3_c[mask3_c], color="oc.orange7", label="Case 3 (Kinetic) — Cooling",   lw=dm.lw(1.2))

    # 난방 부하 점선 (있는 경우)
    if has_heating:
        mask1_h = ~np.isnan(c1_h)
        mask2_h = ~np.isnan(c2_h)
        mask3_h = ~np.isnan(c3_h)
        ax.plot(time_hours[mask1_h], c1_h[mask1_h], color="oc.gray6",   linestyle="--", label="Case 1 — Heating",  lw=dm.lw(1.0))
        ax.plot(time_hours[mask2_h], c2_h[mask2_h], color="oc.blue6",   linestyle="--", label="Case 2 — Heating", lw=dm.lw(1.0))
        ax.plot(time_hours[mask3_h], c3_h[mask3_h], color="oc.orange7", linestyle="--", label="Case 3 — Heating",   lw=dm.lw(1.0))

    ax.set_ylabel("Thermal Load [kW]" if has_heating else "Cooling Load [kW]")
    ax.set_xlabel("Time of Day [Hour]")
    ax.set_title(f"Hourly Load Profile — {date_label} (Timestep Level)", fontsize=15.5, fontweight="bold")

    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_ylim(bottom=0)

    # PV 각도 보조축 설정
    if pv_angles is not None:
        ax2 = ax.twinx()
        # None 및 0 값을 NaN으로 처리하여 플로팅에서 제외
        angles_clean = [a if (a is not None and a != 0.0) else np.nan for a in pv_angles]
        ax2.step(time_hours, angles_clean, where="post", color="oc.orange4", linestyle="-.", lw=dm.lw(1.0), label="Case 3 PV Angle")
        ax2.set_ylabel("PV Tilt Angle [°]")
        ax2.set_ylim(-5, 95)
        ax2.set_yticks([0, 30, 60, 90])
        
        # 범례 병합
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")
        ax2.grid(False) # 보조축 그리드는 겹치지 않게 비활성화
    else:
        ax.legend(loc="upper right")

    ax.grid(True)

    out_png = os.path.join(script_dir, f"{output_stem}.png")
    out_svg = os.path.join(script_dir, f"{output_stem}.svg")
    dm.simple_layout(fig)
    fig.savefig(out_png, dpi=300, transparent=True)
    fig.savefig(out_svg, transparent=True)
    plt.close(fig)
    print(f"  Saved: {out_png}")
    print(f"  Saved: {out_svg}")


def main():
    import json
    project_root = r"c:\Users\taegyu\Codes\EnergyPlus_Project1"
    case1_path = os.path.join(project_root, "run_analysis", "model_realscale_case1", "case1.csv")
    case2_path = os.path.join(project_root, "run_analysis", "model_realscale_case2", "model_realscale_90", "case2_90.csv")
    case3_path = os.path.join(project_root, "run_analysis", "model_realscale_case3", "case3.csv")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "..", "figure", "annual_loads"))
    os.makedirs(figure_dir, exist_ok=True)

    # pv_angles.json 로드
    json_path = os.path.join(script_dir, "pv_angles.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            pv_data = json.load(f)
    else:
        pv_data = {}

    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    # 봄 대표일: 4월 19일
    plot_day(case1_path, case2_path, case3_path,
             pv_angles=pv_data.get("04/19"),
             target_date="04/19",
             date_label="April 19th (Spring)",
             output_stem="apr_19_loads_comparison",
             script_dir=figure_dir)

    # 가을 대표일: 10월 19일
    plot_day(case1_path, case2_path, case3_path,
             pv_angles=pv_data.get("10/19"),
             target_date="10/19",
             date_label="October 19th (Autumn)",
             output_stem="oct_19_loads_comparison",
             script_dir=figure_dir)


if __name__ == "__main__":
    main()

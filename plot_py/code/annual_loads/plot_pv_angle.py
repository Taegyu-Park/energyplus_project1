"""
Case 3 Kinetic BIPV의 타임스텝별 활성 PV 각도를 ESO에서 파싱하여
봄(4/19), 여름(7/19), 가을(10/19)에 대해 3개 subplot으로 그리는 스크립트.

각도 결정 원리:
- PV_1_00_01 (code 740)  = 0°  활성 여부 proxy
- PV_1_10_01 (code 768)  = 10° 활성 여부 proxy
- ...
- PV_1_90_01 (code 896)  = 90° 활성 여부 proxy
각 타임스텝에서 발전량이 0이 아닌 그룹 = 해당 타임스텝의 활성 각도
"""
import re
import numpy as np
import matplotlib.pyplot as plt
import dartwork_mpl as dm

ESO_PATH = r"c:\Users\taegyu\Codes\EnergyPlus_Project1\run_analysis\case3\eplusout.eso"

# 각도 proxy 코드: {ESO_code: angle_deg}
ANGLE_PROXY_CODES = {
    740: 0,
    768: 10,
    784: 20,
    800: 30,
    816: 40,
    832: 50,
    848: 60,
    864: 70,
    880: 80,
    896: 90,
}

TARGET_DATES = {
    "04/19": "April 19 (Spring)",
    "07/19": "July 19 (Summer)",
    "10/19": "October 19 (Autumn)",
}


def parse_pv_angles(eso_path, target_dates):
    """
    ESO를 파싱하여 지정 날짜들의 타임스텝별 활성 각도를 반환.
    Returns: {date_str: list of (hour_float, angle_deg)}
    """
    result = {d: [] for d in target_dates}
    proxy_set = set(ANGLE_PROXY_CODES.keys())

    print(f"[Info] Parsing ESO for PV angle data...")
    with open(eso_path, "r", encoding="utf-8", errors="ignore") as f:
        # 헤더 스킵
        for line in f:
            if line.strip().startswith("End of Data Dictionary"):
                break

        current_dt = None
        current_date = None
        current_hour_f = None
        proxy_vals = {}

        for line in f:
            line = line.strip()
            if not line or line.startswith("End of Data"):
                break

            parts = line.split(",")
            try:
                code = int(parts[0])
            except ValueError:
                continue

            if code == 2:
                # 타임스텝 전환 → 이전 타임스텝 처리
                if current_date in result and proxy_vals:
                    # 발전량 > 0인 각도 그룹 찾기
                    active_angles = [
                        ANGLE_PROXY_CODES[c]
                        for c in ANGLE_PROXY_CODES
                        if proxy_vals.get(c, 0.0) > 0.0
                    ]
                    if active_angles:
                        # 가장 높은 발전량의 각도 (보통 하나)
                        best_code = max(
                            (c for c in ANGLE_PROXY_CODES if proxy_vals.get(c, 0.0) > 0.0),
                            key=lambda c: proxy_vals.get(c, 0.0)
                        )
                        angle = ANGLE_PROXY_CODES[best_code]
                    else:
                        angle = None  # 야간 (발전 없음)
                    result[current_date].append((current_hour_f, angle))

                proxy_vals = {}
                # 날짜/시간 파싱
                try:
                    month = int(parts[2])
                    day   = int(parts[3])
                    hour  = int(float(parts[5]))
                    end_m = int(float(parts[7]))
                    if end_m == 60:
                        dh = hour % 24
                        dm_min = 0
                    else:
                        dh = (hour - 1) % 24
                        dm_min = end_m
                    current_date = f"{month:02d}/{day:02d}"
                    current_hour_f = dh + dm_min / 60.0
                except (IndexError, ValueError):
                    current_date = None
                    current_hour_f = None

            elif code in proxy_set:
                try:
                    val = float(parts[1])
                    proxy_vals[code] = val
                except (IndexError, ValueError):
                    pass

    print("[Info] Parsing complete.")
    return result


def main():
    angles_data = parse_pv_angles(ESO_PATH, list(TARGET_DATES.keys()))

    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})
    fig, axes = plt.subplots(3, 1, figsize=dm.figsize('23cm', '23cm'), sharex=True)

    colors = {"04/19": "oc.green6", "07/19": "oc.orange7", "10/19": "oc.indigo6"}

    for ax, (date_key, date_label) in zip(axes, TARGET_DATES.items()):
        data = angles_data[date_key]
        if not data:
            ax.set_title(f"{date_label} — No data")
            continue

        hours = []
        angles = []
        for h, a in data:
            hours.append(h)
            angles.append(a if a is not None else np.nan)

        hours = np.array(hours)
        angles = np.array(angles, dtype=float)

        # 계단형(step) 플롯
        ax.step(hours, angles, where="post", color=colors[date_key], lw=dm.lw(1.3), label=date_label)
        # 야간(NaN) 구간 표시
        night_mask = np.isnan(angles)
        if night_mask.any():
            ax.fill_between(hours, 0, 90, where=night_mask, alpha=0.08, color="oc.gray5", label="No PV generation")

        ax.set_title(date_label, fontsize=14, fontweight="bold")
        ax.set_ylabel("PV Tilt Angle [°]")
        ax.set_ylim(-5, 95)
        ax.set_yticks([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
        ax.legend(loc="upper right", fontsize=11)
        ax.grid(True, alpha=0.4)

    axes[-1].set_xlabel("Time of Day [Hour]")
    axes[-1].set_xlim(0, 24)
    axes[-1].set_xticks(range(0, 25, 2))
    axes[-1].set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])

    fig.suptitle("Case 3 (Kinetic BIPV) — Active PV Tilt Angle per Timestep", fontsize=15.5, fontweight="bold")
    dm.simple_layout(fig)

    import os
    script_dir = r"c:\Users\taegyu\Codes\EnergyPlus_Project1\plot_py\figure\annual_loads"
    os.makedirs(script_dir, exist_ok=True)
    out_png = os.path.join(script_dir, "case3_pv_angle_seasonal.png")
    out_svg = os.path.join(script_dir, "case3_pv_angle_seasonal.svg")
    fig.savefig(out_png, dpi=300, transparent=True)
    fig.savefig(out_svg, transparent=True)
    plt.close(fig)
    print(f"Saved: {out_png}")
    print(f"Saved: {out_svg}")


if __name__ == "__main__":
    main()

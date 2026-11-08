import os

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import dartwork_mpl as dm

# Setup SVG font settings for Figma editing
mpl.rcParams['svg.fonttype'] = 'none'

# Apply presentation style from dartwork_mpl
dm.style.use("presentation")

# Patch matplotlib font_manager for SVG export compatibility (resolves numeric font weight KeyError)
for w in range(100, 1000, 50):
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

COLOR_SUN = "#f59e0b"   # Sun-tracking angle (Amber)
COLOR_AI = "#2563eb"    # Net-Energy AI optimal angle (Royal Blue)
COLOR_DIFF = "#dc2626"  # Absolute difference (Crimson)


def load_data(project_root):
    sun_path = os.path.join(project_root, "data", "bipv_suntracking_angles_annual.csv")
    ai_path = os.path.join(project_root, "ai_model", "tide", "data", "predictions", "bipv_optimal_angles_annual.csv")

    df_sun = pd.read_csv(sun_path, parse_dates=["timestamp"])
    df_ai = pd.read_csv(ai_path, parse_dates=["timestamp"])

    df = pd.DataFrame({
        "timestamp": df_sun["timestamp"],
        "sun_track_angle": df_sun["optimal_angle"],
        "ai_optimal_angle": df_ai["optimal_angle"],
    })
    df["timestep"] = np.arange(len(df))
    df["abs_diff"] = (df["ai_optimal_angle"] - df["sun_track_angle"]).abs()
    return df


def month_tick_positions(df):
    """월 경계에 해당하는 timestep 위치와 월 라벨(상단 보조축용)"""
    df_months = df.assign(month=df["timestamp"].dt.month)
    ticks = df_months.groupby("month")["timestep"].min().sort_index()
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    labels = [month_abbr[m - 1] for m in ticks.index]
    return ticks.values, labels


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    plot_dir = os.path.join(project_root, "figure", "plot", "fig36_suntracking_vs_ai_angle_comparison")
    os.makedirs(plot_dir, exist_ok=True)

    df = load_data(project_root)
    match_rate = (df["abs_diff"] == 0).mean() * 100

    # Representative week for the zoomed detail panel: a summer week with large divergence
    zoom_start_ts = df.loc[df["timestamp"] == pd.Timestamp("2026-07-13 00:10:00"), "timestep"].iloc[0]
    zoom_end_ts = zoom_start_ts + 6 * 144  # 6 days * 144 timesteps/day

    fig, axes = plt.subplots(
        3, 1, figsize=(15, 11),
        gridspec_kw={"height_ratios": [2.4, 1.6, 1.0]}
    )
    ax_full, ax_zoom, ax_diff = axes

    # -----------------------------------------------------------------
    # Panel 1: Full-year overlay (x = timestep, y = angle)
    # -----------------------------------------------------------------
    ax_full.plot(
        df["timestep"], df["sun_track_angle"],
        color=COLOR_SUN, linewidth=0.35, alpha=0.75, zorder=5,
        label="Sun-Tracking Angle (nearest to Site Solar Altitude)"
    )
    ax_full.plot(
        df["timestep"], df["ai_optimal_angle"],
        color=COLOR_AI, linewidth=0.35, alpha=0.6, zorder=4,
        label="Net-Energy AI Optimal Angle (TiDE schedule)"
    )

    ax_full.set_ylim(-4, 96)
    ax_full.set_yticks(np.arange(0, 91, 10))
    ax_full.set_ylabel("BIPV Control Angle [°]", fontsize=12.5, fontweight='bold')
    ax_full.set_xlim(0, len(df))
    ax_full.set_title(
        f"Annual BIPV Angle Schedule: Sun-Tracking vs. Net-Energy AI Optimal (Gwangju, 10-min timestep)\n"
        f"Match rate = {match_rate:.1f}%  (Mismatch = {100 - match_rate:.1f}%,  n = {len(df):,} timesteps)",
        fontsize=14.5, fontweight='bold', pad=14
    )

    month_ticks, month_labels = month_tick_positions(df)
    ax_full.set_xticks(month_ticks)
    ax_full.set_xticklabels(month_labels, fontsize=10)
    ax_full.set_xlabel("Timestep (month boundary ticks, 10-min resolution, 52,560 steps/year)", fontsize=11)
    ax_full.grid(True, linestyle=':', alpha=0.4)

    # Highlight the zoom window on the full-year panel
    ax_full.axvspan(zoom_start_ts, zoom_end_ts, color="#94a3b8", alpha=0.25, zorder=1)
    ax_full.annotate(
        "Zoomed window\n(see Panel 2)",
        xy=((zoom_start_ts + zoom_end_ts) / 2, 92), xycoords='data',
        ha='center', va='top', fontsize=9, fontweight='bold', color="#334155"
    )

    ax_full.legend(loc="lower center", bbox_to_anchor=(0.5, 1.14), ncols=2,
                   fontsize=10.5, framealpha=0, facecolor="none")

    # -----------------------------------------------------------------
    # Panel 2: Zoomed representative week (mid-summer, large divergence)
    # -----------------------------------------------------------------
    zoom = df[(df["timestep"] >= zoom_start_ts) & (df["timestep"] < zoom_end_ts)]

    ax_zoom.plot(
        zoom["timestep"], zoom["sun_track_angle"],
        color=COLOR_SUN, linewidth=1.6, alpha=0.95, zorder=5,
        marker='o', markersize=2.2,
        label="Sun-Tracking Angle"
    )
    ax_zoom.plot(
        zoom["timestep"], zoom["ai_optimal_angle"],
        color=COLOR_AI, linewidth=1.6, alpha=0.95, zorder=4,
        marker='s', markersize=2.2,
        label="AI Optimal Angle (Net Energy)"
    )
    ax_zoom.fill_between(
        zoom["timestep"], zoom["sun_track_angle"], zoom["ai_optimal_angle"],
        color=COLOR_DIFF, alpha=0.12, zorder=2
    )

    ax_zoom.set_ylim(-4, 96)
    ax_zoom.set_yticks(np.arange(0, 91, 10))
    ax_zoom.set_ylabel("Control Angle [°]", fontsize=12, fontweight='bold')
    ax_zoom.set_xlim(zoom_start_ts, zoom_end_ts)
    ax_zoom.set_title(
        "Detail View: 2026-07-13 – 2026-07-19 (Mid-Summer, Cooling-Dominant Week)",
        fontsize=12.5, fontweight='bold', pad=8
    )

    day_ticks = zoom["timestep"].values[::144]
    day_labels = zoom["timestamp"].dt.strftime("%m/%d").values[::144]
    ax_zoom.set_xticks(day_ticks)
    ax_zoom.set_xticklabels(day_labels, fontsize=9.5)
    ax_zoom.set_xlabel("Timestep (daily ticks)", fontsize=11)
    ax_zoom.grid(True, linestyle=':', alpha=0.45)
    ax_zoom.legend(loc="upper right", fontsize=9.5, framealpha=0, facecolor="none")

    # -----------------------------------------------------------------
    # Panel 3: |AI - Sun-Tracking| absolute difference, full year
    # -----------------------------------------------------------------
    ax_diff.fill_between(
        df["timestep"], df["abs_diff"],
        color=COLOR_DIFF, alpha=0.55, linewidth=0, zorder=3
    )
    ax_diff.plot(df["timestep"], df["abs_diff"], color=COLOR_DIFF, linewidth=0.15, alpha=0.5, zorder=4)

    ax_diff.set_ylim(0, 92)
    ax_diff.set_yticks([0, 30, 60, 90])
    ax_diff.set_ylabel("|Δ Angle| [°]", fontsize=12, fontweight='bold')
    ax_diff.set_xlim(0, len(df))
    ax_diff.set_xticks(month_ticks)
    ax_diff.set_xticklabels(month_labels, fontsize=10)
    ax_diff.set_xlabel("Timestep (month boundary ticks)", fontsize=11)
    ax_diff.set_title("Absolute Angle Difference |AI − Sun-Tracking| over the Full Year", fontsize=12, fontweight='bold', pad=8)
    ax_diff.grid(True, linestyle=':', alpha=0.4)
    ax_diff.axvspan(zoom_start_ts, zoom_end_ts, color="#94a3b8", alpha=0.25, zorder=1)

    plt.tight_layout()

    png_path = os.path.join(plot_dir, "fig36_suntracking_vs_ai_angle_comparison.png")
    svg_path = os.path.join(plot_dir, "fig36_suntracking_vs_ai_angle_comparison.svg")

    plt.savefig(png_path, dpi=300, transparent=True, bbox_inches='tight')
    plt.savefig(svg_path, transparent=True, bbox_inches='tight')
    plt.close()

    print("Figures successfully generated:")
    print(f" - PNG: {png_path}")
    print(f" - SVG: {svg_path}")
    print(f" - Match rate: {match_rate:.2f}%")


if __name__ == "__main__":
    main()

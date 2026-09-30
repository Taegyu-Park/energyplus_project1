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


def load_daily_table(project_root):
    sun_path = os.path.join(project_root, "data", "bipv_suntracking_angles_annual.csv")
    ai_path = os.path.join(project_root, "ai_model", "tide", "data", "predictions", "bipv_optimal_angles_annual.csv")

    df_sun = pd.read_csv(sun_path, parse_dates=["timestamp"])
    df_ai = pd.read_csv(ai_path, parse_dates=["timestamp"])

    df = pd.DataFrame({
        "timestamp": df_sun["timestamp"],
        "sun_track_angle": df_sun["optimal_angle"],
        "ai_optimal_angle": df_ai["optimal_angle"],
    })
    df["date"] = df["timestamp"].dt.date
    df["abs_diff"] = (df["ai_optimal_angle"] - df["sun_track_angle"]).abs()
    df["match"] = df["abs_diff"] == 0
    return df


def find_representative_days(df):
    daily = df.groupby("date").agg(
        mean_absdiff=("abs_diff", "mean"),
        match_rate=("match", "mean"),
        n=("abs_diff", "size"),
    )
    # Ensure full-day data (144 time steps of 10-min interval per day)
    daily = daily[daily["n"] == 144]

    max_day = daily["mean_absdiff"].idxmax()
    min_day = daily["mean_absdiff"].idxmin()
    return max_day, daily.loc[max_day], min_day, daily.loc[min_day]


def plot_day_panel(ax, df, date, stats, title_prefix, is_max_panel):
    day = df[df["date"] == date].copy()
    day["hour"] = day["timestamp"].dt.hour + day["timestamp"].dt.minute / 60.0

    ax.plot(
        day["hour"],
        day["sun_track_angle"],
        color=COLOR_SUN,
        linewidth=2.2,
        alpha=0.95,
        zorder=5,
        marker='o',
        markersize=3.2,
        label="Sun-Tracking Angle"
    )
    ax.plot(
        day["hour"],
        day["ai_optimal_angle"],
        color=COLOR_AI,
        linewidth=2.2,
        alpha=0.95,
        zorder=4,
        marker='s',
        markersize=3.2,
        label="AI Optimal Angle (Net Energy)"
    )

    # Shading difference
    ax.fill_between(
        day["hour"],
        day["sun_track_angle"],
        day["ai_optimal_angle"],
        color=COLOR_DIFF,
        alpha=0.18,
        zorder=2,
        label="|Difference|"
    )

    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_ylim(-4, 96)
    ax.set_yticks(np.arange(0, 91, 10))
    ax.set_ylabel("Control Angle [°]", fontsize=12.5, fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.45)

    badge_color = "#b91c1c" if is_max_panel else "#15803d"
    ax.set_title(
        f"{title_prefix}: {date.strftime('%Y-%m-%d')}  (Mean |Δ| = {stats['mean_absdiff']:.1f}°,  Match rate = {stats['match_rate']*100:.1f}%)",
        fontsize=13.5,
        fontweight='bold',
        pad=10,
        color=badge_color
    )
    ax.legend(loc="upper right", fontsize=9.5, framealpha=0, facecolor="none")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    plot_dir = os.path.join(project_root, "figure", "plot", "fig37_suntracking_vs_ai_angle_representative_days")
    os.makedirs(plot_dir, exist_ok=True)

    df = load_daily_table(project_root)
    max_day, max_stats, min_day, min_stats = find_representative_days(df)

    fig, (ax_max, ax_min) = plt.subplots(2, 1, figsize=(13, 10.5), sharex=True)

    plot_day_panel(ax_max, df, max_day, max_stats, "Most Divergent Day", is_max_panel=True)
    plot_day_panel(ax_min, df, min_day, min_stats, "Most Convergent Day", is_max_panel=False)

    ax_min.set_xlabel("Hour of Day", fontsize=12.5, fontweight='bold')

    fig.suptitle(
        "Representative Days: Sun-Tracking vs. Net-Energy AI Optimal BIPV Angle\n"
        "(Selected by daily mean |AI − Sun-Tracking| angle difference, full year 2026)",
        fontsize=15,
        fontweight='bold',
        y=1.0
    )

    plt.tight_layout(rect=[0, 0, 1, 0.94])

    png_path = os.path.join(plot_dir, "fig37_suntracking_vs_ai_angle_representative_days.png")
    svg_path = os.path.join(plot_dir, "fig37_suntracking_vs_ai_angle_representative_days.svg")

    plt.savefig(png_path, dpi=300, transparent=True, bbox_inches='tight')
    plt.savefig(svg_path, transparent=True, bbox_inches='tight')
    plt.close()

    print(f"[OK] Figures generated successfully:")
    print(f"  PNG: {png_path}")
    print(f"  SVG: {svg_path}")


if __name__ == "__main__":
    main()

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "figure", "code"))
import fig37_suntracking_vs_ai_angle_representative_days as f37  # reuse style & panel

PRED = os.path.join(ROOT, "bipv_experiments", "tide_c5", "predictions")
SUN_PATH = os.path.join(ROOT, "data", "bipv_suntracking_angles_annual_winter0_summer90.csv")
df_sun = pd.read_csv(SUN_PATH, parse_dates=["timestamp"])

for st in (1, 2):
    df_ai = pd.read_csv(os.path.join(PRED, f"annual_tide_strategy{st}_lb36_optimal_angles.csv"),
                        parse_dates=["timestamp"])
    m = pd.merge(df_sun[["timestamp", "optimal_angle"]], df_ai[["timestamp", "optimal_angle_pred"]], on="timestamp")
    df = pd.DataFrame({"timestamp": m["timestamp"], "sun_track_angle": m["optimal_angle"],
                       "ai_optimal_angle": m["optimal_angle_pred"]})
    df["date"] = df["timestamp"].dt.date
    df["abs_diff"] = (df["ai_optimal_angle"] - df["sun_track_angle"]).abs()
    df["match"] = df["abs_diff"] == 0

    fig, axes = plt.subplots(2, 1, figsize=(13, 10.5), sharex=True)
    for ax, day, label, bad in [(axes[0], "2026-12-26", "Winter Day", True),
                                (axes[1], "2026-07-21", "Summer Day", False)]:
        d = df[df["timestamp"].dt.strftime("%Y-%m-%d") == day]["date"].iloc[0]
        sub = df[df["date"] == d]
        stats = {"mean_absdiff": sub["abs_diff"].mean(), "match_rate": sub["match"].mean()}
        f37.plot_day_panel(ax, df, d, stats, label, is_max_panel=bad)
        print(f"ST{st}", day, stats)
    axes[1].set_xlabel("Hour of Day", fontsize=12.5, fontweight="bold")
    fig.suptitle(f"Representative Days: Sun-Tracking vs. Net-Energy AI Optimal BIPV Angle\n"
                 f"(TiDE Strategy {st}, lookback 36; Winter: 12/26, Summer: 7/21, 2026)",
                 fontsize=15, fontweight="bold", y=1.0)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    base = os.path.join(HERE, f"fig37_lb36_st{st}_representative_days")
    plt.savefig(base + ".png", dpi=300, transparent=True, bbox_inches="tight")
    plt.savefig(base + ".svg", transparent=True, bbox_inches="tight")
    plt.close()

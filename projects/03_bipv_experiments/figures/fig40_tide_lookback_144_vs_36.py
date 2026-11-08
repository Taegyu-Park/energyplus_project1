"""TiDE lookback 144 vs 36 비교 (오프라인 test 구간, 같은 타임스텝 기준).

(a)~(c): retrain_lb36.jsonl  — L144 = 기존 체크포인트(1개), L36 = 5시드 재학습
(d)    : lookback_sweep_st1.jsonl — S1, L144/L36 모두 5시드 (공정 비교)
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "tide_c5", "results")


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return pd.DataFrame([json.loads(l) for l in f if l.strip()])


rt = load("retrain_lb36.jsonl")
sw = load("lookback_sweep_st1.jsonl")
sw = sw[(~sw["mask"].astype(bool)) & sw["lookback"].isin([144, 36])]

C144, C36 = "#8C8C8C", "#2F6FD0"
ORACLE = rt["net_oracle"].iloc[0]
FIXED = rt["net_best_fixed"].iloc[0]
rng = np.random.default_rng(0)

fig, axes = plt.subplots(1, 4, figsize=(18, 5.2),
                         gridspec_kw={"width_ratios": [1.15, 1, 1, 0.75]})


def paired_panel(ax, df, col, title, ylabel, strategies=(1, 2), ref=False):
    xs = np.arange(len(strategies))
    w = 0.34
    for i, st in enumerate(strategies):
        d = df[df["strategy"] == st] if "strategy" in df else df
        for lb, off, c in [(144, -w / 2, C144), (36, w / 2, C36)]:
            v = d.loc[d["lookback"] == lb, col].to_numpy(float)
            m = v.mean()
            ax.bar(xs[i] + off, m, w * 0.92, color=c, alpha=0.85,
                   label=f"lookback {lb}" if i == 0 else None, zorder=2)
            if len(v) > 1:
                ax.scatter(xs[i] + off + rng.uniform(-0.06, 0.06, len(v)), v,
                           s=16, color="black", zorder=3, linewidths=0)
                ax.errorbar(xs[i] + off, m, yerr=v.std(ddof=1), color="black",
                            capsize=4, lw=1.2, zorder=4)
            sd = v.std(ddof=1) if len(v) > 1 else 0.0
            txt = f"{m:.3f}" if abs(m) < 1 else (f"{m:.1f}" if abs(m) < 100 else f"{m:.0f}")
            if m < 0:  # 음수 막대: 0 근처 막대 안쪽에 표기
                ax.annotate(txt, (xs[i] + off, 0), ha="center", va="top", xytext=(0, -6),
                            textcoords="offset points", fontsize=10, fontweight="bold",
                            color="white", zorder=5)
            else:      # 양수 막대: 수염 위에 표기
                ax.annotate(txt, (xs[i] + off, m + sd), ha="center", va="bottom", xytext=(0, 4),
                            textcoords="offset points", fontsize=10, fontweight="bold", zorder=5)
    if ref:
        ax.axhline(ORACLE, color="#2E9E5B", ls="--", lw=1.4, label=f"oracle ({ORACLE:.0f})")
        ax.axhline(FIXED, color="#D9822B", ls=":", lw=1.6, label=f"best fixed 30° ({FIXED:.0f})")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"Strategy {s}" for s in strategies], fontsize=11)
    ax.set_title(title, fontsize=12.5, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)


paired_panel(axes[0], rt, "net_chosen", "(a) Net energy of chosen angles\n(lower is better)",
             "Test-period net energy [kWh]", ref=True)
paired_panel(axes[1], rt, "angle_mae", "(b) Angle MAE vs. oracle\n(lower is better)",
             "Angle MAE [°]")
paired_panel(axes[2], rt, "net_mae", "(c) Net prediction MAE\n(lower is better)",
             "Net MAE [kWh / step]")
paired_panel(axes[3], sw.assign(strategy=1), "net_chosen",
             "(d) Fair check: S1, 5 seeds each\n(lower is better)",
             "Test-period net energy [kWh]", strategies=(1,), ref=True)
axes[3].set_ylim(axes[0].get_ylim())

fig.suptitle("TiDE Lookback 144 vs. 36 (offline test set, identical timesteps)",
             fontsize=15, fontweight="bold", y=1.02)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=4, fontsize=10.5, frameon=False, bbox_to_anchor=(0.5, -0.07))
fig.text(0.5, -0.11,
         "(a)–(c): L144 = existing checkpoint (single model), L36 = retrained, 5 seeds (bar = mean, "
         "whisker = ±1 SD, dots = seeds).  (d): both lookbacks trained with 5 seeds under the same recipe.",
         ha="center", fontsize=9.5, color="#444")
plt.tight_layout()
base = os.path.join(HERE, "fig40_tide_lookback_144_vs_36")
plt.savefig(base + ".png", dpi=300, transparent=True, bbox_inches="tight")
plt.savefig(base + ".svg", transparent=True, bbox_inches="tight")
print(rt.groupby(["strategy", "lookback"])[["net_chosen", "angle_mae", "net_mae"]].mean())
print(sw.groupby("lookback")["net_chosen"].agg(["mean", "std"]))

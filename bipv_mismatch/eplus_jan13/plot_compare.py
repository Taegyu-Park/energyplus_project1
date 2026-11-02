"""
eplus_jan13/plot_compare.py
===========================
태양추적 vs 잉여 구간 90° 고정: 잉여·부족 비교 그림 (fig41 색 체계).
입력: compare_jan13.csv (analyze.py 출력, 1/13 07시 ~ 1/14 07시, 구간 시작 시각)
출력: jan13_surplus_deficit_compare.png
  - 위 2개: 실행별 PV·수요(HVAC+조명)와 잉여(초록)/부족(빨강) 영역
  - 아래: 시간대별 잉여·부족 합계 막대 비교
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C_PV, C_DEM, C_SURPLUS, C_DEFICIT = "#f59e0b", "#1e293b", "#10b981", "#dc2626"
RUNS = [("suntracking", "태양추적"), ("surplus90", "잉여 구간 90° 고정")]
WINDOW = ("2006-01-13 10:20", "2006-01-13 14:10")
BANDS = [(7, 10, "07-10"), (10, 14, "10-14"), (14, 19, "14-19"), (19, 24, "19-24"), (24, 31, "익일 00-07")]

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def main():
    d = pd.read_csv(HERE / "compare_jan13.csv", header=[0, 1], index_col=0, parse_dates=True)
    # 계단 끝을 닫기 위해 마지막 구간 끝 시각 추가
    idx = d.index.append(pd.DatetimeIndex([d.index[-1] + pd.Timedelta(minutes=10)]))

    fig = plt.figure(figsize=(13, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 0.8], hspace=0.38)
    ymax = max(d[(r, c)].max() for r, _ in RUNS for c in ("pv", "load")) * 1.1

    for i, (run, label) in enumerate(RUNS):
        ax = fig.add_subplot(gs[i])
        pv = np.r_[d[(run, "pv")].to_numpy(), d[(run, "pv")].iloc[-1]]
        ld = np.r_[d[(run, "load")].to_numpy(), d[(run, "load")].iloc[-1]]
        ax.fill_between(idx, pv, ld, where=pv > ld, step="post", color=C_SURPLUS, alpha=0.45, lw=0)
        ax.fill_between(idx, pv, ld, where=pv <= ld, step="post", color=C_DEFICIT, alpha=0.30, lw=0)
        ax.step(idx, ld, where="post", color=C_DEM, lw=1.4)
        ax.step(idx, pv, where="post", color=C_PV, lw=1.8)
        if run == "surplus90":
            ax.axvspan(pd.Timestamp(WINDOW[0]), pd.Timestamp(WINDOW[1]), color="#64748b", alpha=0.08)
            ax.text(pd.Timestamp("2006-01-13 12:15"), ymax * 0.95, "90° 고정 구간", ha="center", va="top", fontsize=9, color="#475569")
        s, p = d[(run, "surplus")].sum(), d[(run, "purchase")].sum()
        ax.set_title(f"{label}  —  잉여 {s:.1f} kWh, 부족(구매) {p:.1f} kWh", loc="left", fontsize=12, fontweight="bold")
        ax.set_ylim(0, ymax)
        ax.set_xlim(idx[0], idx[-1])
        ax.set_ylabel("kWh / 10분")
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%m/%d %H:%M"))
        ax.grid(axis="y", alpha=0.3)
        if i == 0:
            from matplotlib.lines import Line2D
            from matplotlib.patches import Patch
            ax.legend([Line2D([], [], color=C_PV, lw=1.8), Line2D([], [], color=C_DEM, lw=1.4),
                       Patch(color=C_SURPLUS, alpha=0.45), Patch(color=C_DEFICIT, alpha=0.30)],
                      ["PV 발전", "수요 (냉방/3.0 + 난방/2.5 + 조명)", "잉여 (PV > 수요)", "부족 (구매)"],
                      ncol=4, fontsize=9, loc="upper right")

    # 시간대별 잉여·부족 합계
    ax = fig.add_subplot(gs[2])
    hr = (d.index - pd.Timestamp("2006-01-13")).total_seconds() / 3600
    rows = []
    for h0, h1, lab in BANDS:
        m = (hr >= h0) & (hr < h1)
        rows.append([lab] + [d.loc[m, (r, c)].sum() for r, _ in RUNS for c in ("surplus", "purchase")])
    t = pd.DataFrame(rows, columns=["band", "st_s", "st_p", "s9_s", "s9_p"])
    x = np.arange(len(t))
    w = 0.2
    bars = [(-1.5, "st_s", C_SURPLUS, 0.45, "잉여 · 태양추적"), (-0.5, "s9_s", C_SURPLUS, 0.9, "잉여 · 90° 고정"),
            (0.5, "st_p", C_DEFICIT, 0.35, "부족 · 태양추적"), (1.5, "s9_p", C_DEFICIT, 0.8, "부족 · 90° 고정")]
    for off, col, color, alpha, lab in bars:
        b = ax.bar(x + off * w, t[col], w, color=color, alpha=alpha, label=lab)
        ax.bar_label(b, fmt="%.1f", fontsize=8, padding=1)
    ax.set_xticks(x, t["band"])
    ax.set_ylabel("kWh")
    ax.set_title("시간대별 합계 (1/13 07시 ~ 1/14 07시)", loc="left", fontsize=12, fontweight="bold")
    ax.legend(ncol=4, fontsize=9, loc="upper right")
    ax.set_ylim(0, t[["st_s", "st_p", "s9_s", "s9_p"]].to_numpy().max() * 1.25)
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("case3 1/13 (IWEC): 잉여 구간 90° 고정 전후 잉여·부족 비교", fontsize=14, fontweight="bold")
    out = HERE / "jan13_surplus_deficit_compare.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(t.round(2).to_string(index=False))
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

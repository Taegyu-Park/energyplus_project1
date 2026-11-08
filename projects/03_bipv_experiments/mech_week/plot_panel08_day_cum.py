"""
projects/03_bipv_experiments/mech_week/plot_panel08_day_cum.py
==================================================
공모전 패널 8번 ② 대표일(1/9) 시간에 따른 누적 에너지 (쌓은 면적) (2026-11-04).
- x = 시각(0~24시), y = 그 시각까지의 누적 kWh. 정책별 작은 그래프 두 개(태양고도 추적 | TiDE), y축 공유
- 쌓는 순서(아래→위): 부족 전력 · 냉난방, 부족 전력 · 조명, 잉여 발전 (deficit = 부족 전력, 용도별로 나눔)
  · 부족(구매) = max(부하 − PV, 0), 부하 = 냉방/3 + 난방/2.5 + 조명
  · 부족을 열부하·조명으로 나눌 때는 그 timestep 부하 비율로 나눔(PV 를 두 부하에 같은 비율로 씀)
  · 잉여 = max(PV − 부하, 0)
- 색은 7번 칸(plot_panel07_mech.py)과 같게: 난방 #be123c, 조명 #64748b, PV(잉여) = TARGET
- 이전 판 plot_panel08_day_stack.py(하루 합계 막대)는 그대로 둠
출력: projects/03_bipv_experiments/mech_week/figures/dm_panel08_day_cum.svg (+ .png)
실행: python projects/03_bipv_experiments/mech_week/plot_panel08_day_cum.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
W, H = 178, 112  # pt (① 겨울 합계 200 pt 오른쪽, 사이 8 pt)
LEFT, RIGHT, TOP, BOTTOM, WSPACE = 26, 5, 12, 22, 0.12  # pt
LAYERS = [("heat_def", "부족 전력 · 냉난방", "#be123c"), ("light_def", "부족 전력 · 조명", "#64748b"), ("surplus", "잉여 발전", P.TARGET)]
ALPHA = 1.0  # 반투명이면 격자선이 비쳐 보여 불투명으로
POL = [("태양고도 추적", P.ST_SQL), ("TiDE", P.TIDE)]


def parts(d):
    heat = d.cool / 3 + d.heat / 2.5
    share = (heat / d.load).fillna(0)
    out = pd.DataFrame({"heat_def": d.purchase * share, "light_def": d.purchase * (1 - share), "surplus": d.surplus})
    # 누적: 0시에 0 을 넣고 각 timestep 끝 시각에 값을 찍는다
    c = out.cumsum()
    c.index = c.index + P.STEP
    c.loc[c.index[0] - P.STEP] = 0.0
    return c.sort_index()


def main(D=P.DAY):
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    cs = {k: parts(P.load_day(sql, D)) for k, sql in POL}
    for k, c in cs.items():
        e = c.iloc[-1]
        print(f"{k:>8} 열부하 부족 {e.heat_def:6.1f} 조명 부족 {e.light_def:5.1f} 잉여 {e.surplus:5.1f} 합 {e.sum():6.1f} kWh")
    ymax = max(c.iloc[-1].sum() for c in cs.values())

    fig, axes = plt.subplots(1, 2, figsize=(W / 72, H / 72), sharey=True)
    for ax, (k, _) in zip(axes, POL):
        c = cs[k]
        ax.stackplot(c.index, *[c[col] for col, _, _ in LAYERS], colors=[cl for _, _, cl in LAYERS], alpha=ALPHA, lw=0,
                     labels=[lb for _, lb, _ in LAYERS])
        tot = c.iloc[-1].sum()
        ax.annotate(f"{tot:.0f}", (c.index[-1], tot), xytext=(-1, 1.5), textcoords="offset points", ha="right",
                    va="bottom", color=P.INK1)
        ax.set_title(k, loc="left", color=P.INK1, pad=3)
        ax.set_xlim(D, D + pd.Timedelta(hours=24))
        ax.set_ylim(0, ymax * 1.12)
        # 두 그래프가 붙어 있어 왼쪽 24시와 오른쪽 0시 글자가 겹치므로, 왼쪽은 0~18, 오른쪽은 6~24 만 표시
        hrs = [0, 6, 12, 18] if ax is axes[0] else [6, 12, 18, 24]
        ax.set_xticks([D + pd.Timedelta(hours=h) for h in hrs], [str(h) for h in hrs])
        P.ygrid(ax)
    axes[0].set_ylabel("누적 kWh")
    fig.supxlabel("시각 [h]", fontsize=P.FS, color=P.INK2, y=0.0, va="bottom")
    h, lab = axes[0].get_legend_handles_labels()
    P.legend(axes[0], handles=h[::-1], labels=lab[::-1], loc="upper left")

    fig.subplots_adjust(left=LEFT / W, right=1 - RIGHT / W, top=1 - TOP / H, bottom=BOTTOM / H, wspace=WSPACE)
    out = P.OUT / "dm_panel08_day_cum.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

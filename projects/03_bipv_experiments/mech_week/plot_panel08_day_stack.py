"""
projects/03_bipv_experiments/mech_week/plot_panel08_day_stack.py
====================================================
공모전 패널 8번 ② 대표일(1/9) 하루 누적: 열부하·조명 부하(쌓은 막대)와 PV 발전량 (2026-11-04).
- 정책별로 막대 두 개: 왼쪽 = 부하(열부하 + 조명 쌓기), 오른쪽 = PV 발전
- 열부하 = 냉방/3 + 난방/2.5 (1/9 은 냉방 0), 조명 = 조명 전력, 단위 kWh/일 (0~24시)
- 색은 7번 칸(plot_panel07_mech.py)과 같게: 난방 #be123c, 조명 #64748b, PV = TARGET
- 크기는 ① 겨울 합계(plot_panel08_winter.py, 폭을 줄인 판)의 오른쪽 자리에 맞춤
출력: projects/03_bipv_experiments/mech_week/figures/dm_panel08_day_stack.svg (+ .png)
실행: python projects/03_bipv_experiments/mech_week/plot_panel08_day_stack.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
W, H = 146, 112  # pt
LEFT, RIGHT, TOP, BOTTOM = 26, 4, 12, 14  # pt, 위는 제목 한 줄 자리(① 과 같은 높이), 범례는 축 안 위쪽
HEAT, LIGHT, PV = "#be123c", "#64748b", P.TARGET
BAR_W = 0.36
POL = [("태양고도 추적", P.ST_SQL), ("TiDE", P.TIDE)]


def main(D=P.DAY):
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    v = {}
    for k, sql in POL:
        d = P.load_day(sql, D)
        v[k] = dict(heat=(d.cool / 3 + d.heat / 2.5).sum(), light=d.lights.sum(), pv=d.pv.sum())
        print(f"{k:>8} 열부하 {v[k]['heat']:6.1f} 조명 {v[k]['light']:5.1f} 부하 {v[k]['heat'] + v[k]['light']:6.1f} PV {v[k]['pv']:6.1f} kWh")

    fig, ax = plt.subplots(figsize=(W / 72, H / 72))
    off = BAR_W / 2 + 0.02  # 부하 막대와 PV 막대의 가운데 간격 절반
    for i, (k, _) in enumerate(POL):
        x = v[k]
        xl, xp = i - off, i + off
        ax.bar(xl, x["heat"], BAR_W, color=HEAT, lw=0)
        ax.bar(xl, x["light"], BAR_W, bottom=x["heat"], color=LIGHT, lw=0)
        ax.bar(xp, x["pv"], BAR_W, color=PV, lw=0)
        # 조각 안 숫자(흰 글자), 막대 위 합계
        ax.text(xl, x["heat"] / 2, f"{x['heat']:.0f}", ha="center", va="center", color="white")
        ax.text(xl, x["heat"] + x["light"] / 2, f"{x['light']:.0f}", ha="center", va="center", color="white")
        tot = x["heat"] + x["light"]
        ax.annotate(f"{tot:.0f}", (xl, tot), xytext=(0, 1.5), textcoords="offset points", ha="center", va="bottom",
                    color=P.INK1)
        ax.annotate(f"{x['pv']:.0f}", (xp, x["pv"]), xytext=(0, 1.5), textcoords="offset points", ha="center",
                    va="bottom", color=P.TARGET_DEEP)
    ax.set_xticks(range(len(POL)), [k for k, _ in POL])
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.6, len(POL) - 0.4)
    ymax = max(x["heat"] + x["light"] for x in v.values())
    ax.set_ylim(0, ymax * 1.32)  # 위쪽에 범례 자리
    ax.set_ylabel("kWh")
    P.ygrid(ax)
    ax.set_title("하루 합계 (0~24시)", loc="left", color=P.INK1, pad=3)
    hs = [Patch(color=HEAT, lw=0), Patch(color=LIGHT, lw=0), Patch(color=PV, lw=0)]
    P.legend(ax, handles=hs, labels=["열부하", "조명", "PV 발전"], loc="upper left", ncol=3)

    fig.subplots_adjust(left=LEFT / W, right=1 - RIGHT / W, top=1 - TOP / H, bottom=BOTTOM / H)
    out = P.OUT / "dm_panel08_day_stack.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

"""
projects/03_bipv_experiments/mech_week/plot_panel07_concept2.py
===================================================
공모전 패널 07 "각도 제어의 작동 원리" 개념도 2판 (가상 자료, 2026-11-05).
위: 기준(태양고도 추적, 발전 우선)의 PV·수요 한 줄. 정오 잉여와 오후 구매 두 문제만 표시
가운데: "조절 구간에서 각도↑ (TiDE)" 화살표
아래: 세 칸 a) 열부하  b) PV · 수요  c) 구매 전력. 기준은 회색 점선, TiDE 는 색 실선, 차이는 감소 청록 · 증가 붉은색
가상 곡선은 plot_panel07_concept.curves() 를 그대로 씀 (방향·상대 크기는 실제 1/9 결과와 맞춤)
출력: mech_week/figures/dm_panel07_concept2.svg (+ .png)
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Patch

import plot_panel07_concept as C0
from plot_panel07_concept import P, HEAT, PUR, T0, T1, WS, WE, curves, louver

W, H = 386, 202
BASE = "#94a3b8"  # 기준 점선
GOOD, BAD = P.EVAL, P.LOSS


def frame(ax, ticks=True):
    ax.axvspan(WS, WE, color=P.EVAL, alpha=0.07, lw=0)
    ax.axvline(WE, color=P.EVAL, lw=0.6, ls=P.DASH)
    ax.set_xlim(T0, T1)
    ax.set_yticks([])
    ax.set_xticks([WS, WE], ["조절 시작", "제어 종료"] if ticks else ["", ""])
    ax.tick_params(axis="x", length=2, pad=1.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def note(ax, s, color, x=0.03, ha="left"):
    ax.text(x, 0.97, s, transform=ax.transAxes, ha=ha, va="top", color=color, fontsize=5.5, linespacing=1.15,
            zorder=5, bbox=dict(boxstyle="square,pad=0.15", facecolor="white", edgecolor="none"))


def main():
    P.style()
    t, Cv = curves()
    st, td = Cv["st"], Cv["td"]
    fig = plt.figure(figsize=(W / 72, H / 72))
    L, R = 64, 4
    pt = lambda x, y, w, h: [x / W, y / H, w / W, h / H]  # noqa: E731

    # ── 위: 기준 ──
    by, bh = H - 4 - 56, 56
    fig.text(2 / W, (by + bh) / H, "기준", ha="left", va="top", color=P.FROZEN, fontweight="bold")
    fig.text(2 / W, (by + bh - 9) / H, "태양고도 추적\n발전 우선", ha="left", va="top", color=P.INK3, fontsize=5,
             linespacing=1.15)
    louver(fig.add_axes(pt(6, by - 2, 40, 32)), False)
    ax = fig.add_axes(pt(L, by, W - L - R, bh))
    frame(ax, ticks=False)
    ax.fill_between(t, st["pv"], st["load"], where=st["pv"] > st["load"], interpolate=True, color=P.TARGET_TINT, lw=0)
    ax.fill_between(t, st["pv"], st["load"], where=st["load"] > st["pv"], interpolate=True, color=PUR, alpha=0.4, lw=0)
    ax.plot(t, st["load"], color=P.INK1, lw=0.9)
    ax.plot(t, st["pv"], color=P.TARGET, lw=1.0)
    ax.set_ylim(0, 4.9)
    ax.text(12.85, 2.75, "정오 잉여 (쓰지 못함)", ha="center", va="center", color=P.TARGET_DEEP, fontsize=5.5)
    ax.text(17.7, 1.35, "오후 구매", ha="center", va="center", color=P.FROZEN, fontsize=5.5)
    ax.text(9.5, 1.35, "오전 구매", ha="center", va="center", color=P.FROZEN, fontsize=5.5)
    ax.text(WS + 0.12, 4.75, "조절 구간", ha="left", va="top", color=P.EVAL, fontsize=5.5)

    # ── 가운데: 바꾸는 조작 ──
    my = by - 26
    fig.add_artist(FancyArrowPatch(((L + (W - L - R) / 2) / W, (by - 3) / H), ((L + (W - L - R) / 2) / W, (my + 3) / H),
                                   transform=fig.transFigure, arrowstyle="-|>", mutation_scale=6, color=P.EVAL, lw=1.0))
    fig.text((L + (W - L - R) / 2 + 6) / W, (my + 12) / H, "조절 구간에서만 각도↑ (TiDE: 일사를 실내로)",
             ha="left", va="center", color=P.EVAL, fontweight="bold")

    # ── 아래: 세 칸 ──
    ph, BOT, GAPX = 74, 30, 8
    py = BOT
    fig.text(2 / W, (py + ph + 12) / H, "TiDE", ha="left", va="top", color=P.EVAL, fontweight="bold")
    fig.text(2 / W, (py + ph + 3) / H, "각도↑ · 일사 유입", ha="left", va="top", color=P.INK3, fontsize=5)
    louver(fig.add_axes(pt(6, py + 14, 40, 40)), True)
    pw = (W - L - R - 2 * GAPX) / 3
    cols = [("a) 열부하 (난방)", "heat", 4.7, "구간: 일사로 난방↓\n종료 뒤: 축열 방출로 ↓"),
            ("b) PV 발전 · 전력 수요", "pv", 6.3, "PV↓, 줄어든 몫은\n대부분 기준의 잉여"),
            ("c) 구매 전력 (해소할 부하)", "pur", 4.9, "구간 안 약간↑\n제어 종료 뒤 구매↓")]
    for j, (title, key, ym, s) in enumerate(cols):
        ax = fig.add_axes(pt(L + j * (pw + GAPX), py, pw, ph))
        frame(ax)
        ax.set_ylim(0, ym)
        ax.set_title(title, loc="left", color=P.INK1, pad=3, fontweight="bold")
        if key == "heat":
            ax.fill_between(t, td["heat"], st["heat"], where=st["heat"] > td["heat"], interpolate=True,
                            color=GOOD, alpha=0.2, lw=0)
            ax.plot(t, st["heat"], color=BASE, lw=0.9, ls=P.DASH)
            ax.plot(t, td["heat"], color=HEAT, lw=1.0)
        elif key == "pv":
            ax.fill_between(t, td["pv"], td["load"], where=td["pv"] > td["load"], interpolate=True,
                            color=P.TARGET_TINT, lw=0)
            ax.plot(t, st["pv"], color=BASE, lw=0.9, ls=P.DASH)
            ax.plot(t, td["load"], color=P.INK1, lw=0.9)
            ax.plot(t, td["pv"], color=P.TARGET, lw=1.0)
            ax.text(12.85, 2.25, "잉여", ha="center", va="center", color=P.TARGET_DEEP, fontsize=5)
            ax.text(14.0, 4.0, "기준 PV", ha="left", va="center", color=BASE, fontsize=5)
        else:
            ax.fill_between(t, td["pur"], color=PUR, alpha=0.4, lw=0)
            ax.fill_between(t, td["pur"], st["pur"], where=(st["pur"] > td["pur"]) & (t > WE), interpolate=True,
                            color=GOOD, alpha=0.35, lw=0)
            ax.fill_between(t, st["pur"], td["pur"], where=(td["pur"] > st["pur"]) & (t <= WE), interpolate=True,
                            color=BAD, alpha=0.35, lw=0)
            ax.plot(t, st["pur"], color=BASE, lw=0.9, ls=P.DASH)
            ax.plot(t, td["pur"], color=P.FROZEN, lw=0.9)
            ta = 18.1
            k = np.searchsorted(t, ta)
            ax.annotate("감소", (ta, (st["pur"][k] + td["pur"][k]) / 2), xytext=(17.6, 4.55), ha="center", va="center",
                        color=P.EVAL, fontsize=5, arrowprops=dict(arrowstyle="-", color=P.EVAL, lw=0.5))
        note(ax, s, P.EVAL)
    h = [Line2D([], [], color=BASE, lw=0.9, ls=P.DASH), Line2D([], [], color=HEAT, lw=1.0),
         Line2D([], [], color=P.TARGET, lw=1.0), Line2D([], [], color=P.INK1, lw=0.9),
         Patch(color=P.TARGET_TINT, lw=0), Patch(color=PUR, alpha=0.4, lw=0),
         Patch(color=GOOD, alpha=0.3, lw=0), Patch(color=BAD, alpha=0.35, lw=0)]
    lab = ["기준", "난방", "PV 발전", "전력 수요", "잉여", "구매", "감소분", "증가분"]
    fig.legend(h, lab, loc="lower left", bbox_to_anchor=(L / W, 0), ncol=8, frameon=False, handlelength=1.3,
               columnspacing=0.8, fontsize=5.5, borderaxespad=0.2)
    out = C0.P.OUT / "dm_panel07_concept2.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

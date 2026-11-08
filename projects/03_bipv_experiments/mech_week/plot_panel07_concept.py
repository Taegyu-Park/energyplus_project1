"""
projects/03_bipv_experiments/mech_week/plot_panel07_concept.py
==================================================
공모전 패널 07 "각도 제어의 작동 원리" 개념도 (가상 자료, 2026-11-05).
2행 × 3열. 행 1 = 각도↑ (TiDE: 일사 유입), 행 2 = 각도↓ (태양고도 추적: 발전 우선).
열 a) 열부하(난방)  b) PV 발전 · 전력 수요(잉여 음영)  c) 구매 전력 (수요 − PV, 해소할 부하)
- x축은 조절 구간 앞 ~ 저녁(9~19시)만. 조절 구간 음영, 제어 종료 세로선
- y축 숫자 없음, 위아래 행은 같은 축. 각 칸에 다른 행의 곡선을 옅은 점선으로 겹쳐 비교
- 가상 곡선이지만 방향과 상대 크기는 실제 1/9 결과(mech_week 실행)와 맞춤:
  구간 안 난방·조명↓, PV↓(대부분 잉여분), 구간 안 구매는 약간↑, 구간 뒤 난방(축열 방출)으로 구매↓
출력: mech_week/figures/dm_panel07_concept.svg (+ .png)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Circle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
HEAT = "#be123c"
PUR = "#94a3b8"
W, H = 386, 200  # pt
T0, T1, WS, WE = 9.0, 19.0, 10.0, 16.0
GAIN, PVCUT = 0.7, 0.6  # 가상 곡선 조절값


def curves():
    t = np.linspace(T0, T1, 801)
    sig = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
    w = sig((t - WS - 0.3) / 0.15) * sig((WE - 0.3 - t) / 0.15)  # 조절 구간 안 1
    heat_st = 0.9 + 2.2 * np.exp(-(t - T0) / 1.4) + 1.5 * sig((t - 16.8) / 0.7)
    # 난방 감소: 구간 안 직접 일사로 서서히 커지고, 제어 종료 뒤에는 축열 방출로 천천히 줄어듦 (끊김 없이 이어짐)
    ramp = sig((t - WS - 0.8) / 0.35)
    dec = np.where(t < WE, GAIN * ramp, GAIN * sig((WE - WS - 0.8) / 0.35) * np.exp(-(t - WE) / 4.0))
    heat_td = np.clip(heat_st - dec, 0.15, None)
    light_st = np.full_like(t, 0.8)
    light_td = light_st - 0.2 * w
    pv_st = 4.3 * np.exp(-((t - 12.8) / 2.1) ** 2)
    pv_td = pv_st * (1 - PVCUT * w)
    load_st, load_td = heat_st + light_st, heat_td + light_td
    pur_st, pur_td = np.clip(load_st - pv_st, 0, None), np.clip(load_td - pv_td, 0, None)
    dt = t[1] - t[0]
    inw, aft = (t >= WS) & (t < WE), t >= WE
    print(f"구간 안 구매 추적 {pur_st[inw].sum() * dt:.2f} TiDE {pur_td[inw].sum() * dt:.2f} | "
          f"구간 뒤 추적 {pur_st[aft].sum() * dt:.2f} TiDE {pur_td[aft].sum() * dt:.2f} | "
          f"잉여 추적 {np.clip(pv_st - load_st, 0, None).sum() * dt:.2f} TiDE {np.clip(pv_td - load_td, 0, None).sum() * dt:.2f}")
    return t, dict(td=dict(heat=heat_td, pv=pv_td, load=load_td, pur=pur_td),
                   st=dict(heat=heat_st, pv=pv_st, load=load_st, pur=pur_st))


def louver(ax, open_):
    """루버 단면 아이콘. 오른쪽 세로선 = 창(실내는 오른쪽), 왼쪽 위 해. open_=True: 슬랫이 수평에 가까워 빛이 실내로"""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Circle((0.13, 0.87), 0.09, color=P.TARGET_MID, lw=0))
    ax.plot([0.86, 0.86], [0.12, 0.88], color=P.INK2, lw=1.2)  # 창
    ys = [0.28, 0.5, 0.72]
    if open_:
        for y in ys:  # 각도 크게 → 슬랫이 열려 빛이 사이로 통과
            ax.plot([0.58, 0.76], [y + 0.03, y - 0.03], color=P.EVAL, lw=1.6, solid_capstyle="round")
        ax.add_patch(FancyArrowPatch((0.2, 0.78), (0.98, 0.38), arrowstyle="-|>", mutation_scale=5,
                                     color=P.TARGET, lw=0.8))
    else:
        for y in ys:  # 각도 작게 → 슬랫이 해를 향해 빛을 PV 로 받음
            ax.plot([0.6, 0.74], [y + 0.1, y - 0.1], color=P.FROZEN, lw=1.6, solid_capstyle="round")
        ax.add_patch(FancyArrowPatch((0.2, 0.78), (0.6, 0.57), arrowstyle="-|>", mutation_scale=5,
                                     color=P.TARGET, lw=0.8))


def main():
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    t, C = curves()
    fig = plt.figure(figsize=(W / 72, H / 72))
    L, R, TOP, BOT, GAPX, GAPY = 64, 4, 14, 30, 8, 10
    pw = (W - L - R - 2 * GAPX) / 3
    ph = (H - TOP - BOT - GAPY) / 2
    cols = [("a) 열부하 (난방)", "heat"), ("b) PV 발전 · 전력 수요", "pv"), ("c) 구매 전력 (해소할 부하)", "pur")]
    rows = [("td", "1. 각도↑", "TiDE · 일사 유입", P.EVAL, True), ("st", "2. 각도↓", "태양고도 추적\n발전 우선", P.FROZEN, False)]
    notes = {
        ("td", "heat"): "구간: 일사로 난방↓\n종료 뒤: 축열 방출로 ↓",
        ("st", "heat"): "일사 차단 → 축열 없음",
        ("td", "pv"): "PV↓, 줄어든 몫은\n대부분 잉여",
        ("st", "pv"): "PV↑, 수요를 넘는 몫은\n잉여로 남음",
        ("td", "pur"): "구간 안 약간↑\n제어 종료 뒤 구매↓",
        ("st", "pur"): "제어 종료 뒤\n구매 그대로",
    }
    ymax = {"heat": 4.7, "pv": 6.3, "pur": 4.9}
    GOOD = P.EVAL
    for i, (k, name, sub, col, open_) in enumerate(rows):
        other = "st" if k == "td" else "td"
        y = H - TOP - (i + 1) * ph - i * GAPY
        fig.text(2 / W, (y + ph) / H, name, ha="left", va="top", color=col, fontweight="bold")
        fig.text(2 / W, (y + ph - 9) / H, sub, ha="left", va="top", color=P.INK3, fontsize=5, linespacing=1.15)
        ia = fig.add_axes([4 / W, (y + 1) / H, 46 / W, (ph - 26) / H])
        louver(ia, open_)
        for j, (title, key) in enumerate(cols):
            x = L + j * (pw + GAPX)
            ax = fig.add_axes([x / W, y / H, pw / W, ph / H])
            ax.axvspan(WS, WE, color=P.EVAL, alpha=0.07, lw=0)
            ax.axvline(WE, color=P.EVAL, lw=0.6, ls=P.DASH)
            c, o = C[k], C[other]
            ax.plot(t, o[key], color=P.RULE, lw=0.8, ls=P.DASH)  # 다른 행 (비교)
            if key == "heat":
                if k == "td":
                    ax.fill_between(t, c["heat"], o["heat"], where=o["heat"] > c["heat"], interpolate=True,
                                    color=GOOD, alpha=0.18, lw=0)
                ax.plot(t, c["heat"], color=HEAT, lw=1.0)
            elif key == "pv":
                ax.fill_between(t, c["pv"], c["load"], where=c["pv"] > c["load"], interpolate=True,
                                color=P.TARGET_TINT, lw=0)
                ax.plot(t, c["load"], color=P.INK1, lw=0.9)
                ax.plot(t, c["pv"], color=P.TARGET, lw=1.0)
                ax.text(12.9, (2.25 if k == "td" else 2.9), "잉여", ha="center", va="center", color=P.TARGET_DEEP, fontsize=5)
            else:
                ax.fill_between(t, c["pur"], color=PUR, alpha=0.4, lw=0)
                if k == "td":
                    ax.fill_between(t, c["pur"], o["pur"], where=(o["pur"] > c["pur"]) & (t > WE), interpolate=True,
                                    color=GOOD, alpha=0.35, lw=0)
                    ax.fill_between(t, o["pur"], c["pur"], where=(c["pur"] > o["pur"]) & (t <= WE), interpolate=True,
                                    color=P.LOSS, alpha=0.35, lw=0)
                    ta = 18.1
                    ia_ = np.searchsorted(t, ta)
                    ax.annotate("감소", (ta, (o["pur"][ia_] + c["pur"][ia_]) / 2), xytext=(17.6, 4.55),
                                ha="center", va="center", color=P.EVAL, fontsize=5,
                                arrowprops=dict(arrowstyle="-", color=P.EVAL, lw=0.5))
                ax.plot(t, c["pur"], color=P.FROZEN, lw=0.9)
            ax.set_xlim(T0, T1)
            ax.set_ylim(0, ymax[key])
            ax.set_yticks([])
            ax.set_xticks([WS, WE], ["", ""] if i == 0 else ["조절 시작", "제어 종료"])
            ax.tick_params(axis="x", length=2, pad=1.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            ax.text(0.03, 0.97, notes[(k, key)], transform=ax.transAxes, ha="left", va="top", color=col,
                    fontsize=5.5, linespacing=1.15, zorder=5,
                    bbox=dict(boxstyle="square,pad=0.15", facecolor="white", edgecolor="none"))
            if i == 0:
                ax.set_title(title, loc="left", color=P.INK1, pad=3, fontweight="bold")
    h = [Line2D([], [], color=HEAT, lw=1.0), Line2D([], [], color=P.TARGET, lw=1.0), Line2D([], [], color=P.INK1, lw=0.9),
         Patch(color=P.TARGET_TINT, lw=0), Patch(color=PUR, alpha=0.4, lw=0), Patch(color=GOOD, alpha=0.25, lw=0), Patch(color=P.LOSS, alpha=0.35, lw=0),
         Line2D([], [], color=P.RULE, lw=0.8, ls=P.DASH)]
    lab = ["난방", "PV 발전", "전력 수요", "잉여", "구매", "감소분", "증가분", "다른 행 (비교)"]
    fig.legend(h, lab, loc="lower left", bbox_to_anchor=(L / W, 0), ncol=8, frameon=False, handlelength=1.3,
               columnspacing=0.8, fontsize=5.5, borderaxespad=0.2)
    out = P.OUT / "dm_panel07_concept.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

"""
projects/03_bipv_experiments/mech_week/plot_panel07_real.py
===============================================
공모전 패널 07 "각도 제어의 영향" 3판 (실제 자료, 2026-11-05). 그림 사이에 설명 글을 넣을 수 있게 두 조각으로 나눔.
  A) dm_panel07_base.svg : 기준(태양고도 추적) PV·수요 한 칸 + 루버 아이콘 (반폭)
  B) dm_panel07_tide.svg : TiDE a) 난방 전력  b) PV 발전·수요  c) 구매 전력 + 루버 아이콘. 기준은 회색 점선
자료: mech_week/runs/{mech_st, mech_tide} (같은 설정·같은 시작일), 1/9 9~19시, 10분 kWh (05·08 그래프와 같은 단위)
루버 아이콘: 기준은 슬랫이 햇빛과 수직(발전 최대), TiDE 는 슬랫이 외벽과 수직(수평, 빛이 실내로)
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from load_mech import RUNS, load  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
HEAT, PUR, BASE = "#be123c", "#94a3b8", "#94a3b8"
GOOD, BAD = P.EVAL, P.LOSS
D = pd.Timestamp("2006-01-09")
X0, X1 = D + pd.Timedelta(hours=9), D + pd.Timedelta(hours=19)
LAYOUT = (80, 2, 16, 16, 36)  # 왼쪽(아이콘 자리), 오른쪽, 칸 간격, 아래, 위 (pt, 470 pt 캔버스 기준)


def data():
    sl = slice(D, D + pd.Timedelta(hours=24) - P.STEP)
    a, b = load(RUNS["st"], D.day, D.day + 1)[sl], load(RUNS["tide"], D.day, D.day + 1)[sl]
    ang = pd.read_csv(P.ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(a.index).fillna(0)
    win = ang.index[ang["mask"] == 1]
    w0, w1 = win.min(), win.max() + P.STEP
    inw, aft = (a.index >= w0) & (a.index < w1), a.index >= w1
    d = b - a
    s = dict(heat_in=d.heat[inw].sum(), heat_aft=d.heat[aft].sum(), pv=d.pv.sum(), sur=d.surplus.sum(),
             sur_st=a.surplus.sum(), sur_td=b.surplus.sum(), pur_in=d.purchase[inw].sum(), pur_aft=d.purchase[aft].sum(),
             pur_st=a.purchase.sum(), pur_td=b.purchase.sum())
    print({k: round(v, 1) for k, v in s.items()}, f"{w0:%H:%M}~{w1:%H:%M}")
    keep = (a.index >= X0) & (a.index < X1)  # 19시 재실 종료 직전까지 (19시 급락 제외)
    a, b = a[keep], b[keep]
    t = a.index + P.STEP / 2
    return t, a, b, w0, w1, s  # 10분 kWh (05·08 그래프와 같은 단위)


def louver(ax, mode):
    """루버 단면. 기준과 TiDE 가 같은 그림(해·외벽·슬랫 위치)을 쓰고 슬랫 각도와 광선만 다름.
    오른쪽 세로선 = 외벽(실내는 오른쪽). mode='st': 슬랫이 햇빛과 수직, 'tide': 슬랫이 외벽과 수직(수평).
    광선은 가운데 슬랫 면에 부딪혀 멈춤"""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    sun = np.array([0.14, 0.86])
    ax.add_patch(Circle(sun, 0.09, color=P.TARGET_MID, lw=0))
    ax.plot([0.88, 0.88], [0.1, 0.9], color=P.INK2, lw=1.2)
    cx, ys, half = 0.66, [0.27, 0.5, 0.73], 0.11
    c = np.array([cx, 0.5])
    r = (c - sun) / np.linalg.norm(c - sun)  # 햇빛 방향 (해 → 가운데 슬랫)
    if mode == "st":
        sdir, col = np.array([-r[1], r[0]]), P.FROZEN  # 햇빛에 수직
    else:
        sdir, col = np.array([1.0, 0.0]), P.EVAL       # 외벽에 수직 (수평)
    for y in ys:
        m = np.array([cx, y])
        ax.plot(*zip(m - sdir * half, m + sdir * half), color=col, lw=1.6, solid_capstyle="round")
    nrm = np.array([-sdir[1], sdir[0]])
    if nrm @ r > 0:
        nrm = -nrm                                      # 해 쪽을 향한 슬랫 면의 법선
    # 광선과 가운데 슬랫 면(두께 반영)의 교점에서 멈춤
    face = c + nrm * 0.025
    tt = ((face - sun) @ nrm) / (r @ nrm)
    hit = sun + r * tt
    ax.add_patch(FancyArrowPatch(sun + r * 0.11, hit, arrowstyle="-|>", mutation_scale=5, color=P.TARGET, lw=0.8,
                                 shrinkA=0, shrinkB=0))


def frame(ax, w0, w1, ylim, yt):
    ax.axvspan(w0, w1, color=P.EVAL, alpha=0.07, lw=0)
    ax.axvline(w1, color=P.EVAL, lw=0.6, ls=P.DASH)
    ax.set_xlim(X0, X1)
    ax.set_ylim(*ylim)
    ax.set_yticks(yt)
    hs = [9, 12, 15, 18]
    ax.set_xticks([D + pd.Timedelta(hours=h) for h in hs], [str(h) for h in hs])
    ax.tick_params(length=2, pad=1.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def save(fig, name):
    out = P.OUT / f"{name}.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


def base(t, a, w0, w1, s):
    """TiDE 그림과 같은 캔버스 배율(Figma 에서 386/470 배로 rescale)과 같은 칸 크기·여백. 기준과 TiDE 칸을 그대로 비교"""
    L, R, GAP, BOT, TOP = LAYOUT
    pw, H = (470 - L - R - 2 * GAP) / 3, 128
    W = L + pw + R
    fig = plt.figure(figsize=(W / 72, H / 72))
    fig.text(1 / W, 1 - 1 / H, "태양고도 추적 제어", ha="left", va="top", color=P.FROZEN, fontweight="bold")
    fig.text(1 / W, 1 - 9 / H, "PV 발전 우선", ha="left", va="top", color=P.INK3, fontsize=5)
    louver(fig.add_axes([0, 12 / H, 57 / W, 57 / H]), "st")
    ph = H - BOT - TOP
    ax = fig.add_axes([L / W, BOT / H, pw / W, ph / H])
    ax.text(0, 1.0 + 11 / ph, "PV 발전 · 수요", transform=ax.transAxes, ha="left", va="bottom", color=P.INK1,
            fontweight="bold")
    ax.text(0, 1.0 + 3 / ph, f"잉여 {s['sur_st']:.1f} · 부족 {s['pur_st']:.1f} kWh", transform=ax.transAxes,
            ha="left", va="bottom", color=P.FROZEN, fontsize=5.5)
    frame(ax, w0, w1, (0, 5.2), [0, 2, 4])
    ax.fill_between(t, a.pv, a.load, where=a.pv > a.load, interpolate=True, color=P.TARGET_TINT, lw=0)
    ax.fill_between(t, a.pv, a.load, where=a.load > a.pv, interpolate=True, color=PUR, alpha=0.4, lw=0)
    ax.plot(t, a.load, color=P.INK1, lw=0.8)
    ax.plot(*P.pv_curve(a.pv), color=P.TARGET, lw=0.9)
    ax.set_ylabel("kWh", labelpad=1)
    ax.text(D + pd.Timedelta(hours=12.9), 3.0, "잉여", ha="center", color=P.TARGET_DEEP, fontsize=5)
    ax.text(D + pd.Timedelta(hours=17.6), 0.65, "부족", ha="center", color=P.FROZEN, fontsize=5)
    print(f"기준 캔버스 {W:.2f} x {H} pt")
    save(fig, "dm_panel07_base_term")


def tide(t, a, b, w0, w1, s):
    W, H = 470, 128  # Figma 에서 386 pt 폭으로 rescale. 각 칸 아래에 Figma 설명 글이 들어감
    fig = plt.figure(figsize=(W / 72, H / 72))
    fig.text(1 / W, 1 - 1 / H, "TiDE", ha="left", va="top", color=P.EVAL, fontweight="bold")
    fig.text(1 / W, 1 - 9 / H, "조절 구간 각도↑", ha="left", va="top", color=P.INK3, fontsize=5)
    louver(fig.add_axes([0, 12 / H, 57 / W, 57 / H]), "tide")  # 아이콘 1.3배
    L, R, GAP, BOT, TOP = LAYOUT
    pw, ph = (W - L - R - 2 * GAP) / 3, H - BOT - TOP
    cols = [
        ("a) 난방 전력", f"구간 {s['heat_in']:+.1f} · 종료 뒤 {s['heat_aft']:+.1f} kWh"),
        ("b) PV 발전 · 수요", f"PV {s['pv']:+.1f} kWh (잉여 {s['sur']:+.1f})"),
        ("c) 부족 전력", f"구간 {s['pur_in']:+.1f} · 종료 뒤 {s['pur_aft']:+.1f} kWh"),
    ]
    for j, (title, sub) in enumerate(cols):
        ax = fig.add_axes([(L + j * (pw + GAP)) / W, BOT / H, pw / W, ph / H])
        ax.text(0, 1.0 + 11 / ph, title, transform=ax.transAxes, ha="left", va="bottom", color=P.INK1, fontweight="bold")
        ax.text(0, 1.0 + 3 / ph, sub, transform=ax.transAxes, ha="left", va="bottom", color=P.EVAL, fontsize=5.5)
        if j == 0:
            frame(ax, w0, w1, (0, 5.2), [0, 2, 4])
            ax.set_ylabel("kWh", labelpad=1)
            ax.fill_between(t, b.heat, a.heat, where=a.heat > b.heat, interpolate=True, color=GOOD, alpha=0.25, lw=0)
            ax.plot(t, a.heat, color=BASE, lw=0.8, ls=P.DASH)
            ax.plot(t, b.heat, color=HEAT, lw=0.9)
        elif j == 1:
            frame(ax, w0, w1, (0, 5.2), [0, 2, 4])
            ax.fill_between(t, b.pv, b.load, where=b.pv > b.load, interpolate=True, color=P.TARGET_TINT, lw=0)
            ax.plot(*P.pv_curve(a.pv), color=BASE, lw=0.8, ls=P.DASH)
            ax.plot(t, b.load, color=P.INK1, lw=0.8)
            ax.plot(*P.pv_curve(b.pv), color=P.TARGET, lw=0.9)
        else:
            frame(ax, w0, w1, (0, 5.2), [0, 2, 4])
            ax.fill_between(t, b.purchase, color=PUR, alpha=0.4, lw=0)
            ax.fill_between(t, b.purchase, a.purchase, where=a.purchase > b.purchase, interpolate=True,
                            color=GOOD, alpha=0.45, lw=0)
            ax.fill_between(t, a.purchase, b.purchase, where=b.purchase > a.purchase, interpolate=True,
                            color=BAD, alpha=0.45, lw=0)
            ax.plot(t, a.purchase, color=BASE, lw=0.8, ls=P.DASH)
            ax.plot(t, b.purchase, color=P.FROZEN, lw=0.8)
        if j:
            ax.set_yticklabels([])
        ax.set_xlabel("")
    h = [Line2D([], [], color=BASE, lw=0.8, ls=P.DASH), Line2D([], [], color=HEAT, lw=0.9),
         Line2D([], [], color=P.TARGET, lw=0.9), Line2D([], [], color=P.INK1, lw=0.8),
         Patch(color=P.TARGET_TINT, lw=0), Patch(color=PUR, alpha=0.4, lw=0),
         Patch(color=GOOD, alpha=0.35, lw=0), Patch(color=BAD, alpha=0.45, lw=0), Patch(color=P.EVAL, alpha=0.07, lw=0)]
    lab = ["태양고도 추적 제어", "난방", "PV", "수요", "잉여", "부족", "감소", "증가", "조절 구간"]
    for j in range(3):
        print(f"칸 {j}: x {L + j * (pw + GAP):.1f} pt, 폭 {pw:.1f} pt (캔버스 {W} pt 기준)")
    fig.legend(h, lab, loc="upper right", bbox_to_anchor=(1 - R / W, 1), ncol=9, frameon=False, handlelength=1.2,
               columnspacing=0.7, fontsize=5.5, borderaxespad=0.1)
    fig.text(1 - R / W, 0.5 / H, "시각 [h]", ha="right", va="bottom", color=P.INK3, fontsize=5)
    save(fig, "dm_panel07_tide_term")


def main():
    P.style()
    t, a, b, w0, w1, s = data()
    base(t, a, w0, w1, s)
    tide(t, a, b, w0, w1, s)


if __name__ == "__main__":
    main()

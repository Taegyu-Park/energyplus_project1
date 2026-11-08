"""
projects/03_bipv_experiments/mech_week/plot_panel07_angle.py
================================================
공모전 패널 07 "각도 제어의 영향": 태양고도 추적 제어 그래프 옆에 들어갈 1/9 PV 각도 선택 그래프 (2026-11-05).
- 자료: tide_policy/eplus_week_oracle/angles_week.csv (theta_st = 태양고도 추적, tide = E+ 에 넣은 TiDE 각도, mask = 조절 구간)
  mech_tide 실행 스케줄(week_tide_oracle.csv)과 같은 값임을 확인함
- x축: 광주 1/9 일출~일몰 (NOAA 근사식으로 계산)
- 칸 크기·캔버스 배율은 plot_panel07_real.py 의 LAYOUT 과 같음 (Figma 에서 386/470 배로 rescale)
출력: mech_week/figures/dm_panel07_angle.svg (+ .png)
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

import plot_panel07_real as PR
from plot_panel07_real import P, D, LAYOUT, BASE

LAT, LON, TZ = 35.17, 126.89, 9  # 광주


def sun_times(day):
    """NOAA 근사식 일출·일몰 (지방 표준시, 대기 굴절 −0.833°)"""
    n = day.dayofyear
    g = 2 * np.pi / 365 * (n - 1)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g)
                    - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
           + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    lat = np.radians(LAT)
    ha = np.degrees(np.arccos(np.cos(np.radians(90.833)) / (np.cos(lat) * np.cos(dec)) - np.tan(lat) * np.tan(dec)))
    noon = 720 - 4 * LON - eot + TZ * 60
    return day + pd.Timedelta(minutes=noon - 4 * ha), day + pd.Timedelta(minutes=noon + 4 * ha)


def main():
    P.style()
    rise, sset = sun_times(D)
    print(f"일출 {rise:%H:%M} · 일몰 {sset:%H:%M}")
    ang = pd.read_csv(P.ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang[(ang.index >= D) & (ang.index < D + pd.Timedelta(days=1))]
    win = ang.index[ang["mask"] == 1]
    w0, w1 = win.min(), win.max() + P.STEP
    # 계단 그래프: 각 10분 스텝 시작~끝, 일출·일몰에서 자름
    # svg 는 clipPath 를 지우므로 축 밖 구간은 자료에서 직접 잘라냄 (일출~일몰)
    ang = ang[(ang.index + P.STEP > rise) & (ang.index < sset)]
    edges = list(ang.index) + [ang.index[-1] + P.STEP]
    edges[0], edges[-1] = max(edges[0], rise), min(edges[-1], sset)
    edges = pd.DatetimeIndex(edges)

    L0, R0, _, BOT, TOP = LAYOUT
    pw = (470 - L0 - R0 - 2 * 16) / 3
    L, R = 30, 4
    W, H = L + pw + R, 128
    ph = H - BOT - TOP
    fig = plt.figure(figsize=(W / 72, H / 72))
    ax = fig.add_axes([L / W, BOT / H, pw / W, ph / H])
    ax.axvspan(w0, w1, color=P.EVAL, alpha=0.07, lw=0)
    ax.stairs(ang["theta_st"].to_numpy(), edges, color=BASE, lw=0.8, ls=P.DASH, baseline=None)
    ax.stairs(ang["tide"].to_numpy(), edges, color=P.EVAL, lw=0.9, baseline=None)
    ax.set_xlim(rise, sset)
    ax.set_ylim(0, 95)
    ax.set_yticks([0, 30, 60, 90])
    hs = [8, 10, 12, 14, 16]
    ax.set_xticks([D + pd.Timedelta(hours=h) for h in hs], [str(h) for h in hs])
    ax.tick_params(length=2, pad=1.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_ylabel("각도 [°]", labelpad=1)
    ax.text(0, 1.0 + 11 / ph, "PV 각도 선택", transform=ax.transAxes, ha="left", va="bottom", color=P.INK1,
            fontweight="bold")
    h = [Line2D([], [], color=BASE, lw=0.8, ls=P.DASH), Line2D([], [], color=P.EVAL, lw=0.9)]
    # 범례는 제목 아래 줄(다른 그래프의 부제 자리), 축 폭 안에 둠
    ax.legend(h, ["태양고도 추적 제어", "TiDE"], loc="lower left", bbox_to_anchor=(0, 1.0 + 1 / ph), ncol=2,
              frameon=False, handlelength=1.2, columnspacing=0.7, fontsize=5.5, borderaxespad=0, borderpad=0,
              handletextpad=0.4)
    fig.text(1 - R / W, 0.5 / H, "시각 [h]", ha="right", va="bottom", color=P.INK3, fontsize=5)
    print(f"캔버스 {W:.2f} x {H} pt, 조절 구간 {w0:%H:%M}~{w1:%H:%M}")
    PR.save(fig, "dm_panel07_angle")


if __name__ == "__main__":
    main()

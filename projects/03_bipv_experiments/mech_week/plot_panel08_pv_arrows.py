"""
projects/03_bipv_experiments/mech_week/plot_panel08_pv.py
=============================================
공모전 패널 8번 ② PV 발전·전력 수요 그래프 축소판 (2026-11-04).
- plot_panel08_pv_term.py 복사본: 코드 화살표·잉여 면적 없음(Figma 의 손으로 그린 PV 감소 화살표를 위에 얹기 위한 바탕)
- plot_panel07_pv.py 와 같은 자료·스타일. 시간 범위만 09~21시로 자르고, 폭을 줄여 칸 왼쪽에 붙인다.
  오른쪽 남는 자리에는 Figma 에서 그래프 설명 글을 넣는다.
- 왼쪽 여백은 plot_panel07_all.py 와 같은 고정 36 pt (위 ① 그래프와 y축 이름 자리 맞춤)
- 원본 파일은 수정하지 않고 plot_panel_dm 의 함수만 가져온다.
출력: projects/03_bipv_experiments/mech_week/figures/dm_panel08_pv_day0109.svg (+ .png)
실행: python projects/03_bipv_experiments/mech_week/plot_panel08_pv.py
"""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MISMATCH / "explain_surplus_heating"))
import plot_panel_dm as P  # noqa: E402
from shared.paths import MISMATCH

P.OUT = HERE / "figures"
W, H = 228, 130  # pt
LEFT, RIGHT, TOP, BOTTOM = 36, 6, 30, 22  # pt, 위는 범례(2열 3줄) 자리
H0, H1 = 9, 21  # 시각 범위
YMAX = 5.0  # 09~21시 최대 약 4.4 kWh
G1 = 19  # 강조 구간 끝 (시작은 태양추적 PV·수요 교차 timestep)
# 색 (상수로 빼서 후보 비교용으로 바꿔 그릴 수 있게 함)
SPAN, SPAN_ALPHA, SPAN_TEXT = P.EVAL, 0.06, P.EVAL  # 조절 구간 배경·글자
FILL, FILL_ALPHA = P.EVAL, 0.35  # 구매 전력(강조) 면적
PV_ARROW = False  # 화살표는 Figma 에서 사용자가 그린 여러 화살표 묶음(1813:60675)을 붙여 씀


def main(D=P.DAY):
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    a, b = P.load_day(P.ST_SQL, D), P.load_day(P.TIDE, D)
    t = a.index + P.STEP / 2
    ang = pd.read_csv(P.ANGLES, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(pd.date_range(D, D + pd.Timedelta(hours=24) - P.STEP, freq=P.STEP)).fillna(0)
    win = ang.index[ang["mask"] == 1]
    w0, w1 = win.min(), win.max() + P.STEP

    # 설명 글용 수치 (kWh, 10분 합계의 합)
    def seg(df, s, e):
        x = df.loc[s:e - P.STEP]
        return x.pv.sum(), x.load.sum(), x.surplus.sum(), x.purchase.sum()

    for nm, s, e in [("하루", D, D + pd.Timedelta(hours=24)), ("09~21", D + pd.Timedelta(hours=H0), D + pd.Timedelta(hours=H1)),
                     ("조절 구간", w0, w1), ("구간 뒤~21", w1, D + pd.Timedelta(hours=H1)),
                     ("구간 뒤~24", w1, D + pd.Timedelta(hours=24))]:
        sa, sb = seg(a, s, e), seg(b, s, e)
        print(f"{nm:>10} | 태양추적 PV {sa[0]:6.1f} 수요 {sa[1]:6.1f} 잉여 {sa[2]:5.1f} 부족 {sa[3]:6.1f}"
              f" | TiDE PV {sb[0]:6.1f} 수요 {sb[1]:6.1f} 잉여 {sb[2]:5.1f} 부족 {sb[3]:6.1f}")
    print(f"PV 최대 태양추적 {a.pv.max():.2f} TiDE {b.pv.max():.2f} (kWh/10분)")

    # Figma 용 SVG 는 클리핑을 지우므로(strip_clip) xlim 만으로는 선이 축 밖으로 나간다.
    # 자료를 09~21시로 자르고, 양 끝 시각의 값은 선형 보간으로 넣어 선이 축 끝에서 정확히 시작·끝나게 한다.
    x0, x1 = D + pd.Timedelta(hours=H0), D + pd.Timedelta(hours=H1)

    def cut(s):
        s = pd.Series(s.to_numpy(), index=s.index + P.STEP / 2)
        s = s.reindex(s.index.union([x0, x1])).interpolate(method="time")
        return s.loc[x0:x1]

    def cut_pv(pv):
        s = cut(pv)
        on = s > 1e-6
        keep = on | on.shift(1, fill_value=False) | on.shift(-1, fill_value=False)
        return s.index, s.where(keep).to_numpy()

    pa, pb, la, lb = cut(a.pv), cut(b.pv), cut(a.load), cut(b.load)
    fig, ax = plt.subplots(figsize=(W / 72, H / 72))
    ax.axvspan(w0, w1, color=SPAN, alpha=SPAN_ALPHA, lw=0)
    ax.text(w0 + (w1 - w0) / 2, YMAX - 0.12, f"AI 제어 구간 {w0:%H:%M}~{w1:%H:%M}", ha="center", va="top", color=SPAN_TEXT)
    # 강조: 각도 조절로 건물이 실제 이득을 본 구간 = 오후 수요(난방) 감소. 잉여 면적은 칠하지 않는다.
    # 시작 = 정오 이후 태양추적 PV 가 처음으로 수요 아래로 내려가는 timestep(잉여 끝, 구매 시작), 끝 = G1시
    pm = a.loc[D + pd.Timedelta(hours=12):]
    g0 = pm.index[(pm.pv < pm.load).to_numpy()][0]
    g1 = D + pd.Timedelta(hours=G1)
    sl = slice(g0, g1 - P.STEP)
    gain = (a.load - b.load).loc[sl].sum()
    print(f"태양추적 PV<수요 교차 timestep {g0:%H:%M} (PV {a.pv[g0]:.2f} < 수요 {a.load[g0]:.2f}, "
          f"직전 {a.pv[g0 - P.STEP]:.2f} vs {a.load[g0 - P.STEP]:.2f})")
    print(f"{g0:%H:%M}~{G1}시 수요 감소 {gain:.2f} kWh (태양추적 {a.load.loc[sl].sum():.1f} → TiDE {b.load.loc[sl].sum():.1f})"
          f" | 구매 {a.purchase.loc[sl].sum():.2f} → {b.purchase.loc[sl].sum():.2f}"
          f" (감소 {a.purchase.loc[sl].sum() - b.purchase.loc[sl].sum():.2f}) | PV {a.pv.loc[sl].sum():.2f} → {b.pv.loc[sl].sum():.2f}")
    # 면적 = (태양추적 PV·수요 곡선의 교차점에서 x축으로 내린 수직선) + 검은 점선(수요·태양추적) + 검은 실선(수요·TiDE)
    # 교차점은 그려진 두 선(10분 값을 구간 가운데에 찍고 직선 연결)이 실제로 만나는 시각을 선형 보간으로 구한다.
    d = (pa - la).loc[D + pd.Timedelta(hours=12):]
    k = np.flatnonzero((d.to_numpy()[:-1] > 0) & (d.to_numpy()[1:] <= 0))[0]
    ta, tb, da, db = d.index[k], d.index[k + 1], d.iloc[k], d.iloc[k + 1]
    tc = ta + (tb - ta) * (da / (da - db))
    yc = float(np.interp(mdates.date2num(tc), mdates.date2num(la.index), la.to_numpy()))
    print(f"교차점 {tc:%H:%M:%S}, 수요 {yc:.2f} kWh/10분")
    # 교차 시각 tc 와 끝(두 수요 곡선이 19시 급감 뒤 다시 만나는 점)까지만 남긴다
    end = g1 + P.STEP
    grid = la.index.union([tc])
    sa = la.reindex(grid).interpolate(method="time").loc[tc:end]
    sb = lb.reindex(grid).interpolate(method="time").loc[tc:end]
    ax.fill_between(sa.index, sa, sb, where=(sa >= sb).to_numpy(), interpolate=True, color=FILL, alpha=FILL_ALPHA, lw=0,
                    label="오후 부하 저감")
    ax.plot([tc, tc], [0, yc], color=P.INK3, lw=0.5, ls=(0, (1.2, 1.2)))  # 교차점에서 x축으로 내린 수직선
    if PV_ARROW:
        # 조절 구간 안에서 두 PV 곡선 차이가 가장 큰 시각에 아래쪽 화살표. 글자는 하루 PV 감소량
        dp = (pa - pb).loc[w0:w1]
        ta = dp.idxmax()
        ya, yb = float(pa[ta]), float(pb[ta])
        ax.annotate("", xy=(ta, yb + 0.06), xytext=(ta, ya - 0.06),
                    arrowprops=dict(arrowstyle="-|>,head_length=0.35,head_width=0.18", color=P.TARGET_DEEP, lw=0.6,
                                    shrinkA=0, shrinkB=0))
        # 글자는 태양추적 PV 점선과 겹치지 않게 TiDE PV 쪽(아래)에 붙인다. 색이 PV 계열이라 'PV'는 생략
        ax.text(ta + pd.Timedelta(minutes=5), yb + 0.28, f"−{a.pv.sum() - b.pv.sum():.1f} kWh",
                ha="left", va="center", color=P.TARGET_DEEP)
        print(f"PV 화살표 {ta:%H:%M} {ya:.2f} → {yb:.2f}, 하루 PV {a.pv.sum():.1f} → {b.pv.sum():.1f}")
    ax.plot(*cut_pv(a.pv), color=P.TARGET, lw=0.8, ls=P.DASH, label="PV · 태양추적")
    ax.plot(*cut_pv(b.pv), color=P.TARGET, lw=1.0, label="PV · TiDE")
    ax.plot(la.index, la, color=P.INK1, lw=0.8, ls=P.DASH, label="수요 · 태양추적")
    ax.plot(lb.index, lb, color=P.INK1, lw=0.9, label="수요 · TiDE")
    ax.set_ylim(0, YMAX)
    ax.set_ylabel("kWh")
    ax.set_xlabel("시각 [h]")
    ax.set_xlim(D + pd.Timedelta(hours=H0), D + pd.Timedelta(hours=H1))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(H0, H1 + 1, 3)))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - D).total_seconds() / 3600):d}"))
    P.legend(ax, loc="lower left", bbox_to_anchor=(0, 1), ncol=2)

    fig.subplots_adjust(left=LEFT / W, right=1 - RIGHT / W, top=1 - TOP / H, bottom=BOTTOM / H)
    out = P.OUT / f"dm_panel08_pv_day{D:%m%d}_arrows.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

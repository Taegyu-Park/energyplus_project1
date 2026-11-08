"""
bipv_experiments/mech_week/plot_panel08_winter_cum.py
=====================================================
공모전 패널 8번 ② 겨울철 전체(11~3월, 149일) '오후 부하 저감' 누적 (2026-11-04).
- 2026-11-04 수정: 실제 부족 전력 차 점선은 빼고 오후 수요 감소(③ 청록 면)만 표시, 범례 없음(제목으로 대신)
- ③(plot_panel08_pv_arrows.py)의 청록 면적을 매일 구해 겨울 순서(11월 → 3월)로 누적한다.
  하루 면적 = 정오 이후 태양추적 PV 가 처음으로 수요 아래로 내려가는 timestep 부터 19시까지
             (수요·태양추적 − 수요·TiDE) 의 합. ③ 과 같은 정의(timestep 합, 교차점 보간은 하지 않음)
  태양추적 PV 가 하루 종일 수요보다 작아 잉여가 없는 날(흐린 날)은 교차점이 없으므로 0 으로 둔다.
- 같은 구간의 실제 부족 전력 차(부족·태양추적 − 부족·TiDE)도 같이 출력한다(그림에는 점선으로 표시).
- 자료: 태양추적 = c3_FE_ST_lw_dl400 (case3 E+ 연간), TiDE = eplus_winter_oracle/runs/winter_tide_* (월별 조각)
  하루 = 07시 ~ 다음 날 07시 (plot_winter_bar.py 와 같은 평가 스텝)
출력: bipv_experiments/mech_week/figures/dm_panel08_winter_cum.svg (+ .png)
실행: python bipv_experiments/mech_week/plot_panel08_winter_cum.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WIN = ROOT / "bipv_mismatch" / "tide_policy" / "eplus_winter_oracle"
sys.path.insert(0, str(ROOT / "bipv_mismatch" / "explain_surplus_heating"))
sys.path.insert(0, str(WIN))
import plot_panel_dm as P  # noqa: E402
import plot_winter_bar as WB  # noqa: E402

P.OUT = HERE / "figures"
W, H = 178, 112  # pt (① 겨울 합계 200 pt 오른쪽)
LEFT, RIGHT, TOP, BOTTOM = 26, 8, 12, 14  # pt
G1 = 19  # 하루 면적 끝 시각 (③ 과 같음)
FILL, FILL_ALPHA = P.EVAL, 0.35  # ③ 의 '오후 부하 저감' 면적과 같은 색
STEP = pd.Timedelta(minutes=10)


def winter_frames():
    ang = pd.read_csv(WIN / "angles_winter.csv", parse_dates=["start"]).set_index("start")
    steps = ang.index
    st = WB.load(WB.ST).loc[steps]
    parts = []
    for name, month in WB.CHUNKS.items():
        x = WB.load(WIN / "runs" / f"winter_tide_{name}" / "eplusout.sql")
        own = steps[(steps - pd.Timedelta(hours=7)).month == month]
        parts.append(x.loc[own])
    td = pd.concat(parts).sort_index()
    assert td.index.equals(steps)
    return st, td, steps


def daily(st, td, steps):
    rows = []
    for d0 in steps[::144]:
        D = d0.normalize()
        a = st.loc[d0:d0 + pd.Timedelta(hours=24) - STEP]
        b = td.loc[a.index]
        gain = real = 0.0
        g0 = None
        if (a.pv > a.load).any():
            pm = a.loc[D + pd.Timedelta(hours=12):]
            g0 = pm.index[(pm.pv < pm.load).to_numpy()][0]
            s = slice(g0, D + pd.Timedelta(hours=G1) - STEP)
            gain = (a.load - b.load).loc[s].sum()
            real = (a.deficit - b.deficit).loc[s].sum()
        rows.append(dict(day=D, g0=g0, gain=gain, real=real))
    r = pd.DataFrame(rows)
    # 겨울 순서: 11·12월 → 1~3월
    r["order"] = np.where(r.day.dt.month >= 10, 0, 1)
    return r.sort_values(["order", "day"]).reset_index(drop=True)


def main():
    st, td, steps = winter_frames()
    r = daily(st, td, steps)
    n0 = (r.g0.isna()).sum()
    print(f"{len(r)}일, 잉여 없는 날 {n0}일 | 면적(수요 차) 합 {r.gain.sum():.1f} kWh, 같은 구간 실제 부족 차 {r.real.sum():.1f} kWh")
    print(f"하루 전체 부족 차 합 {(st.deficit - td.deficit).sum():.1f} kWh, 1/9 면적 {r.set_index('day').gain[pd.Timestamp('2006-01-09')]:.2f}")

    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(r) + 1)
    cum = np.r_[0, r.gain.cumsum().to_numpy()]  # kWh (MWh 로 하면 0.42 처럼 작아 kWh 로)
    cum_real = np.r_[0, r.real.cumsum().to_numpy()]
    fig, ax = plt.subplots(figsize=(W / 72, H / 72))
    ax.fill_between(x, 0, cum, step="post", color=FILL, alpha=FILL_ALPHA, lw=0)
    ax.step(x, cum, where="post", color=FILL, lw=0.9)
    ax.annotate(f"{cum[-1]:.0f} kWh", (x[-1], cum[-1]), xytext=(-1, 2), textcoords="offset points", ha="right",
                va="bottom", color=P.EVAL)
    # x 눈금: 각 달의 첫날
    first = r.groupby(r.day.dt.to_period("M"), sort=False).head(1)
    ax.set_xticks(first.index, [f"{m}월" for m in first.day.dt.month])
    ax.set_xlim(0, len(r))
    ax.set_ylim(0, cum[-1] * 1.15)
    ax.set_ylabel("누적 kWh")
    P.ygrid(ax)
    fig.subplots_adjust(left=LEFT / W, right=1 - RIGHT / W, top=1 - TOP / H, bottom=BOTTOM / H)
    out = P.OUT / "dm_panel08_winter_cum.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

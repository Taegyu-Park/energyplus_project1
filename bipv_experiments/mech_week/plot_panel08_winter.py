"""
bipv_experiments/mech_week/plot_panel08_winter.py
=================================================
공모전 패널 8번 ① 겨울철 전체(11~3월) 잉여 발전·전체 부하 합계 막대 (2026-11-04).
- 원본: bipv_mismatch/tide_policy/eplus_winter_oracle/plot_winter_bar.py (수정하지 않고 load() 와 자료 경로만 가져옴)
- 원본과 다른 점: 고정 0° 제외(태양고도 추적 vs TiDE 만), 'TiDE 최종' → 'TiDE', y축 'MWh / 겨울' → 'MWh',
  그림 안 큰 제목 없음(Figma 칸 제목으로 대신), 변화율은 두 막대 사이 회색 사다리꼴 위에 표시(2026-11-04), 패널 스타일(plot_panel_dm: scientific-kr, 6pt, A-PPTL 색)
- 자료: 태양추적 = pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400 (case3 E+ 연간)
        TiDE   = eplus_winter_oracle/runs/winter_tide_{jan,feb,mar,nov,dec} (case3 E+, 월별 조각, 예열 구간은 버림)
  집계 = angles_winter.csv 의 평가 스텝(149일, 하루 = 07시 ~ 다음 날 07시), 수요 = 냉방/3 + 난방/2.5 + 조명
- 왼쪽 여백 36 pt 는 ② 그래프(plot_panel08_pv.py)와 같게 해서 두 그래프의 y축을 세로로 맞춘다.
출력: bipv_experiments/mech_week/figures/dm_panel08_winter_bar.svg (+ .png)
실행: python bipv_experiments/mech_week/plot_panel08_winter.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WIN = ROOT / "bipv_mismatch" / "tide_policy" / "eplus_winter_oracle"
sys.path.insert(0, str(ROOT / "bipv_mismatch" / "explain_surplus_heating"))
sys.path.insert(0, str(WIN))
import plot_panel_dm as P  # noqa: E402
import plot_winter_bar as WB  # noqa: E402

P.OUT = HERE / "figures"
W, H = 200, 112  # pt (오른쪽에 ② 시간 누적(178 pt)을 넣기 위해 386 → 232 → 200 으로 줄임, 2026-11-04)
LEFT, RIGHT, TOP, BOTTOM, WSPACE = 36, 4, 12, 14, 0.16  # pt, 위는 소제목 한 줄 자리
BAR_W = 0.28  # 막대 폭 (사이 간격에 감소율 글자가 들어가도록 좁게)
GAP_FILL, GAP_ALPHA, GAP_TEXT = P.FROZEN_TINT, 0.9, P.INK3  # 두 막대 윗변을 잇는 회색 면, 감소율 글자
POL = [("태양고도 추적", "#94a3b8", P.INK3), ("TiDE", P.EVAL, P.EVAL)]  # 이름, 막대 색(기준 회색 = 7번 칸 BASE), 값 글자 색


def winter_totals():
    ang = pd.read_csv(WIN / "angles_winter.csv", parse_dates=["start"]).set_index("start")
    steps = ang.index
    st = WB.load(WB.ST)
    parts = []
    for name, month in WB.CHUNKS.items():  # 원본과 같은 조각 이어 붙이기: 그 달에 시작하는 평가일만
        x = WB.load(WIN / "runs" / f"winter_tide_{name}" / "eplusout.sql")
        own = steps[(steps - pd.Timedelta(hours=7)).month == month]
        assert own.difference(x.index).empty, name
        parts.append(x.loc[own])
    tide = pd.concat(parts).sort_index()
    assert tide.index.equals(steps)
    cols = ["pv", "load", "surplus", "deficit"]
    t = pd.DataFrame({"태양고도 추적": st.loc[steps, cols].sum(), "TiDE": tide[cols].sum()}).T / 1000  # MWh
    return t, len(steps) // 144


def main():
    t, ndays = winter_totals()
    print(f"[겨울 {ndays}일, 07시 ~ 다음 날 07시] (MWh)\n{t.round(3).to_string()}")
    P.style()
    P.OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(W / 72, H / 72), sharey=True)  # 두 그래프 y축 같은 눈금(2026-11-04)
    for ax, (col, title) in zip(axes, [("surplus", "잉여 발전"), ("load", "전체 부하")]):
        va, vb = t.loc["태양고도 추적", col], t.loc["TiDE", col]
        # 두 막대 사이: 앞 막대 오른쪽 윗모서리 → 뒤 막대 왼쪽 윗모서리를 잇는 회색 사다리꼴 + 가운데 감소율
        x0, x1 = BAR_W / 2, 1 - BAR_W / 2
        ax.fill([x0, x0, x1, x1], [0, va, vb, 0], color=GAP_FILL, alpha=GAP_ALPHA, lw=0, zorder=1)
        ax.text(0.5, min(va, vb) * 0.5, f"{(vb - va) / va * 100:+.1f}%".replace("-", "−"), ha="center", va="center",
                color=GAP_TEXT, fontweight="bold", zorder=3)
        for i, (k, c, tc) in enumerate(POL):
            v = t.loc[k, col]
            ax.bar(i, v, color=c, width=BAR_W, lw=0, zorder=2)
            ax.annotate(f"{v:.2f}", (i, v), xytext=(0, 1.5), textcoords="offset points", ha="center", va="bottom",
                        color=tc)
        ax.set_xticks(range(len(POL)), [k for k, _, _ in POL])
        ax.tick_params(axis="x", length=0)
        ax.set_xlim(-0.42, len(POL) - 0.58)  # 좌우 여백을 줄여 막대 사이(감소율 글자 자리)를 넓힘
        ax.set_ylim(0, t[["surplus", "load"]].to_numpy().max() * 1.15)  # 두 그래프 공통 범위
        ax.set_title(title, loc="left", color=P.INK1, pad=3)
        P.ygrid(ax)
    axes[0].set_ylabel("MWh")
    w, h = W, H
    fig.subplots_adjust(left=LEFT / w, right=1 - RIGHT / w, top=1 - TOP / h, bottom=BOTTOM / h, wspace=WSPACE)
    out = P.OUT / "dm_panel08_winter_bar.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


if __name__ == "__main__":
    main()

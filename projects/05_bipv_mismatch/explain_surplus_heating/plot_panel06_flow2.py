"""
projects/05_bipv_mismatch/explain_surplus_heating/plot_panel06_flow2.py
===========================================================
공모전 패널 06번 흐름도 2판(예시형)에 들어갈 미니 그래프 2개 (2026-11-04).
대표일 1/17, case2 고정 40° 실제 결과 (dataset_final/case2_mm_train.csv).

1) dm_panel06_d_raw     : "시뮬레이션 결과는 여러 데이터" — 고정 40°의 출력 9개를 0~1로 맞춰 한 축에 겹침
2) dm_panel06_e_extract : "목적에 맞게 추출·가공" — 같은 축에 PV 발전·전력 수요 2개만 남기고 차이(미스매치)에 음영

PV 발전과 전력 수요는 두 그래프 모두 같은 기준(둘 중 큰 값)으로 나눠, 2)의 선이 1)의 선과 정확히 같은 모양이 되게 함.
스타일·글자 크기는 plot_panel06_flow.py 와 같음 (4.2pt).
출력: explain_surplus_heating/figures/dm_panel06_{d_raw,e_extract}.svg (+ .png)
실행: python projects/05_bipv_mismatch/explain_surplus_heating/plot_panel06_flow2.py
"""

import matplotlib.pyplot as plt
import pandas as pd

import plot_panel_dm as P
from plot_panel06_flow import CASE2, D, X0, X1, hours, style

ANGLE = 40
SIZE = (62 / 72, 36 / 72)
OTHERS = [  # (열, 색) — 일부러 여러 색을 섞어 "복잡한 결과" 로 보이게 함
    ("heat_load", "#be123c"), ("lights_kwh", "#ca8a04"), ("poa", "#7c3aed"), ("pv_cell_temp", "#0891b2"),
    ("south_zone_temp", "#16a34a"), ("south_win_tx", "#db2777"), ("purchase", "#64748b"),
]
WEATHER = [("outdoor_temp", "#2563eb"), ("ghi", "#a16207")]


def data():
    c2 = pd.read_csv(CASE2, parse_dates=["timestamp"])
    c2.index = c2.timestamp - P.STEP
    x = c2.loc[X0:X1]
    out = pd.DataFrame(index=x.index + P.STEP / 2)
    pv, dem = x[f"pv_gen_{ANGLE}"].to_numpy(), x[f"demand_elec_{ANGLE}"].to_numpy()
    ref = max(pv.max(), dem.max())
    out["pv"], out["dem"] = pv / ref, dem / ref
    for c, _ in OTHERS:
        v = x[f"{c}_{ANGLE}"]
        out[c] = ((v - v.min()) / (v.max() - v.min() + 1e-9)).to_numpy()
    for c, _ in WEATHER:
        v = x[c]
        out[c] = ((v - v.min()) / (v.max() - v.min() + 1e-9)).to_numpy()
    return out


def axes():
    fig, ax = plt.subplots(figsize=SIZE)
    ax.set_ylim(0, 1.08)
    ax.set_yticks([])
    hours(ax)
    return fig, ax


def chart_raw(x):
    fig, ax = axes()
    for c, col in OTHERS + WEATHER:
        ax.plot(x.index, x[c], color=col, lw=0.45, alpha=0.85)
    ax.plot(x.index, x.dem, color=P.INK1, lw=0.45)
    ax.plot(x.index, x.pv, color=P.TARGET, lw=0.45)
    P.save(fig, "dm_panel06_d_raw")


def chart_extract(x):
    fig, ax = axes()
    ax.fill_between(x.index, x.pv, x.dem, color="#e2e8f0", lw=0)
    ax.plot(x.index, x.dem, color=P.INK1, lw=0.7)
    ax.plot(x.index, x.pv, color=P.TARGET, lw=0.7)
    ax.text(X0 + pd.Timedelta(minutes=15), x.dem.iloc[0] + 0.03, "수요", va="bottom", color=P.INK1)
    i = x.pv.idxmax()
    ax.text(i, x.pv.max() + 0.03, "PV", ha="center", va="bottom", color=P.TARGET)
    P.save(fig, "dm_panel06_e_extract")


def main():
    style()
    x = data()
    print(f"[d/e] {D:%m/%d} 고정 {ANGLE}°, 선 {len(OTHERS) + len(WEATHER) + 2}개 → 2개")
    chart_raw(x)
    chart_extract(x)


if __name__ == "__main__":
    main()

"""
eplus_jan13/analyze_a50_10to11.py
=================================
jan13_a50_10to11 (10~11시 50°, 11:00~14:10 90°) vs 태양추적, jan13_surplus90.png 와 같은 형식의 그림.
읽기·집계는 analyze.py 의 load() 를 그대로 쓴다 (수요 L = 냉방/3.0 + 난방/2.5 + 조명).

출력: eplus_jan13/jan13_a50_10to11.png, 표준 출력(1/13 07시 ~ 1/14 07시 합계, 시간대별)
"""

import matplotlib.pyplot as plt
import pandas as pd

from analyze import BANDS, EVAL, HERE, RUNS, load

RUNS = {**RUNS, "a50_10to11": HERE / "runs" / "jan13_a50_10to11" / "eplusout.sql"}
LABEL = {"suntracking": "태양추적", "surplus90": "잉여구간 90°", "a50_10to11": "10~11시 50° + 90°"}


def main():
    d = {k: load(p) for k, p in RUNS.items()}
    st, new = d["suntracking"], d["a50_10to11"]

    pre = (new.loc[:"2006-01-12"] - st.loc[new.index[0]:"2006-01-12"])[["pv", "purchase"]].abs().sum()
    print(f"[검증] 1/6~1/12 연간 태양추적과의 차이 합: PV {pre.pv:.3f}, 구매 {pre.purchase:.3f} kWh")

    ev = slice(EVAL[0], pd.Timestamp(EVAL[1]) - pd.Timedelta(minutes=10))
    cols = ["pv", "hvac", "lights", "load", "purchase", "surplus"]
    tab = pd.DataFrame({LABEL[k]: df.loc[ev, cols].sum() for k, df in d.items()}).T
    print(f"\n[평가] {EVAL[0]} ~ {EVAL[1]} 합계 (kWh)\n{tab.round(2).to_string()}")

    print("\n[시간대별 구매 / 잉여] 태양추적 | 잉여90° | 10~11시 50°")
    for h0, h1, label in BANDS:
        parts = []
        for df in d.values():
            x = df.loc[ev]
            hr = (x.index - pd.Timestamp("2006-01-13")).total_seconds() / 3600
            x = x[(hr >= h0) & (hr < h1)]
            parts.append(f"{x.purchase.sum():6.2f} / {x.surplus.sum():5.2f}")
        print(f"  {label:14s} " + " | ".join(parts))

    plt.rcParams["font.family"] = "Malgun Gothic"
    fig, ax = plt.subplots(figsize=(13, 5))
    x = st.loc["2006-01-13 00:00":"2006-01-14 12:00"]
    y = new.loc["2006-01-13 00:00":"2006-01-14 12:00"]
    ax.step(x.index, x.pv, where="post", color="#f59e0b", lw=1.2, ls="--", label="PV 태양추적")
    ax.step(y.index, y.pv, where="post", color="#f59e0b", lw=1.8, label="PV 10~11시 50° + 90°")
    ax.step(x.index, x.load, where="post", color="#1e293b", lw=1.2, ls="--", label="수요(HVAC+조명) 태양추적")
    ax.step(y.index, y.load, where="post", color="#1e293b", lw=1.8, label="수요(HVAC+조명) 10~11시 50° + 90°")
    ax.axvspan(pd.Timestamp("2006-01-13 10:00"), pd.Timestamp("2006-01-13 11:00"), color="#6366f1", alpha=0.12, label="50° 구간")
    ax.axvspan(pd.Timestamp("2006-01-13 11:00"), pd.Timestamp("2006-01-13 14:10"), color="#10b981", alpha=0.12, label="90° 구간")
    ax.set_ylabel("kWh / 10분")
    ax.legend(ncol=3, fontsize=9, loc="upper right")
    ax.set_title("case3 1/13 (IWEC): 10~11시 50° + 11:00~14:10 90° vs 태양추적")
    fig.tight_layout()
    out = HERE / "jan13_a50_10to11.png"
    fig.savefig(out, dpi=150)
    print(f"\n[*] {out}")


if __name__ == "__main__":
    main()

"""
bipv_mismatch/explain_surplus_heating/plot_jan13_bar.py
=======================================================
대표일 (IWEC, 07시 ~ 다음 날 07시, 기본 1/9; 처음엔 1/13) 잉여 발전·부족(구매) 합계 막대 비교 (2026-11-03).

- 고정 0°   : dataset_final/case2_mm_train.csv 의 pv_gen_0, demand_elec_0 (case2, jan13_fixed_angle0 그림과 같은 자료)
- 태양추적  : pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400 (case3 E+)
- TiDE 최종 : tide_policy/eplus_week_oracle/runs/week_tide_oracle (case3 E+, 오라클학습 + 1시간 고정 버퍼)
- 수요 = 냉방/3.0 + 난방/2.5 + 조명, 잉여 = Σ max(PV − 수요, 0), 부족 = Σ max(수요 − PV, 0) (10분)
- --window: 하루 합계 대신 TiDE 조절 구간(태양추적을 하지 않는 스텝, eplus_week_oracle/angles_week.csv 의 mask)만 합산
- --load: 오른쪽 막대를 부족 대신 전체 부하(수요)로
- --to-sunset: 시작은 --window 와 같고 끝을 일몰까지 (case2 sun_altitude 가 처음 0 이하가 되는 구간 종료 시각)

출력: explain_surplus_heating/figures/day{MMDD}[_window|_sunset]_surplus_{deficit|load}_bar.{png,svg}
실행: python bipv_mismatch/explain_surplus_heating/plot_jan13_bar.py [--window | --to-sunset] [--load]
"""

import argparse
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import dartwork_mpl as dm

HERE = Path(__file__).resolve().parent
BM = HERE.parent
sys.path.insert(0, str(BM / "eplus_jan13"))
from plot_day import flatten_svg  # noqa: E402

sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

CASE2 = BM / "dataset_final" / "case2_mm_train.csv"
TIDE = BM / "tide_policy" / "eplus_week_oracle" / "runs" / "week_tide_oracle" / "eplusout.sql"
ANGLES = BM / "tide_policy" / "eplus_week_oracle" / "angles_week.csv"
STEP = pd.Timedelta(minutes=10)
D0 = pd.Timestamp("2006-01-09 07:00")
D1 = D0 + pd.Timedelta(hours=24) - STEP
POLICIES = [("고정 0°", "#94a3b8"), ("태양추적", "#64748b"), ("TiDE 최종", "#2563eb")]


def control_steps():
    """D0 ~ D1 중 TiDE 가 태양추적 대신 각도를 정한 스텝 (구간 시작 시각)"""
    a = pd.read_csv(ANGLES, parse_dates=["start"]).set_index("start").loc[D0:D1]
    assert ((a.tide != a.theta_st) == (a["mask"] == 1)).all()
    return a.index[a["mask"] == 1]


def sunset_steps():
    """조절 구간 시작 ~ 일몰. case2 timestamp(구간 종료 라벨)에서 태양 고도가 처음 0 이하인 구간까지 포함"""
    start = control_steps().min()
    c2 = pd.read_csv(CASE2, usecols=["timestamp", "sun_altitude"], parse_dates=["timestamp"]).set_index("timestamp")
    alt = c2.sun_altitude.loc[start + STEP:D1 + STEP]
    end = alt.index[alt <= 0][0]  # 일몰을 품은 구간의 종료 시각
    return pd.date_range(start, end - STEP, freq=STEP)


def totals(steps):
    c2 = pd.read_csv(CASE2, usecols=["timestamp", "pv_gen_0", "demand_elec_0"], parse_dates=["timestamp"])
    c2.index = c2.timestamp - STEP
    x = c2.loc[steps]
    e = x.pv_gen_0 - x.demand_elec_0
    out = {"고정 0°": dict(surplus=e.clip(lower=0).sum(), deficit=(-e).clip(lower=0).sum(),
                         load=x.demand_elec_0.sum())}
    for k, p in [("태양추적", RUNS["태양추적"]), ("TiDE 최종", TIDE)]:
        y = load(p).loc[steps]
        out[k] = dict(surplus=y.surplus.sum(), deficit=y.purchase.sum(), load=y.load.sum())
    return pd.DataFrame(out).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", action="store_true", help="TiDE 조절 구간 스텝만 합산")
    ap.add_argument("--to-sunset", action="store_true", help="조절 구간 시작 ~ 일몰 스텝만 합산")
    ap.add_argument("--load", action="store_true", help="부족 대신 전체 부하")
    args = ap.parse_args()
    if args.to_sunset:
        steps = sunset_steps()
        span = f"조절 시작 ~ 일몰 {steps.min():%H:%M} ~ {steps.max() + STEP:%H:%M}"
        unit, out = "kWh / 구간", HERE / "figures" / f"day{D0:%m%d}_sunset_surplus_deficit_bar.png"
    elif args.window:
        steps = control_steps()
        span = f"태양추적을 하지 않는 구간 {steps.min():%H:%M} ~ {steps.max() + STEP:%H:%M}"
        unit, out = "kWh / 구간", HERE / "figures" / f"day{D0:%m%d}_window_surplus_deficit_bar.png"
    else:
        steps = pd.date_range(D0, D1, freq=STEP)
        span, unit = "07시 ~ 다음 날 07시", "kWh / 일"
        out = HERE / "figures" / f"day{D0:%m%d}_surplus_deficit_bar.png"
    if args.load:
        out = out.with_name(out.name.replace("_deficit_", "_load_"))
    right = ("load", "전체 부하 (냉방/3 + 난방/2.5 + 조명)") if args.load else ("deficit", "부족 (구매 전력)")
    t = totals(steps)
    print(f"[{D0.month}/{D0.day} {span}, {len(steps)}스텝] (kWh)\n", t.round(2).to_string())
    dm.style.use("presentation-kr")
    plt.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "path"
    fig, axes = plt.subplots(1, 2, figsize=(16 / 2.54, 9 / 2.54))
    for ax, col, title in [(axes[0], "surplus", "잉여 발전"), (axes[1], *right)]:
        for i, (k, c) in enumerate(POLICIES):
            v = t.loc[k, col]
            ax.bar(i, v, color=c, width=0.62)
            ax.annotate(f"{v:.1f}", (i, v), xytext=(0, 3), textcoords="offset points", ha="center",
                        va="bottom", fontsize=10)
        ax.set_xticks(range(len(POLICIES)), [k for k, _ in POLICIES], fontsize=10)
        ax.set_ylim(0, t[col].max() * 1.15)
        ax.set_ylabel(unit, fontsize=10)
        ax.tick_params(axis="y", labelsize=9)
        ax.grid(axis="y", alpha=0.3)
        ax.set_title(title, fontsize=12, fontweight="bold", pad=6)
    fig.suptitle(f"{D0.month}/{D0.day} 대표일 잉여 발전과 {"부하" if args.load else "부족"} ({span})", fontsize=13, fontweight="bold", y=0.99)
    fig.subplots_adjust(left=0.1, right=0.98, bottom=0.12, top=0.8, wspace=0.35)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", transparent=True)
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight", transparent=True)
    flatten_svg(out.with_suffix(".svg"))
    plt.close(fig)
    print(f"[*] {out} (+ .svg)")


if __name__ == "__main__":
    main()

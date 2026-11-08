"""
eplus_open/analyze_week.py
==========================
case3 E+ 1주 비교: 태양추적(eplus_winter/runs/w_suntracking_wk) vs TiDE 잉여 구간 각도(runs/open_m0_wk, m=0).
테스트 기상 TMYx 2011-2025, 1/6~1/15 실행 중 평가 1/9 07시 ~ 1/14 07시 (평일 5일, 하루 = 07시 ~ 다음날 07시).
수요 = 냉방/3.0 + 난방/2.5 + 조명, 구매 = Σ max(수요 − PV, 0) (10분).
case2 데이터(학습 데이터 기준)가 같은 각도에서 예상한 값도 함께 비교 → case2 낙관 정도 확인.

출력: eplus_open/{week_compare.csv, week_compare.png}
"""

import sqlite3
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shared.paths import EXPERIMENTS

HERE = Path(__file__).resolve().parent
MM = HERE.parent
RUNS = {"태양추적": MM / "eplus_winter" / "runs" / "w_suntracking_wk" / "eplusout.sql",
        "TiDE": HERE / "runs" / "open_m0_wk" / "eplusout.sql"}
SCHED = {"태양추적": EXPERIMENTS / "schedules" / "suntracking_w0s90.csv",
         "TiDE": MM / "schedules" / "open_test_m+0.00.csv"}
VARS = {"Generator Produced DC Electricity Energy": "pv",
        "Zone Ideal Loads Supply Air Total Cooling Energy": "cool",
        "Zone Ideal Loads Supply Air Total Heating Energy": "heat",
        "Zone Lights Electricity Energy": "lights"}
EVAL = (pd.Timestamp("2006-01-09 07:00"), pd.Timestamp("2006-01-14 07:00"))
ANGLES = np.arange(0, 100, 10)
C_PV, C_DEM, C_SUR, C_DEF = "#f59e0b", "#1e293b", "#10b981", "#dc2626"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def load_sql(sql):
    names = ",".join(f"'{n}'" for n in VARS)
    q = f"""SELECT t.Month, t.Day, t.Hour, t.Minute, d.Name, SUM(v.Value) AS val FROM ReportData v
            JOIN ReportDataDictionary d ON v.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON v.TimeIndex = t.TimeIndex
            WHERE d.ReportingFrequency = 'Zone Timestep' AND d.Name IN ({names})
              AND (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)
            GROUP BY t.TimeIndex, d.Name"""
    with sqlite3.connect(sql) as con:
        raw = pd.read_sql(q, con)
    raw["t"] = (pd.to_datetime(dict(year=2006, month=raw.Month, day=raw.Day)) + pd.to_timedelta(raw.Hour, "h")
                + pd.to_timedelta(raw.Minute, "m") - pd.Timedelta(minutes=10))
    df = raw.pivot_table(index="t", columns="Name", values="val").rename(columns=VARS) / 3.6e6
    df["load"] = df.cool / 3.0 + df.heat / 2.5 + df.lights
    return df.loc[EVAL[0]:EVAL[1] - pd.Timedelta(minutes=10)]


def case2_expect(name):
    """case2 테스트 데이터에서 같은 스케줄 각도의 PV·수요"""
    d = pd.read_csv(MM / "dataset_open" / "open_test.csv")
    th = pd.read_csv(SCHED[name])["optimal_angle"].to_numpy()
    r = np.arange(len(d))
    pick = lambda c: d[[f"{c}_{a}" for a in ANGLES]].to_numpy()[r, th // 10]
    out = pd.DataFrame({"pv": pick("pv_gen"), "heat": pick("heat_load"), "lights": pick("lights_kwh"), "angle": th},
                       index=pd.to_datetime(d["timestamp"]) - pd.Timedelta(minutes=10))
    out["load"] = out.heat / 2.5 + out.lights
    return out.loc[EVAL[0]:EVAL[1] - pd.Timedelta(minutes=10)]


def summary(df):
    return {"PV": df.pv.sum(), "수요": df.load.sum(), "난방열": df.heat.sum(), "조명": df.lights.sum(),
            "구매": (df.load - df.pv).clip(lower=0).sum(), "잉여": (df.pv - df.load).clip(lower=0).sum()}


def main():
    ep = {k: load_sql(v) for k, v in RUNS.items()}
    c2 = {k: case2_expect(k) for k in RUNS}
    for k in ep:
        ep[k]["angle"] = c2[k]["angle"].reindex(ep[k].index).to_numpy()

    tab = pd.DataFrame({f"E+ {k}": summary(v) for k, v in ep.items()} | {f"case2 {k}": summary(v) for k, v in c2.items()}).T
    tab.loc["E+ 차이"] = tab.loc["E+ TiDE"] - tab.loc["E+ 태양추적"]
    tab.loc["case2 차이(예상)"] = tab.loc["case2 TiDE"] - tab.loc["case2 태양추적"]
    print(f"[1주 합계] {EVAL[0]} ~ {EVAL[1]} (kWh, 난방열은 열량)")
    print(tab.round(1).to_string())

    print("\n[시간대별 구매 / 잉여, E+] 태양추적 → TiDE (5일 합, kWh)")
    bands = [(7, 10, "07-10"), (10, 13, "10-13"), (13, 16, "13-16"), (16, 19, "16-19"), (19, 31, "19-익일07")]
    for h0, h1, lab in bands:
        def b(df):
            hr = ((df.index - df.index.normalize()).total_seconds() / 3600).to_numpy()
            hr = np.where(hr < 7, hr + 24, hr)
            x = df[(hr >= h0) & (hr < h1)]
            return (x.load - x.pv).clip(lower=0).sum(), (x.pv - x.load).clip(lower=0).sum()
        (p0, s0), (p1, s1) = b(ep["태양추적"]), b(ep["TiDE"])
        print(f"  {lab:9s} 구매 {p0:7.1f} → {p1:7.1f} ({p1 - p0:+6.1f}) | 잉여 {s0:6.1f} → {s1:6.1f} ({s1 - s0:+6.1f})")

    print("\n[일별 구매, E+] (07시~익일 07시)")
    for k, v in ep.items():
        day = (v.index - pd.Timedelta(hours=7)).date
        print(f"  {k:5s}", " ".join(f"{x:6.1f}" for x in (v.load - v.pv).clip(lower=0).groupby(day).sum()))

    out = pd.concat({k: v for k, v in ep.items()}, axis=1)
    out.to_csv(HERE / "week_compare.csv")

    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True, gridspec_kw={"height_ratios": [1, 1, 0.5]})
    for ax, (k, v) in zip(axes[:2], ep.items()):
        idx = v.index.append(pd.DatetimeIndex([v.index[-1] + pd.Timedelta(minutes=10)]))
        pv, ld = np.r_[v.pv.to_numpy(), v.pv.iloc[-1]], np.r_[v.load.to_numpy(), v.load.iloc[-1]]
        ax.fill_between(idx, pv, ld, where=pv > ld, step="post", color=C_SUR, alpha=0.45, lw=0)
        ax.fill_between(idx, pv, ld, where=pv <= ld, step="post", color=C_DEF, alpha=0.3, lw=0)
        ax.step(idx, ld, where="post", color=C_DEM, lw=1.2)
        ax.step(idx, pv, where="post", color=C_PV, lw=1.5)
        s = summary(v)
        ax.set_title(f"case3 E+ {k} — 구매 {s['구매']:.0f} kWh, 잉여 {s['잉여']:.0f} kWh, 수요 {s['수요']:.0f} kWh",
                     loc="left", fontweight="bold")
        ax.set_ylabel("kWh / 10분")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend([plt.Line2D([], [], color=C_PV), plt.Line2D([], [], color=C_DEM),
                    plt.Rectangle((0, 0), 1, 1, color=C_SUR, alpha=0.45), plt.Rectangle((0, 0), 1, 1, color=C_DEF, alpha=0.3)],
                   ["PV", "수요 (냉방/3 + 난방/2.5 + 조명)", "잉여", "부족(구매)"], ncol=4, fontsize=9, loc="upper right")
    ax = axes[2]
    for k, ls, c in [("태양추적", "--", "#64748b"), ("TiDE", "-", "#2563eb")]:
        ax.step(ep[k].index, ep[k]["angle"], where="post", ls=ls, color=c, label=k)
    ax.set_ylabel("각도 [°]")
    ax.legend(fontsize=9, loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H시"))
    fig.suptitle("case3 E+ 1주 비교 (TMYx 2011-2025, 1/9~1/13 평일): 태양추적 vs TiDE 잉여 구간 각도 (m=0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(HERE / "week_compare.png", dpi=140)
    print(f"\n[*] {HERE / 'week_compare.png'}")


if __name__ == "__main__":
    main()

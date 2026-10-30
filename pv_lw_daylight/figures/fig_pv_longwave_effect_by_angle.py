"""
pv_lw_daylight/figures/fig_pv_longwave_effect_by_angle.py
=========================================================
PV 장파복사 연동이 연간 냉난방 열부하를 바꾸는 정도를 BIPV 고정각(case2, 0~90°)별로 보인다.

연간 열부하 변화율 [%] = (PV 복사 연동 − 기준안) / 기준안 — 난방(감소), 냉방(증가)

입력: pv_lw_daylight/runs/annual/c2_RF_{base,lw}_A<각도>/summary.json
출력: pv_lw_daylight/figures/fig_pv_longwave_effect_by_angle.{png,svg}
(결과가 없는 각도는 건너뜀 — 예: 90° 실행 실패 시 80°까지만 표시)
"""

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import dartwork_mpl as dm

mpl.rcParams["svg.fonttype"] = "none"
dm.style.use("presentation")
for w in range(100, 1000, 50):  # SVG 내보내기 시 숫자 font weight KeyError 회피
    fm.weight_dict[w] = w
    fm.weight_dict[str(w)] = w

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = ROOT / "runs" / "annual"
OUT = HERE / "fig_pv_longwave_effect_by_angle"

C_HEAT = "#eb6834"   # 주황 — 난방
C_COOL = "#2a78d6"   # 파랑 — 냉방
INK, MUTED, GRID = "#1f1f1d", "#6b6a63", "#e4e3dd"


def load() -> pd.DataFrame:
    rows = []
    for a in range(0, 100, 10):
        pb, pl = RUNS / f"c2_RF_base_A{a:02d}" / "summary.json", RUNS / f"c2_RF_lw_A{a:02d}" / "summary.json"
        if not (pb.exists() and pl.exists()):
            print(f"{a}°: 결과 없음 → 제외")
            continue
        b, l = json.loads(pb.read_text(encoding="utf-8")), json.loads(pl.read_text(encoding="utf-8"))
        rows.append({
            "angle": a,
            "heat_base": b["heating_thermal_kwh"], "cool_base": b["cooling_thermal_kwh"],
            "dheat": l["heating_thermal_kwh"] - b["heating_thermal_kwh"],
            "dcool": l["cooling_thermal_kwh"] - b["cooling_thermal_kwh"],
            "dhvac": l["hvac_electric_kwh"] - b["hvac_electric_kwh"],
        })
    df = pd.DataFrame(rows)
    df["dheat_pct"] = 100 * df.dheat / df.heat_base
    df["dcool_pct"] = 100 * df.dcool / df.cool_base
    return df


def main():
    df = load()
    df.to_csv(OUT.with_suffix(".csv"), index=False)
    print(df.round(3).to_string(index=False))

    fig, ax = plt.subplots(figsize=(9.5, 5.4))

    ax.axhline(0, color=MUTED, lw=1.0, zorder=1)
    for col, color, label in (("dcool_pct", C_COOL, "Cooling load"), ("dheat_pct", C_HEAT, "Heating load")):
        ax.plot(df.angle, df[col], color=color, lw=2, marker="o", ms=8, mec="white", mew=2, zorder=3, label=label)
        # 직접 라벨: 0°와 변화가 가장 작은 각도
        for i in (0, int(df[col].abs().values.argmin())):
            v = df[col].iloc[i]
            ax.annotate(f"{v:+.1f}%", (df.angle.iloc[i], v), textcoords="offset points",
                        xytext=(0, 11 if v > 0 else -17), ha="center", fontsize=10.5, color=INK)
    lim = max(df.dcool_pct.abs().max(), df.dheat_pct.abs().max()) * 1.35
    ax.set_ylim(-lim, lim)
    ax.set_ylabel("Annual thermal load change [%]\n(PV longwave on − off)", fontsize=12, color=INK)
    ax.legend(loc="upper right", frameon=False, fontsize=10.5)
    ax.set_title("Effect of PV longwave radiation on annual thermal load", loc="left", fontsize=12.5, color=INK, pad=10)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_xlabel("BIPV louver angle [°]  (0° = closed, vertical · 90° = open, horizontal)", fontsize=12, color=INK)
    ax.set_xticks(df.angle)
    ax.set_xlim(df.angle.min() - 5, df.angle.max() + 5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelcolor=INK)

    fig.savefig(OUT.with_suffix(".png"), dpi=300, transparent=True, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".svg"), transparent=True, bbox_inches="tight")
    print(f"저장: {OUT}.png/.svg")


if __name__ == "__main__":
    main()

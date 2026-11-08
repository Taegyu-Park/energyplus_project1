"""
bipv_mismatch/explain_surplus_heating/plot_panel_dm.py
======================================================
공모전 패널(Figma 26건물에너지시뮬레이션, Document 1660:938)에 넣는 그림 전부를 dartwork-mpl 논문 스타일로 (2026-11-03).

- 스타일: dm.style.use("scientific-kr") (dartwork-mpl 의 논문용 프리셋) 위에 글자 6pt 로 맞춤
  · 글꼴은 프리셋 그대로 Paperlogy (dartwork_mpl/asset/font 에 들어 있음, 기본 굵기 300)
    (2026-11-04 전까지는 Noto Sans KR 로 덮어썼음. Paperlogy 가 없다고 잘못 판단했던 것)
- Figma 에 안전한 svg: 글자는 도형으로 (svg.fonttype=path + eplus_jan13/plot_day.flatten_svg 로 <use> 펼침),
  clipPath 는 지움 (Figma 가 잘라내기 영역을 잘못 적용해 면·격자가 어긋남), 해치(pattern) 안 씀
  · 여백은 dm.simple_layout 으로 맞춤
- 색: A-PPTL 디자인 토큰 값 (PV = target, TiDE = eval, 태양고도 추적 = frozen, 손실 = loss, 글자 = ink)
- 해치(hatch)는 쓰지 않음: svg <pattern> 은 Figma 가져오기에서 빠짐 (A-PPTL "Figma-safe SVG" 규칙)
- 폭은 패널 칸 본문 폭 386 pt 에 맞춤

그림 (figures/dm_*.svg)
1) dm_panel03_iwec_temperature : 광주 IWEC 연간 외기온 (일평균 + 일 최저~최고), 학습·평가 기간(11~3월)·대표일 1/9
2) dm_panel05_day0117_st       : 1/17 태양고도 추적 PV 발전·전력 수요, 잉여·부족 음영 (반폭 193 pt, 격자 없음, PV 0 구간 선 생략)
   · 대표일 1/17: 12~2월 평일 63일 중 PV·수요 일합계가 평균에 2번째로 가깝고 시간별 모양은 1번째 (2026-11-04)
2b) dm_panel05_day0117_split  : 1/17 태양고도 추적, 전력 수요를 조명·난방 전력으로 쌓은 면적 + PV 발전 (잉여·부족 음영 없음)
2c) dm_panel05_seasons        : 계절별 대표일 4개(봄 4/20, 여름 7/18, 가을 10/5, 겨울 1/17) 태양고도 추적, 수요를 냉방·난방·조명 전력으로 쌓고 PV 겹침
   · 대표일 (2026-11-04, "일반적으로 생각할 수 있는 부하"): 평일, PV·수요 일합계가 기준 기간 평균 ±20~25% 안,
     09~17시 10분 사이 수요 변화 ≤ 0.3 kWh (여름 0.5, 갑자기 튀는 값 없음), 아침 예열 최대가 기준 기간 중앙값 이하,
     그중 시간별 모양이 평균에 가장 가까운 날. 기준 기간: 봄 4월, 여름 6~8월, 가을 10월, 겨울 12~2월
     (3~5월·9~11월 전체는 난방일과 냉방일이 섞여 평균에 가까운 날이 없음)
   · 봄은 06시 예열 급증(야간 설정온도 완화 뒤 난방 재가동)이 없는 4월 평일로 다시 고름: 05~08시 최대 ≤ 1.0 kWh, 맑은 날 → 4/20
     (4월 평균 대비 PV +24%, 수요 −22%; 4/25~27 은 흐린 날이라 제외)
   · 여름은 7월 평일 중 고름. 7월은 장마로 흐린 날(PV ≈ 34)과 맑고 더운 날(아침 예냉 6~7.5 kWh, 수요 350~430)로 갈려
     평균에 맞는 날이 없음 → 맑은 날 중 수요가 7월 평균 수준(+7%), 아침 예냉 작음(1.75), 낮 튐 작음(0.24)인 7/18.
     12~13시 오목한 부분은 점심시간 재실·조명 스케줄이라 7월 맑은 날에 모두 나타나는 정상 모양
3) dm_panel07a_day0109_profile : 1/9 태양고도 추적 vs TiDE 최종, 루버 각도 + PV 발전·전력 수요
   · 7번 ②~④ 와 같은 주간 실행(eplus_week_oracle) 자료. panel07a(DAY05, winter=True) 로 부르면 겨울 전체 실행의 1/17 판
4) dm_panel07b_day0109_cum     : 1/9 난방 전력·조명 전력·PV 발전 누적 (0시부터)
5) dm_panel07c_day0109_ledger  : 1/9 하루 변화 폭포 그래프 (TiDE − 태양고도 추적)
6) dm_panel07d_weekdays        : 평일 1/9~1/13 날짜별 잉여·부족, 태양고도 추적 vs TiDE

자료: IWEC EPW(data/KOR_Kwangju.471560_IWEC (1).epw), case3 E+ (태양추적 pv_lw_daylight/runs/annual/c3_FE_ST_lw_dl400,
      TiDE tide_policy/eplus_week_oracle/runs/week_tide_oracle, 날짜별 합 eplus_week_oracle/results_daily.csv)
실행: python bipv_mismatch/explain_surplus_heating/plot_panel_dm.py
"""

import re
import sys
from pathlib import Path

import dartwork_mpl as dm
import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
BM = HERE.parent
ROOT = BM.parent
sys.path.insert(0, str(BM / "tide_policy" / "eplus_week"))
from analyze import RUNS, load  # noqa: E402

sys.path.insert(0, str(BM / "eplus_jan13"))
from plot_day import flatten_svg  # noqa: E402

EPW = ROOT / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
TIDE = BM / "tide_policy" / "eplus_week_oracle" / "runs" / "week_tide_oracle" / "eplusout.sql"
ANGLES = BM / "tide_policy" / "eplus_week_oracle" / "angles_week.csv"
DAILY = BM / "tide_policy" / "eplus_week_oracle" / "results_daily.csv"
WINTER = BM / "tide_policy" / "eplus_winter_oracle"  # TiDE 각도로 돌린 겨울 전체(11~3월) case3 E+, 월별 조각
OUT = HERE / "figures"
DAY = pd.Timestamp("2006-01-09")
DAY05 = pd.Timestamp("2006-01-17")  # 05번 대표일 (겨울 평균에 가장 가까운 평일)
ST_SQL = RUNS["태양추적"]
STEP = pd.Timedelta(minutes=10)
W = 386  # pt
FS = 6

# A-PPTL 토큰 값
INK1, INK2, INK3 = "#0f172a", "#334155", "#64748b"
GRID, RULE = "#e2e8f0", "#cbd5e1"
TARGET, TARGET_MID, TARGET_TINT, TARGET_DEEP = "#ea580c", "#fb923c", "#ffedd5", "#9a3412"
FROZEN, FROZEN_TINT = "#475569", "#e2e8f0"
EVAL, LOSS = "#0f766e", "#be123c"
DASH = (0, (3, 1.6))


def style():
    dm.style.use("scientific-kr")
    for w in range(100, 1000, 50):  # svg 텍스트 저장 시 숫자 굵기(400 등) KeyError 방지 (eplus_jan13/plot_day.py 와 같은 처리)
        mpl.font_manager.weight_dict[w] = w
        mpl.font_manager.weight_dict[str(w)] = w
    mpl.rcParams.update({
        "svg.fonttype": "path", "axes.unicode_minus": False,
        "font.size": FS, "axes.labelsize": FS, "axes.titlesize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
        "legend.fontsize": FS, "text.color": INK2, "axes.labelcolor": INK2, "xtick.color": INK3, "ytick.color": INK3,
        "axes.edgecolor": RULE, "savefig.transparent": True,
    })


def fig_ax(h, *args, **kw):
    return plt.subplots(*args, figsize=(W / 72, h / 72), **kw)


def save(fig, name, **margins):
    """dm.simple_layout 으로 여백 맞춤. 왼쪽 정렬 제목·여러 줄 눈금 글자는 잡지 못해 칸별로 mt/ml 을 따로 줌"""
    dm.simple_layout(fig, margin="1.5pt", **margins)
    out = OUT / f"{name}.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    strip_clip(out)
    flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out} (+ .png)")


def strip_clip(path):
    """clipPath 정의와 clip-path 참조를 지움 (모든 요소가 축 범위 안에 있으므로 잘라낼 것이 없음)"""
    s = path.read_text(encoding="utf-8")
    s = re.sub(r'\s*clip-path="url\(#[^)]+\)"', "", s)
    s = re.sub(r"<clipPath.*?</clipPath>", "", s, flags=re.S)
    path.write_text(s, encoding="utf-8")


def ygrid(ax):
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def hour_axis(ax, step=3, d=DAY, grid=True):
    ax.set_xlim(d, d + pd.Timedelta(hours=24))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=step))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - d).total_seconds() / 3600):d}"))
    if grid:
        ygrid(ax)


def pv_curve(pv):
    """PV 곡선용 (시각, 값). 10분 합계를 구간 가운데(시작 + 5분)에 찍고 점 사이는 직선(선형 보간, 수요 곡선과 같음).
    발전이 있는 구간 바로 앞·뒤의 0 한 점씩은 남겨 선이 x축에서 출발해 x축으로 내려오게 하고,
    그 밖의 0(밤)은 NaN 으로 비워 x축 위에 선을 긋지 않음"""
    on = pv > 1e-6
    keep = on | on.shift(1, fill_value=False) | on.shift(-1, fill_value=False)
    return pv.index + STEP / 2, pv.where(keep).to_numpy()


def legend(ax, **kw):
    return ax.legend(frameon=False, handlelength=1.4, columnspacing=0.9, borderaxespad=0.1, **kw)


def day(df):
    return df.loc[DAY:DAY + pd.Timedelta(hours=24) - STEP]


def iwec_temperature():
    epw = pd.read_csv(EPW, skiprows=8, header=None)
    tdb = pd.Series(epw[6].to_numpy(), index=pd.date_range("2006-01-01", periods=len(epw), freq="h"))
    d = tdb.resample("D").agg(["mean", "min", "max"])
    print(f"[IWEC] 연평균 {tdb.mean():.1f} °C, 최저 {tdb.min():.1f}, 최고 {tdb.max():.1f}")
    fig, ax = fig_ax(74)
    for a, b in [("2006-01-01", "2006-04-01"), ("2006-11-01", "2007-01-01")]:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="#f1f5f9", lw=0, zorder=0)  # surface/wash-strong
    ax.fill_between(d.index, d["min"], d["max"], color=TARGET_TINT, lw=0, label="일 최저~최고")
    ax.plot(d.index, d["mean"], color=TARGET, lw=0.9, label="일평균")
    ax.axvline(DAY, color=EVAL, lw=0.7, ls=(0, (2, 1.2)))
    ax.annotate("대표일 1/9", (DAY, d["max"].max()), xytext=(3, -1), textcoords="offset points", va="top", color=EVAL)
    ax.text(pd.Timestamp("2006-02-15"), -11.5, "학습·평가 기간(11~3월)", ha="center", va="bottom", color=INK3)
    ax.text(pd.Timestamp("2006-12-01"), -11.5, "(11~12월)", ha="center", va="bottom", color=INK3)
    ax.axhline(0, color=RULE, lw=0.5)
    ax.set_xlim(pd.Timestamp("2006-01-01"), pd.Timestamp("2007-01-01"))
    ax.set_ylim(-13, 38)
    ax.set_xticks(pd.date_range("2006-01-01", "2006-12-01", freq="MS"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{mdates.num2date(v).month}월"))
    ax.set_ylabel("외기온 [°C]")
    ygrid(ax)
    legend(ax, loc="lower right", bbox_to_anchor=(1, 1), ncol=2)  # 범례는 그래프 위 바깥
    save(fig, "dm_panel03_iwec_temperature")


def load_day(sql, d):
    """analyze.load 와 같은 계산을 임의의 하루(0~24시)에 (analyze.load 는 1/2~1/16 만 읽음)"""
    import sqlite3
    from analyze import VARS
    names = ",".join(f"'{n}'" for n in VARS)
    q = f"""SELECT t.Month, t.Day, t.Hour, t.Minute, d.Name, SUM(v.Value) AS val
            FROM ReportData v
            JOIN ReportDataDictionary d ON v.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON v.TimeIndex = t.TimeIndex
            WHERE d.ReportingFrequency = 'Zone Timestep' AND d.Name IN ({names})
              AND t.Month = {d.month} AND t.Day IN ({d.day}, {(d + pd.Timedelta(days=1)).day})
              AND (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)
            GROUP BY t.TimeIndex, d.Name"""
    with sqlite3.connect(sql) as con:
        raw = pd.read_sql(q, con)
    raw["t"] = (pd.to_datetime(dict(year=2006, month=raw.Month, day=raw.Day))
                + pd.to_timedelta(raw.Hour, "h") + pd.to_timedelta(raw.Minute, "m") - pd.Timedelta(minutes=10))
    df = raw.pivot_table(index="t", columns="Name", values="val").rename(columns=VARS) / 3.6e6
    df["load"] = df.cool / 3.0 + df.heat / 2.5 + df.lights
    df["purchase"] = (df.load - df.pv).clip(lower=0)
    df["surplus"] = (df.pv - df.load).clip(lower=0)
    return df.loc[d:d + pd.Timedelta(hours=24) - STEP]


def panel05():
    D = DAY05
    x = load_day(ST_SQL, D)
    t = x.index + STEP / 2
    s = x.index[x.pv > x.load]
    am = x.load[:D + pd.Timedelta(hours=10)].idxmax()
    pm = x.load[D + pd.Timedelta(hours=15):D + pd.Timedelta(hours=20)].idxmax()
    print(f"[05] {D:%m/%d} PV {x.pv.sum():.1f}, 수요 {x.load.sum():.1f} (난방 {x.heat.sum() / 2.5:.1f}, 조명 {x.lights.sum():.1f}),"
          f" 잉여 {x.surplus.sum():.1f}, 부족 {x.purchase.sum():.1f}, 잉여 구간 {s.min():%H:%M}~{s.max() + STEP:%H:%M},"
          f" 아침 최대 {am:%H:%M} {x.load[am]:.2f}, 오후 최대 {pm:%H:%M} {x.load[pm]:.2f}, PV 최대 {x.pv.max():.2f}")
    fig, ax = plt.subplots(figsize=(W / 2 / 72, 128 / 72))
    ax.fill_between(t, x.pv, x.load, where=x.pv > x.load, interpolate=True, color=TARGET_TINT, lw=0,
                    label=f"잉여 발전 {x.surplus.sum():.1f} kWh")
    ax.fill_between(t, x.pv, x.load, where=x.load > x.pv, interpolate=True, color=FROZEN_TINT, alpha=0.7, lw=0,
                    label=f"부족 (구매) {x.purchase.sum():.1f} kWh")
    ax.plot(t, x.load, color=INK1, lw=0.9, label="전력 수요")
    ax.plot(*pv_curve(x.pv), color=TARGET, lw=1.0, label="PV 발전")
    ax.annotate("정오 전후 잉여", (s.min() + (s.max() - s.min()) / 2, x.pv.max()), xytext=(0, 2),
                textcoords="offset points", ha="center", color=TARGET_DEEP)
    ax.annotate("아침 예열", (am + pd.Timedelta(minutes=90), x.load[am]), xytext=(3, -1),  # 최대 구간(약 1시간) 오른쪽
                textcoords="offset points", ha="left", va="top", color=INK3)
    ax.annotate("오후 난방", (pm, x.load[pm]), xytext=(0, 2),
                textcoords="offset points", ha="center", color=INK3)
    top = np.ceil(max(x.load.max(), x.pv.max()))
    ax.set_ylim(0, top + 0.2)
    ax.set_yticks(range(0, int(top) + 1))
    ax.set_xlim(D, D + pd.Timedelta(hours=24))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - D).total_seconds() / 3600):d}"))
    ax.set_xlabel("시각 [h]")
    ax.set_ylabel("kWh")
    h, lab = ax.get_legend_handles_labels()
    order = [3, 2, 0, 1]
    legend(ax, handles=[h[i] for i in order], labels=[lab[i] for i in order], ncol=2,
           loc="lower left", bbox_to_anchor=(0, 1))  # 범례는 그래프 위 바깥 (반폭이라 안쪽은 곡선과 겹침)
    save(fig, f"dm_panel05_day{D:%m%d}_st")


def panel05_split():
    """05번 시안: 수요를 조명(아래, 재실 시간 바탕) + 난방 전력(위)으로 쌓고 PV 발전 선을 겹침. 냉방은 겨울이라 0"""
    D = DAY05
    x = load_day(ST_SQL, D)
    t = x.index + STEP / 2
    heat_e, light, cool_e = x.heat / 2.5, x.lights, x.cool / 3.0
    assert cool_e.sum() < 0.05, f"냉방 {cool_e.sum():.2f} kWh"
    fig, ax = plt.subplots(figsize=(W / 2 / 72, 128 / 72))
    ax.fill_between(t, 0, light, color="#fef3c7", lw=0, label=f"조명 전력 {light.sum():.1f} kWh")       # 조명 = 따뜻한 연노랑 (amber-100)
    ax.fill_between(t, light, light + heat_e, color="#fecdd3", lw=0, label=f"난방 전력 {heat_e.sum():.1f} kWh")  # loss tint
    ax.plot(t, x.load, color=INK1, lw=0.6, label=f"전력 수요 {x.load.sum():.1f} kWh")
    ax.plot(*pv_curve(x.pv), color=TARGET, lw=1.0, label=f"PV 발전 {x.pv.sum():.1f} kWh")
    top = np.ceil(max(x.load.max(), x.pv.max()))
    ax.set_ylim(0, top + 0.2)
    ax.set_yticks(range(0, int(top) + 1))
    hour_axis(ax, step=6, d=D, grid=False)
    ax.set_xlabel("시각 [h]")
    ax.set_ylabel("kWh")
    h, lab = ax.get_legend_handles_labels()
    order = [3, 1, 2, 0]
    legend(ax, handles=[h[i] for i in order], labels=[lab[i] for i in order], ncol=2,
           loc="lower left", bbox_to_anchor=(0, 1))
    save(fig, f"dm_panel05_day{D:%m%d}_split")


SEASONS = [("봄", "2006-04-20"), ("여름", "2006-07-18"), ("가을", "2006-10-05"), ("겨울", "2006-01-17")]
COOL_C, HEAT_C, LIGHT_C = "#bae6fd", "#fecdd3", "#fef3c7"  # 냉방 하늘색, 난방 연분홍, 조명 따뜻한 연노랑


def panel05_seasons():
    """계절별 대표일 4개를 한 줄로 (y축 공유). 칸 제목 아래에 그날 잉여·부족 합계"""
    days = [(n, pd.Timestamp(d)) for n, d in SEASONS]
    xs = {n: load_day(ST_SQL, d) for n, d in days}
    top = np.ceil(max(max(x.load.max(), x.pv.max()) for x in xs.values()))
    fig, axes = fig_ax(112, 1, 4, sharey=True, gridspec_kw=dict(wspace=0.12))
    for ax, (n, D) in zip(axes, days):
        x = xs[n]
        t = x.index + STEP / 2
        light, heat_e, cool_e = x.lights, x.heat / 2.5, x.cool / 3.0
        ax.fill_between(t, 0, light, color=LIGHT_C, lw=0, label="조명")
        ax.fill_between(t, light, light + heat_e, color=HEAT_C, lw=0, label="난방")
        ax.fill_between(t, light + heat_e, light + heat_e + cool_e, color=COOL_C, lw=0, label="냉방")
        ax.plot(t, x.load, color=INK1, lw=0.5, label="총 전력 사용량")
        ax.plot(*pv_curve(x.pv), color=TARGET, lw=0.9, label="PV 발전")
        win = n == "겨울"
        ax.set_title(f"{n} {D.month}/{D.day}", loc="left", color=INK1, fontweight="bold" if win else "normal", pad=8)
        ax.text(0, 1.015, f"잉여 {x.surplus.sum():.0f} · 부족 {x.purchase.sum():.0f} kWh", transform=ax.transAxes,
                ha="left", va="bottom", color=TARGET_DEEP if win else INK3, fontsize=FS - 0.5)
        print(f"[05s4] {n} {D:%m/%d} PV {x.pv.sum():.1f} 수요 {x.load.sum():.1f} (냉 {cool_e.sum():.1f} 난 {heat_e.sum():.1f}"
              f" 조 {light.sum():.1f}) 잉여 {x.surplus.sum():.1f} 부족 {x.purchase.sum():.1f}")
        ax.set_xlim(D, D + pd.Timedelta(hours=24))
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[6, 12, 18]))  # 0·24 는 옆 칸 눈금과 겹쳐서 뺌
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda v, _, D=D: f"{round((mdates.num2date(v).replace(tzinfo=None) - D).total_seconds() / 3600):d}"))
        ax.set_xlabel("시각 [h]")
    axes[0].set_ylim(0, top + 0.2)
    axes[0].set_yticks(range(0, int(top) + 1, 2))
    axes[0].set_ylabel("kWh")
    h, lab = axes[0].get_legend_handles_labels()
    order = [4, 3, 2, 1, 0]
    fig.legend([h[i] for i in order], [lab[i] for i in order], ncol=5, frameon=False, loc="upper right",
               bbox_to_anchor=(1, 1), handlelength=1.4, columnspacing=0.9, borderaxespad=0.1)
    save(fig, "dm_panel05_seasons", mt="22pt")


def panel07a(D=DAY, winter=False):
    """05번처럼 격자 없음, y축 kWh, 발전 없는 밤 PV 선 생략.
    winter=False: 1/9~1/13 주간 실행(7번 ②~④ 와 같은 자료), True: 겨울 전체 실행(월별 조각)"""
    if winter:
        month = {1: "jan", 2: "feb", 3: "mar", 11: "nov", 12: "dec"}[D.month]
        tide_sql, ang_csv = WINTER / "runs" / f"winter_tide_{month}" / "eplusout.sql", WINTER / "angles_winter.csv"
    else:
        tide_sql, ang_csv = TIDE, ANGLES
    a, b = load_day(ST_SQL, D), load_day(tide_sql, D)
    t = a.index + STEP / 2
    ang = pd.read_csv(ang_csv, parse_dates=["start"]).set_index("start")
    ang = ang.reindex(pd.date_range(D, D + pd.Timedelta(hours=24) - STEP, freq=STEP)).fillna(0)
    win = ang.index[ang["mask"] == 1]
    print(f"[07a] {D:%m/%d} 조절 {win.min():%H:%M}~{win.max() + STEP:%H:%M} | 태양추적 PV {a.pv.sum():.1f} 수요 {a.load.sum():.1f}"
          f" 잉여 {a.surplus.sum():.1f} 부족 {a.purchase.sum():.1f} | TiDE PV {b.pv.sum():.1f} 수요 {b.load.sum():.1f}"
          f" 잉여 {b.surplus.sum():.1f} 부족 {b.purchase.sum():.1f}")
    fig, (ax0, ax1) = fig_ax(170, 2, 1, sharex=True, gridspec_kw=dict(height_ratios=[1, 2.6], hspace=0.12))
    for ax in (ax0, ax1):
        ax.axvspan(win.min(), win.max() + STEP, color=EVAL, alpha=0.06, lw=0)
    ax0.step(ang.index, ang.theta_st, where="post", color=FROZEN, lw=0.9, ls=DASH, label="태양고도 추적")
    ax0.step(ang.index, ang.tide, where="post", color=EVAL, lw=1.0, label="TiDE")
    ax0.set_ylim(-5, 100)
    ax0.set_yticks([0, 45, 90])
    ax0.set_ylabel("각도 [°]")
    ax0.text(win.min() + (win.max() - win.min()) / 2, 52, f"조절 구간 {win.min():%H:%M}~{win.max() + STEP:%H:%M}",
             ha="center", va="center", color=EVAL)
    legend(ax0, loc="upper left")
    ax1.fill_between(t, a.pv, a.load, where=a.pv > a.load, interpolate=True, color=TARGET_TINT, lw=0,
                     label=f"태양추적 잉여 {a.surplus.sum():.1f} kWh")
    ax1.fill_between(t, b.pv, b.load, where=b.pv > b.load, interpolate=True, color=TARGET_MID, alpha=0.55, lw=0,
                     label=f"TiDE 잉여 {b.surplus.sum():.1f} kWh")
    ax1.plot(*pv_curve(a.pv), color=TARGET, lw=0.8, ls=DASH, label="PV · 태양추적")
    ax1.plot(*pv_curve(b.pv), color=TARGET, lw=1.0, label="PV · TiDE")
    ax1.plot(t, a.load, color=INK1, lw=0.8, ls=DASH, label="수요 · 태양추적")
    ax1.plot(t, b.load, color=INK1, lw=0.9, label="수요 · TiDE")
    ax1.set_ylim(0, 7.2)
    ax1.set_ylabel("kWh")
    ax1.set_xlabel("시각 [h]")
    legend(ax1, loc="upper right", ncol=3)
    for ax in (ax0, ax1):
        hour_axis(ax, d=D, grid=False)
    save(fig, f"dm_panel07a_day{D:%m%d}_profile")


def panel07b(st, td):
    a, b = day(st), day(td)
    t = a.index + STEP
    rows = [("난방 전력", "heat", 1 / 2.5), ("조명 전력", "lights", 1.0), ("PV 발전", "pv", 1.0)]
    fig, axes = fig_ax(112, 1, 3, sharex=True, gridspec_kw=dict(wspace=0.3))
    for ax, (title, col, k) in zip(axes, rows):
        ca, cb = (a[col] * k).cumsum(), (b[col] * k).cumsum()
        ax.plot(t, ca, color=FROZEN, lw=0.9, ls=DASH, label="태양고도 추적")
        ax.plot(t, cb, color=EVAL, lw=1.1, label="TiDE")
        ax.set_title(title, loc="left", color=INK1, pad=9)
        ax.text(0, 1.03, f"{ca.iloc[-1]:.1f} → {cb.iloc[-1]:.1f} kWh ({cb.iloc[-1] - ca.iloc[-1]:+.1f})",
                transform=ax.transAxes, color=EVAL, va="bottom")
        ax.set_ylim(0, max(ca.iloc[-1], cb.iloc[-1]) * 1.08)
        hour_axis(ax, step=6)
        ax.set_xlabel("시각 [h]")
    axes[0].set_ylabel("누적 kWh")
    legend(axes[1], loc="upper left")
    save(fig, f"dm_panel07b_day{DAY:%m%d}_cum", mt="17pt")


def panel07c(st, td):
    a, b = day(st), day(td)
    d_pv, d_sur = (b.pv - a.pv).sum(), (b.surplus - a.surplus).sum()
    d_heat, d_light = ((b.heat - a.heat) / 2.5).sum(), (b.lights - a.lights).sum()
    d_cool, d_pur = ((b.cool - a.cool) / 3.0).sum(), (b.purchase - a.purchase).sum()
    self_use = -(d_pv - d_sur)  # PV 감소 중 자가소비분 → 구매 증가 요인
    print(f"[07c] PV {d_pv:.2f}, 잉여 {d_sur:.2f}, 자가소비분 +{self_use:.2f}, 난방 {d_heat:.2f}, 조명 {d_light:.2f}, "
          f"냉방 {d_cool:.2f}, 구매 {d_pur:.2f} (검산 {self_use + d_heat + d_light + d_cool:.2f})")
    steps = [("PV 감소 중\n자가소비분", self_use, LOSS), ("난방 저감", d_heat, EVAL), ("조명 저감", d_light, EVAL)]
    fig, ax = fig_ax(100)
    x0 = 0.0
    for i, (_, v, c) in enumerate(steps):
        ax.barh(i, v, left=x0, color=c, height=0.56)
        ax.annotate(f"{v:+.1f}", (x0 + v, i), xytext=(3 if v > 0 else -3, 0), textcoords="offset points",
                    ha="left" if v > 0 else "right", va="center", color=c)
        if i < len(steps) - 1:
            ax.plot([x0 + v, x0 + v], [i + 0.28, i + 0.72], color=RULE, lw=0.5)
        x0 += v
    n = len(steps)
    ax.barh(n, d_pur, color=INK1, height=0.56)
    ax.annotate(f"{d_pur:+.1f}", (d_pur, n), xytext=(-3, 0), textcoords="offset points", ha="right", va="center",
                color=INK1)
    ax.barh(n + 1.2, d_sur, color=FROZEN_TINT, height=0.56, edgecolor=FROZEN, lw=0.5)
    ax.annotate(f"{d_sur:+.1f}  원래 남던 전력이라 구매와 무관", (0, n + 1.2), xytext=(3, 0), textcoords="offset points",
                ha="left", va="center", color=FROZEN)
    ax.set_yticks(list(range(n + 1)) + [n + 1.2], [s[0] for s in steps] + ["= 구매 전력 변화", "잉여 발전 변화"])
    ax.invert_yaxis()
    ax.axvline(0, color=RULE, lw=0.6)
    ax.set_xlim(-30, 20)
    ax.set_xlabel("TiDE − 태양고도 추적 [kWh / 일]")
    ax.grid(axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    save(fig, f"dm_panel07c_day{DAY:%m%d}_ledger", ml="46pt")


def panel07d():
    d = pd.read_csv(DAILY, parse_dates=["date"])
    d = d[d.date.dt.weekday < 5]
    pol = [("태양추적", "태양고도 추적", FROZEN), ("TiDE 오라클학습", "TiDE", EVAL)]
    days = sorted(d.date.unique())
    fig, axes = fig_ax(100, 1, 2, gridspec_kw=dict(wspace=0.22))
    for ax, (col, title) in zip(axes, [("surplus", "잉여 발전"), ("purchase", "부족 (구매)")]):
        for j, (k, lab, c) in enumerate(pol):
            v = d[d.policy == k].set_index("date").loc[days, col]
            ax.bar(np.arange(len(days)) + (j - 0.5) * 0.38, v, width=0.36, color=c if j else FROZEN_TINT,
                   edgecolor=c, lw=0.5, label=f"{lab} (합 {v.sum():.1f})")
        ax.set_xticks(range(len(days)), [f"{pd.Timestamp(x).month}/{pd.Timestamp(x).day}" for x in days])
        ax.set_title(title, loc="left", color=INK1, pad=3)
        ax.set_ylabel("kWh / 일")
        ygrid(ax)
        legend(ax, loc="upper right" if col == "surplus" else "upper left")
    axes[1].set_ylim(0, 420)
    save(fig, "dm_panel07d_weekdays", mt="9pt")


def main():
    """python plot_panel_dm.py [03 05 07a 07b 07c 07d] : 번호를 주면 그 그림만 다시 그림"""
    only = set(sys.argv[1:])
    style()
    OUT.mkdir(parents=True, exist_ok=True)
    if not only or "03" in only:
        iwec_temperature()
    st, td = load(RUNS["태양추적"]), load(TIDE)
    for key, fn in [("05", panel05), ("05s", panel05_split), ("05s4", panel05_seasons), ("07a", panel07a), ("07b", lambda: panel07b(st, td)),
                    ("07c", lambda: panel07c(st, td)), ("07d", panel07d)]:
        if not only or key in only:
            fn()


if __name__ == "__main__":
    main()

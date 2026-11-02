"""
eplus_jan13/plot_day.py
=======================
1/13 하루(0~24시) PV·수요 비교 그림 공통 함수 (dartwork-mpl presentation-kr 스타일, 18×11 cm, png+svg 글자 벡터).
analyze.py(jan13_surplus90) 와 plot_a50_10to11.py(jan13_a50_10to11) 가 같이 쓴다.
"""

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import copy
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import dartwork_mpl as dm
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from scipy.interpolate import PchipInterpolator

for _w in range(100, 1000, 50):  # svg 텍스트 저장 시 숫자 굵기(300 등) KeyError 방지 (fig41 과 같은 처리)
    fm.weight_dict[_w] = _w
    fm.weight_dict[str(_w)] = _w

C_PV, C_DEM = "#f59e0b", "#1e293b"
C_MM = "#e11d48"  # 미스매치 음영
SVG_NS, XLINK_NS = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def flatten_svg(path):
    """matplotlib svg 의 <use>(글자 모양·눈금 표식 참조)를 실제 <path> 로 펼침 → 글자·숫자 모두 독립 벡터 도형"""
    tree = ET.parse(path)
    root = tree.getroot()
    defs = {e.get("id"): e for e in root.iter(f"{{{SVG_NS}}}path") if e.get("id")}
    used = set()
    for parent in list(root.iter()):
        for i, use in enumerate(list(parent)):
            if use.tag != f"{{{SVG_NS}}}use":
                continue
            ref = use.get(f"{{{XLINK_NS}}}href", "").lstrip("#")
            if ref not in defs:
                continue
            used.add(ref)
            tf = " ".join(t for t in [use.get("transform", ""),
                                      f"translate({use.get('x', '0')} {use.get('y', '0')})"] if t)
            g = ET.Element(f"{{{SVG_NS}}}g", {"transform": tf})
            if use.get("style"):
                g.set("style", use.get("style"))
            shape = copy.deepcopy(defs[ref])
            del shape.attrib["id"]
            g.append(shape)
            parent.remove(use)
            parent.insert(i, g)
    for parent in list(root.iter()):  # 쓰인 정의는 지우고 빈 <defs> 정리
        for d in list(parent):
            if d.tag == f"{{{SVG_NS}}}defs":
                for e in list(d):
                    if e.get("id") in used:
                        d.remove(e)
                if len(d) == 0:
                    parent.remove(d)
    tree.write(path, encoding="utf-8", xml_declaration=True)
DAY0 = pd.Timestamp("2006-01-13")


DASH, GAP = 4.0, 2.5  # 점선 선·간격 길이 [pt], 곡선 위 직선거리 기준


def draw_even_dashes(ax, x, y, color, lw=1.6):
    """곡선을 따라가며 직선거리(화면 pt)로 DASH 선 / GAP 간격을 번갈아 잘라 직선 선분으로 그림
    → 꺾이는 곳에서도 점선 한 칸의 길이·간격이 같게 보임 (NaN 은 끊김)"""
    fig = ax.figure
    fig.canvas.draw()
    to_pt = ax.transData.transform
    scale = 72 / fig.dpi
    segs = []
    ok = ~np.isnan(y)
    for run in np.split(np.arange(len(y)), np.where(np.diff(ok.astype(int)) != 0)[0] + 1):
        if not ok[run[0]] or len(run) < 2:
            continue
        P = to_pt(np.column_stack([x[run], y[run]])) * scale
        cur, k, on, pts = P[0], 1, True, [P[0]]
        while k < len(P):
            L = DASH if on else GAP
            # cur 에서 직선거리 L 인 점을 다음 선분들에서 찾음
            while k < len(P) and np.hypot(*(P[k] - cur)) < L:
                k += 1
            if k >= len(P):
                break
            a_, b_ = P[k - 1], P[k]
            d = b_ - a_
            f = d @ d
            g = 2 * d @ (a_ - cur)
            h = (a_ - cur) @ (a_ - cur) - L * L
            tt = (-g + np.sqrt(max(g * g - 4 * f * h, 0))) / (2 * f) if f > 0 else 1.0
            nxt = a_ + np.clip(tt, 0, 1) * d
            if on:
                segs.append([cur, nxt])
            cur, on = nxt, not on
        if on and np.hypot(*(P[-1] - cur)) > 0.5:  # 남은 꼬리 (짧으면 생략)
            segs.append([cur, P[-1]])
    inv = ax.transData.inverted()
    segs = [inv.transform(np.array(sg) / scale) for sg in segs]
    ax.add_collection(LineCollection(segs, colors=color, linewidths=lw, capstyle="butt", zorder=3))


def plot_day(base, ctrl, ctrl_label, spans, title, out_png):
    """base·ctrl: pv, load 열을 가진 10분 DataFrame (구간 시작 시각 index), ctrl=None 이면 base(태양추적)만
    spans: [(시작, 끝, 음영 색, 범례, 글자 색)] 태양추적이 아닌 구간 (음영 + 시각 표기)"""
    dm.style.use("presentation-kr")  # dartwork 한국어 프리셋 (Paperlogy)
    plt.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["svg.fonttype"] = "path"  # svg 글자를 벡터 외곽선으로
    fig, ax = plt.subplots(figsize=(18 / 2.54, 11 / 2.54))
    end = DAY0 + pd.Timedelta(hours=24)
    x = base.loc[DAY0:end - pd.Timedelta(minutes=10)]
    y = None if ctrl is None else ctrl.loc[DAY0:end - pd.Timedelta(minutes=10)]
    t_fine = pd.date_range(DAY0, end, freq="1min")

    def curve(s):
        """10분 구간값을 구간 중앙(+5분)에 두고 PCHIP 으로 부드럽게 연결 (넘침 없음), 0시·24시는 끝값 유지"""
        tm = np.r_[0.0, (s.index - DAY0).total_seconds() / 3600 + 5 / 60, 24.0]
        v = np.r_[s.iloc[0], s.to_numpy(), s.iloc[-1]]
        return t_fine, PchipInterpolator(tm, v)((t_fine - DAY0).total_seconds() / 3600)

    if ctrl is None:  # 태양추적만: 실선 2개
        lines = [ax.plot(*curve(x.pv), color=C_PV, lw=1.6)[0],
                 ax.plot(*curve(x.load), color=C_DEM, lw=1.6)[0]]
        labels = ["PV 발전", "수요"]
    else:
        def dashed(sx, sy, c):
            """태양추적 점선: 제어안 실선과 선 두께 이내로 겹치는 곳(|차이| < 0.06 kWh)은 그리지 않음.
            실제 선분은 배치 확정 후 draw_even_dashes 가 그림 (범례용 대리 선만 반환)"""
            t, vx = curve(sx)
            _, vy = curve(sy)
            pending.append((mdates.date2num(t), np.where(np.abs(vx - vy) < 0.06, np.nan, vx), c))
            return Line2D([], [], color=c, lw=1.6, ls=(0, (DASH / 1.6, GAP / 1.6)), dash_capstyle="butt")

        pending = []

        lines = [dashed(x.pv, y.pv, C_PV),
                 ax.plot(*curve(y.pv), color=C_PV, lw=1.6, zorder=2)[0],
                 dashed(x.load, y.load, C_DEM),
                 ax.plot(*curve(y.load), color=C_DEM, lw=1.6, zorder=2)[0]]
        labels = ["PV 발전 · 태양추적", f"PV 발전 · {ctrl_label}", "수요 · 태양추적", f"수요 · {ctrl_label}"]
    # 미스매치(잉여·부족 구분 없이 |PV − 수요|): 실선(제어안) PV·수요 사이 음영, 구간 안만
    m = x if ctrl is None else y
    _, pv_c = curve(m.pv)
    _, ld_c = curve(m.load)
    in_span = np.zeros(len(t_fine), bool)  # 태양추적이 아닌 구간 안에서만
    for t0, t1, *_ in spans:
        in_span |= (t_fine >= pd.Timestamp(t0)) & (t_fine <= pd.Timestamp(t1))
    if in_span.any():
        lines.append(ax.fill_between(t_fine, pv_c, ld_c, where=in_span, color=C_MM, alpha=0.22, lw=0, zorder=1))
        labels.append("미스매치")
    bounds = {}  # 경계 시각 → 글자 색
    for t0, t1, c, lab, c_txt in spans:
        t0, t1 = pd.Timestamp(t0), pd.Timestamp(t1)
        lines.append(ax.axvspan(t0, t1, color=c, alpha=0.12, lw=0, zorder=0))
        labels.append(lab)
        # 태양추적이 아닌 구간: 경계 점선 (시각은 아래에서 x축에 표기)
        ax.vlines([t0, t1], 0, 1, transform=ax.get_xaxis_transform(), color=c_txt, lw=0.8, ls=":", zorder=1)
        for t in (t0, t1):
            bounds.setdefault(t, c_txt)

    ax.set_xlim(DAY0, end)
    ax.set_ylim(0, 7.2)
    ax.spines["left"].set_bounds(0, 7)  # y축 선은 마지막 눈금(7)에서 끝냄
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{round((mdates.num2date(v).replace(tzinfo=None) - DAY0).total_seconds() / 3600):d}"))
    ax.tick_params(labelsize=11)
    # 경계 시각: 정시 눈금 아래 줄에 HH:MM 굵게, 가까운 시각(1.6 h 미만)은 다음 줄로
    rows, last = [], []
    for t in sorted(bounds):
        r = next((k for k, tl in enumerate(last) if t - tl >= pd.Timedelta(hours=1.6)), len(last))
        last[r:r + 1] = [t]
        rows.append((t, r))
    for t, r in rows:
        ax.annotate(f"{t:%H:%M}", xy=(mdates.date2num(t), 0), xycoords=ax.get_xaxis_transform(),
                    xytext=(0, -22 - 15 * r), textcoords="offset points", ha="center", va="top",
                    fontsize=11, fontweight="bold", color=bounds[t], annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=bounds[t], lw=0.8, shrinkA=0, shrinkB=0))
    n_rows = max((r for _, r in rows), default=-1) + 1
    ax.set_xlabel("시각 [h]", fontsize=13, labelpad=10 + 16 * n_rows)
    ax.set_ylabel("kWh", fontsize=13)
    ax.grid(axis="y", alpha=0.3)
    # 범례: 그래프 안 오른쪽 위 1열 (19시 이후 수요 0.5 위는 비어 있음)
    ax.legend(lines, labels, ncol=1, fontsize=9, frameon=False, loc="upper right", handlelength=1.6,
              borderaxespad=0.2, labelspacing=0.35)
    ax.set_title(f"{DAY0.month}/{DAY0.day}, {title}", fontsize=14, fontweight="bold", pad=8)
    dm.simple_layout(fig)
    if ctrl is not None:
        for tx, v, c in pending:
            draw_even_dashes(ax, tx, v, c)
    fig.savefig(out_png, dpi=300, bbox_inches="tight", transparent=True)
    fig.savefig(out_png.with_suffix(".svg"), bbox_inches="tight", transparent=True)
    flatten_svg(out_png.with_suffix(".svg"))
    plt.close(fig)
    return out_png

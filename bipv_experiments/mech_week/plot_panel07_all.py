"""
bipv_experiments/mech_week/plot_panel07_all.py
==============================================
패널 7번 그래프 ①(메커니즘)·②(누적)·③(PV·수요)를 같은 고정 여백으로 다시 그린다 (2026-11-05).
- dm.simple_layout 은 그래프마다 글자 폭에 맞춰 여백을 정해, 칸 안에서 그림 영역(축)의 왼쪽·오른쪽 끝이 서로 어긋났다.
  여기서는 plot_panel_dm.save 를 fig.subplots_adjust(고정 pt 여백) 로 바꿔 세 그래프의 축 좌우 끝을 맞춘다.
- ② 는 plot_panel_dm.panel07b 를 그대로 부른다 (원본 파일은 수정하지 않음)
출력: mech_week/figures/dm_panel07_{mech,cum,pv}_day0109.svg (+ .png)
실행: python bipv_experiments/mech_week/plot_panel07_all.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "bipv_mismatch" / "explain_surplus_heating"))
sys.path.insert(0, str(HERE))
import plot_panel_dm as P  # noqa: E402

P.OUT = HERE / "figures"
LEFT, RIGHT = 36, 6  # pt, 세 그래프 공통 (y축 눈금 + y축 이름 한 줄이 들어가는 폭)


def pt(v):
    return float(str(v).replace("pt", ""))


def save_aligned(fig, name, mt=6, mb=22, **_):
    """고정 pt 여백. 왼쪽·오른쪽은 모든 그래프 공통, 위·아래만 그래프별로"""
    w, h = fig.get_size_inches() * 72
    fig.subplots_adjust(left=LEFT / w, right=1 - RIGHT / w, top=1 - pt(mt) / h, bottom=pt(mb) / h)
    out = P.OUT / f"{name}.svg"
    fig.savefig(out)
    fig.savefig(out.with_suffix(".png"), dpi=300)
    P.strip_clip(out)
    P.flatten_svg(out)
    plt.close(fig)
    print(f"[*] {out}")


P.save = save_aligned


def main():
    import plot_panel07_mech as M
    import plot_panel07_pv as V
    from analyze import RUNS, load

    M.main()
    P.style()
    P.panel07b(load(RUNS["태양추적"]), load(P.TIDE))
    V.main()


if __name__ == "__main__":
    main()

"""
bipv_mismatch/explain_surplus_heating/plot_panel06_formula.py
=============================================================
공모전 패널 06번 설정 표 아래 "목적 함수" 줄에 넣을 수식 svg (2026-11-04).
글꼴은 LaTeX 기본(Computer Modern, mathtext "cm"), arg min 아래에 각도 범위.

정답 각도(오라클) 정의 — Notion 공모전 > TiDE > 목적함수:
  조절 구간의 timestep t 마다, case2 각도별 PV 발전·수요를 1° 간격으로 보간해
  |PV − 수요| 가 최소인 각도 (태양추적 각도 ~ 90° 범위). 수요 = 냉방/3.0 + 난방/2.5 + 조명.

출력: explain_surplus_heating/figures/dm_panel06_formula.svg (+ .png)
실행: python bipv_mismatch/explain_surplus_heating/plot_panel06_formula.py
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent / "figures" / "dm_panel06_formula"
FS = 6.5
INK = "#334155"
TEX = (r"$\theta^{*}_{t}=\underset{\theta_{\mathrm{st},t}\,\leq\,\theta\,\leq\,90^{\circ}}{\mathrm{arg\,min}}"
       r"\;\left|\,P_{\mathrm{PV}}(\theta,t)-D(\theta,t)\,\right|,"
       r"\qquad D=\frac{Q_{\mathrm{c}}}{3.0}+\frac{Q_{\mathrm{h}}}{2.5}+E_{\mathrm{L}}$")


def main():
    mpl.rcParams.update({"mathtext.fontset": "cm", "svg.fonttype": "path"})
    fig = plt.figure(figsize=(3, 0.4))
    fig.text(0, 0.5, TEX, fontsize=FS, color=INK, va="center")
    for ext in ("svg", "png"):
        fig.savefig(OUT.with_suffix(f".{ext}"), bbox_inches="tight", pad_inches=0.03, transparent=True, dpi=600)
    plt.close(fig)
    print(f"[*] {OUT}.svg")


if __name__ == "__main__":
    main()

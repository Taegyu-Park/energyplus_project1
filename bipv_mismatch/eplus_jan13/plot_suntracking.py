"""
eplus_jan13/plot_suntracking.py
===============================
1/13 (IWEC) case3 태양추적만의 PV 발전·수요 (잉여 구간 표시 없음), jan13_surplus90 과 같은 스타일 (plot_day.py).
출력: eplus_jan13/jan13_suntracking.{png,svg}
"""

from analyze import HERE, RUNS, load
from plot_day import plot_day


def main():
    out = plot_day(load(RUNS["suntracking"]), None, None, [], "태양추적 PV 발전과 수요", HERE / "jan13_suntracking.png")
    print(f"[*] {out} (+ .svg)")


if __name__ == "__main__":
    main()

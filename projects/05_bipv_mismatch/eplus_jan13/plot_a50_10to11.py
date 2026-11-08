"""
eplus_jan13/plot_a50_10to11.py
==============================
jan13_a50_10to11.png 를 jan13_surplus90.png 와 같은 스타일(plot_day.py)로 다시 그림 (png+svg).
analyze_a50_10to11.py 는 그대로 두고 그림만 이 스크립트로 덮어쓴다.
"""

from analyze import HERE, RUNS, load
from plot_day import plot_day


def main():
    st = load(RUNS["suntracking"])
    new = load(HERE / "runs" / "jan13_a50_10to11" / "eplusout.sql")
    out = plot_day(st, new, "50°→90° 고정",
                   [("2006-01-13 11:00", "2006-01-13 14:10", "#10b981", "90° 고정 구간", "#047857"),
                    ("2006-01-13 10:00", "2006-01-13 11:00", "#6366f1", "50° 고정 구간", "#4338ca")],
                   "50°→90° 고정 vs 태양추적", HERE / "jan13_a50_10to11.png")
    print(f"[*] {out} (+ .svg)")


if __name__ == "__main__":
    main()

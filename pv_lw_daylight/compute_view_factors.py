"""
pv_lw_daylight/compute_view_factors.py
=======================================================
남측 외피(창 2개 + 창을 뺀 외벽 2개)에서 본 PV 루버 6단의 뷰팩터를 각도(0~90°)별로 계산한다.

- 기하: case3_v3_south_fixed.idf 의 Shade_<단>_<각도>_<번호> (case2 각 각도와 동일함이 검증됨)
- 방법: 외피 표면의 샘플 점에서 외향 법선(-y) 기준 코사인 가중 광선을 쏘아, 처음 맞는 단을 센다.
  (단끼리 서로 가리는 효과까지 포함, 같은 단의 16개 패널은 하나의 사각형으로 합침)
- 출력: view_factors.csv (surface, angle, row, vf)

사용: python pv_lw_daylight/compute_view_factors.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
IDF = HERE.parent / "bipv_experiments" / "idf" / "case3_v3_south_fixed.idf"
OUT = HERE / "view_factors.csv"
ANGLES = list(range(0, 100, 10))
ROWS = range(1, 7)
GRID = 0.25          # 샘플 점 간격 [m]
N_RAYS = 1000        # 샘플 점당 광선 수
SEED = 0


def parse_polygons(text: str) -> dict:
    """이름 → 꼭짓점 배열 (Shading:Building:Detailed, FenestrationSurface:Detailed, BuildingSurface:Detailed)"""
    polys = {}
    for m in re.finditer(r"(?ms)^(Shading:Building:Detailed|FenestrationSurface:Detailed|BuildingSurface:Detailed),(.*?);", text):
        fields = [f.split("!-")[0].strip() for f in m.group(2).split("\n")]
        fields = [x for f in fields for x in f.split(",")]
        fields = [x.strip() for x in fields if x.strip() != ""]
        name = fields[0]
        nums = []
        for x in reversed(fields):
            try:
                nums.append(float(x))
            except ValueError:
                break
        nums = nums[::-1]
        n = len(nums) // 3 * 3
        polys[name] = np.array(nums[len(nums) - n:]).reshape(-1, 3)
    return polys


def row_rects(polys: dict) -> dict:
    """(angle, row) → (원점 P0, 변 벡터 U(x방향), V(경사 방향)) — 같은 단의 패널 16개를 합친 사각형"""
    rects = {}
    for a in ANGLES:
        for r in ROWS:
            pts = np.vstack([v for k, v in polys.items() if re.fullmatch(rf"Shade_{r}_{a:02d}_\d+", k)])
            x0, x1 = pts[:, 0].min(), pts[:, 0].max()
            # 경첩(위쪽, 벽 쪽) 모서리와 반대쪽 모서리: z 최대·y 최대 점 vs 최소 점
            hinge = pts[np.lexsort((pts[:, 1], pts[:, 2]))][-1]
            free = pts[np.lexsort((-pts[:, 1], -pts[:, 2]))][-1]
            if a == 90:  # 수평: z 동일 → y로 구분
                hinge = pts[pts[:, 1].argmax()]
                free = pts[pts[:, 1].argmin()]
            p0 = np.array([x0, hinge[1], hinge[2]])
            U = np.array([x1 - x0, 0.0, 0.0])
            V = np.array([0.0, free[1] - hinge[1], free[2] - hinge[2]])
            rects[(a, r)] = (p0, U, V)
    return rects


def sample_points(poly: np.ndarray, holes: list) -> np.ndarray:
    """y=0 평면의 (x,z) 직사각형 표면 샘플 점 (holes 직사각형 제외)"""
    x0, x1 = poly[:, 0].min(), poly[:, 0].max()
    z0, z1 = poly[:, 2].min(), poly[:, 2].max()
    xs = np.arange(x0 + GRID / 2, x1, GRID)
    zs = np.arange(z0 + GRID / 2, z1, GRID)
    X, Z = np.meshgrid(xs, zs)
    pts = np.column_stack([X.ravel(), np.zeros(X.size), Z.ravel()])
    keep = np.ones(len(pts), bool)
    for h in holes:
        hx0, hx1, hz0, hz1 = h[:, 0].min(), h[:, 0].max(), h[:, 2].min(), h[:, 2].max()
        keep &= ~((pts[:, 0] > hx0) & (pts[:, 0] < hx1) & (pts[:, 2] > hz0) & (pts[:, 2] < hz1))
    return pts[keep]


def cosine_rays(n: int, rng) -> np.ndarray:
    """외향 법선 (0,-1,0) 기준 코사인 가중 방향"""
    u1, u2 = rng.random(n), rng.random(n)
    r, phi = np.sqrt(u1), 2 * np.pi * u2
    a, b, c = r * np.cos(phi), r * np.sin(phi), np.sqrt(1 - u1)
    return np.column_stack([a, -c, b])  # x, y(외향), z


def view_factors(points: np.ndarray, rects: dict, angle: int, rng) -> np.ndarray:
    """표면 평균 뷰팩터 [단 1..6]"""
    hits = np.zeros(6)
    total = 0
    for p in points:
        d = cosine_rays(N_RAYS, rng)
        best_t = np.full(N_RAYS, np.inf)
        best_r = np.full(N_RAYS, -1)
        for r in ROWS:
            p0, U, V = rects[(angle, r)]
            nrm = np.cross(U, V)
            denom = d @ nrm
            with np.errstate(divide="ignore", invalid="ignore"):
                t = ((p0 - p) @ nrm) / denom
            q = p + d * t[:, None] - p0
            s = q @ U / (U @ U)
            w = q @ V / (V @ V)
            ok = (t > 1e-9) & (s >= 0) & (s <= 1) & (w >= 0) & (w <= 1) & (t < best_t)
            best_t[ok] = t[ok]
            best_r[ok] = r
        for r in ROWS:
            hits[r - 1] += np.count_nonzero(best_r == r)
        total += N_RAYS
    return hits / total


def main():
    text = IDF.read_text(encoding="utf-8", errors="ignore")
    polys = parse_polygons(text)
    rects = row_rects(polys)
    rng = np.random.default_rng(SEED)

    surfaces = {}
    for fl in (1, 2):
        wall = polys[f"BIPV_office_{fl}_S..Wall_S"]
        win = polys[f"BIPV_office_{fl}_S..Wall_S_Glz0"]
        surfaces[f"BIPV_office_{fl}_S..Wall_S_Glz0"] = sample_points(win, [])
        surfaces[f"BIPV_office_{fl}_S..Wall_S"] = sample_points(wall, [win])

    rows = []
    for s, pts in surfaces.items():
        for a in ANGLES:
            vf = view_factors(pts, rects, a, rng)
            for r in ROWS:
                rows.append({"surface": s, "angle": a, "row": r, "vf": vf[r - 1]})
            print(f"{s:32s} A{a:02d}  n={len(pts):4d}  sum={vf.sum():.3f}  " + " ".join(f"{v:.3f}" for v in vf), flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()

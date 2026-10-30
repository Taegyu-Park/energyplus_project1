"""
build_case3_v3_south_fixed.py
=============================
case3_v3_south.idf 의 차양 모델링 오류 2가지를 고친 case3_v3_south_fixed.idf 를 생성한다.
원본 IDF(case_idf/case3_v3_KS/case3_v3_south.idf)는 읽기만 하고, 결과는 이 폴더에 쓴다.

1. 0° 차양(TransSched_BIPV_A00)이 벽면과 같은 평면(y=0)에 있어 EnergyPlus가 그늘을 계산하지 않음
   → case2_0.idf 와 동일하게 y=-0.1 m 로 이격
2. SimpleSkyDiffuseModeling 은 차양 투과율이 변하지 않는다고 가정하므로, 투과율 액추에이터로
   차양을 전환하는 case3에서는 확산 일사 차폐가 모든 각도에서 무시됨
   → DetailedSkyDiffuseModeling 으로 변경
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "case_idf" / "case3_v3_KS" / "case3_v3_south.idf"  # 원본 (읽기만 함)
DST = HERE / "case3_v3_south_fixed.idf"
A00_OFFSET_Y = -0.1  # case2_0.idf 와 동일


def offset_a00_shades(text: str) -> tuple[str, int]:
    pattern = re.compile(
        r"(Shading:Building:Detailed,\s*\n\s*Shade_\d+_00_\d+,[^\n]*\n\s*TransSched_BIPV_A00,[^\n]*\n[^\n]*\n)"
        r"((?:\s*[-\d.]+,\s*[-\d.]+,\s*[-\d.]+[,;][^\n]*\n){4})"
    )

    def fix_vertices(m):
        verts = re.sub(
            r"([-\d.]+),(\s*)([-\d.]+),(\s*)([-\d.]+)([,;])",
            lambda v: f"{v.group(1)},{v.group(2)}{A00_OFFSET_Y if float(v.group(3)) == 0 else v.group(3)},"
                      f"{v.group(4)}{v.group(5)}{v.group(6)}",
            m.group(2),
        )
        return m.group(1) + verts

    return pattern.subn(fix_vertices, text)


def main():
    text = SRC.read_text(encoding="utf-8", errors="ignore")

    text, n_shades = offset_a00_shades(text)
    if n_shades != 96:
        raise RuntimeError(f"0° 차양 96개 중 {n_shades}개만 수정됨")

    text, n_sky = re.subn(
        r"SimpleSkyDiffuseModeling(,\s*!- Sky Diffuse Modeling Algorithm)", r"DetailedSkyDiffuseModeling\g<1>", text
    )
    if n_sky != 1:
        raise RuntimeError(f"Sky Diffuse Modeling 치환 실패 (matches={n_sky})")

    DST.write_text(text, encoding="utf-8")
    print(f"[*] {DST.name} 생성: 0° 차양 {n_shades}개 y={A00_OFFSET_Y} m 이격, DetailedSkyDiffuseModeling")


if __name__ == "__main__":
    main()

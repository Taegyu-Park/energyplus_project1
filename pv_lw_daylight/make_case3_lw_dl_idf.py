"""
pv_lw_daylight/make_case3_lw_dl_idf.py
======================================
run_pvlw.py 가 실행할 때마다 붙이던 case3 최종 조건을 IDF 파일 자체에 넣은 단독 실행용 IDF를 만든다.
(c3_FE_ST_lw_dl400 연간 실행과 같은 설정, 기존 파일은 수정하지 않음)

- 원본: bipv_experiments/idf/case3_v3_south_fixed.idf
- runner.prepare_idf: FullExterior, Ideal Loads 용량 고정(case2_max_over_angles.eio), RunPeriod 연간 그대로
- PV Semiconductor Bandgap 1.12 → 1.25 (음수 Rs 보정), 이코노마이저 DifferentialEnthalpy
- PV 장파: 남측 4면 SurfaceProperty:SurroundingSurfaces/LocalEnvironment + T_eff 스케줄 (플러그인이 매 스텝 갱신)
- 조명: case3 기본 주광 계산은 루버 차양을 무시하므로 case2 주광 배율표(dl_mult_FE_L400.csv)를 플러그인이 적용
- 플러그인 모듈 → bipv_schedule_lw_standalone (설정·스케줄 경로 기본값 내장), SearchPaths = pv_lw_daylight, bipv_experiments

출력: bipv_experiments/idf/case3_v3_south_fixed_lw_dl.idf, pv_lw_daylight/standalone/case3_lw_dl400_config.json
실행: energyplus -w data/KOR_KJ_Gwangju.471560_IWEC.epw -d <출력폴더> bipv_experiments/idf/case3_v3_south_fixed_lw_dl.idf
"""

import json
import re
import shutil
import tempfile
from pathlib import Path

import run_pvlw as rp

SRC_IDF = rp.EXP_DIR / "idf" / "case3_v3_south_fixed.idf"
OUT_IDF = rp.EXP_DIR / "idf" / "case3_v3_south_fixed_lw_dl.idf"
CONFIG = rp.HERE / "standalone" / "case3_lw_dl400_config.json"
SIZING = rp.EXP_DIR / "sizing" / "case2_max_over_angles.eio"
DAYLIGHT_TABLE = rp.HERE / "daylight_tables" / "dl_mult_FE_L400.csv"
PV_BANDGAP = 1.25
ECONOMIZER = "DifferentialEnthalpy"
PLUGIN_MODULE = "bipv_schedule_lw_standalone"


def main():
    if OUT_IDF.exists():
        raise FileExistsError(f"{OUT_IDF} 이미 있음 (덮어쓰지 않음)")
    with tempfile.TemporaryDirectory() as tmp:
        idf_copy = rp.runner.prepare_idf(Path(tmp), None, None, False, None, SRC_IDF, False, "FullExterior", SIZING, False)
        text = idf_copy.read_text(encoding="utf-8")

    text, n = re.subn(r"\b1\.12(,\s*!- Semiconductor Bandgap)", rf"{PV_BANDGAP}\g<1>", text)
    if n != 1:
        raise RuntimeError(f"Semiconductor Bandgap 치환 실패 ({n})")
    text, n = re.subn(r"\bDifferentialDryBulb(,\s*!-+ Outdoor Air Economizer Type)", rf"{ECONOMIZER}\g<1>", text)
    if n != 10:
        raise RuntimeError(f"Economizer Type 치환 수 {n} != 10")

    angles = rp.detect_angles(text)
    cfg = rp.lw_config(angles, None, rp.generator_rows(text))
    cfg["daylight_table"] = {"table": str(DAYLIGHT_TABLE), "zones": rp.S_ZONES,
                             "lights": [f"{z}_Space SmallOffice Building_Lighting" for z in rp.S_ZONES],
                             "schedule": "SmallOffice Building_Lighting Schedule"}
    text = rp.patch_idf(text, "case3", cfg, None, "Continuous")

    # run_pvlw 는 bipv_schedule_lw_plugin + 환경변수로 실행 → 단독 실행용 모듈로 교체
    text, n = re.subn(r"\bbipv_schedule_lw_plugin(,\s*!- Module Name)", rf"{PLUGIN_MODULE}\g<1>", text)
    if n != 1:
        raise RuntimeError(f"플러그인 모듈 치환 실패 ({n})")

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    header = ("! case3_v3_south_fixed_lw_dl.idf — pv_lw_daylight/make_case3_lw_dl_idf.py 로 생성\n"
              "! case3_v3_south_fixed.idf + FullExterior + 용량 고정 + Eg 1.25 + DifferentialEnthalpy\n"
              "! + PV 장파 연동(SurroundingSurfaces) + 주광 배율표 조명 (플러그인 bipv_schedule_lw_standalone)\n")
    OUT_IDF.write_text(header + text, encoding="utf-8")
    print(f"[*] 각도 {angles}, 장파 표면 {len(cfg['surfaces'])}개\n[*] {OUT_IDF}\n[*] {CONFIG}")


if __name__ == "__main__":
    main()

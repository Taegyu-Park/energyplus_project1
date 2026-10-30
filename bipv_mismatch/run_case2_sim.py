"""
run_case2_sim.py
================
case2_KS 고정각도(0~90°) IDF 10개에 설정 보정과 출력 변수를 추가해 연간 시뮬레이션한다.
- 입력 IDF : case_idf/case2_KS/case2_{angle}.idf (수정하지 않음)
- 보정     : 그림자 Timestep 계산, DetailedSkyDiffuseModeling, Ideal Loads 용량 통일
             (bipv_experiments/runs/c2_RF_A* 와 같은 설정, One-Diode PV)
- 출력 IDF : bipv_mismatch/idf/case2_KS/case2_{angle}.idf
- 결과     : bipv_mismatch/case2_KS/case2_{angle}/  (case_analysis/normal/case2_KS와 동일 구조)
- --weather tmyx : 같은 IDF를 TMYx(2011-2025) 기상으로 실행 → bipv_mismatch/case2_KS_TMYx/ (일반화 test용)

사용: python bipv_mismatch/run_case2_sim.py --jobs 10 [--weather tmyx]
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "bipv_experiments"))
from runner import EP_DIR, WEATHER_PATH, prepare_idf  # noqa: E402

WORK_DIR = ROOT / "bipv_mismatch"
SRC_IDF_DIR = ROOT / "case_idf" / "case2_KS"
IDF_OUT_DIR = WORK_DIR / "idf" / "case2_KS"
WEATHERS = {
    "iwec": (WEATHER_PATH, WORK_DIR / "case2_KS"),
    "tmyx": (ROOT / "data" / "KOR_KJ_Gwangju.471560_TMYx.2011-2025.epw", WORK_DIR / "case2_KS_TMYx"),
}
SIZING_EIO = ROOT / "bipv_experiments" / "sizing" / "case2_max_over_angles.eio"
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
PV_BANDGAP = 1.25  # eV, E+ 파라미터 추출용 피팅값 (원본 1.12)

# 전체 키(*)로 출력하는 변수
SITE_OUTPUTS = [
    "Site Outdoor Air Relative Humidity",
    "Site Outdoor Air Dewpoint Temperature",
    "Site Wind Speed",
    "Site Sky Temperature",
    "Site Horizontal Infrared Radiation Rate per Area",
    "Site Total Sky Cover",
    "Site Day Type Index",
]
ZONE_OUTPUTS = [
    "Zone Mean Air Temperature",
    "Zone Operative Temperature",
    "Zone Air Relative Humidity",
    "Zone People Occupant Count",
    "Zone Thermostat Heating Setpoint Temperature",
    "Zone Thermostat Cooling Setpoint Temperature",
    "Zone Ideal Loads Zone Sensible Heating Energy",
    "Zone Ideal Loads Zone Sensible Cooling Energy",
    "Zone Ideal Loads Zone Latent Heating Energy",
    "Zone Ideal Loads Zone Latent Cooling Energy",
    "Zone Lights Electricity Energy",
    "Zone Electric Equipment Electricity Energy",
]
# 남측 파사드 표면 (키 지정)
SOUTH_WALLS = ["BIPV_office_1_S..Wall_S", "BIPV_office_2_S..Wall_S"]
SOUTH_WINDOWS = ["BIPV_office_1_S..Wall_S_Glz0", "BIPV_office_2_S..Wall_S_Glz0"]
SURFACE_OUTPUTS = [
    ("Surface Inside Face Temperature", SOUTH_WALLS + SOUTH_WINDOWS),
    ("Surface Outside Face Incident Solar Radiation Rate per Area", SOUTH_WALLS + SOUTH_WINDOWS),
    ("Surface Window Transmitted Solar Radiation Energy", SOUTH_WINDOWS),
]


def representative_pv(text: str, angle: int) -> list[str]:
    """6개 단(row)마다 첫 번째 발전기 이름을 고른다 (PV_{row}_{angle}_{nn})."""
    names = sorted(set(re.findall(rf"\bPV_(\d)_{angle}_(\d+)\b", text)), key=lambda x: (x[0], int(x[1])))
    first = {}
    for row, nn in names:
        first.setdefault(row, f"PV_{row}_{angle}_{nn}")
    if len(first) != 6:
        raise RuntimeError(f"{angle}°: 대표 PV 발전기 {len(first)}개 (6개 기대)")
    return [first[r] for r in sorted(first)]


def extra_outputs(text: str, angle: int) -> str:
    lines = ["", "! ── bipv_mismatch: 추가 출력 변수 ──"]
    lines += [f"Output:Variable,*,{v},TimeStep;" for v in SITE_OUTPUTS + ZONE_OUTPUTS]
    for var, keys in SURFACE_OUTPUTS:
        lines += [f"Output:Variable,{k},{var},TimeStep;" for k in keys]
    lines += [f"Output:Variable,{k},Generator PV Cell Temperature,TimeStep;" for k in representative_pv(text, angle)]
    return "\n".join(lines) + "\n"


def build_idf(angle: int) -> Path:
    """보정·출력 추가 IDF를 idf/case2_KS/case2_{angle}.idf 로 저장"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_idf = prepare_idf(Path(tmp), days=None, sky_diffuse="DetailedSkyDiffuseModeling",
                              idf_path=SRC_IDF_DIR / f"case2_{angle}.idf", shadow_timestep=True,
                              ideal_sizing_from=SIZING_EIO)
        text = tmp_idf.read_text(encoding="utf-8")
    # One-Diode PV 밴드갭 보정: Eg 1.12면 E+ 닫힌 식 Rs = -0.879 Ω(음수) → Newton 발산(TMYx 70°)·저일사 출력 왜곡.
    # Eg 1.25 → Rs +0.091 Ω, 셀당 이상계수 1.22, STC 394.3 W, Voc 온도계수(데이터시트) 유지
    text, n = re.subn(r"\b1\.12(,\s*!- Semiconductor Bandgap)", rf"{PV_BANDGAP}\g<1>", text)
    if n != 1:
        raise RuntimeError(f"{angle}°: Semiconductor Bandgap 치환 실패 (matches={n})")
    for key in SOUTH_WALLS + SOUTH_WINDOWS:
        if f"{key}," not in text:
            raise RuntimeError(f"{angle}°: 표면 {key} 없음")
    out = IDF_OUT_DIR / f"case2_{angle}.idf"
    out.write_text(text + extra_outputs(text, angle), encoding="utf-8")
    return out


def run(angle: int, epw: Path, out_root: Path) -> str:
    idf = IDF_OUT_DIR / f"case2_{angle}.idf"
    out_dir = out_root / f"case2_{angle}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    cmd = [str(EP_DIR / "energyplus.exe"), "-w", str(epw), "-d", str(out_dir), str(idf)]
    print(f"[start] case2_{angle}", flush=True)
    with open(out_dir / "run_stdout.log", "w", encoding="utf-8", errors="ignore") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        raise RuntimeError(f"case2_{angle}: EnergyPlus exit code {rc}")
    return f"case2_{angle}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--angles", type=int, nargs="*", default=ANGLES)
    ap.add_argument("--idf-only", action="store_true", help="IDF만 만들고 실행하지 않음")
    ap.add_argument("--weather", choices=list(WEATHERS), default="iwec")
    ap.add_argument("--reuse-idf", action="store_true", help="idf/case2_KS 의 기존 IDF를 다시 만들지 않고 사용")
    args = ap.parse_args()
    epw, out_root = WEATHERS[args.weather]
    assert epw.exists(), epw
    IDF_OUT_DIR.mkdir(parents=True, exist_ok=True)

    for a in args.angles:
        if args.reuse_idf:
            assert (IDF_OUT_DIR / f"case2_{a}.idf").exists(), f"IDF 없음: case2_{a}"
        else:
            print(f"[idf  ] {build_idf(a).relative_to(ROOT)}", flush=True)
    if args.idf_only:
        return

    print(f"[epw  ] {epw.name} -> {out_root.relative_to(ROOT)}", flush=True)
    failed = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run, a, epw, out_root): a for a in args.angles}
        for f in as_completed(futs):
            try:
                print(f"[done ] {f.result()}", flush=True)
            except Exception as e:
                failed.append(futs[f])
                print(f"[FAIL ] {e}", flush=True)
    if failed:
        sys.exit(f"실패 각도: {sorted(failed)}")


if __name__ == "__main__":
    main()

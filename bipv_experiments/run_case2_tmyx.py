"""
run_case2_tmyx.py
=================
case2_KS 고정각도(0~90°) IDF 10개를 TMYx(2011-2025) 기상으로 병렬 시뮬레이션한다.
- 입력 IDF: case_idf/case2_KS/case2_{angle}.idf (수정하지 않고 그대로 사용)
- 출력    : case_analysis/normal/case2_KS_TMYx/case2_{angle}/  (case2_KS와 동일 구조)

사용: python bipv_experiments/run_case2_tmyx.py --jobs 10
"""

import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EP_EXE = Path(r"C:\EnergyPlusV25-2-0\energyplus.exe")
EPW = ROOT / "data" / "KOR_KJ_Gwangju.471560_TMYx.2011-2025.epw"
IDF_DIR = ROOT / "case_idf" / "case2_KS"
OUT_ROOT = ROOT / "case_analysis" / "normal" / "case2_KS_TMYx"
ANGLES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]


def run(angle: int) -> str:
    out_dir = OUT_ROOT / f"case2_{angle}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(EP_EXE), "-w", str(EPW), "-d", str(out_dir), str(IDF_DIR / f"case2_{angle}.idf")]
    print(f"[start] case2_{angle}", flush=True)
    with open(out_dir / "run_stdout.log", "w", encoding="utf-8", errors="ignore") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        raise RuntimeError(f"case2_{angle}: EnergyPlus exit code {rc}")
    return f"case2_{angle}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=10)
    args = ap.parse_args()
    assert EPW.exists(), EPW
    failed = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run, a): a for a in ANGLES}
        for f in as_completed(futs):
            try:
                print(f"[done ] {f.result()}", flush=True)
            except Exception as e:
                failed.append(futs[f])
                print(f"[FAIL ] {e}", flush=True)
    print("실패:", failed if failed else "없음", flush=True)


if __name__ == "__main__":
    main()

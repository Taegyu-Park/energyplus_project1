"""
pv_lw_daylight/move_finished_runs.py
====================================
예전 위치(bipv_experiments/pv_lw_daylight/runs)에서 아직 실행 중이던 run을, 끝나는 대로 이 폴더 runs/<group>/ 로 옮긴다.
- 끝남 기준: summary.json 존재
- 예전 위치를 쓰는 energyplus 프로세스가 3분 연속 없으면, 남은 폴더(실패 run)도 옮기고 종료
(폴더 정리 과정에서 한 번만 쓰는 스크립트)
"""

import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "bipv_experiments" / "pv_lw_daylight" / "runs"


def group(name: str) -> str:
    if name.startswith("tbl_"):
        return "daylight_table"
    if name.startswith(("c2_RF_", "c3_FE_ST_")):
        return "annual"
    return "tests"


def old_location_busy() -> bool:
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bipv_experiments*pv_lw_daylight*' "
          "-and $_.Name -ne 'powershell.exe' } | Measure-Object | Select-Object -ExpandProperty Count")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    return int(out or 0) > 0


def move(d: Path, note=""):
    dst = HERE / "runs" / group(d.name) / d.name
    shutil.move(str(d), str(dst))
    print(f"이동{note}: {d.name} → runs/{group(d.name)}/", flush=True)


def main():
    idle = 0
    while True:
        for d in sorted(OLD.iterdir()) if OLD.exists() else []:
            if (d / "summary.json").exists():
                move(d)
        idle = 0 if old_location_busy() else idle + 1
        if idle >= 3:  # 3분 연속 비어 있으면(배치 내 job 사이 공백 대비)
            for d in sorted(OLD.iterdir()) if OLD.exists() else []:
                move(d, " (summary 없음, 실패 run)")
            print("예전 위치를 쓰는 프로세스 없음 → 종료", flush=True)
            return
        time.sleep(60)


if __name__ == "__main__":
    main()

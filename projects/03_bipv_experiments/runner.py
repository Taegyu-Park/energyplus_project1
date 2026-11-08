"""
bipv_experiments/runner.py
==========================
BIPV 각도 스케줄 실험용 EnergyPlus 러너 (프로젝트 기존 파일을 수정하지 않는 독립 실험 폴더용).

- IDF 사본을 runs/<name>/ 에 만들고 PythonPlugin 모듈을 bipv_schedule_plugin(이 폴더)으로 고정
- 스케줄 CSV 경로는 환경변수 BIPV_SCHEDULE_CSV 로 플러그인에 전달
- 여러 run 병렬 실행
- 배치 JSON의 각 job: name, schedule, idf, start(MM-DD), days, sky_diffuse, shadow_timestep,
  solar_distribution, ideal_sizing_from(eplusout.eio 경로), pv_simple
  (PythonPlugin 이 없는 IDF(case2 등)는 schedule 생략 가능)
- 상대 경로는 저장소 루트 기준

사용 예:
  python bipv_experiments/runner.py --batch bipv_experiments/schedules/diag5_batch.json --jobs 8
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
CWD = EXP_DIR.parent
IDF_PATH = EXP_DIR / "idf" / "case3_v3_south_fixed.idf"
WEATHER_PATH = CWD / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
EP_DIR = Path(r"C:\EnergyPlusV25-2-0")
COP_COOLING = 3.0
COP_HEATING = 2.5


def analyze_results(out_dir: Path) -> dict:
    """eplusout.sql 에서 기간 합계(kWh)를 계산해 summary.json 으로 저장"""
    conn = sqlite3.connect(out_dir / "eplusout.sql")

    def get_kwh(var_name):
        row = conn.execute(
            """SELECT SUM(rd.Value) FROM ReportData rd
               JOIN ReportDataDictionary d ON rd.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
               JOIN Time t ON rd.TimeIndex = t.TimeIndex
               WHERE d.Name = ? AND t.WarmupFlag = 0""",
            (var_name,),
        ).fetchone()
        return (row[0] or 0.0) / 3.6e6

    cool = get_kwh("Zone Ideal Loads Supply Air Total Cooling Energy")
    heat = get_kwh("Zone Ideal Loads Supply Air Total Heating Energy")
    pv = get_kwh("Facility Total Produced Electricity Energy")
    conn.close()
    hvac = cool / COP_COOLING + heat / COP_HEATING
    return {
        "total_bipv_generation_kwh": pv,
        "total_cooling_load_thermal_kwh": cool,
        "total_heating_load_thermal_kwh": heat,
        "hvac_electric_consumption_kwh": hvac,
        "net_energy_consumption_kwh": hvac - pv,
    }


OUT_ROOT = EXP_DIR / "runs"
PLUGIN_MODULE = "bipv_schedule_plugin"
# --diag: 창 일사 차폐 진단용 출력
DIAG_OUTPUTS = [
    "Surface Outside Face Sunlit Fraction",
    "Surface Window Transmitted Beam Solar Radiation Energy",
    "Surface Window Transmitted Diffuse Solar Radiation Energy",
    "Zone Windows Total Transmitted Solar Radiation Energy",
    "Surface Outside Face Incident Beam Solar Radiation Rate per Area",
    "Surface Outside Face Incident Sky Diffuse Solar Radiation Rate per Area",
]


IDEAL_SIZING_FIELDS = [
    ("Design Size Maximum Sensible Heating Capacity", "Maximum Sensible Heating Capacity"),
    ("Design Size Maximum Cooling Air Flow Rate", "Maximum Cooling Air Flow Rate"),
    ("Design Size Maximum Total Cooling Capacity", "Maximum Total Cooling Capacity"),
]


def read_ideal_loads_sizing(eio_path: Path) -> dict:
    """eplusout.eio 에서 Ideal Loads 자동 산정값을 읽는다: {시스템명(대문자): {IDF 필드명: 값}}"""
    sizing = {}
    for line in Path(eio_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5 or parts[0] != "Component Sizing Information" or parts[1] != "ZoneHVAC:IdealLoadsAirSystem":
            continue
        for eio_field, idf_field in IDEAL_SIZING_FIELDS:
            if parts[3].startswith(eio_field):
                sizing.setdefault(parts[2].upper(), {})[idf_field] = float(parts[4])
    if not sizing:
        raise RuntimeError(f"Ideal Loads 사이징 값을 찾지 못함: {eio_path}")
    return sizing


def apply_ideal_loads_sizing(text: str, sizing: dict) -> str:
    """모든 Ideal Loads 의 Autosize 필드를 고정값으로 바꿔, 모델 간 장치 용량을 동일하게 맞춘다."""

    def fix(m):
        obj = m.group(0)
        name = re.search(r"ZoneHVAC:IdealLoadsAirSystem,\s*\n\s*([^,]+),", obj).group(1).strip().upper()
        if name not in sizing:
            raise RuntimeError(f"사이징 값 없음: {name}")
        for field, value in sizing[name].items():
            obj, n = re.subn(rf"Autosize(,\s*!-+ {re.escape(field)})", rf"{value:.6f}\g<1>", obj)
            if n != 1:
                raise RuntimeError(f"{name}: '{field}' Autosize 치환 실패 (matches={n})")
        return obj

    # 줄 맨 앞의 객체 정의만 대상 (EquipmentList 안의 참조는 제외)
    text, n = re.subn(r"(?m)^ZoneHVAC:IdealLoadsAirSystem,[^;]*;", fix, text)
    if n != len(sizing):
        raise RuntimeError(f"Ideal Loads 객체 수({n})와 사이징 값 수({len(sizing)}) 불일치")
    return text


def prepare_idf(out_dir: Path, days: int | None, start: date | None = None, diag: bool = False,
                sky_diffuse: str | None = None, idf_path: Path = IDF_PATH,
                shadow_timestep: bool = False, solar_distribution: str | None = None,
                ideal_sizing_from: Path | None = None, pv_simple: bool = False) -> Path:
    text = idf_path.read_text(encoding="utf-8", errors="ignore")

    if "PythonPlugin:Instance" in text:
        text, n = re.subn(
            r"(PythonPlugin:Instance,\s*\n\s*KineticBIPVPlugin,[^\n]*\n[^\n]*\n\s*)[^,\n]+(,\s*!- Module Name)",
            rf"\g<1>{PLUGIN_MODULE}\g<2>",
            text,
        )
        if n != 1:
            raise RuntimeError(f"PythonPlugin Module Name 치환 실패 (matches={n})")

    if shadow_timestep:
        text, n = re.subn(
            r"Periodic(,\s*!- Shading Calculation Update Frequency Method\s*\n\s*)\d+(,\s*!- Shading Calculation Update Frequency)",
            r"Timestep\g<1>\g<2>",
            text,
        )
        if n != 1:
            raise RuntimeError(f"Shading Calculation Update Frequency 치환 실패 (matches={n})")

    if days or start:
        start = start or date(2006, 1, 1)
        end = start + timedelta(days=days - 1) if days else date(2006, 12, 31)
        text, n = re.subn(
            r"(RunPeriod,\s*\n\s*Run Period 1,[^\n]*\n\s*)1(,[^\n]*\n\s*)1(,[^\n]*\n[^\n]*\n\s*)\d+(,[^\n]*\n\s*)\d+(,)",
            rf"\g<1>{start.month}\g<2>{start.day}\g<3>{end.month}\g<4>{end.day}\g<5>",
            text,
        )
        if n != 1:
            raise RuntimeError(f"RunPeriod 치환 실패 (matches={n})")

    if sky_diffuse:
        text, n = re.subn(r"\w+SkyDiffuseModeling(,\s*!- Sky Diffuse Modeling Algorithm)", rf"{sky_diffuse}\g<1>", text)
        if n != 1:
            raise RuntimeError(f"Sky Diffuse Modeling 치환 실패 (matches={n})")

    if solar_distribution:
        text, n = re.subn(r"\w+(,\s*!- Solar Distribution)", rf"{solar_distribution}\g<1>", text)
        if n != 1:
            raise RuntimeError(f"Solar Distribution 치환 실패 (matches={n})")

    if pv_simple:
        # PV 를 단순 모델로 교체 (Decoupled 모드라 냉난방 부하에는 영향 없음; one-diode 수치 실패 회피용)
        text, n1 = re.subn(r"PhotovoltaicPerformance:EquivalentOne-Diode(,\s*!- Performance Object Type)",
                           r"PhotovoltaicPerformance:Simple\g<1>", text)
        text, n2 = re.subn(r"(PhotovoltaicPerformance:Simple,\s*!- Performance Object Type\s*\n\s*)[^,\n]+(,)",
                           r"\g<1>BIPV_Simple_PV\g<2>", text)
        if n1 == 0 or n1 != n2:
            raise RuntimeError(f"PV 모델 교체 실패 (type={n1}, name={n2})")
        text += "\nPhotovoltaicPerformance:Simple,BIPV_Simple_PV,0.9189,Fixed,0.18,;\n"

    if ideal_sizing_from:
        text = apply_ideal_loads_sizing(text, read_ideal_loads_sizing(ideal_sizing_from))

    if diag:
        text += "\n" + "".join(f"Output:Variable,*,{v},TimeStep;\n" for v in DIAG_OUTPUTS)

    idf_copy = out_dir / f"{idf_path.stem}_run.idf"
    idf_copy.write_text(text, encoding="utf-8")
    return idf_copy


def run_one(schedule: Path | None, name: str, days: int | None = None, start: date | None = None,
            diag: bool = False, sky_diffuse: str | None = None, idf_path: Path = IDF_PATH,
            shadow_timestep: bool = False, solar_distribution: str | None = None,
            ideal_sizing_from: Path | None = None, pv_simple: bool = False) -> dict:
    idf_path = idf_path if idf_path.is_absolute() else (CWD / idf_path).resolve()
    if schedule is not None:
        schedule = (CWD / schedule).resolve() if not Path(schedule).is_absolute() else Path(schedule)
        if not schedule.exists():
            raise FileNotFoundError(schedule)

    out_dir = OUT_ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    idf_copy = prepare_idf(out_dir, days, start, diag, sky_diffuse, idf_path, shadow_timestep, solar_distribution,
                           ideal_sizing_from, pv_simple)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(EP_DIR / "api" / "python"), str(EXP_DIR), env.get("PYTHONPATH", "")]
    )
    if schedule is not None:
        env["BIPV_SCHEDULE_CSV"] = str(schedule)

    cmd = [str(EP_DIR / "energyplus.exe"), "-w", str(WEATHER_PATH), "-d", str(out_dir), str(idf_copy)]
    print(f"[start] {name}  idf={idf_path.name}  schedule={schedule.name if schedule else '-'}", flush=True)
    with open(out_dir / "run_stdout.log", "w", encoding="utf-8", errors="ignore") as log:
        proc = subprocess.run(cmd, env=env, cwd=str(EXP_DIR), stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{name}: EnergyPlus exit code {proc.returncode} (see {out_dir / 'run_stdout.log'})")

    summary = analyze_results(out_dir)
    summary_path = out_dir / "summary.json"
    summary.update({"name": name, "simulation_model": idf_path.name,
                    "schedule_csv": str(schedule) if schedule else None, "days": days,
                    "start": start.isoformat() if start else None, "sky_diffuse": sky_diffuse,
                    "shadow_timestep": shadow_timestep, "solar_distribution": solar_distribution,
                    "ideal_sizing_from": str(ideal_sizing_from) if ideal_sizing_from else None,
                    "pv_simple": pv_simple})
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[done ] {name}  net={summary['net_energy_consumption_kwh']:.1f} kWh", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--schedule", type=Path, help="각도 스케줄 CSV (optimal_angle 컬럼)")
    parser.add_argument("--name", help="출력 폴더 이름 (bipv_experiments/runs/<name>)")
    parser.add_argument("--batch", type=Path, help='JSON 목록: [{"name": ..., "schedule": ...}, ...]')
    parser.add_argument("--idf", type=Path, default=IDF_PATH, help="실행할 IDF (기본 idf/case3_v3_south_fixed.idf)")
    parser.add_argument("--jobs", type=int, default=4, help="병렬 실행 수")
    parser.add_argument("--days", type=int, default=None, help="시작일부터 N일만 실행")
    parser.add_argument("--start", default=None, help="시작일 MM-DD (기본 01-01)")
    parser.add_argument("--diag", action="store_true", help="창 일사 차폐 진단 출력 추가")
    parser.add_argument("--sky-diffuse", default=None,
                        help="Sky Diffuse Modeling 알고리즘 덮어쓰기 (예: DetailedSkyDiffuseModeling)")
    args = parser.parse_args()

    if args.batch:
        jobs = json.loads(args.batch.read_text(encoding="utf-8"))
    elif args.schedule and args.name:
        jobs = [{"name": args.name, "schedule": str(args.schedule)}]
    else:
        parser.error("--schedule/--name 또는 --batch 필요")

    def parse_start(v):
        return date(2006, *map(int, v.split("-"))) if v else None

    failed = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {
            ex.submit(
                run_one,
                Path(j["schedule"]) if j.get("schedule") else None,
                j["name"],
                j.get("days", args.days),
                parse_start(j.get("start", args.start)),
                args.diag,
                j.get("sky_diffuse", args.sky_diffuse),
                Path(j.get("idf", args.idf)),
                j.get("shadow_timestep", False),
                j.get("solar_distribution"),
                Path(j["ideal_sizing_from"]) if j.get("ideal_sizing_from") else None,
                j.get("pv_simple", False),
            ): j["name"]
            for j in jobs
        }
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                failed.append(futures[fut])
                print(f"[FAIL ] {futures[fut]}: {e}", flush=True)

    if failed:
        sys.exit(f"실패한 run: {failed}")


if __name__ == "__main__":
    main()

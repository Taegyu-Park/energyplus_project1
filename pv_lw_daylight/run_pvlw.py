"""
pv_lw_daylight/run_pvlw.py
===========================================
PV 장파복사 연동 + 남측 주광 연동 조명 제어를 case2(고정각)·case3(각도 제어) IDF에 적용해 실행한다.
(plan_pv_facade_longwave_coupling.md 구현, 기존 파일은 수정하지 않음)

- IDF 설정 변경(그림자 갱신, 하늘 확산, 일사 분배, 용량 고정, RunPeriod)은 bipv_experiments/runner.prepare_idf 를 재사용
- 그 위에 patch_idf() 로 다음을 추가
  * lw:       남측 창·외벽 4면에 SurfaceProperty:SurroundingSurfaces/LocalEnvironment + 온도 스케줄,
              PythonPlugin(case2: pv_lw_plugin.PVLongwaveFixedPlugin, case3: bipv_schedule_lw_plugin)
  * daylight: BIPV_office_{1,2}_S 에 Daylighting:ReferencePoint/Controls (SplitFlux, 설정조도 lx)
  * 검증용 출력 변수
- 결과: pv_lw_daylight/runs/<group>/<name>/ (group: tests | daylight_table | annual, summary.json 포함)

배치 JSON job 필드:
  name, group("tests"|"daylight_table"|"annual"), case("case2"|"case3"), idf, schedule(case3), angle(case2),
  lw(bool), daylight_lx(숫자|null, case2 기본 주광 계산), lighting_control("Continuous"|"ContinuousOff"),
  daylight_table(case3: build_daylight_table.py 로 만든 각도별 조명 전력 배율 CSV), daylight_native_ok(case3 검증용),
  lw_test_temp(고정 온도 C, 검증용), lw_vf_zero(bool, 뷰팩터 0 검증용),
  pv_simple(bool, PV 결과가 필요 없는 주광 표 실행용), pv_bandgap(예: 1.25), economizer(예: "DifferentialEnthalpy"), weather(EPW 경로), start("MM-DD"), days, sky_diffuse, shadow_timestep, solar_distribution, ideal_sizing_from, subs([[정규식, 치환]]), extra_outputs([변수명], 진단용),
  out_dir(결과 폴더, 루트 기준 상대경로 — 지정 시 runs/<group>/<name> 대신 사용),
  mismatch_outputs(bool, case2: bipv_mismatch/run_case2_sim.py 의 데이터셋용 출력 변수 추가)

사용: python pv_lw_daylight/run_pvlw.py --batch <json> --jobs 10
"""

import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CWD = HERE.parent
EXP_DIR = CWD / "bipv_experiments"  # runner.py, bipv_schedule_plugin.py, case3 IDF
sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(HERE))
import runner  # noqa: E402  (bipv_experiments/runner.py)
from compute_view_factors import parse_polygons  # noqa: E402

RUNS_ROOT = HERE / "runs"  # tests/ daylight_table/ annual/
VF_CSV = HERE / "view_factors.csv"
ALL_ANGLES = list(range(0, 100, 10))
S_ZONES = ["BIPV_office_1_S", "BIPV_office_2_S"]
LW_SURFACES = [f"{z}..Wall_S_Glz0" for z in S_ZONES] + [f"{z}..Wall_S" for z in S_ZONES]
# 기준점: 존 중앙(x=16), 깊이 중간(y=2.5), 작업면 85 cm (KS A 3011)
REF_POINTS = {"BIPV_office_1_S": (16.0, 2.5, 0.85), "BIPV_office_2_S": (16.0, 2.5, 4.85)}


# ---------------------------------------------------------------- IDF 패치
def generator_rows(text: str) -> dict:
    """{angle: {row: [발전기 이름]}} — 단은 이름이 아니라 차양 기하(경첩 높이)로 판별 (case2 이름의 첫 숫자는 단이 아님)"""
    polys = parse_polygons(text)
    out = {}
    for m in re.finditer(r"(?m)^Generator:Photovoltaic,\s*\n\s*([^,]+),[^\n]*\n\s*([^,]+),", text):
        gen, surf = m.group(1).strip(), m.group(2).strip()
        a = int(re.fullmatch(r"Shade_\d_(\d+)_\d+", surf).group(1))
        ztop = polys[surf][:, 2].max()
        row = int(round((8.0 - ztop) / (4.0 / 3.0))) + 1
        if not 1 <= row <= 6:
            raise RuntimeError(f"단 판별 실패: {gen} z={ztop}")
        out.setdefault(a, {}).setdefault(row, []).append(gen)
    for a, rows in out.items():
        if sorted(rows) != list(range(1, 7)) or any(len(v) != 16 for v in rows.values()):
            raise RuntimeError(f"A{a}: 단별 발전기 수 이상 { {r: len(v) for r, v in rows.items()} }")
    return out


def lw_config(angles: list, fixed_angle, gen_rows: dict, test_temp=None, vf_zero=False) -> dict:
    vf = pd.read_csv(VF_CSV)
    surfaces = []
    for i, s in enumerate(LW_SURFACES):
        d = vf[vf.surface == s]
        per_angle = {str(a): [float(d[(d.angle == a) & (d.row == r)].vf.iloc[0]) for r in range(1, 7)] for a in angles}
        if vf_zero:
            per_angle = {a: [0.0] * 6 for a in per_angle}
        fmax = max(sum(v) for v in per_angle.values())
        surfaces.append({"name": s, "schedule": f"PVLW_Teff_{i + 1}", "fmax": fmax, "vf": per_angle})
    cell_keys = {str(a): {str(r): gen_rows[a][r] for r in range(1, 7)} for a in angles}
    return {"angles": angles, "fixed_angle": fixed_angle, "rows": 6, "cell_keys": cell_keys,
            "beta_sky": 0.5 ** 0.5, "test_fixed_temp": test_temp, "surfaces": surfaces}


def detect_angles(text: str) -> list:
    return sorted({int(a) for a in re.findall(r"(?m)^\s*PV_\d_(\d+)_\d\d,\s*!- Name", text)})


def patch_idf(text: str, case: str, cfg: dict | None, daylight_lx, lighting_control: str, extra_outputs=None) -> str:
    add = ["\n! ===== pv_lw_daylight (run_pvlw.py) =====\n"]

    if cfg is not None and cfg.get("surfaces"):
        for s in cfg["surfaces"]:
            fmax = round(s["fmax"], 6)
            sched = s["schedule"]
            # F_max 가 0 이면(검증용) 주변 표면 뷰팩터 0 → 기본(하늘 0.5, 지면 0.5)과 동일해야 함
            # 합이 1을 넘지 않도록 하늘·지면은 1e-6 단위로 내림
            sky = gnd = math.floor((1.0 - fmax) / 2.0 * 1e6) / 1e6
            add.append(f"Schedule:Constant,{sched},,20;\n")
            add.append(f"SurfaceProperty:SurroundingSurfaces,PVLW_SS_{sched},{sky:.6f},,{gnd:.6f},,PV_Louvers,{fmax:.6f},{sched};\n")
            add.append(f"SurfaceProperty:LocalEnvironment,PVLW_LE_{sched},{s['name']},,PVLW_SS_{sched},,;\n")
        # 플러그인용 센서 요청 (RunPeriod 빈도: 핸들만 필요)
        add.append("Output:Variable,*,Generator PV Cell Temperature,RunPeriod;\n")
        add.append("Output:Variable,Environment,Site Sky Temperature,Timestep;\n")
        add.append("Output:Variable,Environment,Site Outdoor Air Drybulb Temperature,Timestep;\n")
        for s in cfg["surfaces"]:
            add.append(f"Output:Variable,{s['schedule']},Schedule Value,Timestep;\n")
        for a in cfg["angles"]:
            for r in range(1, 7):
                add.append(f"Output:Variable,{cfg['cell_keys'][str(a)][str(r)][0]},Generator PV Cell Temperature,Timestep;\n")

    if cfg is not None and cfg.get("daylight_table"):
        if case != "case3":
            raise RuntimeError("주광 배율 표는 case3 전용")
        add.append(f"Output:Variable,{cfg['daylight_table']['schedule']},Schedule Value,RunPeriod;\n")

    if cfg is not None:
        search = f"PythonPlugin:SearchPaths,PVLW_SearchPaths,Yes,Yes,No,{HERE},{EXP_DIR};\n"
        if case == "case3":
            text, n = re.subn(r"(?ms)^PythonPlugin:SearchPaths,.*?;", lambda m: search.strip(), text)
            if n != 1:
                raise RuntimeError(f"SearchPaths 치환 실패 ({n})")
            text, n = re.subn(r"(PythonPlugin:Instance,\s*\n\s*KineticBIPVPlugin,[^\n]*\n[^\n]*\n\s*)[^,\n]+(,\s*!- Module Name)",
                              r"\g<1>bipv_schedule_lw_plugin\g<2>", text)
            if n != 1:
                raise RuntimeError(f"플러그인 모듈 치환 실패 ({n})")
        elif cfg.get("surfaces"):
            if "PythonPlugin:" in text:
                raise RuntimeError("case2 IDF에 이미 PythonPlugin 이 있음")
            add.append(search)
            add.append("PythonPlugin:Instance,PVLongwavePlugin,Yes,pv_lw_plugin,PVLongwaveFixedPlugin;\n")

    if daylight_lx is not None:
        for z in S_ZONES:
            x, y, zz = REF_POINTS[z]
            add.append(f"Daylighting:ReferencePoint,DRP_{z},{z},{x},{y},{zz};\n")
            add.append(f"Daylighting:Controls,DLC_{z},{z},SplitFlux,,{lighting_control},0.3,0.2,,1.0,,,22,,"
                       f"DRP_{z},1.0,{daylight_lx};\n")
        add.append("Output:Variable,*,Daylighting Reference Point 1 Illuminance,Timestep;\n")
        add.append("Output:Variable,*,Daylighting Lighting Power Multiplier,Timestep;\n")

    # 공통 검증 출력 (남측 4면)
    for s in LW_SURFACES:
        for v in ("Surface Outside Face Temperature", "Surface Inside Face Temperature",
                  "Surface Outside Face Net Thermal Radiation Heat Gain Rate"):
            add.append(f"Output:Variable,{s},{v},Timestep;\n")
    add.append("Output:Variable,*,Zone Lights Electricity Energy,Timestep;\n")
    for v in extra_outputs or []:  # 진단용 추가 출력 (key *, Timestep)
        add.append(f"Output:Variable,*,{v},Timestep;\n")
    return text + "".join(add)


# ---------------------------------------------------------------- 실행/요약
def summarize(out_dir: Path) -> dict:
    conn = sqlite3.connect(out_dir / "eplusout.sql")

    freq_order = ["Zone Timestep", "HVAC System Timestep", "Hourly", "Daily", "Monthly", "Run Period", "Annual"]

    def kwh(name, key=None):
        """같은 변수가 여러 빈도로 있으면 가장 짧은 빈도 하나만 합산"""
        cond, args = "d.Name = ?", [name]
        if key:
            cond += " AND upper(d.KeyValue) = upper(?)"
            args.append(key)
        freqs = {r[0] for r in conn.execute(f"SELECT DISTINCT ReportingFrequency FROM ReportDataDictionary d WHERE {cond}", args)}
        if not freqs:
            return float("nan")
        freq = min(freqs, key=lambda f: freq_order.index(f) if f in freq_order else 99)
        v = conn.execute(
            f"""SELECT SUM(rd.Value) FROM ReportData rd
                JOIN ReportDataDictionary d ON rd.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
                JOIN Time t ON rd.TimeIndex = t.TimeIndex
                WHERE {cond} AND d.ReportingFrequency = ? AND (t.WarmupFlag = 0 OR t.WarmupFlag IS NULL)""",
            args + [freq]).fetchone()[0]
        return (v or 0.0) / 3.6e6

    cool = kwh("Zone Ideal Loads Supply Air Total Cooling Energy")
    heat = kwh("Zone Ideal Loads Supply Air Total Heating Energy")
    pv = kwh("Facility Total Produced Electricity Energy")
    lights = kwh("Zone Lights Electricity Energy")
    lights_s = sum(kwh("Zone Lights Electricity Energy", z) for z in S_ZONES)
    conn.close()
    hvac = cool / runner.COP_COOLING + heat / runner.COP_HEATING
    return {"cooling_thermal_kwh": cool, "heating_thermal_kwh": heat, "hvac_electric_kwh": hvac,
            "pv_kwh": pv, "lights_kwh": lights, "lights_south_kwh": lights_s,
            "net_hvac_minus_pv_kwh": hvac - pv, "net_hvac_lights_minus_pv_kwh": hvac + lights - pv}


def run_job(j: dict) -> dict:
    name, case = j["name"], j["case"]
    out_dir = (CWD / j["out_dir"]) if j.get("out_dir") else RUNS_ROOT / j.get("group", "tests") / name
    out_dir.mkdir(parents=True, exist_ok=True)
    idf_path = (CWD / j["idf"]).resolve()
    start = date(2006, *map(int, j["start"].split("-"))) if j.get("start") else None
    idf_copy = runner.prepare_idf(
        out_dir, j.get("days"), start, False, j.get("sky_diffuse"), idf_path, j.get("shadow_timestep", False),
        j.get("solar_distribution"), (CWD / j["ideal_sizing_from"]) if j.get("ideal_sizing_from") else None,
        j.get("pv_simple", False))
    text = idf_copy.read_text(encoding="utf-8")
    if j.get("pv_bandgap"):  # One-Diode Eg 보정 (bipv_mismatch/run_case2_sim.py 와 동일, 1.25 → Rs 양수)
        text, n = re.subn(r"\b1\.12(,\s*!- Semiconductor Bandgap)", rf"{j['pv_bandgap']}\g<1>", text)
        if n != 1:
            raise RuntimeError(f"{name}: Semiconductor Bandgap 치환 실패 ({n})")
    if j.get("economizer"):  # Ideal Loads 외기 냉방 방식 (원본 DifferentialDryBulb 는 습한 여름 고착 → DifferentialEnthalpy)
        text, n = re.subn(r"\bDifferentialDryBulb(,\s*!-+ Outdoor Air Economizer Type)", rf"{j['economizer']}\g<1>", text)
        if n != 10:
            raise RuntimeError(f"{name}: Economizer Type 치환 수 {n} != 10")
    for pat, rep in j.get("subs", []):
        text, n = re.subn(pat, rep, text)
        if n == 0:
            raise RuntimeError(f"{name}: subs 치환 없음: {pat}")

    angles = detect_angles(text)
    fixed = j.get("angle") if case == "case2" else None
    if case == "case2" and angles != [fixed]:
        raise RuntimeError(f"{name}: case2 각도 불일치 IDF={angles} job={fixed}")
    if case == "case3" and j.get("daylight_lx") is not None and not j.get("daylight_native_ok"):
        raise RuntimeError(f"{name}: case3 기본 주광 계산은 너무 느림 → daylight_table 사용")
    cfg = None
    if j.get("lw", True):
        cfg = lw_config(angles, fixed, generator_rows(text), j.get("lw_test_temp"), j.get("lw_vf_zero", False))
    if j.get("daylight_table"):
        cfg = cfg or {"angles": angles}
        cfg["daylight_table"] = {"table": str((CWD / j["daylight_table"]).resolve()), "zones": S_ZONES,
                                 "lights": [f"{z}_Space SmallOffice Building_Lighting" for z in S_ZONES],
                                 "schedule": "SmallOffice Building_Lighting Schedule"}
        if not Path(cfg["daylight_table"]["table"]).exists():
            raise FileNotFoundError(cfg["daylight_table"]["table"])
    if cfg is not None:
        (out_dir / "pvlw_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    text = patch_idf(text, case, cfg, j.get("daylight_lx"), j.get("lighting_control", "Continuous"), j.get("extra_outputs"))
    if j.get("mismatch_outputs"):  # TiDE 데이터셋(build_dataset.py)용 출력 — run_case2_sim.py 와 같은 목록
        if case != "case2":
            raise RuntimeError(f"{name}: mismatch_outputs 는 case2 전용")
        sys.path.insert(0, str(CWD / "bipv_mismatch"))
        from run_case2_sim import extra_outputs as mismatch_extra_outputs
        text += mismatch_extra_outputs(text, fixed)
    idf_copy.write_text(text, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(runner.EP_DIR / "api" / "python"), str(HERE), str(EXP_DIR),
                                         env.get("PYTHONPATH", "")])
    if cfg is not None:
        env["PVLW_CONFIG"] = str(out_dir / "pvlw_config.json")
    if j.get("schedule"):
        sched = (CWD / j["schedule"]).resolve()
        if not sched.exists():
            raise FileNotFoundError(sched)
        env["BIPV_SCHEDULE_CSV"] = str(sched)

    epw = (CWD / j["weather"]).resolve() if j.get("weather") else runner.WEATHER_PATH
    cmd = [str(runner.EP_DIR / "energyplus.exe"), "-w", str(epw), "-d", str(out_dir), str(idf_copy)]
    print(f"[start] {name}", flush=True)
    with open(out_dir / "run_stdout.log", "w", encoding="utf-8", errors="ignore") as log:
        rc = subprocess.run(cmd, env=env, cwd=str(EXP_DIR), stdout=log, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        raise RuntimeError(f"{name}: EnergyPlus exit code {rc} (see {out_dir / 'run_stdout.log'})")
    summary = summarize(out_dir)
    summary.update({"name": name, "job": j})
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done ] {name}  HVAC={summary['hvac_electric_kwh']:.0f}  lights={summary['lights_kwh']:.0f}  "
          f"PV={summary['pv_kwh']:.0f} kWh", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--only", nargs="*", help="이 이름의 job만 실행")
    args = ap.parse_args()
    jobs = json.loads(args.batch.read_text(encoding="utf-8"))
    if args.only:
        jobs = [j for j in jobs if j["name"] in args.only]
    failed = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run_job, j): j["name"] for j in jobs}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                failed.append(futs[f])
                print(f"[FAIL ] {futs[f]}: {e}", flush=True)
    if failed:
        sys.exit(f"실패: {failed}")


if __name__ == "__main__":
    main()

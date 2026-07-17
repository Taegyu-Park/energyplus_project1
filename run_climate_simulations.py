import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# -------------------------------------------------------------
# 설정 및 경로 정의
# -------------------------------------------------------------
CWD = Path(r"c:\Users\taegyu\Codes\energyplus_project1")
IDF_PATH = CWD / "case_idf" / "case3_v3.idf"
PLUGIN_PATH = CWD / "model_pythonpluginsystem.py"
OUT_ROOT_DIR = CWD / "case_analysis"

# 백업 경로
IDF_BACKUP = CWD / "case_idf" / "case3_v3.idf.bak"
PLUGIN_BACKUP = CWD / "model_pythonpluginsystem.py.bak"

# 기후별 날씨 및 DDY 정의
CLIMATES = {
    "Phoenix": {
        "epw": CWD / "data" / "USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780_TMY3.epw",
        "ddy": CWD / "data" / "USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780_TMY3.ddy"
    },
    "Helsinki": {
        "epw": CWD / "data" / "FIN_Helsinki.029740_IWEC.epw",
        "ddy": CWD / "data" / "FIN_Helsinki.029740_IWEC.ddy"
    }
}

# 색상별 성능 사양 정의
COLOR_SPECS = {
    "white": {
        "rated_power": 250.0,
        "isc": 6.91,
        "voc": 45.90,
        "impp": 6.33,
        "vmpp": 39.50,
        "temp_isc": 0.004146,
        "temp_voc": -0.137700
    },
    "light_gray_beige": {
        "rated_power": 350.0,
        "isc": 9.37,
        "voc": 46.48,
        "impp": 9.01,
        "vmpp": 39.12,
        "temp_isc": 0.005622,
        "temp_voc": -0.139440
    },
    "terracotta": {
        "rated_power": 390.0,
        "isc": 10.42,
        "voc": 46.64,
        "impp": 9.99,
        "vmpp": 39.11,
        "temp_isc": 0.006252,
        "temp_voc": -0.139920
    }
}

def get_energyplus_dir():
    """Environment 또는 표준 경로에서 EnergyPlus 설치 디렉토리 탐색"""
    env_path = CWD / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ENERGYPLUS_DIR="):
                    path = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if os.path.exists(path):
                        return Path(path)

    ep_bin = shutil.which("energyplus")
    if ep_bin:
        return Path(ep_bin).parent

    default_path = Path(r"C:\EnergyPlusV25-2-0")
    if default_path.exists():
        return default_path

    print("ERROR: EnergyPlus V25-2-0 설치 디렉토리를 찾을 수 없습니다.")
    sys.exit(1)

def backup_files():
    """시뮬레이션 전 원본 파일 백업"""
    print("\n[1] 원본 파일 백업 생성 중...")
    if IDF_PATH.exists():
        shutil.copy2(IDF_PATH, IDF_BACKUP)
        print(f"  IDF 백업 완료: {IDF_BACKUP.name}")
    else:
        print(f"ERROR: 원본 IDF 파일을 찾을 수 없습니다: {IDF_PATH}")
        sys.exit(1)

    if PLUGIN_PATH.exists():
        shutil.copy2(PLUGIN_PATH, PLUGIN_BACKUP)
        print(f"  Plugin 백업 완료: {PLUGIN_BACKUP.name}")
    else:
        print(f"ERROR: 원본 Plugin 파일을 찾을 수 없습니다: {PLUGIN_PATH}")
        sys.exit(1)

def restore_files():
    """백업 파일로부터 원본 복원 및 백업 파일 삭제"""
    print("\n[원상 복구] 원본 파일 복원 중...")
    if IDF_BACKUP.exists():
        shutil.copy2(IDF_BACKUP, IDF_PATH)
        os.remove(IDF_BACKUP)
        print("  IDF 파일 원상 복구 완료.")
    if PLUGIN_BACKUP.exists():
        shutil.copy2(PLUGIN_BACKUP, PLUGIN_PATH)
        os.remove(PLUGIN_BACKUP)
        print("  Plugin 파일 원상 복구 완료.")

def remove_objects_by_type(idf_content, object_type):
    """IDF 내용에서 특정 타입의 객체들을 주석의 세미콜론 영향 없이 안전하게 제거"""
    lines = idf_content.splitlines()
    out_lines = []
    in_object = False
    
    for line in lines:
        # 주석을 제외한 코어 로직 한 줄 검토
        clean_line = re.sub(r'![^\r\n]*', '', line).strip()
        
        if not in_object:
            if clean_line.lower().startswith(object_type.lower() + ",") or clean_line.lower() == object_type.lower():
                in_object = True
                if clean_line.endswith(";"):
                    in_object = False
                continue
            out_lines.append(line)
        else:
            if clean_line.endswith(";"):
                in_object = False
            continue
            
    return "\n".join(out_lines)

def parse_ddy_file(ddy_path):
    """DDY 파일에서 Site:Location 및 모든 SizingPeriod:DesignDay 객체 추출 (주석 제거 적용)"""
    with open(ddy_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # 주석 제거하여 주석 내 세미콜론(;)에 꼬이지 않도록 처리
    clean_content = re.sub(r'![^\r\n]*', '', content)
    
    # Site:Location 추출
    site_location_match = re.search(r'(?i)Site:Location,.*?;', clean_content, re.DOTALL)
    site_location = site_location_match.group(0) if site_location_match else ""
    
    # SizingPeriod:DesignDay 리스트 추출
    designdays = re.findall(r'(?i)SizingPeriod:DesignDay,.*?;', clean_content, re.DOTALL)
    
    return site_location, designdays

def update_idf_climate_and_performance(spec, site_location, designdays):
    """IDF 파일에서 기존 기동 기후/설계일 객체들을 지우고 신규 DDY 정보와 BIPV 스펙을 이식"""
    with open(IDF_PATH, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. 기존 Site:Location 및 SizingPeriod:DesignDay 안전하게 제거
    content = remove_objects_by_type(content, "Site:Location")
    content = remove_objects_by_type(content, "SizingPeriod:DesignDay")

    # 2. 신규 설계일 객체들 및 위/경도 정보 추가 (파일 끝에 붙임)
    new_blocks = "\n\n" + site_location + "\n\n" + "\n\n".join(designdays)
    content += new_blocks

    # 3. PhotovoltaicPerformance:EquivalentOne-Diode 객체 대체
    new_perf_block = f"""PhotovoltaicPerformance:EquivalentOne-Diode,
    Shinsung_SolarSkin_250W_Performance,  !- Name
    CrystallineSilicon,           !- Cell type
    66,                           !- Number of Cells in Series
    2.186184,                     !- Active Area {{m2}}
    0.85,                         !- Transmittance Absorptance Product
    1.12,                         !- Semiconductor Bandgap {{eV}}
    500.0,                        !- Shunt Resistance {{ohms}}
    {spec['isc']:.2f},                         !- Short Circuit Current {{A}}
    {spec['voc']:.2f},                        !- Open Circuit Voltage {{V}}
    25,                           !- Reference Temperature {{C}}
    1000,                         !- Reference Insolation {{W/m2}}
    {spec['impp']:.2f},                         !- Module Current at Maximum Power {{A}}
    {spec['vmpp']:.2f},                        !- Module Voltage at Maximum Power {{V}}
    {spec['temp_isc']:.6f},                     !- Temperature Coefficient of Short Circuit Current {{A/K}}
    {spec['temp_voc']:.6f},                    !- Temperature Coefficient of Open Circuit Voltage {{V/K}}
    20,                           !- Nominal Operating Cell Temperature Test Ambient Temperature {{C}}
    45.0,                         !- Nominal Operating Cell Temperature Test Cell Temperature {{C}}
    800,                          !- Nominal Operating Cell Temperature Test Insolation {{W/m2}}
    80.0,                         !- Module Heat Loss Coefficient {{W/m2-K}}
    50000;                        !- Series Modules"""

    pattern = r"(?i)PhotovoltaicPerformance:EquivalentOne-Diode,\s*Shinsung_SolarSkin_250W_Performance,\s*.*?\s*50000;"
    content, count = re.subn(pattern, new_perf_block, content, flags=re.DOTALL)
    
    if count == 0:
        print("WARNING: IDF 내에서 PhotovoltaicPerformance 객체를 치환하지 못했습니다.")
        sys.exit(1)

    with open(IDF_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("  IDF 기후 환경 및 BIPV 성능 업데이트 완료.")

def update_plugin_rated_power(rated_power):
    """Plugin 파일의 PV_RATED_POWER 파라미터를 동적으로 변경"""
    with open(PLUGIN_PATH, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    pattern = r"(PV_RATED_POWER\s*=\s*)[\d\.]+"
    modified_content, count = re.subn(pattern, f"\\g<1>{rated_power}", content)

    if count == 0:
        print("WARNING: Plugin 내에서 PV_RATED_POWER 변수를 치환하지 못했습니다.")
        sys.exit(1)

    with open(PLUGIN_PATH, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"  Python Plugin 파라미터 적용 완료 (PV_RATED_POWER = {rated_power})")

def run_simulation(climate_name, color, ep_dir, epw_path):
    """EnergyPlus 시뮬레이션 프로세스 구동 및 결과 정리"""
    # 임시 출력 디렉토리
    out_dir = OUT_ROOT_DIR / f"temp_{climate_name}_{color}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ep_exe = ep_dir / "energyplus.exe"
    
    env = os.environ.copy()
    ep_python_api_path = str(ep_dir / "api" / "python")
    env["PYTHONPATH"] = ep_python_api_path + os.pathsep + env.get("PYTHONPATH", "")

    print(f"\n[{climate_name.upper()} - {color.upper()}] 시뮬레이션 구동 중...")
    
    cmd = [
        str(ep_exe),
        "-w", str(epw_path),
        "-d", str(out_dir),
        str(IDF_PATH)
    ]

    try:
        subprocess.run(cmd, env=env, check=True, text=True, capture_output=True)
        print(f"  => [{climate_name.upper()} - {color.upper()}] 시뮬레이션 정상 완료!")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: [{climate_name.upper()} - {color.upper()}] 시뮬레이션 도중 에러가 발생했습니다.")
        print(f"  상세 에러 내용:\n{e.stderr}")
        raise e

    # eplusout.csv 파일 생성 여부 확인 및 ReadVarsESO를 통한 수동 변환
    csv_file = out_dir / "eplusout.csv"
    if not csv_file.exists():
        readvars_exe = ep_dir / "PostProcess" / "ReadVarsESO.exe"
        if readvars_exe.exists():
            try:
                subprocess.run([str(readvars_exe)], cwd=str(out_dir), check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                print(f"  WARNING: ReadVarsESO 변환 실패: {e}")

    # 최종 저장 경로 (bipv_variation/5zone/기후명/)
    final_dest_dir = OUT_ROOT_DIR / "bipv_variation" / "5zone" / climate_name
    final_dest_dir.mkdir(parents=True, exist_ok=True)
    
    success = False
    
    # CSV 저장
    if csv_file.exists():
        dest_csv = final_dest_dir / f"case3_{color}.csv"
        try:
            shutil.copy2(csv_file, dest_csv)
            print(f"  => CSV 저장 완료: {dest_csv.name}")
            success = True
        except Exception as e:
            print(f"  WARNING: CSV 복사 실패: {e}")
            
    # SQL 저장 (이후 SQL 쿼리 분석용)
    sql_file = out_dir / "eplusout.sql"
    if sql_file.exists():
        dest_sql = final_dest_dir / f"case3_{color}.sql"
        try:
            shutil.copy2(sql_file, dest_sql)
            print(f"  => SQL 저장 완료: {dest_sql.name}")
        except Exception as e:
            print(f"  WARNING: SQL 복사 실패: {e}")

    # 에러 및 HTML 테이블 결과도 복사해 두면 진단 및 디버깅에 매우 용이함
    for ext, name in [(".err", "error.err"), (".htm", "summary.htm")]:
        temp_f = out_dir / f"eplusout{ext}" if ext == ".err" else out_dir / f"case3_v3tbl{ext}"
        if not temp_f.exists():
            # Alternative search
            for f in out_dir.glob(f"*{ext}"):
                temp_f = f
                break
        if temp_f.exists():
            shutil.copy2(temp_f, final_dest_dir / f"case3_{color}{ext}")

    # 임시 결과 폴더 전체 삭제
    if success:
        shutil.rmtree(out_dir, ignore_errors=True)
        print(f"  => 임시 폴더 삭제 완료: {out_dir.name}")

def main():
    ep_dir = get_energyplus_dir()
    print(f"EnergyPlus 디렉토리: {ep_dir}")

    # 1. 원본 백업
    backup_files()

    try:
        for climate_name, paths in CLIMATES.items():
            print(f"\n" + "#"*60)
            print(f" {climate_name.upper()} 기후 지역 시뮬레이션 시작")
            print("#"*60)
            
            # DDY 파일 파싱
            site_location, designdays = parse_ddy_file(paths["ddy"])
            print(f"  DDY 파싱 완료 ({len(designdays)}개 DesignDay 검출)")

            for color, spec in COLOR_SPECS.items():
                print(f"\n" + "-"*40)
                print(f"  {climate_name} - {color.upper()} 케이스 가동 준비")
                print("-"*40)
                
                # IDF 원상복구 후 새로운 조건 덮어쓰기
                shutil.copy2(IDF_BACKUP, IDF_PATH)
                update_idf_climate_and_performance(spec, site_location, designdays)
                
                # Plugin 원상복구 후 새로운 PV 용량 설정
                shutil.copy2(PLUGIN_BACKUP, PLUGIN_PATH)
                update_plugin_rated_power(spec["rated_power"])
                
                # 시뮬레이션 실행
                run_simulation(climate_name, color, ep_dir, paths["epw"])
                
    except Exception as e:
        print(f"\n시뮬레이션 구동 중 예외 발생: {e}")
    finally:
        # 무조건 복원
        restore_files()
        print("\n[완료] 시뮬레이션 스케줄 종료 및 원본 복구 완료.")

if __name__ == "__main__":
    main()

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
WEATHER_PATH = CWD / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
OUT_ROOT_DIR = CWD / "case_analysis"

# 백업 경로
IDF_BACKUP = CWD / "case_idf" / "case3_v3.idf.bak"
PLUGIN_BACKUP = CWD / "model_pythonpluginsystem.py.bak"

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
    # 1. .env 파일 파싱 시도
    env_path = CWD / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ENERGYPLUS_DIR="):
                    path = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if os.path.exists(path):
                        return Path(path)

    # 2. 시스템 PATH 환경변수 탐색
    ep_bin = shutil.which("energyplus")
    if ep_bin:
        return Path(ep_bin).parent

    # 3. 디폴트 윈도우 설치 경로 확인
    default_path = Path(r"C:\EnergyPlusV25-2-0")
    if default_path.exists():
        return default_path

    print("ERROR: EnergyPlus V25-2-0 설치 디렉토리를 찾을 수 없습니다.")
    print("원인: .env 파일에 ENERGYPLUS_DIR=경로 를 추가해 주거나, 시스템 PATH 환경변수에 등록해 주세요.")
    sys.exit(1)

def backup_files():
    """시뮬레이션 전 원본 파일 백업"""
    print("\n[1/4] 원본 파일 백업 생성 중...")
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

def update_idf_performance(spec):
    """IDF 파일의 BIPV 성능 모델 파라미터를 동적으로 변경"""
    with open(IDF_PATH, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # PhotovoltaicPerformance:EquivalentOne-Diode 객체 대체용 템플릿
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

    # 기존 PhotovoltaicPerformance:EquivalentOne-Diode 객체를 정규표현식으로 찾아 치환
    pattern = r"(?i)PhotovoltaicPerformance:EquivalentOne-Diode,\s*Shinsung_SolarSkin_250W_Performance,\s*.*?\s*50000;"
    
    modified_content, count = re.subn(pattern, new_perf_block, content, flags=re.DOTALL)
    
    if count == 0:
        print("WARNING: IDF 내에서 PhotovoltaicPerformance 객체를 치환하지 못했습니다. 형식을 다시 확인하십시오.")
        sys.exit(1)

    with open(IDF_PATH, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"  IDF 파라미터 적용 완료 (Isc={spec['isc']}A, Voc={spec['voc']}V, Power={spec['rated_power']}W)")

def update_plugin_rated_power(rated_power):
    """Plugin 파일의 PV_RATED_POWER 파라미터를 동적으로 변경"""
    with open(PLUGIN_PATH, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # PV_RATED_POWER = XXX.X 형식 변경
    pattern = r"(PV_RATED_POWER\s*=\s*)[\d\.]+"
    modified_content, count = re.subn(pattern, f"\\g<1>{rated_power}", content)

    if count == 0:
        print("WARNING: Plugin 내에서 PV_RATED_POWER 변수를 치환하지 못했습니다.")
        sys.exit(1)

    with open(PLUGIN_PATH, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"  Python Plugin 파라미터 적용 완료 (PV_RATED_POWER = {rated_power})")

def run_simulation(color, ep_dir):
    """EnergyPlus 시뮬레이션 프로세스 구동 및 결과 정리"""
    out_dir = OUT_ROOT_DIR / f"case3_{color}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ep_exe = ep_dir / "energyplus.exe"
    
    # EnergyPlus Python API를 찾을 수 있도록 PYTHONPATH 환경 변수 구성
    env = os.environ.copy()
    ep_python_api_path = str(ep_dir / "api" / "python")
    env["PYTHONPATH"] = ep_python_api_path + os.pathsep + env.get("PYTHONPATH", "")

    print(f"\n[{color.upper()}] 시뮬레이션 프로세스 구동 중...")
    print(f"  출력 디렉토리: {out_dir}")

    cmd = [
        str(ep_exe),
        "-w", str(WEATHER_PATH),
        "-d", str(out_dir),
        str(IDF_PATH)
    ]

    # 시뮬레이션 프로세스 실행
    try:
        result = subprocess.run(cmd, env=env, check=True, text=True, capture_output=True)
        print(f"  => [{color.upper()}] 시뮬레이션 정상 완료!")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: [{color.upper()}] 시뮬레이션 도중 에러가 발생했습니다.")
        print(f"  상세 에러 내용:\n{e.stderr}")
        raise e

    # eplusout.csv 파일 생성 여부 확인 및 ReadVarsESO를 통한 수동 변환
    csv_file = out_dir / "eplusout.csv"
    if not csv_file.exists():
        print("  eplusout.csv 파일이 없습니다. ReadVarsESO를 통해 .eso에서 변환을 시도합니다...")
        readvars_exe = ep_dir / "PostProcess" / "ReadVarsESO.exe"
        if readvars_exe.exists():
            try:
                # ReadVarsESO.exe를 working directory(out_dir)에서 실행
                subprocess.run([str(readvars_exe)], cwd=str(out_dir), check=True, capture_output=True)
                print("  => ReadVarsESO 변환 완료!")
            except subprocess.CalledProcessError as e:
                print(f"  WARNING: ReadVarsESO 변환 실패: {e}")
        else:
            print("  WARNING: ReadVarsESO.exe를 찾을 수 없어 변환을 건너뜁니다.")

    # 변환된 csv 결과를 bipv_variation 폴더에 이름 붙여 저장
    success = False
    if csv_file.exists():
        bipv_var_dir = OUT_ROOT_DIR / "bipv_variation"
        bipv_var_dir.mkdir(parents=True, exist_ok=True)
        dest_csv = bipv_var_dir / f"case3_{color}.csv"
        try:
            shutil.copy2(csv_file, dest_csv)
            print(f"  => 결과 CSV를 다음 경로로 저장함: {dest_csv}")
            success = True
        except Exception as e:
            print(f"  WARNING: CSV 결과 이동 실패: {e}")
    else:
        print("  WARNING: 최종 eplusout.csv 파일이 생성되지 않아 bipv_variation 저장을 건너뜁니다.")

    # 변환된 csv 파일 이외의 모든 시뮬레이션 결과 파일 제거
    if success:
        print(f"  => 변환 완료에 따라 임시 결과 폴더 전체 삭제: {out_dir.name}")
        shutil.rmtree(out_dir, ignore_errors=True)
    else:
        # 에러 분석을 위해 임시 결과 폴더를 남겨두되, 불필요한 대용량 파일만 정리
        cleanup_simulation_folder(out_dir)

def cleanup_simulation_folder(folder_path):
    """시뮬레이션 결과 폴더 내 대용량 임시 파일 삭제"""
    keep_extensions = {".eso", ".err", ".htm", ".png", ".py", ".csv"} # csv는 보존 대상에 포함시킴
    print(f"  결과 폴더 정리 중... ({folder_path.name})")
    
    deleted_count = 0
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = Path(root) / filename
            ext = file_path.suffix.lower()
            
            if ext not in keep_extensions:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    pass
    print(f"  정리 완료 (불필요한 임시 파일 {deleted_count}개 삭제됨)")

def main():
    ep_dir = get_energyplus_dir()
    print(f"탐색된 EnergyPlus 경로: {ep_dir}")

    # 백업 진행
    backup_files()

    try:
        for color, spec in COLOR_SPECS.items():
            print(f"\n" + "="*50)
            print(f" {color.upper()} 케이스 설정 시작")
            print("="*50)
            
            # 1. 파일 수정
            update_idf_performance(spec)
            update_plugin_rated_power(spec["rated_power"])
            
            # 2. 실행
            run_simulation(color, ep_dir)
            
    except Exception as e:
        print(f"\n시뮬레이션 중 치명적인 오류 발생: {e}")
    finally:
        # 무조건 원본 복구
        restore_files()

if __name__ == "__main__":
    main()

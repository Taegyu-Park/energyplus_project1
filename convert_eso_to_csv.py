import subprocess
import sys
from pathlib import Path

def convert_eso():
    project_root = Path(__file__).parent.resolve()
    results_dir = project_root / "gl2_results"
    
    # 1. EnergyPlus 공식 ReadVarsESO.exe 포스트 프로세싱 유틸리티 탐색
    ep_version = "EnergyPlusV25-2-0"
    candidates = [
        Path(f"C:/{ep_version}/PostProcess/ReadVarsESO.exe"),
        Path(f"C:/{ep_version}/ReadVarsESO.exe"),
        Path("C:/EnergyPlusV23-1-0/PostProcess/ReadVarsESO.exe"),
    ]
    
    readvars_exe = None
    for candidate in candidates:
        if candidate.exists():
            readvars_exe = candidate
            break
            
    if not readvars_exe:
        print("[Error] ReadVarsESO.exe 변환 유틸리티를 찾을 수 없습니다.")
        print("EnergyPlus 설치 경로를 확인해 주세요.")
        sys.exit(1)
        
    print(f"[Info] 공식 ReadVarsESO 유틸리티 로드 성공: {readvars_exe}")
    print("-" * 60)
    
    # 2. gl2_0부터 gl2_90까지의 서브폴더 순회
    angles = [str(x) for x in range(0, 100, 10)]
    
    success_count = 0
    fail_count = 0
    
    for angle in angles:
        target_dir = results_dir / f"gl2_{angle}"
        eso_file = target_dir / "eplusout.eso"
        
        if not eso_file.exists():
            print(f"[Skip] .eso 파일이 존재하지 않습니다: gl2_results/gl2_{angle}/eplusout.eso")
            continue
            
        print(f"[Convert] '{target_dir.name}' 폴더 내 .eso -> .csv 변환 실행 중...")
        
        # ReadVarsESO.exe는 실행되는 작업 디렉토리(CWD)에 존재하는 eplusout.eso를
        # 자동으로 읽어 eplusout.csv로 출력하는 구조로 설계되어 있습니다.
        try:
            subprocess.run(
                [str(readvars_exe)],
                cwd=str(target_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # 최종 생성된 eplusout.csv 검증
            csv_file = target_dir / "eplusout.csv"
            if csv_file.exists():
                print(f"[Success] {target_dir.name}/eplusout.csv 변환 성공!")
                success_count += 1
            else:
                print(f"[Fail] {target_dir.name} 폴더에 eplusout.csv 파일이 생성되지 않았습니다.")
                fail_count += 1
                
        except subprocess.CalledProcessError as e:
            print(f"[Fail] ReadVarsESO 실행 실패: {e}")
            print(f"  - 상세 에러: {e.stderr}")
            fail_count += 1
            
        print("-" * 60)
        
    print(f"[Completed] .eso -> .csv 일괄 변환 작업이 종료되었습니다.")
    print(f"  - 성공: {success_count}건 / 실패: {fail_count}건")

if __name__ == "__main__":
    convert_eso()

import sys
from pathlib import Path

# 1. EnergyPlus 설치 경로 설정 (pyenergyplus 모듈 로드용)
EP_PATH = r"C:\EnergyPlusV25-2-0"
if EP_PATH not in sys.path:
    sys.path.insert(0, EP_PATH)

try:
    from pyenergyplus.api import EnergyPlusAPI
except ImportError:
    print(f"[Error] '{EP_PATH}' 경로에서 pyenergyplus 모듈을 불러올 수 없습니다.")
    print("EnergyPlus 설치 경로가 올바른지 확인해 주세요.")
    sys.exit(1)

def run_simulation():
    # 프로젝트 루트 폴더 (스크립트 위치 기준)
    project_root = Path(__file__).parent.resolve()
    
    # 기상 파일 경로 설정
    weather_path = project_root / "data" / "KOR_Kwangju.471560_IWEC (1).epw"
    if not weather_path.exists():
        print(f"[Error] EPW 기상 파일을 찾을 수 없습니다: {weather_path}")
        sys.exit(1)
        
    # 0도부터 90도까지 10도 간격 각도 리스트
    angles = ["0", "10", "20", "30", "40", "50", "60", "70", "80", "90"]
    
    # 2. EnergyPlus API 인스턴스 생성
    api = EnergyPlusAPI()
    
    print(f"[Start Batch] 총 {len(angles)}개의 각도별 IDF 일괄 시뮬레이션을 가동합니다.")
    print("-" * 60)
    
    success_count = 0
    fail_count = 0
    
    for angle in angles:
        # 입력 및 출력 파일 경로 설정
        idf_path = project_root / "gl2_sets" / f"gl2_{angle}.idf"
        output_dir = project_root / "gl2_results" / f"gl2_{angle}"
        
        # 경로 및 파일 존재 확인
        if not idf_path.exists():
            print(f"[Error] IDF 파일을 찾을 수 없습니다 (각도 {angle}도): {idf_path}")
            fail_count += 1
            continue
            
        # 출력 폴더 자동 생성
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 새로운 시뮬레이션 상태(State) 생성
        state = api.state_manager.new_state()
        
        # 4. 실행 인자 구성
        arguments = [
            "-d", str(output_dir),
            "-w", str(weather_path),
            str(idf_path)
        ]
        
        print(f"[Run] {angle}도 시뮬레이션 시작...")
        print(f"  - IDF 파일 : {idf_path.name}")
        print(f"  - 출력 폴더 : {output_dir.relative_to(project_root)}")
        
        # 5. 시뮬레이션 가동
        status = api.runtime.run_energyplus(state, arguments)
        
        if status == 0:
            print(f"[Success] {angle}도 시뮬레이션 완료!")
            success_count += 1
        else:
            print(f"[Fail] {angle}도 시뮬레이션 실패 (에러 코드: {status})")
            print(f"  - 상세 에러 로그: '{output_dir.relative_to(project_root)}/eplusout.err'")
            fail_count += 1
            
        # 6. 완료된 시뮬레이션 상태 소멸 (메모리 누수 방지)
        api.state_manager.delete_state(state)
        print("-" * 60)
        
    print(f"[Batch Completed] 배치 시뮬레이션 작업 종료.")
    print(f"  - 성공: {success_count}건 / 실패: {fail_count}건")

if __name__ == "__main__":
    run_simulation()

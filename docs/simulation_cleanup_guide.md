# EnergyPlus 시뮬레이션 결과 폴더 정리 가이드

EnergyPlus 시뮬레이션 실행 후 생성되는 수많은 대용량 결과 파일들 중, 분석에 필요한 핵심 데이터 파일만 보존하고 불필요한 파일을 안전하게 일괄 삭제하여 디스크 공간을 효율적으로 관리하기 위한 가이드입니다.

---

## 1. 파일 보존 및 삭제 기준

각 시뮬레이션 결과 폴더(`dg_xx_pv`, `final_pv` 등) 내에서 다음 규칙에 따라 파일 정리를 수행합니다.

### 🟢 보존 대상 파일 (Keep)
다음 확장자를 가진 파일들은 결과 분석 및 검증을 위해 **절대 삭제하지 않고 보존**합니다.
* **`.eso`**: 시뮬레이션 시간별/상세 출력 데이터 파일 (가장 중요)
* **`.err`**: 시뮬레이션 에러/워닝 로그 파일 (`eplusout.err`, `sqlite.err` 등)
* **`.htm`**: 테이블 형태의 시뮬레이션 결과 요약 보고서 (`eplustbl.htm` 등)
* **`.png`**: 그래프나 시각화 이미지 파일
* **`.py`**: 분석용 파이썬 스크립트 파일

### 🔴 삭제 대상 파일 (Remove)
상기 보존 대상을 제외한 모든 대용량 시뮬레이션 중간/결과 파일들은 디스크 여유 공간 확보를 위해 **삭제**합니다.
* **`.sql`**: SQLite 데이터베이스 파일 (보통 매우 큰 용량 차지)
* **`.csv`**: 엑셀 형식의 변환 데이터 파일 (용량이 매우 큼)
* **`.bnd`, `.eio`, `.mdd`, `.mtd`, `.mtr`, `.rdd`, `.shd`, `.audit`, `.end`** 등 시스템 생성 중간 파일들

---

## 2. 자동 정리 파이썬 스크립트

아래 스크립트는 지정된 루트 경로 하위의 결과 폴더들을 안전하게 스캔하여 보존/삭제 기준에 맞추어 정리를 자동 수행합니다. 

윈도우 콘솔 환경의 한글 인코딩(`CP949`)이나 이모지 깨짐 문제가 발생하지 않도록 단순 텍스트 로그 형식으로 설계되었습니다.

### 스크립트 코드

프로젝트 폴더 내 원하는 위치에 `clean_results.py` 등으로 저장하여 실행하실 수 있습니다.

```python
import os
import sys

def clean_simulation_folders(root_dir, dry_run=True):
    # 보존할 확장자 정의 (대소문자 구분 없음)
    keep_extensions = {'.eso', '.err', '.htm', '.png', '.py'}
    
    print(f"=== {'[DRY RUN] ' if dry_run else '[REAL DELETE] '}Starting Cleanup ===")
    print(f"Target Directory: {root_dir}\n")
    
    if not os.path.exists(root_dir):
        print(f"Error: Directory '{root_dir}' does not exist.")
        return

    # 최상위 경로 아래에 위치한 하위 결과 폴더 목록 추출
    try:
        subdirs = [os.path.join(root_dir, name) for name in os.listdir(root_dir) 
                   if os.path.isdir(os.path.join(root_dir, name))]
    except Exception as e:
        print(f"Error listing directory: {e}")
        return
    
    total_deleted = 0
    total_kept = 0
    
    for subdir in subdirs:
        dir_name = os.path.basename(subdir)
        print(f"\nAnalyzing folder: {dir_name}")
        
        # 결과 폴더 내부 파일 재귀 탐색
        for dirpath, _, filenames in os.walk(subdir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                _, ext = os.path.splitext(filename)
                ext_lower = ext.lower()
                
                # 보존/삭제 판단
                if ext_lower in keep_extensions:
                    print(f"  [KEEP] {os.path.relpath(file_path, root_dir)}")
                    total_kept += 1
                else:
                    print(f"  [REMOVE] {os.path.relpath(file_path, root_dir)}")
                    total_deleted += 1
                    if not dry_run:
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            print(f"  [ERROR] Failed to delete {file_path}: {e}")
                            
    print("\n====================================")
    print(f"Cleanup finished ({'Dry Run' if dry_run else 'REAL RUN'})")
    print(f"Kept files: {total_kept}")
    print(f"Removed (or target) files: {total_deleted}")
    print("====================================")

if __name__ == "__main__":
    # 시뮬레이션 폴더들이 모여 있는 루트 경로 설정
    target_path = r"c:\Users\taegyu\Codes\EnergyPlus_Project1\backups\sim_folder_backup"
    
    # 인자로 --real을 주면 실제 삭제를 실행하며, 그렇지 않으면 Dry Run(안전 테스트)을 구동합니다.
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        dry_run = False
        
    clean_simulation_folders(target_path, dry_run=dry_run)
```

---

## 3. 스크립트 실행 방법

작성된 스크립트는 커맨드라인(터미널)에서 아래와 같이 안전하게 단계를 거쳐 실행하는 것을 권장합니다.

### 1단계: Dry Run (안전 검사)
실제 삭제를 진행하기 전에, 어떤 파일이 삭제 대상이고 보존 대상인지 화면을 통해 미리 확인합니다.
```bash
python clean_results.py
```
> **Tip:** 화면에 출력되는 리스트에서 보존되어야 할 파일이 `[REMOVE]`로 처리되지 않았는지 확인하십시오.

### 2단계: Real Delete (실제 파일 삭제)
목록 검토가 끝났다면 뒤에 `--real` 옵션을 붙여 실행하면 대상 파일들을 안전하게 디스크에서 삭제합니다.
```bash
python clean_results.py --real
```

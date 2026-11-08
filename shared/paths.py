"""리포 전체에서 쓰는 경로 상수.

스크립트 위치(폴더 깊이)와 상관없이 같은 경로를 쓰도록 여기서만 정의한다.
사용 예: ``from shared.paths import DATA, EXPERIMENTS``

EnergyPlus PythonPlugin 모듈은 EnergyPlus 내장 Python에서 돌아 이 모듈을 import할 수 없다.
그런 파일은 ``pyproject.toml``을 찾아 올라가는 방식으로 루트를 직접 구한다.
"""

from pathlib import Path


def _find_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("pyproject.toml 이 있는 리포 루트를 찾지 못함")


ROOT = _find_root()

# 공용 자원
SHARED = ROOT / "shared"
DATA = SHARED / "data"            # 날씨 파일, PV 모듈 목록, 태양추적 각도 등
CASE_IDF = SHARED / "case_idf"    # case1/case2/case3 기준 IDF
PLUGINS = SHARED / "plugins"      # 루트에 있던 model_pythonpluginsystem*.py

DOCS = ROOT / "docs"
REFERENCE = ROOT / "reference"

# 프로젝트
PROJECTS = ROOT / "projects"
BASELINE = PROJECTS / "01_baseline_bipv"        # 케이스1~3 기본·색상·기후·96배치·경제성
TIDE_V1 = PROJECTS / "02_tide_v1"               # 최초 TiDE 파이프라인 (옛 ai_model/tide)
EXPERIMENTS = PROJECTS / "03_bipv_experiments"  # Phase0·고정각·c5 재평가 (옛 bipv_experiments)
PVLW = PROJECTS / "04_pv_lw_daylight"           # PV 장파·주광 결합 (옛 pv_lw_daylight)
MISMATCH = PROJECTS / "05_bipv_mismatch"        # TiDE 정책 (옛 bipv_mismatch)

# 옛 case_analysis/ 가 나뉜 위치
BASELINE_RESULTS = BASELINE / "results"  # normal/, bipv_variation/
TIDE_V1_RESULTS = TIDE_V1 / "results"    # case3_v3_south_tide*/

# 날씨 파일
WEATHER_IWEC = DATA / "KOR_Kwangju.471560_IWEC (1).epw"
WEATHER_TMYX_2004 = DATA / "KOR_KJ_Gwangju.471560_TMYx.2004-2018.epw"
WEATHER_TMYX_2011 = DATA / "KOR_KJ_Gwangju.471560_TMYx.2011-2025.epw"


def figures_dir(project: Path, name: str) -> Path:
    """프로젝트의 그림 저장 폴더 ``<project>/figures/plot/<name>``."""
    return project / "figures" / "plot" / name

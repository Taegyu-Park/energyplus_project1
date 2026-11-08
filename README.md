# 건물에너지시뮬레이션 — 키네틱 BIPV

EnergyPlus로 키네틱 BIPV 차양의 각도 제어를 시뮬레이션하고, TiDE 모델로 각도를 예측해 net 에너지를 줄이는 연구.

## 폴더 구조

```
projects/
  01_baseline_bipv/     케이스1~3 기본 비교, 색상·기후·방위, 96개 PV 배치, 경제성 (fig1~34)
  02_tide_v1/           최초 TiDE 파이프라인(학습·예측)과 case3 TiDE/태양추적 실행 (fig35~39)
  03_bipv_experiments/  Phase 0 case3 버그 수정, 고정각·One-Diode 재평가, lookback 36 (fig40~43)
  04_pv_lw_daylight/    PV 장파 복사·주광 결합 실행
  05_bipv_mismatch/     발전-수요 미스매치 기반 TiDE 정책 (open/window/oracle)
shared/
  paths.py              모든 경로 상수 (아래 참고)
  data/                 날씨 파일(EPW/DDY), PV 모듈 목록, 태양추적 각도
  case_idf/             case1/case2/case3 기준 IDF와 case3 플러그인 사본
  plugins/              EnergyPlus PythonPlugin 모듈 (model_pythonpluginsystem*.py)
docs/                   공통 문서, 매뉴얼, 이미지 프롬프트
reference/              참고 논문
```

각 프로젝트 폴더 안의 공통 하위 폴더:

| 폴더 | 내용 | git |
|---|---|---|
| `figures/code/`, `figures/plot/` | 그림 스크립트와 결과(png/svg) | 추적 |
| `results/` (01, 02) | EnergyPlus 실행 결과 (옛 `case_analysis/`) | 무시 |
| `runs/` (03, 04, 05 일부) | EnergyPlus 실행 결과 | 무시 |
| `docs/` | 프로젝트별 계획·정리 문서 | 추적 |

시뮬레이션 출력과 학습 데이터셋은 용량이 커서 git에 올리지 않는다(`.gitignore`). 각 폴더의 실행·생성 스크립트로 다시 만들 수 있다.

## 경로 규칙

스크립트는 폴더 깊이(`Path(__file__).parents[N]`)로 루트를 계산하지 않고 `shared.paths`의 상수를 쓴다.

```python
from shared.paths import DATA, CASE_IDF, EXPERIMENTS, BASELINE_RESULTS

epw = DATA / "KOR_Kwangju.471560_IWEC (1).epw"
sql = BASELINE_RESULTS / "normal" / "case3" / "eplusout.sql"
```

| 상수 | 위치 |
|---|---|
| `ROOT` | 리포 루트 (`pyproject.toml` 위치) |
| `DATA`, `CASE_IDF`, `PLUGINS` | `shared/data`, `shared/case_idf`, `shared/plugins` |
| `BASELINE`, `TIDE_V1`, `EXPERIMENTS`, `PVLW`, `MISMATCH` | `projects/01_…` ~ `projects/05_…` |
| `BASELINE_RESULTS`, `TIDE_V1_RESULTS` | `projects/01_…/results`, `projects/02_…/results` |

`shared`는 `uv sync` 때 editable 패키지로 설치되므로 어느 폴더에서 실행해도 import된다.
EnergyPlus PythonPlugin 모듈은 EnergyPlus 내장 Python에서 돌아 `shared`를 import할 수 없으므로,
`pyproject.toml`을 찾아 올라가는 방식으로 루트를 직접 구한다.

## 환경

```bash
uv sync            # 의존성 + shared 패키지 설치
uv run python projects/03_bipv_experiments/runner.py --help
```

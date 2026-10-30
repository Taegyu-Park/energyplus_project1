# 구매 전력 최소화 kinetic BIPV 각도 결정 — case2 기반 TiDE 계획

## Context
- **목적 (2026-10-26 변경)**: kinetic BIPV 각도 제어로 **평가 기간 평일의 PV 공급–HVAC 수요 미스매치**를 최소화한다. 아래 "목적 재정의" 참고.
  - ~~연간 구매 전력 최소화~~ → 구매 전력은 보조 지표로 함께 보고한다.
  - `HVAC 전력 = 냉방/3.0 + 난방/2.5` (열부하 정의는 그대로)
  - `부족(구매) = max(HVAC 전력 − PV, 0)`, `잉여 = max(PV − HVAC 전력, 0)`
  - 수요는 HVAC만 포함.
- **사용 형태**: 오프라인 연간 스케줄 생성. TMY 기상을 미래까지 안다고 가정하고, 결과는 EnergyPlus로 검증한다.
- **대상**: 남측 파사드 BIPV(6단, 96모듈), 광주 IWEC, 10분 간격. 학습 데이터는 case2(고정각 0~90°)만 쓴다.
- **현재 데이터셋(`ai_model/tide/data/dataset/`)의 문제**
  1. case3 결과가 섞인 증강본이다.
  2. 원본 case2_KS는 그림자를 30일마다 계산하고, 냉난방 용량을 각도마다 따로 산정한다. PV가 각도에 대해 비단조이고 라벨이 10°/40°에 몰린다.
  3. 라벨이 부호 있는 net 기준이다.
  4. 요일, 미래 기상, 열적 상태 feature가 없다.
- **확인된 수급 구조**
  - 여름 평일 낮과 겨울에는 PV가 부족하다(7월 PV 1,780 vs HVAC 5,448 kWh).
  - 봄·가을과 주말에는 PV가 남는다.
  - 주간 71%는 여러 각도의 구매 전력이 모두 0이다(동점).

## 목적 재정의 (사용자 확정, 2026-10-26)
- **미스매치** = `w_def · 부족 + w_sur · 잉여`. 구매 최소화는 잉여를 무시하므로 미스매치 최소화와 다르다.
- **평일만** 대상으로 한다. 주말은 재실 0, 부하 거의 0이고 PV가 전부 잉여라(IWEC 주말 구매 0.13 MWh, 잉여 13.5 MWh) 초점이 아니다.
- **평가 기간: 11/1 ~ 3/31 평일 (난방기, 약 108일)** — 2026-10-26 확정 (이전안 9/1~6/30을 대체)
  - 여름(7~8월): 부하가 PV보다 월등히 커서 PV가 전부 부하에 쓰인다. 미스매치가 순수 부족분이라 각도로 조정할 여지가 없다(잉여 비율 IWEC·TMYx 0.0~0.1).
  - 봄·가을(4월 말~5월 초, 9월 말~10월): PV가 주간 부하를 거의 다 덮어 미스매치가 거의 전부 잉여다. 각도로 할 수 있는 일은 발전량 줄이기뿐이다.
  - 겨울: 해가 떠 있어도 아침 난방 부족과 한낮 잉여가 같은 날 공존한다(시간대 어긋남). 주간 부족·잉여 공존량 min(부족, 잉여) 중 11~3월이 IWEC 70%, TMYx 68%를 차지한다.
  - 그림: `figure/plot/fig41_1_*`(겨울 평일), `fig43_*`(여름·가을 평일)
- **평가 시간대: 하루 전체** (2026-10-26 확정). 해 뜨기 전 시간은 따로 다루지 않는다.
  - 해가 떠 있는 시간만으로 잘라도 겨울은 가을처럼 되지 않는다: 주간 부족 0인 날 0/108(태양추적), 부족의 41%가 일출 후 1시간, 12%가 일몰 전 1시간, 잉여의 95%가 한낮.
  - 해 진 후 HVAC가 각도에 따라 18~29% 달라지므로(낮 일사의 축열 효과) 하루 전체로 봐야 이 효과가 잡힌다. 해 뜨기 전 부족은 각도에 따라 3~4%만 달라져 순위에 거의 영향이 없다.
- **비교 기준안: 기존 태양고도 추적형 실행** (2026-10-26 사용자 확정, 이전에 쓰던 고정 10°는 구매 전력 기준 최선 고정각이라 새 목적과 무관)
  - 결과: `bipv_experiments/runs/c3_FE_suntracking_od` (시계열 `bipv_experiments/analysis/c3_net_timeseries_onediode.csv`의 `*_ST` 열), IWEC
  - 스케줄 `suntracking_w0s90`: 낮은 태양고도 최근접 10° 단위, 밤은 11~3월 0°, 그 외 90°
  - case2 고정각 결과를 이어 붙인 추적안은 쓰지 않는다: PV는 맞아도 부하는 그 각도로 계속 운전한 열적 이력을 담고 있어 실제 추적 운전과 다르다.
  - 설정 차이(참고): 그림자 Periodic, FullExterior(반사 없음), 기본 하늘 확산 모델, PV Eg 1.12. 이번 case2 실행은 그림자 Timestep, FullExteriorWithReflections, DetailedSkyDiffuseModeling, Eg 1.25. 용량 산정(`case2_max_over_angles.eio`)은 같다.
  - 난방기 평일 기준값(IWEC): 해 뜨기 전 부족 4.44, 주간 부족 5.24 / 잉여 8.44, 해 진 후 부족 1.38 MWh. 주간 부족 0인 날 0/108일.
- **적용 범위**: 기간·평일 제한은 라벨과 평가 지표에만 적용한다. 학습 데이터는 시계열 연속성과 lookback(예: 9/1 예측에 8월 말 필요) 때문에 1년 전체를 그대로 쓴다.
- **열부하**: HVAC 전력 환산 그대로.
- **가중치 `w_def : w_sur` = 1 : 1** (2026-10-26 우선 설정, 바뀔 수 있음). 참고(평일 전체, 오라클, IWEC):
  - 1:1이면 구매는 그대로(20.10→20.11 MWh)이고, 미스매치 감소(37.69→35.43 MWh)는 거의 전부 잉여 감소다. 구매가 0으로 동점인 시간에 발전이 적은 각도(주간 90° 25%→54%)를 골라 PV를 덜 만드는 효과다.
  - 잉여를 왜 줄이는지(역송·계통 부담 vs 비용)에 따라 가중치를 정한다.
- 모델(Strategy 2)은 성분을 예측하므로 목적이 바뀌어도 재학습 불필요. 라벨·평가만 다시 계산한다.

## 결정 기준 (사용자 확정, 목적 재정의 전)
1. **1단계, HVAC 최소안 (기본)**: 매 시점 구매 전력이 가장 작은 각도를 고른다. 동점이면 그 순간의 HVAC 전력이 가장 작은 각도를 고른다. → 미스매치 기준으로 대체 예정(가중치 확정 후)
2. **2단계, 권장안 (비교 실험)**: 블록 단위 각도 계획(예: 낮/밤 각도)으로 24시간 구매 전력 합을 최소화하고, 동점이면 HVAC 최소. 건물 열관성(축열과 사전 차단) 효과의 크기를 확인하는 것이 목적이다.

## 작업 폴더 (신규, 기존 파일은 수정하지 않음)
```
energyplus_project1/bipv_mismatch/
├── PLAN.md                      ← 이 계획을 저장
├── run_case2_sim.py             ← 이번에 실행
├── idf/case2_KS/case2_{angle}.idf   ← 출력 변수·설정을 추가한 IDF 10개 (case_idf/case2_KS와 같은 구조)
├── case2_KS/case2_{angle}/      ← 시뮬레이션 결과 (case_analysis/normal/case2_KS와 같은 구조)
│   ├── eplusout.sql, eplusout.err, run_stdout.log, …
├── dataset/                     ← (Step 3) 학습 데이터셋
└── (Step 4~6 스크립트)
```

## Step 1. 계획 저장
이 문서를 `bipv_mismatch/PLAN.md`로 저장한다.

## Step 2. case2 고정각 10개 재시뮬레이션 (이번 실행 범위)
`bipv_mismatch/run_case2_sim.py`를 새로 만든다.
- **입력**: `case_idf/case2_KS/case2_{a}.idf` (원본, 수정하지 않음)
- **IDF 사본 생성**: `bipv_experiments/runner.py`의 `prepare_idf()`를 import해서 재사용한다.
  - `shadow_timestep=True`: 그림자를 Periodic 30에서 Timestep으로 바꾼다.
  - `ideal_sizing_from=bipv_experiments/sizing/case2_max_over_angles.eio`: 각도 간 용량을 통일한다.
  - `sky_diffuse="DetailedSkyDiffuseModeling"`: SimpleSky 버그 이력(Phase 0) 때문에 c2_RF와 같게 맞춘다.
  - Solar Distribution은 원본 그대로(FullExteriorWithReflections), PV는 One-Diode.
  - 이 조합은 기존 `bipv_experiments/runs/c2_RF_A*`와 같고, 90°까지 One-Diode로 성공한 이력이 있다. FullExterior는 90°에서 One-Diode가 실패해 pv_simple로 대체된 이력이 있어 쓰지 않는다.
- **추가할 출력 변수** (`Output:Variable,…,TimeStep`, 사본 끝에 추가. 이름은 rdd에서 확인함)
  - **Site (*)**: Outdoor Air Relative Humidity, Outdoor Air Dewpoint Temperature, Wind Speed, Sky Temperature, Horizontal Infrared Radiation Rate per Area, Total Sky Cover, Day Type Index
  - **Zone (*)**: Mean Air Temperature, Operative Temperature, Air Relative Humidity, People Occupant Count, Thermostat Heating/Cooling Setpoint Temperature, Ideal Loads Zone Sensible/Latent Heating/Cooling Energy, Lights Electricity Energy, Electric Equipment Electricity Energy (기존 Hourly와 별도로 TimeStep)
  - **남측 표면** (키를 지정: `BIPV_office_{1,2}_S..Wall_S`, `..Wall_S_Glz0`): Surface Inside Face Temperature, Surface Outside Face Incident Solar Radiation Rate per Area, Surface Window Transmitted Solar Radiation Energy (창만)
  - **PV**: Generator PV Cell Temperature. 6개 단마다 대표 발전기 1개(IDF에서 `PV_{row}_{a}_..` 첫 번째를 정규식으로 선택)
- **IDF 저장**: 설정 변경과 출력 추가를 마친 IDF를 `bipv_mismatch/idf/case2_KS/case2_{a}.idf`에 저장한다. 결과 폴더에는 IDF를 복사하지 않고 이 파일로 실행한다. `prepare_idf()`가 결과 폴더에 만드는 `_run.idf` 사본은 idf 폴더로 옮긴다.
- **실행**: `C:\EnergyPlusV25-2-0\energyplus.exe -w data/KOR_Kwangju.471560_IWEC (1).epw -d bipv_mismatch/case2_KS/case2_{a} bipv_mismatch/idf/case2_KS/case2_{a}.idf`
  - 10개를 병렬로 실행한다(각 약 4분, `run_case2_tmyx.py`의 ThreadPoolExecutor 패턴).
  - 로그는 `run_stdout.log`에 남긴다. 실패하면 각도와 exit code를 보고한다.

### Step 2-1. One-Diode PV 밴드갭 보정 (2026-10-26 추가)
- **문제**: TMYx 70°가 2/7 15:00~15:10에서 Fatal(`EquivalentOneDiode ... exponential of too large a number`, VV=44.576, II=-4208.8)로 결정론적 실패.
- **원인**: E+ 25.2 `Photovoltaics.cc`는 Rs를 닫힌 식으로 계산한다(엔지니어링 레퍼런스의 [0, Rsmax] 이분탐색 설명과 다름). `Shinsung_SolarSkin_390W_Performance`(Ns 66, Voc 46.64, βVoc -0.13992, Eg 1.12)는 a_ref 5.12 V(셀당 이상계수 3.0), **Rs -0.879 Ω**이 된다. 음수 Rs에서는 개방전압 부근 Newton 도함수가 G≈556 W/m²에서 0을 지나 발산한다. 성공한 실행도 PV 곡선이 왜곡되어 있다(STC 408 W, 200 W/m² 상대효율 68%).
- **조치**: `run_case2_sim.py`의 `build_idf()`에서 `Semiconductor Bandgap`을 1.12 → **1.25 eV**(`PV_BANDGAP`)로 치환한다. Rs +0.091 Ω, 이상계수 1.22, STC 394.3 W(데이터시트 390.7 W), 200 W/m² 상대효율 96%, Voc 온도계수는 데이터시트 값 유지. Eg는 물리적 밴드갭이 아니라 E+ 파라미터 추출용 피팅값이다.
- **검증**: E+ 알고리즘 파이썬 재현 모델이 E+ 출력과 0.02 W 이내로 일치(Eg 1.12·1.25 모두). Eg 1.25로 70° TMYx 1/1~2/8 시험 실행 통과.
- **이전 결과 보존**: `case2_KS_Eg112/`, `case2_KS_TMYx_Eg112/`, `idf/case2_KS_Eg112/`
- **후속**: Step 6의 case3 등 같은 성능 객체를 쓰는 다른 IDF도 같은 보정이 필요하다. 과거 "FullExterior 90°에서 One-Diode 실패" 이력도 같은 원인일 가능성이 있다.

## Step 3. 학습 데이터셋 구축 (다음 단계)
- 기존 `build_case2_ks_tide_dataset.py`의 `extract_weather_and_time`과 `extract_angle_data` 로직을 재사용한다(새 스크립트로 복사·확장).
- PV는 `Generator Produced DC Electricity Energy` 합으로 계산한다(Facility와의 비율 0.96 확인).
- timestamp는 2006년 그대로 유지한다(요일 보존).
- **추가 feature**
  - 요일, 주말/휴일, 재실·설정온도 스케줄
  - Site 습도·풍속·운량·장파
  - 각도별 패널 입사각 cos θ와 POA 추정
  - 남측 존 온도, 창 투과일사
  - 미래 기상은 future covariate로 쓴다.
- **라벨과 지표**: 구매 전력, 남는 PV, 1단계 라벨(구매 최소, 동점이면 HVAC 최소)
- **분할**: ~~월별 블록(1~21 / 22~25 / 26~말일)~~ → Step 4의 기상 연도 분할로 변경 (2026-10-26)
- **최종 조건 데이터셋 (2026-10-28, `build_dataset.py` 기본 `--set final`)**: PV 장파 연동 + 주광 400 lx + DifferentialEnthalpy + Eg 1.25, 기상 파일 1개 = 1년 = 분할 1개
  - train = IWEC (`case2_KS_IWEC_final`), val = TMYx.2004-2018 (`case2_KS_TMYx2004`), test = TMYx.2011-2025 (`case2_KS_TMYx2011_final`) → `dataset_final/case2_mm_{train,val,test}.csv` (각 52,560행 × 160열)
  - 조명은 각도별 열 `lights_kwh_{a}`(주광 연동). **2026-10-29 사용자 결정: 수요 = HVAC + 조명** (`demand_elec_{a}`), 구매 = max(수요 − PV, 0), 잉여 = max(PV − 수요, 0), 동점 시 수요 최소
  - 재생성 결과(IWEC/TMYx2004/TMYx2011, MWh): 오라클 구매 31.65/29.53/31.43, 최선 고정각 40° 32.79/30.78/32.57 (−3.5%/−4.1%/−3.5%), 주간 동점 비율 51/60/57% (조명 제외 때 74%)
  - val(TMYx2004)은 PV가 가장 많은 해라 train과 test 사이에 있지 않다(30° PV DC: 44.8 / 60.6 / 53.6 MWh)
- **구현 (옛 조건, `--set legacy`)**: `build_dataset.py` (IWEC → `dataset/case2_gp_dataset.csv`, `--weather tmyx` → `dataset/case2_gp_tmyx_dataset.csv`)
  - TMYx는 Eg 1.25 IDF(`idf/case2_KS/`)로 `case2_KS_TMYx/`에 재시뮬레이션. 요일 배치는 IWEC와 같음(2006-01-01 일요일)
  - TMYx는 IWEC보다 냉방 +66%, PV +20% (10° 기준) → 학습 범위 밖 테스트

## Step 4. TiDE 학습
`train_tide.py`를 복사해 수정한다. Strategy 2(PV·냉방·난방 30개 성분)를 예측하고, 목적함수는 예측 후 계산한다. 가치 기준이 바뀌어도 재학습하지 않아도 된다.

**분할 (사용자 확정, 2026-10-26)** — `train_tide_gp.py`
- 날짜 중간 블록을 빼면 학습 시계열이 끊기고 인접일 누설로 검증이 낙관적이 되므로, 학습·검증은 IWEC, 테스트는 다른 기상 연도인 TMYx로 한다.
- **모델 A (에폭 선택 전용)**: IWEC에서 1/15~28, 4/15~28, 7/15~28, 10/15~28을 검증, 앞뒤 1일 버퍼 제외 나머지를 학습. 조기 종료 없이 30 에폭 전부 돌리고 검증 손실 최소 에폭만 가져간다. 가중치는 버린다.
- **모델 B (최종)**: IWEC 365일 전체를 같은 코사인 스케줄(T_max 30)로 best epoch까지 학습. 검증 없음.
- **테스트**: 모델 B를 TMYx 365일로 평가(성분별 R², 구매 전력 regret, 월별). 테스트 결과로 설정을 고르지 않는다.
- 설정(lookback, 입력 변수 등)을 비교할 때는 모델 A 검증 손실로 고른다.

**1차 결과 (2026-10-26, 구매 최소 기준, 연간 전체)** — `checkpoints/tide_gp_B_tmyx_eval.json`
- 모델 A best epoch 30 (검증 MSE 0.0318). 모델 B TMYx R²: PV 0.997, 냉방 0.950, 난방 0.996
- TMYx 연간 구매: 고정 10° 27,773 / TiDE 27,069 (−2.5%) / 오라클 26,814 (−3.5%) kWh
- 절감은 겨울·늦가을에서 나오고, 7~8월(구매의 62%)은 오라클도 −1% 안팎 → 목적 재정의의 계기
- 미해결: 입력에 10개 각도의 과거 PV·부하가 들어가는데, 실제 각도 전환 운전에서는 관측할 수 없다(Step 5 전 정리 필요).

## Step 5. 각도 스케줄 생성
1단계 HVAC 최소안, 2단계 블록 계획 최적화를 만든다. 출력은 `timestamp,optimal_angle` CSV.

## Step 6. EnergyPlus 폐루프 검증
`bipv_experiments/runner.py`와 case3 fixed IDF, One-Diode로 실행한다. PV는 선택 각도 발전기만 합산한다. 비교 대상은 고정 30°, 태양추적, 1단계, 2단계이고, 연간 구매 전력·남는 PV·HVAC로 비교한다.

## 검증 (Step 2)
- 10개 모두 `EnergyPlus Completed Successfully`, Severe 0인지 확인한다.
- `Time` 테이블에서 웜업 제외 Interval=10 스텝이 52,560개인지 확인한다.
- 추가 출력 변수가 모두 SQL에 있는지 확인한다.
- 연간 PV·냉난방 합계를 `bipv_experiments/runs/c2_RF_A{a}/summary.json`과 비교한다(같은 설정이므로 거의 같아야 함).
- 각도별 PV가 원본 case2_KS보다 단조에 가까워졌는지 확인한다.

## 각도 결정 규칙 재정의 (사용자 확정, 2026-10-29)
1. **수요 > PV (모든 각도에서 구매 > 0)**: 구매 전력이 최소인 각도.
2. **PV ≥ 수요가 되는 각도가 있음**: 수요만큼만 쓰고 나머지는 버린다(curtail, 미스매치에 넣지 않음). 구매 0 각도 중 **채광 최대 + 움직임 최소**.
- 구현: `label_mismatch.py` (연간 Viterbi, 비용 = −채광점수 + λ·|Δθ|/10°, 규칙 1 시점은 구매 최소 각도만 허용). 채광 = 남측 2개 존 기준점 조도 평균(`extract_daylight.py` → `dataset_final/daylight_{split}.csv`). 출력 `labels/mm_label_{split}_{raw|useful}_lam{λ}_tol{r}.csv`
- 1차 결과(IWEC, 평가기간 11~3월 평일, raw·λ 0.05·엄격): 구매 14.73 MWh(기존 라벨과 같음), 버린 PV 5.05(기존 5.59), 잉여 시점 조도 5,358 lx(기존 3,929), 이동 11.1회·289°/일(기존 16.9회·557°/일)
- 관찰: 조도는 90°(수평)가 압도적이라(잉여 시점 최대 조도 각도의 85%) 잉여 구간은 거의 90° 고정. 남은 움직임의 대부분(7.3회·204°/일)은 규칙 1 주간(아침·오후 부족)에서 구매 최소 각도가 10분마다 바뀌는 것. 규칙 1에 허용오차 5%를 주면 구매 +0.14 MWh(+1%)에 이동 170°/일.
- 미결정: 채광 지표(raw 조도 vs 설정조도 400 lx 상한), λ, 규칙 1 허용오차.

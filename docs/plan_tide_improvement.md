# TiDE Strategy 1 개선 계획 (Net Energy를 태양추적 룰베이스 이하로)

## Context
fig38 결과: 시뮬레이션 기준 **Strategy 1(ST1)이 태양추적(룰베이스)보다 net energy가 살짝 나쁘다.**
냉난방 부하는 줄었지만 PV 발전도 같이 줄어 상쇄됐다.

| 연간 Net Energy (kWh, 작을수록 좋음) | 값 |
|---|---|
| 태양추적 (시뮬레이션, fig38 baseline) | −4,658 |
| ST1 (시뮬레이션, `case3_v3_south_tide`) | −4,463 |
| 태양추적 (오프라인: 데이터셋 각도 컬럼) | −6,237 |
| ST1 (오프라인: 예측 각도의 true net) | −4,895 |
| ST2 (오프라인) | −4,038 |
| 이론 최적 (oracle, 시각별 최적 각도) | −7,177 |

## 현재 파이프라인에서 확인된 원인 후보
1. **각도 간 차이가 공통 성분에 묻힌다.** 시각별 net_energy의 각도 간 표준편차는 평균 0.071인데, 시간에 따른 공통 변동(10개 각도 평균)의 표준편차는 1.73이다(약 4%). MSE로 10개를 같이 학습하면 R²≈0.73은 공통 성분에서 나오고, `argmin`은 작은 차이로 결정된다. 각도 MAE 33°가 이를 뒷받침한다.
2. **오프라인 지표와 시뮬레이션이 다르다.** 태양추적이 오프라인 −6,237인데 시뮬레이션은 −4,658이다. 데이터셋은 "고정각도 1년 실행"의 반사실 값이라 동적 제어와 다르다. 오프라인은 **순위 비교용 대리 지표**로만 쓴다.
3. **입력 설계.** 날씨(외기온, 직달/확산 일사)가 past 전용이라 미래 구간에서 못 쓴다. (EPW 표준기상년이라 미래 값을 알고 있는 셈) 태양 방위각은 불연속(0/360)이다. 각도별 입사각/면일사량 같은 물리 특성은 없다. `month_sin/cos`는 실제로 day-of-year다. 요일/점유 스케줄이 없다.
4. **학습 과정.** best epoch이 2~3(이후 과적합), 하이퍼파라미터 탐색 없음, 체크포인트를 MSE로 고름(의사결정 지표 아님).
5. **추론 입력.** `predict_annual_tide.py`는 lookback 입력에 **실제(시뮬레이션) 10각도 net 값**을 쓴다. 실제 폐루프 배포에서는 이런 값이 없으므로 성능이 낙관적일 수 있다.

## 원칙
- **비용이 싼 것부터**: 재학습이 필요 없는 후처리 → 타깃/손실 → 입력 → 하이퍼파라미터 순.
- **선택 기준은 MSE가 아니라 의사결정 지표**: 오프라인 net(예측 각도의 true net 합), PV 합, 냉·난방 합, regret.
- EnergyPlus 1년 시뮬레이션은 약 8시간이므로 **최종 후보 1~2개만** 돌린다.
- 모든 실험은 같은 train/val/test 분할(매월 1~21/22~25/26~말일)을 쓰고, 결과를 표로 누적한다(`docs/tide_experiment_log.md`).

## Phase 0. 기준선 재현 (재학습 없음)
- 위 표의 오프라인 수치를 스크립트로 재현한다. (test 구간만 따로도 집계)
- 지표: 예측 각도의 true net 합, PV 합, 냉·난방 합, 각도 MAE, regret.
- 룰베이스(`data/bipv_suntracking_angles_annual.csv`)와 oracle을 같은 스크립트로 같은 지표로 계산한다.
- 수정: `evaluate_tide.py`(또는 새 `ai_model/tide/decision_metrics.py`). 입력은 `data/predictions/annual_tide_strategy1_optimal_angles.csv`의 `net_energy_pred_*`/`net_energy_true_*`.

## Phase A. 후처리/결정 규칙 (기존 모델 그대로, 재학습 없음) ★ 우선
| 실험 | 내용 |
|---|---|
| A1 | 지평선 집계: horizon step 0만 쓰지 않고 향후 k스텝(예: 6, 12, 24) 예측 net의 평균으로 `argmin`. 열적 지연을 반영 |
| A2 | 하이브리드: 기본은 태양추적, AI가 임계값 ε 이상 이득을 예측할 때만 덮어씀 |
| A3 | 야간(`sun_altitude≤0`) 각도 고정(0° 또는 90°). `docs/plan_winter_night_angle_0.md`와 정합 확인 |
- 수정: `predict_annual_tide.py`의 "Optimal PV Angle Determination" 구간(argmin 직전)에 후처리 옵션 추가. 기존 출력 CSV 형식은 유지한다.

## Phase B. 타깃/손실 재설계 (가장 큰 효과 기대)
| 실험 | 내용 |
|---|---|
| B1 | 타깃 분해: `공통(각도 평균)` + `각도별 편차(net_a − 평균)`를 따로 정규화해서 예측. 편차 예측에 집중시킴 |
| B2 | 편차에 가중 MSE(편차 채널 가중치 ↑) |
| B3 | 랭킹/결정 손실 추가: `softmax(−β·pred)`로 "soft-argmin 기대 net"(`Σ softmax·true_net`)을 손실에 더함. 또는 최적 각도 교차엔트로피 |
| B4 | ST1(직접 net)과 ST2(PV/냉/난 분해) 비교. ST2 개선은 아래 "Strategy 2 개선안" 참고 |
- 수정: `train_tide.py`의 타깃 구성(`STRATEGY_1_TARGETS`), 손실(`criterion`), `validate()`(의사결정 지표 추가).
- 체크포인트 선택을 val MSE → val 의사결정 지표(오프라인 net)로 변경.

## Phase C. 입력(특성) 추가/수정
| 실험 | 내용 |
|---|---|
| C1 | `outdoor_temp`, `direct_solar`, `diffuse_solar`를 **future covariate**로도 제공 (past 전용 → 둘 다) |
| C2 | 방위각 `sin/cos` 변환, 고도-방위로 만든 태양 벡터 |
| C3 | 각도별 물리 특성 10개: 입사각 코사인 `cos(θ_inc,a)`, 면일사량 대리값 `direct·cos(θ_inc,a)+diffuse·(1+cos a)/2` |
| C4 | 요일/점유 스케줄(시간대 × 평일/주말), 냉방·난방 시즌 플래그, `day_of_year` 명칭 정정 |
| C5 | 절제 실험: lookback 타깃 제거/가림(추론 시 실제값 의존 제거), lookback 길이 36/72/144/288 |
- 새 특성은 데이터셋 CSV에 컬럼으로 추가하는 전처리 스크립트(`ai_model/tide/data_preprocessing/add_physics_features.py`)로 만든다. 기존 데이터셋은 덮어쓰지 않고 새 파일로 저장한다.
- 수정: `train_tide.py`의 `PAST_COV_COLS`/`FUTURE_COV_COLS`. `tide_model.py`는 입력 차원만 바뀜(구조 변경 없음).
- C5는 "현재 성능이 폐루프에서도 유지되는가"를 보는 점검이다.

## Phase D. 학습 과정/하이퍼파라미터
- 조기 종료(patience 5) + 의사결정 지표 기준 체크포인트.
- 탐색 범위: lr {3e-4, 1e-3}, weight decay {1e-4, 1e-3, 1e-2}, dropout {0.1, 0.2, 0.3}, hidden {128, 256, 512}, horizon {6, 24, 72}.
- 소규모 랜덤 탐색(10~20회, 각 1~2분, GPU RTX 2060). 목적함수는 val 오프라인 net.
- 시드 앙상블(5개) 평균 예측으로 argmin. 노이즈가 큰 차이 예측의 분산을 줄인다.
- 수정: `train_tide.py`(args에 위 항목 추가, `--seed`, early stopping).

## Phase E. 폐루프(시뮬레이션) 검증
- Phase A~D에서 오프라인 net이 태양추적(−6,237)보다 좋은 후보 1~2개 선정.
- `predict_annual_tide.py`로 스케줄 생성 → `run_case3_south_tide_sim.py --strategy N`으로 EnergyPlus 1년 실행(약 8시간).
- `figure/code/fig38_*.py`를 갱신해 baseline(태양추적 −4,658) 대비 난방/냉방/PV/HVAC/Net을 비교한다.
- 오프라인 개선이 시뮬레이션에서도 재현되는지(순위 일치)를 기록한다.

## Strategy 2 개선안 (PV/냉방/난방 30개 분해 예측)

### 현황 (fig38_1, 시뮬레이션)
| 연간 (kWh) | 태양추적 | ST1 | ST2 |
|---|---|---|---|
| 난방 부하 | 38,066 | 33,732 | 36,710 |
| 냉방 부하 | 54,568 | 53,654 | 55,940 |
| PV 발전 | 38,074 | 35,841 | 36,937 |
| HVAC 전력 | 33,416 | 31,377 | 33,330 |
| Net Energy | −4,658 | −4,463 | −3,606 |

ST2는 ST1만큼 냉난방을 줄이지 못했고 PV도 태양추적보다 적어 net이 가장 나쁘다. (시뮬레이션 설정이 ST1과 동일한지는 아직 확인하지 않았다.)

### 원인 (예측 CSV `annual_tide_strategy{1,2}_optimal_angles.csv`로 확인)
1. **각도 간 순위를 못 맞힌다.** 한 시각 안에서 10개 각도의 예측/정답 상관은 낮 ST1 0.64, ST2 0.48이고 밤 ST1 0.58, ST2 0.20이다. 낮의 최적-최악 각도 net 차이(평균 0.46)가 net 예측 MAE(ST1 0.50, ST2 0.63)와 비슷하다.
2. **세 예측의 오차가 합쳐진다.** `net = 냉방/3.0 + 난방/2.5 − PV`에서 냉방(R² 0.74)·난방(0.70)이 PV(0.82)보다 부정확하고, 각도별 오차가 독립적이라 argmin이 흔들린다. ST1은 net을 직접 맞춰 오차가 일부 상쇄된다.
3. **밤 편향.** 밤에 ST2는 net을 평균 −0.053 낮게 예측한다. 정답은 0 이상인데 예측은 −0.1~−0.19인 샘플이 보인다. 밤 PV는 0이라 냉난방 예측 오류가 그대로 드러나며, 12/26 밤 각도가 불규칙하게 튀는 원인으로 보인다.
4. **이론 한계.** 정답 라벨 기준 oracle이 태양추적보다 낮 합계로 약 8% 좋을 뿐이다(−12,872 대 −11,944). 모델이 고른 각도는 ST1(−10,630), ST2(−9,921) 모두 태양추적보다 나쁘다.

### 개선 실험
| 실험 | 내용 | 재학습 |
|---|---|---|
| S2-A1 | 밤 각도 고정(0° 또는 90°). 밤 오류 제거 (Phase A3와 동일) | 불필요 |
| S2-A2 | 하이브리드: 태양추적을 기본으로, ST2가 ε 이상 이득을 예측할 때만 덮어씀 | 불필요 |
| S2-A3 | 지평선 집계(향후 k스텝 평균) 후 argmin | 불필요 |
| S2-B1 | 각도 평균(공통) + 각도 편차를 따로 예측 (PV, 냉방, 난방 각각). 편차 채널 가중치 ↑ | 필요 |
| S2-B2 | 조합된 net으로 soft-argmin 결정 손실(`Σ softmax(−β·net_pred)·net_true`)을 추가해 순위를 직접 학습 | 필요 |
| S2-B3 | 냉난방은 합쳐서 "HVAC 전기"(`냉/3.0+난/2.5`) 한 채널로 예측해 오차 합성 단계를 줄임 (PV + HVAC 2채널) | 필요 |
| S2-B4 | ST1+ST2 앙상블: 두 net 예측의 평균으로 argmin | 불필요 |
| S2-C | Phase C의 입력 특성(각도별 입사각/면일사량, 방위각 sin/cos, future covariate)을 ST2에도 적용 | 필요 |
| S2-D | 체크포인트 선택을 val MSE 대신 오프라인 net(의사결정 지표)로 변경, 시드 앙상블 | 필요 |

- 우선순위: S2-A1/A2/A3/B4(재학습 없음) → S2-B1~B3 → S2-C/D.
- 수정: `train_tide.py`의 `STRATEGY_2_TARGETS`와 손실, `predict_annual_tide.py`의 strategy 2 조합 구간(`net_pred = cool/3.0 + heat/2.5 − pv`).
- 평가: ST1과 같은 의사결정 지표(예측 각도의 true net 합, PV 합, 냉난방 합, regret)를 낮/밤으로 나눠 기록한다. 구성요소별(PV, 냉방, 난방) 각도 간 상관도 함께 본다. 이 분해는 아직 하지 않았다.
- 시뮬레이션은 오프라인에서 태양추적(−6,237)과 ST1(−4,895)을 모두 넘는 후보만 돌린다.

## 성공 기준
1. 오프라인: net이 태양추적(−6,237)보다 작다.
2. 시뮬레이션: net < −4,658 kWh, PV가 태양추적 대비 큰 폭으로 줄지 않음(손실 대비 이득 확인).
3. 모든 실험이 `docs/tide_experiment_log.md`에 표로 남는다. (재현 명령 포함)

## 수정/신규 파일 요약
- 수정: `ai_model/tide/train_tide.py`, `predict_annual_tide.py`, `evaluate_tide.py`, `figure/code/fig38_tide_strategy1_vs_strategy2_energy_comparison.py`
- 신규: `ai_model/tide/decision_metrics.py`, `ai_model/tide/data_preprocessing/add_physics_features.py`, `docs/tide_experiment_log.md`
- 재사용: `ContiguousBlockTiDEDataset`, `validate()`, `run_training()`(`train_tide.py`), `bipv_suntracking_angles_annual.csv`(룰베이스), `run_case3_south_tide_sim.py`, `data/predictions/*_optimal_angles.csv`

## 검증 방법
- Phase 0: 재현 수치가 위 표(−4,895 / −6,237 / −7,177)와 일치하는지 확인.
- 각 Phase: 같은 test 구간에서 의사결정 지표 표를 출력해서 전 단계와 비교.
- 마지막: 시뮬레이션 `*_annual_summary.json`을 fig38 스크립트로 읽어 그림/수치 확인.
- 재학습 후 체크포인트는 기존 것을 덮어쓰지 않고 이름을 구분해 저장한다. (예: `tide_strategy1_expB1_best.pt`)

## 리스크
- 오프라인 지표와 시뮬레이션의 차이(태양추적에서만 1,578 kWh)가 커서 오프라인 개선이 그대로 나오지 않을 수 있다.
- lookback에 실제값을 쓰는 현재 방식은 폐루프에서 낙관적일 수 있다. (C5로 확인)
- 각도 간 차이가 본질적으로 작아 모델이 구분할 수 있는 한계가 있을 수 있다. 이 경우 Phase A(후처리)와 하이브리드(A2)가 현실적인 해법이다.

# fig38 이후 작업 정리 (2026-09-22 ~ 2026-10-08)

- 작성일: 2026-10-09
- 범위: `figure/plot/fig38_tide_strategy1_vs_strategy2_energy_comparison/` (9/22 16:55)를 그린 이후 진행한 모든 작업
- Net energy 정의: `냉방/3.0 + 난방/2.5 − PV` (kWh, 10개 zone 합, 10분 간격 52,560 step)
- 각도 정의: tilt = 90° − angle → **0° = 패널 수직(벽에 붙음)**, **90° = 패널 수평**

---

## 0. 한눈에 보기

| 시점 | 무엇을 했나 | 핵심 결과 |
|---|---|---|
| 9/22 | fig38: 태양추적 vs TiDE | 태양추적 −4,658 < TiDE S1 −4,463 → **TiDE가 짐** |
| 9/29~10/1 | 플러그인 분리, 겨울밤 0°, 데이터셋 점검, fig37·fig38_1·fig38_2 | 겨울밤 각도는 부하에 영향 없음. S1/S2 모두 case3 섞인 증강 데이터로 학습됐음 확인 |
| 10/1~10/4 | Phase 0 (case3 고정각 10개 + oracle) | 결과에서 **냉방이 각도와 무관** → case3 모델링 버그 2개 발견 |
| 10/4~10/6 | case3 IDF 수정, case2와 검증, 사이징·반사 진단 | 수정 IDF가 case2와 일치. 반사·사이징 문제 정리 |
| 10/6 | (다른 세션) lookback 144 → 36 | 오프라인에서 lb36이 우수 → 재학습, 연간 각도 산출 |
| 10/6~10/7 | case2 연간 재실행, case3 동적 실행 | TiDE가 태양추적을 이김. Simple PV 6배 버그 발견 |
| 10/7~10/8 | One-Diode로 재실행, 30° 대조군 | **최종: TiDE S1 −3,167 / 고정30° −2,924 / S2 −2,735 / 태양추적 −2,092** |

**결론 요약**
1. fig38에서 TiDE가 진 주원인은 **평가에 쓴 case3 모델의 버그**였다. 열적 관성은 부차적이었다.
2. 버그를 고치고 다시 평가하니 **TiDE S1이 태양추적보다 1,075 kWh 좋다**.
3. 열적 관성 효과는 실제로 있다. 각도를 자주 바꾸는 TiDE에서만 **난방이 700~1,160 kWh 늘어난다**.
4. 다만 **고정 30°와 비교하면 S1은 243 kWh만 좋고, S2는 오히려 나쁘다.**

---

## 1. 출발점: fig38 (9/22)

| 연간 (kWh) | 태양추적 | TiDE S1 |
|---|---|---|
| 난방 | 38,066 | 33,732 |
| 냉방 | 54,568 | 53,654 |
| PV | 38,074 | 35,841 |
| HVAC 전력 | 33,416 | 31,377 |
| **Net** | **−4,658** | **−4,463** |

- **나타난 현상:** TiDE는 HVAC를 2,039 kWh 줄였지만 PV를 2,233 kWh 잃었다. 그래서 net에서 태양추적에 졌다.
- **사용자 가설:** 특정 시점의 부하는 이전 시간의 영향(열적 관성)을 받는다. 그런데 모델은 timestep마다 argmin만 하므로 최적이 아니다.
- **평가 모델:** case3 (`case_idf/case3_v3_KS/case3_v3_south.idf`). 10개 각도 형상을 모두 넣고, Python 플러그인이 투과율로 켜고 끈다.
- **학습 데이터:** case2 (`case_idf/case2_KS/case2_{각도}.idf`). 각도마다 IDF가 하나씩 있다.

> 참고: fig38의 S1 막대(−4,463)는 9/19 모델(증강 이전) 결과였다. 9/22에 증강 데이터로 학습한 체크포인트로 S1을 다시 예측해 재실행했다.

---

## 2. 9/29 ~ 10/1: 정리 작업과 추가 분석

### 2.1 제어 플러그인 분리, 겨울밤 0° (9/29)
- 계획서: `docs/plan_winter_night_angle_0.md`
- 플러그인을 둘로 나눴다.
  - `model_pythonpluginsystem_sun_tracking.py`: 태양추적. 11~3월 밤은 0°로 바꿨다.
  - `model_pythonpluginsystem_ai.py`: AI 스케줄 CSV를 읽는다.
- `model_pythonpluginsystem_fixed.py` 등 옛 파일은 삭제했다.

### 2.2 학습 데이터셋 점검, 폴더 정리 (9/30)
- `case2_ks_bipv_tide_dataset.csv`는 **증강본**이다.
  - `build_case2_case3_augmented_dataset.py`가 만든다.
  - 태양추적이 더 좋은 시각에는 고정각 컬럼 값을 case3 값으로 덮어썼다.
- 9/21 체크포인트(S1, S2)를 검증했다. scaler와 val_loss를 비교해 보니 **둘 다 이 증강 데이터로 학습된 것**이 확인됐다.
  - ⚠ 이후 case3에 버그가 있었음이 밝혀졌으므로, **현재 S1/S2 학습 데이터에는 버그 있는 case3 값이 섞여 있다**.
- case3 전용 데이터셋과 모델도 시도했다.
  - 각도별 후보를 출력하지 않아서 최적 각도를 고를 수 없었다.
  - 그래서 삭제했다.
- 폴더 정리 후 커밋: `7229093`, `17103ac`
- 개선 계획 문서: `docs/plan_tide_improvement.md`
  - 오프라인(라벨 기준) Net: 태양추적 −6,237, S1 −4,895, S2 −4,038, oracle −7,177
  - 진단 1: 각도 간 차이(표준편차 0.071)가 시간에 따른 공통 변동(1.73)에 묻힌다.
  - 진단 2: 추론할 때 lookback에 실제 10각도 net 값을 넣는다. 실제 제어에서는 이 값을 알 수 없다.

### 2.3 겨울밤 0° 태양추적 시뮬레이션, fig37 (10/1)
- 실행 결과: `case_analysis/bipv_variation/5zone_NSEW_korean/case3_v3_south_winter0_summer90`
- 기존 태양추적 결과와 **시간별 값까지 완전히 같았다**. 즉 밤 각도는 부하에 영향이 없다.
  - 10/6에 수정 IDF로 다시 확인했다. 1/1~1/14, 0° vs 90° 모두 5,862.8 kWh로 같았다.
  - EnergyPlus에서 차양 표면은 일사만 가린다. 그래서 밤에는 효과가 0이다.
- 새 각도 CSV: `data/bipv_suntracking_angles_annual_winter0_summer90.csv`
- fig37: 대표일 12/26, 7/21. AI 선은 S2 스케줄로 그렸다.

### 2.4 fig38_1, fig38_2 (10/1)

| 연간 (kWh) | 태양추적 | S1 | S2 |
|---|---|---|---|
| 난방 | 38,066 | 33,732 | 36,710 |
| 냉방 | 54,568 | 53,654 | 55,940 |
| PV | 38,074 | 35,841 | 36,937 |
| **Net** | **−4,658** | −4,463 | −3,606 |

- fig38_2(대표 주)
  - 겨울(12/23~29): S1이 가장 좋았다.
  - 여름(7/18~24): 태양추적이 가장 좋았다. S1이 진 원인은 PV 감소였다.
- S2 부진 원인
  - 각도 간 차이(0.46)가 예측 MAE(S1 0.50, S2 0.63)보다 작다.
  - S2는 밤 예측의 각도 간 상관이 0.20으로 낮다.
- ⚠ 이 그림들은 모두 **버그 있는 case3** 결과다. 지금은 무효다.

---

## 3. 10/1 ~ 10/4: Phase 0 — 원인 분해 시도

- 계획: `C:\Users\taegyu\.claude\plans\ml-piped-clock.md`
  - Phase 0: case3로 고정각 10개와 oracle을 돌려 원인을 나눈다.
  - Phase 1~4: 시간가변 각도 데이터 생성, TiDE 재정식화, MPC
- 실행: case3 고정각 0~90° 연간 10개, 태양추적, 현재 S1/S2, oracle(timestep별 net 최소), oracle_pvmax. 총 15개.
- 결과 (버그 있는 case3): oracle 오프라인 −8,728, 동적 실행 −7,624, oracle_pvmax −6,002
- 보고서: `bipv_experiments/docs/phase0_results.md`
  - ⚠ **무효**. 버그 있는 case3 기준이라 다시 써야 한다.
- **결정적 발견 (사용자 지적)**
  - 고정각 결과에서 **0°를 빼면 냉방 부하가 각도와 무관하게 거의 같았다**.
  - PV가 만드는 그늘이 반영되지 않는다는 뜻이다. → case3 모델링을 조사했다.

---

## 4. 10/4 ~ 10/6: case3 모델링 버그 수정과 검증

### 4.1 발견한 버그 2개

| # | 버그 | 증상 | 수정 |
|---|---|---|---|
| 1 | 0° 차양이 남측 벽과 같은 평면(y=0) | EnergyPlus가 그림자를 계산하지 않음. 0°가 차양 없음과 같음 | case2처럼 y=−0.1로 이동 |
| 2 | `SimpleSkyDiffuseModeling` + 투과율 스위칭 | 산란일사 차폐를 각도가 바뀌어도 다시 계산하지 않음 → 냉방이 각도와 무관 | `DetailedSkyDiffuseModeling` |

- 수정 IDF: `bipv_experiments/idf/case3_v3_south_fixed.idf`
  - 생성 스크립트: `bipv_experiments/idf/build_case3_v3_south_fixed.py`
  - 원본 IDF는 건드리지 않았다.
- 10개 각도 모두 형상이 case2와 같음을 확인했다.

### 4.2 진단으로 정리한 평가 조건

| 항목 | 문제 | 결정 |
|---|---|---|
| HVAC 사이징 | Ideal Loads 자동 사이징이 사이징 시점의 차양에 따라 달라진다. 이코노마이저 외기량 한도도 함께 바뀐다 | **10개 각도 사이징 결과 중 최대값으로 고정** (`bipv_experiments/sizing/case2_max_over_angles.eio`) |
| 반사 (`FullExteriorWithReflections`) | 반사 계산은 투명 처리된 차양도 불투명 반사체로 취급한다 (Engineering Reference ch.6). case3에서는 쓸 수 없다 | 사용자 결정: **반사는 반드시 켠다**. 그래서 case2(반사 켬)를 기준으로 하고 case3는 반사를 끈다. 아래 방법 C로 합친다 |
| PV 모델 | 사용자 결정: **반드시 One-Diode** | §7 참고 |

- 검증 결과 (수정 case3 vs case2, 같은 조건)
  - PV 차이 0.0%
  - 냉방 차이 −1.2%. zone 대부분이 정확히 일치했다.
  - 창 직달·산란 일사도 일치했다.
- 반사 켬 vs 끔 (case2 기준)
  - PV ±3%, 난방 −4~8%, 냉방 +5~12%
  - 반사를 끄면 차양의 냉방 저감 효과가 절반이 된다.
  - timestep별 최적 각도 라벨은 32.5%만 일치한다.

### 4.3 작업 폴더 규칙
- 사용자 지시: "기존 파일 수정·삭제 금지, 루트에 폴더 따로 만들어 실행"
  - 그 뒤로 모든 실험은 `bipv_experiments/`에서 했다.
- 앞서 수정했던 원본 파일 3개는 복원했다.
  - `build_case2_ks_tide_dataset.py`, `model_pythonpluginsystem_ai.py`, `run_case3_south_tide_sim.py`
- 주요 파일

| 파일 | 역할 |
|---|---|
| `bipv_experiments/runner.py` | 독립 실행기. 옵션: 사이징 고정, solar distribution, sky diffuse, PV 모델 등. 배치 JSON 실행 |
| `bipv_experiments/bipv_schedule_plugin.py` | 날짜 기반 인덱스로 스케줄 CSV를 재생하는 플러그인 |
| `bipv_experiments/analysis/` | SQL 추출, 고정각 데이터셋, oracle 스케줄, 최종 비교 스크립트 |
| `bipv_experiments/schedules/` | 각도 스케줄 CSV, 배치 JSON |
| `bipv_experiments/runs/` | 모든 실행 결과 |

---

## 5. 10/6 ~ 10/7: case2 연간 재실행과 평가 방법 C

### 5.1 case2 고정각 연간 (반사 켬, 사이징 고정, One-Diode)

| 각도 | 0 | 10 | 20 | **30** | 40 | 50 | 60 | 70 | 80 | 90 |
|---|---|---|---|---|---|---|---|---|---|---|
| Net | −2,186 | −2,872 | −2,182 | **−2,924** | −2,600 | −1,999 | −1,192 | +115 | +1,998 | +4,411 |

- 데이터셋
  - `bipv_experiments/analysis/c2_RF_fixed_angle_dataset.csv` (반사 켬)
  - `c2_FE_fixed_angle_dataset.csv` (반사 끔)
- 스티칭: 스케줄이 고른 각도의 고정각 값을 timestep마다 가져와 합한다. 열적 관성은 무시된다.
  - 태양추적 −2,170, S1 −3,697, S2 −3,044, oracle −4,355
  - 원본 case2 데이터(자동 사이징)로 해도 순위는 같다. 태양추적 −2,359, S1 −3,919, S2 −3,231.
  - → **fig38에서 TiDE가 진 것은 평가에 쓴 case3 버그 때문**이다.

### 5.2 평가 방법 C (혼합)
```
최종 부하 = case2 반사켬 스티칭
          + [ (case3 동적 − case2 반사끔 스티칭)            ← 관성 효과 + 모델 차이
            − (case3 30°고정 − case2 반사끔 30°고정) ]      ← 모델 차이 (대조군)
최종 PV   = case2 반사켬 스티칭   (PV는 관성 없음, 완전히 더해짐)
```

### 5.3 기타
- fig39_1을 7/21로 다시 그렸다: `bipv_experiments/figures/fig39_1_summer_cooling_load_all_zones_jul21/`
  - 주황색 선(태양추적)은 아직 버그 있는 case3 결과다.

---

## 6. 10/6: (다른 세션) lookback 144 → 36

스크립트 폴더: `bipv_experiments/tide_c5/`

| 단계 | 스크립트 | 결과 (test 구간 net 합, 작을수록 좋음) |
|---|---|---|
| 절제 실험 (S1, 3시드) | `c5_ablation.py` | L144 −558 / **이력 가림 −411** / L36 −697 / L72 −807. oracle −842, 고정30° −372 |
| lookback 스윕 (5시드, 구간 통일) | `c5_lookback_sweep.py` | L18 −610 / L36 −628 / L72 −609 / **L144 −574 (최하)** |
| lb36 재학습 (S1/S2, 5시드) | `retrain_lb36.py` | S1 −538 → −681, S2 −405 → −688. 각도 MAE S1 21.6°→18.6°, S2 19.2°→15.0° |
| 연간 각도 산출 (5시드 앙상블) | `predict_annual_lb36.py` | `tide_c5/predictions/bipv_optimal_angles_annual_strategy{1,2}_lb36.csv` |

- 해석
  - 이력을 가리면 성능이 크게 떨어진다. 즉 모델이 실제 제어에서는 알 수 없는 "10개 각도 전체의 과거 net"에 의존한다.
  - lookback 18~72 사이 차이는 시드 노이즈 수준이다. 그래서 36을 채택했다.
- 그림: `bipv_experiments/figures/fig37_lb36_st{1,2}_representative_days.{png,svg}`
- 시뮬레이션: `runs/c3_FE_tide_s1_lb36`, `c3_FE_tide_s2_lb36`
  - ⚠ **Simple PV로 실행돼 무효**다 (§7).
  - **One-Diode로는 아직 돌리지 않았다.**

---

## 7. 10/7: PV 모델 문제

| 문제 | 내용 | 조치 |
|---|---|---|
| One-Diode 수치 실패 | `c2_FE_A90` 실행이 2/9 11:50에 멈췄다 ("failed to find maximum power point", 전류 −4,027 A) | 물리적 원인은 없다. 맑은 겨울 정오였고 직전 PV 96개 출력도 모두 정상이었다. E+ 뉴턴 반복법이 개방전압 근처에서 발산한 것이다. 같은 90°라도 반사 켬 실행 2개는 1년을 완주했다 |
| Simple PV 6배 버그 | Simple PV는 각도별 가용성 스케줄을 무시한다. 그래서 Facility PV가 960개 생성기 전체의 합이 된다 (7월 2일 진단에서 5.87배) | case3 동적 실행의 `summary.json` PV·net은 무효. 결과: `runs/corrected_pv_summary.csv` (참고용) |
| 사용자 결정 | **PV는 무조건 One-Diode** | Simple로 돌던 30° 대조군을 중지하고, 4개를 One-Diode로 다시 실행 |

- One-Diode 재실행 4개는 모두 오류 없이 완주했다 (각 15~16시간).
  - `runs/c3_FE_fixed_A30_od`, `c3_FE_suntracking_od`, `c3_FE_tide_s1_od`, `c3_FE_tide_s2_od`
- 30° 대조군: case3와 case2 사이에 **PV 차이는 0**, 난방 +1,844, 냉방 −2,242 kWh
  - 이전에 모든 스케줄에 비슷하게 붙던 보정의 대부분이 관성이 아니라 이 모델 차이였다.

---

## 8. 최종 결과 (10/8, One-Diode, 방법 C)

스크립트 `bipv_experiments/analysis/final_onediode_comparison.py` → `final_onediode_comparison.csv`

| 스케줄 | PV | 난방 (관성 보정) | 냉방 (관성 보정) | 스티칭 net | **최종 net** |
|---|---|---|---|---|---|
| **TiDE S1** | 35,609 | 39,687 (+1,161) | 49,702 (+199) | −3,697 | **−3,167** |
| 고정 30° | 35,855 | 40,237 (0) | 50,508 (0) | −2,924 | **−2,924** |
| TiDE S2 | 35,699 | 39,938 (+704) | 50,968 (+82) | −3,044 | **−2,735** |
| 태양추적 | 35,557 | 40,326 (+6) | 52,004 (+226) | −2,170 | **−2,092** |

- **S1과 태양추적:** S1이 1,075 kWh 좋다.
- **S1과 고정 30°:** S1이 243 kWh만 좋다. S2는 고정 30°보다 나쁘다.
- **관성 효과**
  - 거의 전부 난방에서 나타난다.
  - 각도를 자주 바꾸는 TiDE에서만 생긴다.
  - S1은 관성 때문에 약 500 kWh를 잃었다. 사용자 가설이 확인됐다.
- **PV 검증:** case3 One-Diode PV와 case2 스티칭 PV의 차이는 0~157 kWh(0.4% 이하)다.

---

## 9. 무효가 된 결과 (인용 금지)

| 결과 | 무효 이유 |
|---|---|
| fig38, fig38_1, fig38_2, fig36/37의 net 수치 | 버그 있는 case3 |
| `bipv_experiments/docs/phase0_results.md`, oracle −7,624 등 | 버그 있는 case3 |
| fig39_1의 Kinetic(주황) 선 | 버그 있는 case3 |
| `runs/c3_FE_*` (`_od` 제외), `c3_FE_tide_s*_lb36`의 `summary.json` | Simple PV (PV 6배) |
| `runs/corrected_pv_summary.csv` (태양추적 −8,611 등) | Simple PV 기준 (One-Diode보다 PV +14%) |

---

## 10. 남은 과제

1. **lb36 스케줄을 One-Diode로 case3 실행**하고, 방법 C로 위 표에 추가한다.
2. **TiDE를 다시 학습한다.** 현재 S1/S2는 버그 있는 case3 값이 섞인 증강 데이터로 학습됐다. case2 반사 켬과 사이징 고정 데이터로 다시 학습하는 것을 검토한다.
3. **관성을 고려한 결정 방식**을 도입한다. 각도 전환 페널티, 수평선 최적화(MPC) 등이다. 그래야 고정 30°와의 격차를 벌릴 수 있다.
4. **lookback 입력 문제를 해결한다.** 실제 제어에서는 고른 각도의 이력만 존재한다.
5. `bipv_experiments/docs/phase0_results.md`를 수정된 결과로 다시 쓴다. fig38 계열과 fig39_1 주황 선도 다시 그린다.
6. `runner.py`의 summary가 Facility PV를 쓰는 문제를 정리한다. 지금은 One-Diode만 쓰므로 영향은 없다.

# TiDE (Time-series Dense Encoder) BIPV Net Energy Optimization Repository

본 디렉터리(`ai_model/tide/`)는 Kinetic BIPV 및 동적 차양 시스템의 **Net Energy 최소화**를 위한 **Google TiDE 시계열 신경망 모델 아키텍처, 훈련 및 추론 스크립트, 체크포인트, 데이터셋 및 연간 예측 결과물**을 체계적으로 통합 관리하는 전용 폴더입니다.

---

## 1. 디렉터리 구조 및 파일 설명

```text
ai_model/tide/
├── tide_model.py                # TiDE 신경망 구조 (DenseMLP, Residual Block, Future/Past Covariate 인코더-디코더)
├── train_tide.py                # 시계열 블록 기반 훈련 파이프라인 (전략 1, 전략 2 지원)
├── predict_annual_tide.py        # 연간(52,560 스텝) 최적 PV 각도 시퀀스 추론 및 스케줄 생성 스크립트
├── evaluate_tide.py             # 미학습 테스트 세트(Test Set) 정량 평가 스크립트 (MAE, RMSE, R², Hit Rate, Regret)
│
├── checkpoints/                 # 학습 완료된 모델 가중치 및 정규화 스케일러
│   ├── tide_strategy1_best.pt   # 전략 1(End-to-End Net Energy) 최적 가중치
│   ├── tide_strategy1_scaler.json
│   ├── tide_strategy2_best.pt   # 전략 2(물리 구성요소 30개 분해) 최적 가중치
│   └── tide_strategy2_scaler.json
│
├── data/
│   ├── dataset/                 # TiDE 학습 및 검증용 마스터 데이터셋
│   │   ├── case2_ks_bipv_tide_dataset.csv               # 동적 케이스(case3) 결합 증강 마스터 데이터셋 (52,560행)
│   │   ├── case2_ks_bipv_tide_dataset_static_backup.csv  # 증강 전 정적 원본 백업본
│   │   ├── case2_ks_train.csv                           # 학습 세트 (매월 1~21일 블록, 36,288행)
│   │   ├── case2_ks_val.csv                             # 검증 세트 (매월 22~25일 블록, 6,912행)
│   │   └── case2_ks_test.csv                            # 테스트 세트 (매월 26~말일 블록, 9,360행)
│   │
│   └── predictions/             # 연간 최적 각도 및 평가 예측 결과물
│       ├── annual_tide_strategy1_optimal_angles.csv     # 전략 1 연간 예측 각도 및 Net Energy (52,560행)
│       ├── annual_tide_strategy2_optimal_angles.csv     # 전략 2 연간 예측 각도 및 Net Energy (52,560행)
│       ├── bipv_optimal_angles_annual.csv               # EnergyPlus 시뮬레이션 주입용 최종 스케줄
│       ├── eval_strategy1_results.json / .csv           # 전략 1 테스트 세트 평가 결과
│       └── eval_strategy2_results.json / .csv           # 전략 2 테스트 세트 평가 결과
│
└── data_preprocessing/          # 데이터셋 구축 및 전처리 유틸리티
    ├── build_case2_ks_tide_dataset.py                   # 정적 각도(0°~90°) 전수 시뮬레이션 기반 초기 데이터셋 생성기
    ├── build_case2_case3_augmented_dataset.py           # 동적 태양 추종(case3) 결합 데이터 증강기
    ├── compute_suntracking_angle_schedule.py            # 태양고도 추종 각도 스케줄 생성 (출력: 루트 data/bipv_suntracking_angles_annual.csv)
    └── split_case2_ks_dataset.py                        # 시계열 계절 블록 분할기
```

---

## 2. 주요 스크립트 실행 방법

```bash
# 1. 전략 2 모델 훈련 (30 Epochs, GPU)
uv run python ai_model/tide/train_tide.py --strategy 2 --epochs 30 --device cuda

# 2. 연간 최적 각도 스케줄 추론 (52,560 타임스텝)
uv run python ai_model/tide/predict_annual_tide.py --strategy 2

# 3. 미학습 테스트 세트 정량 성능 평가
uv run python ai_model/tide/evaluate_tide.py --strategy 2
```

---

## 3. 최신 성능 성적표 (전략 2 기준, Test Set)

* **PV 발전량 예측 설명력 ($R^2$)**: **`0.8157`** (MAE `0.33 W`, RMSE `0.53 W`)
* **냉방 부하 예측 설명력 ($R^2$)**: **`0.7447`** (MAE `0.96 W`, RMSE `1.91 W`)
* **난방 부하 예측 설명력 ($R^2$)**: **`0.7017`** (MAE `0.67 W`, RMSE `1.43 W`)
* **최적 각도 예측 오차 (Angle MAE)**: **`21.49°`** (전략 1의 32.1° 대비 33% 개선)
* **허용 오차 적중률 (±10° 이내)**: **`45.89%`**
* **평균 에너지 손실 (Regret)**: **`0.05 W`**

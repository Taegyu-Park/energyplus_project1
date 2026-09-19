# 키네틱 BIPV 중복 서피스 광학(주광 조도) 검증 계획서
> **목적**: EnergyPlus에서 키네틱 BIPV를 구현하기 위해 각도별로 10개씩 중복 배치된 Shading 서피스(1개 활성화 + 9개 투명 스케줄) 방식이 실내 작업면 조도(Daylight Illuminance)를 왜곡(과대 또는 과소평가)하는지 여부를 실증 검증함.

> [!IMPORTANT]
> **실행 순서 안내 (최우선 선행 단계: Step 1)**  
> 본 검증은 실내 조명 제어 적용 계획인 **[daylightin_control.md](file:///c:/Users/taegyu/Codes/energyplus_project1/daylightin_control.md)**를 실행하기 전에 **반드시 가장 먼저 완료해야 하는 '선행 필수 단계(Step 1)'**입니다.  
> 1. **Step 1 (본 문서)**: 1일 테스트 시뮬레이션을 통해 10개 서피스 중복 배치의 조도 왜곡 여부를 먼저 검증.
> 2. **Step 2 ([daylightin_control.md](file:///c:/Users/taegyu/Codes/energyplus_project1/daylightin_control.md))**: 검증 결과 이상이 없음을 확인하거나 보정 방안을 확정한 후, 최종 모델에 본격적인 주광 연동 조명 디밍 제어 시스템을 구축.

---

## 1. 비교 대상 모델 선정 및 정합성 검증

PV 설치 방위(Configuration)가 1:1로 완벽히 일치해야 광학적 비교가 성립하므로, **남측 외벽(Y=0)에 동일하게 96개 모듈 그리드로 배치된 모델 쌍(Pair)**을 비교 대상으로 확정합니다.

| 구분 | 모델 파일 경로 | Shading 서피스 수 | 모델 특징 및 검증 역할 |
| :---: | :--- | :---: | :--- |
| **모델 A<br>(검증 대상)** | `case_idf/case3_v3_KS/case3_v3_south.idf` | 총 960개<br>(각도당 96개 × 10개 각도) | - **남측 전용 키네틱 BIPV 모델**<br>- 10개 각도 서피스가 겹쳐져 있음<br>- PythonPlugin으로 실시간 각도 추종 |
| **모델 B<br>(정답 기준)** | `case_idf/case2_KS/case2_70.idf`<br>*(또는 case2_40.idf)* | 총 96개<br>(70° 각도 단독 96개) | - **남측 전용 정적 단독 모델 (Ground Truth)**<br>- 겹쳐진 다른 각도 서피스가 0개이며 물리적으로 70° 단독 설치 |

> **[참고: case3_v3_max를 제외한 이유]**  
> `case3_v3_max.idf`는 남측(780)뿐 아니라 동측(90), 서측(90) 등 3면에 분산 배치된 모델이므로, 남측 전용 단독 모델인 `case2_XX`와 1:1 비교 시 PV 배치 불일치로 인한 오차가 발생합니다. 따라서 남측에만 96개가 동일하게 배치된 `case3_v3_south.idf`를 사용합니다.

---

## 2. 시뮬레이션 설정 규격 (1일 초고속 검증)

장시간 소요되는 연간 시뮬레이션 대신, 일사량이 풍부하고 태양 고도가 높은 **여름철 대표 맑은 날 1일(7월 21일)**만 지정하여 약 10~20초 내에 시뮬레이션을 완료합니다.

### 2.1. RunPeriod 설정
```idf
RunPeriod,
    1-Day Daylight Validation,    !- Name
    7,                            !- Begin Month (7월)
    21,                           !- Begin Day of Month (21일)
    2006,                         !- Begin Year
    7,                            !- End Month (7월)
    21,                           !- End Day of Month (21일)
    2006,                         !- End Year
    Friday,                       !- Day of Week for Start Day
    No, No, No, Yes, Yes;
```

### 2.2. Daylighting Controls 객체 구성 (남측 외주부 존)
1층 및 2층 남측 외주부 존(`BIPV_office_1_S`, `BIPV_office_2_S`) 중심부 작업면에 센서를 배치합니다:
- **기준점 위치 (`Daylighting:ReferencePoint`)**:
  - 1층: $X = 16.0\,\text{m}$, $Y = 2.5\,\text{m}$, $Z = 0.75\,\text{m}$ (창문에서 2.5m 들어간 데스크 높이)
  - 2층: $X = 16.0\,\text{m}$, $Y = 2.5\,\text{m}$, $Z = 4.75\,\text{m}$
- **제어기 (`Daylighting:Controls`)**:
  - `Daylighting Method`: **`SplitFlux`**
  - `Lighting Control Type`: `ContinuousOff`
  - `Illuminance Setpoint`: `500 lux`

### 2.3. 핵심 출력 변수 (`Output:Variable`)
- `Daylighting Reference Point 1 Illuminance [lux]` (실시간 작업면 조도)
- `Daylighting Lighting Power Multiplier []` (주광에 의한 디밍 비율)
- `Surface Window Transmitted Beam Solar Radiation Rate [W]` (창호 투과 직달일사)
- `Surface Window Transmitted Diffuse Solar Radiation Rate [W]` (창호 투과 확산일사)

---

## 3. 검증 실행 및 대조 방법 (내일 수행 단계)

### Step 1. 테스트용 IDF 복사본 생성
원본 파일을 보존하기 위해 `scratch/daylight_val/` 폴더에 생성:
1. `scratch/daylight_val/val_kinetic_south.idf` (`case3_v3_south.idf` 기반 + 1일 RunPeriod + Daylighting)
2. `scratch/daylight_val/val_static_70.idf` (`case2_70.idf` 기반 + 1일 RunPeriod + Daylighting)

### Step 2. 1일 시뮬레이션 1회 실행 (각 약 15초 소요)
EnergyPlus 25.2.0 엔진으로 각 케이스 실행:
```powershell
& "C:\EnergyPlusV25-2-0\energyplus.exe" -d scratch/daylight_val/run_kinetic -w EnergyPlus/weather/KOR_Kwangju.IWEC.471560_IWEC.epw scratch/daylight_val/val_kinetic_south.idf
& "C:\EnergyPlusV25-2-0\energyplus.exe" -d scratch/daylight_val/run_static -w EnergyPlus/weather/KOR_Kwangju.IWEC.471560_IWEC.epw scratch/daylight_val/val_static_70.idf
```

### Step 3. 타임스텝별 실내 조도(Lux) 대조 판정
1. 7월 21일 낮 시간대(11:00 ~ 13:00) 중 **키네틱 모델이 70° 루버 각도를 선택한 타임스텝**을 추출합니다.
2. 그 시각의 **키네틱 모델 실내 조도($E_{\text{kinetic}}$)**와 **정적 70° 단독 모델 실내 조도($E_{\text{static\_70}}$)**를 1:1 비교합니다.

---

## 4. 결과 판정 및 후속 조치 기준

- **Case A: 조도 오차 1% 미만 (완벽 일치)**  
  ➜ 10개 겹쳐진 투명 서피스가 광학적으로 아무런 간섭/왜곡을 주지 않음이 실증 입증됨.  
  ➜ 현재의 10개 중복 키네틱 구조 그대로 안심하고 실내 조명 디밍 제어 시스템 구축 진행.

- **Case B: 키네틱 모델 조도가 더 낮게 나오는 경우 (과소평가 발생)**  
  ➜ 투명 상태인 9개의 서피스 형상이 천공 확산광(Sky Diffuse)을 기하학적으로 가리고 있음.  
  ➜ **해결책**: `ShadowCalculation`의 확산광 알고리즘을 `SimpleSkyDiffuseModeling`에서 `DetailedSkyDiffuseModeling`으로 전환하거나, 확산광 투과율 보정 적용.

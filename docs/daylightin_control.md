# Kinetic BIPV 차양 연동 실내 조명 제어(Daylighting Control) 계획

> [!IMPORTANT]
> **실행 순서 안내 (후속 구현 단계: Step 2)**  
> 본 계획(실제 조명 제어 적용 및 모델 반영)은 반드시 **[DAYLIGHTING_VERIFICATION_PLAN.md](file:///c:/Users/taegyu/Codes/energyplus_project1/DAYLIGHTING_VERIFICATION_PLAN.md)**의 **'10개 중복 서피스 광학 왜곡 사전 검증(Step 1)'을 먼저 수행하여 이상이 없음을 확인한 후에 진행**해야 합니다.  
> 만약 사전 검증에서 확산광 과소평가 등 왜곡이 발견될 경우, 해당 보정 설정(예: `DetailedSkyDiffuseModeling`)을 반영한 상태에서 본 계획을 적용합니다.

## 1. 개요 및 배경

현재 [case3_v3_max.idf](file:///c:/Users/taegyu/Codes/energyplus_project1/case_idf/case3_v3_KS/case3_v3_max.idf) 모델은 태양 고도를 실시간 추종하는 외장 키네틱 BIPV 루버(남측 780개, 동/서측 각 90개)가 적용되어 있습니다. 
그러나 실내 조명은 **외부 일사 및 BIPV 차양 각도와 무관하게 고정 타임 스케줄(6.896 W/m², 최대 70% 점등)**로만 동작하고 있습니다.

루버가 태양을 가려 직달일사를 차단하면:
1. **냉방 부하는 감소**하고 **BIPV 발전량은 증가**하지만,
2. **실내 작업면 조도(Daylight Illuminance)가 저하**되어 자연 채광 이용률이 떨어지고 조명 요구도가 증가합니다.

따라서 **차양에 의해 변화하는 실내 조도를 정밀하게 추적하여 조명 에너지를 동적으로 절감/보상하는 조명 제어 시스템** 구축이 필요합니다.

---

## 2. 권장 제어 전략 (2단계 접근법)

### [1단계 - 필수 기반] EnergyPlus 내장 물리 기반 주광 연속 디밍 제어 (Daylighting:Controls)
EnergyPlus의 내부 광학(SplitFlux) 엔진을 이용하여, BIPV 루버의 투과/그림자 효과가 창문을 거쳐 실내 작업면에 도달하는 조도(Lux)를 실시간 계산하고 조명을 연속 디밍(Continuous Dimming)합니다.

- **목표 조도(Setpoint)**: KS A 3011 및 국내 사무실 작업면 표준 기준 **500 lux**
- **디밍 방식**: `ContinuousOff` (자연 채광으로 500 lux 이상 확보 시 최소 전력 10~20%로 낮춘 뒤 완전 소등 가능)
- **센서 위치(Reference Point)**: 
  - 각 외주부 존(South, East, West, North)의 창문 중심선에서 실내 쪽으로 2.5m(외주부 깊이 5m의 1/2 지점), 책상 작업면 높이 **Z = 0.75m (2층은 4.75m)**에 1개씩 배치.
  - 코어 존(Core)은 창문이 없어 주광 효과가 미미하므로 고정 스케줄 유지.
- **조명 객체 분리**: 현재 1개의 `SpaceList`로 일괄 적용된 조명을 **코어 조명**과 **외주부(방위별) 조명**으로 분리 정의.

### [2단계 - 심화 제어] Python Plugin 연동 BIPV-조명 복합 최적 제어 (Trade-off Optimization)
현재 [model_pythonpluginsystem_fixed.py](file:///c:/Users/taegyu/Codes/energyplus_project1/case_idf/case3_v3_KS/model_pythonpluginsystem_fixed.py)의 플러그인은 태양 고도각만을 기반으로 루버 각도를 결정합니다.
- 조도 센서 변수(`Daylighting Lighting Power Multiplier` 또는 `Zone Lights Electric Power`)를 Python Plugin에서 모니터링
- BIPV 각도 변경 시 발생하는 **'BIPV 발전량(+) vs 실내 조명 전력 증가(-)'**의 넷 에너지(Net Energy) 트레이드오프 분석 및 최적 각도 보정 로직 연계.

---

## 3. 사용자 검토 및 결정 필요 사항 (User Review Required)

> [!IMPORTANT]
> **조명 제어 방식 및 목표 조도 설정**
> 1. **목표 조도 수준**: 일반 사무실 표준인 **500 lux**를 권장합니다. 혹시 다른 기준(예: 300 lux 또는 400 lux)을 원하시는지 확인이 필요합니다.
> 2. **디밍 방식 선택**:
>    - **Continuous**: 주광이 충분해도 최소 전력비(보통 10~20%)를 유지하며 감광.
>    - **ContinuousOff (권장)**: 주광이 충분하여 500 lux를 넘어가면 최소 전력비 도달 후 완전히 꺼짐(소등).
> 3. **적용 범위**: BIPV가 설치된 **South, East, West** 및 자연 채광이 들어오는 **North** 외주부(Perimeter) 존에만 주광 제어를 적용하고, 창문이 없는 **Core** 존은 기존 고정 스케줄을 유지합니다.

---

## 4. 세부 작업 계획 (Proposed Changes)

### Component 1: IDF 모델 조명 구조 재구성
#### [MODIFY] [case3_v3_max.idf](file:///c:/Users/taegyu/Codes/energyplus_project1/case_idf/case3_v3_KS/case3_v3_max.idf)
1. **`Lights` 객체 세분화**:
   - `SmallOffice Building_Lighting` 단일 객체를 2개 그룹으로 분리:
     - `Core_Lighting`: 1층/2층 Core Space (기존 스케줄 그대로 유지)
     - `Perimeter_Lighting_1F_S`, `Perimeter_Lighting_1F_E`, `Perimeter_Lighting_1F_W`, `Perimeter_Lighting_1F_N` (2층 포함 각 외주부 존별 분리 또는 존 연동)
2. **`Daylighting:ReferencePoint` 객체 추가 (총 8개)**:
   - 1층 4개 외주부 존 (South, East, North, West) 중심 작업면 (Z=0.75m)
   - 2층 4개 외주부 존 (South, East, North, West) 중심 작업면 (Z=4.75m)
3. **`Daylighting:Controls` 객체 추가 (총 8개)**:
   - Method: `SplitFlux`
   - Control Type: `ContinuousOff`
   - Setpoint: `500 lux`
   - Minimum Input Power Fraction: `0.1` (10%)
   - Minimum Light Output Fraction: `0.1` (10%)
4. **출력 변수(`Output:Variable`) 추가**:
   - `Daylighting Reference Point 1 Illuminance [lux]` (작업면 실시간 조도)
   - `Daylighting Lighting Power Multiplier []` (주광에 의한 조명 감광율)
   - `Zone Lights Electricity Energy [J]` (존별 조명 전력 소비량)

---

### Component 2: Python Plugin 모니터링 연동 (선택적 확장)
#### [MODIFY] [model_pythonpluginsystem_fixed.py](file:///c:/Users/taegyu/Codes/energyplus_project1/case_idf/case3_v3_KS/model_pythonpluginsystem_fixed.py)
- 각 존의 주광 조도 및 조명 소비 전력을 센서로 수집하여 BIPV 발전 출력과 동기화 모니터링.

---

## 5. 검증 계획 (Verification Plan)

### Automated Simulation Verification
- OpenStudio / EnergyPlus 25.2.0 엔진을 통한 시뮬레이션 실행:
  ```powershell
  & "C:\EnergyPlusV25-2-0\energyplus.exe" -d test_lighting_run -w ... case3_v3_max.idf
  ```
- **검증 항목**:
  1. `eplusout.err` 파일에서 Fatal / Severe 에러 0건 확인.
  2. BIPV 루버 각도가 변할 때 작업면 조도(`Daylighting Reference Point Illuminance`)가 그림자에 따라 연동하여 변화하는지 확인.
  3. 맑은 날 낮 시간대에 외주부 조명 전력(`Zone Lights Electricity Energy`)이 스케줄 값(70%) 대비 크게 감광되어 절감되는지 확인.
  4. 야간(일몰 후)에는 주광 제어기가 개입하지 않고 기존 야간 스케줄(18%)로 정상 복귀하는지 확인.

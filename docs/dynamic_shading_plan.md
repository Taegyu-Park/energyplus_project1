# Kinetic BIPV 동적 각도 가변 및 발전량 오차 극복 구현 계획서

이 문서는 EnergyPlus에서 상부 힌지축을 기준으로 동적으로 회전하는 **Kinetic BIPV(가변형 건물일체형 태양광 시스템)**를 구현할 때 발생하는 발전량 계산 오차 문제를 극복하고, 실제 대규모 확장 시 발생하는 시스템 복잡도를 완벽하게 차단하기 위한 최종 실행 계획서입니다.

---

## 🔍 1. 구현 목표 및 제어 사양

### 1.1 가변 힌지 각도 기하학
`gl2.idf`의 shading `BIPV` 객체는 상부 힌지축($Y=0, Z=3$)을 기준으로 수직($0^\circ$, 외벽 밀착)에서 수평($90^\circ$, 기존 설계안)까지 회전 운동을 해야 합니다.
* **회전각 $\theta$ ($0^\circ$ ~ $90^\circ$)에 따른 비고정 정점($V_1, V_4$)의 좌표 공식**:
  * $$Y(\theta) = -3.0 \times \sin(\theta)$$
  * $$Z(\theta) = 3.0 \times \cos(\theta)$$
  * $X$ 좌표는 고정이므로 변하지 않습니다 ($V_1$의 $X=3$, $V_4$의 $X=0$).

### 1.2 BIPV 발전 모듈 사양
* **탑재 모델**: `PhotovoltaicPerformance:EquivalentOne-Diode` (5파라미터 다이오드 물리 모델)
* **특성**: 실시간 셀 온도 및 도달 일사량에 따라 발전 효율이 자동으로 변동함.

---

## 💡 2. 발전량 오차 극복을 위한 최종 솔루션 제안

### 🌟 솔루션 A: 하이브리드 이산화 + 발전기 가동 스케줄(Availability) 실시간 차단 - [최종 채택안]
EnergyPlus의 뛰어난 내장 3D 음영 캐싱 엔진과 5파라미터 다이오드 물리 방정식을 100% 보존하면서, 파이썬 API를 통해 사용되지 않는 각도의 대기 전력 발전량만 완벽하게 계통상에서 분리시키는 하이브리드 전략입니다.

* **구현 메커니즘**:
  1. IDF에 각도별 10개의 회전된 Shading 표면 및 10개의 BIPV 모듈을 기하 공식($Y(\theta), Z(\theta)$)으로 자동 생성하여 각각 BIPV를 부착합니다.
  2. 10개의 각 BIPV 발전기 객체를 **`ElectricLoadCenter:Generators`** 목록에 등록하고, 각각 개별적인 **`Generator Availability Schedule`**을 지정합니다. (예: `BIPV_30_Avail`, `BIPV_40_Avail` 등)
  3. 파이썬 API 콜백 함수(`BeginTimestepBeforePredictor` 단계)에서 현재 목표 각도(예: $40^\circ$)를 계산합니다.
  4. **[핵심 Switch 제어]** 작동해야 하는 $40^\circ$ BIPV의 `Availability Schedule` 값만 `1.0` (정상 가동 활성화)으로 덮어쓰고, **작동하지 않는 나머지 9개 각도 BIPV들의 `Availability Schedule` 값은 실시간으로 `0.0` (가동 완전 정지 / 계통 완전 분리)으로 강제 주입(Actuator Override)합니다.**
* **장점**: 
  * 활성화된 1개의 가변 각도 BIPV만 전기를 생산하며, 해당 각도의 닿는 일사량과 패널 온도에 기반해 **`EquivalentOne-Diode` 물리 방정식이 완벽한 정밀도로 비선형 발전 효율을 능동 연산**합니다.
  * 비가동 상태의 9개 BIPV는 계통에서 완전히 셧다운되므로, 대기 발전량이 완벽하게 소거되어 **Kinetic BIPV 발전에 따른 전력 해석 오차가 정확하게 `0.0W`로 유지**됩니다.
  * 3D 그림자가 창면과 겹치는 고난도의 기하 수학 코딩을 파이썬에 올릴 필요 없이 EnergyPlus의 뛰어난 내장 물리 행렬 캐싱 엔진을 100% 신뢰할 수 있습니다.

---

## ⚡ 3. 대규모 확장 시 '오류 폭발(Error Explosion)' 방지 자동화 전략

이산화(Discretization) 및 Availability 제어 기법을 대규모 가변형 BIPV 시스템(예: 100개 이상의 패널, 수천 개의 형상)에 적용할 때 필연적으로 발생하는 복잡도와 휴먼 에러를 원천 통제하기 위한 시스템적 자동화 규칙입니다. 뼈대 구축부터 파이썬 제어 아키텍처까지 오류 없이 작동하도록 3대 자동화 기둥을 확립합니다.

### 3.1 철저한 '네이밍 컨벤션(Naming Convention)' 확립
객체가 수천 개로 확장되어도 파이썬 정규표현식(Regex)과 루프로 완벽 추적 및 자동 매핑할 수 있도록 뼈대 생성 단계부터 엄격한 컨벤션을 인가합니다.
* **명명 표준안**: `[객체타입]_[패널ID]_[각도]`
* **명명 규칙 예시**:
  * `Surface_BIPV001_A00` (1번 패널, 0도 형상의 Shading Surface)
  * `Surface_BIPV001_A15` (1번 패널, 15도 형상의 Shading Surface)
  * `Generator_BIPV001_A15` (1번 패널, 15도 각도에 연결된 PV 발전기)
  * `AvailSched_BIPV001_A15` (1번 패널, 15도 각도 BIPV의 Availability 스케줄)

### 3.2 절차적 생성(Procedural Generation)을 통한 IDF 구축
수천 개의 3D 정점 및 스케줄 객체를 사람이 직접 타이핑하거나 복사하는 수동 가공 방식은 100% 에러를 유발합니다.
* **해결책**: 라이노/Grasshopper(Honeybee)의 데이터 트리 맵핑 기능을 활용하거나, 파이썬 **EPPy** 라이브러리를 사용하여 `for` 루프 기하 공식을 통해 IDF 뼈대 파일을 코드로 절차적 자동 빌드합니다.
* **효과**: 패널 수가 10개에서 500개로 늘어나도 소스 코드 매개변수 수정 한 번으로 수 초 내에 완벽한 무결성 IDF가 자동 구축됩니다.

### 3.3 파이썬 API: 하드코딩 배제 및 '딕셔너리 매핑(Dictionary Mapping)'
API 콜백 함수 내에서 수천 개 패널의 액추에이터를 개별 제어 시 코드가 무한히 늘어나는 것을 방지하기 위해, **동적 캐싱 딕셔너리 구조**를 설계합니다.

* **동적 제어 로직**: 
  1. 시뮬레이션 최초 1회 기동 시, 파이썬이 엔진 내부를 리딩하여 모든 액추에이터 핸들(메모리 주소)을 패널 ID와 각도별로 캐싱 및 자료구조화합니다.
  2. 시스템 내부 루프를 단 1개의 표준화된 제어식으로 압축하여 가동합니다.

```python
# 1. 딕셔너리를 활용한 동적 핸들 맵핑 캐싱 구조
bipv_system = {
    "BIPV001": { 0: handle_0, 15: handle_15, 30: handle_30 },
    "BIPV002": { 0: handle_0, 15: handle_15, 30: handle_30 }
    # 패널이 1,000개로 확장되어도 이 단일 딕셔너리에 동적으로 자동 담김
}

# 2. 패널 및 각도 수와 무관하게 일정한 O(1) 길이를 유지하는 확장형 제어 루프
for panel_id, angles in bipv_system.items():
    # 타임스텝별 물리 연산을 거친 각 패널 고유의 최적 각도 산출
    optimal_angle = calculate_optimal_angle(sun_altitude, panel_id) 
    
    for angle, handle in angles.items():
        if angle == optimal_angle:
            # 선택된 최적 각도의 발전기 스케줄만 운전 가동 (ON)
            api.exchange.set_actuator_value(state, handle, 1.0) 
        else:
            # 나머지 대기 PV 발전기들은 전기 계통에서 완전 분리 셧다운 (OFF)
            api.exchange.set_actuator_value(state, handle, 0.0) 
```

---

## 💡 4. 주광 연동 조명 제어(Daylighting Control) 및 실시간 에너지 트레이드오프 분석

Kinetic BIPV를 적용할 때 냉난방 부하 및 발전량뿐만 아니라, 자연광 유입 감소에 따른 **실내 인공 조명 에너지 소비량**을 실시간 연동하여 분석합니다.

### 4.1 조명 제어 메커니즘 (`Daylighting:Controls`)
동적 차양의 각도 변화에 따라 실내 조도를 500 lux로 일정하게 유지하기 위한 동적 디밍 제어를 도입합니다.
* **센서 배치**: 실내 작업면 높이인 $Z = 0.8\text{m}$의 존 중앙에 가상 조도 센서 배치 (예: $X=1.5, Y=1.5, Z=0.8$).
* **제어 방식**: **`Continuous/Off`** 디밍 제어
  * 자연광이 풍부하여 실내 조도가 $500\text{ lux}$를 초과하는 경우, 인공 조명 부하를 완전히 차단($0\%$)하여 에너지 소비를 극대화로 차단합니다.
  * 자연광이 부족한 경우, 부족한 lux만큼 조명 출력을 선형 비례적으로 조절(Dimming)합니다.

### 4.2 3차원 에너지 트레이드오프 (Tri-objective Trade-off)
최적의 Kinetic 각도는 다음 세 가지 에너지 거동의 상충 관계를 실시간 연립 방정식으로 해석하여 결정됩니다:
1. **냉난방 부하**: 차양 각도를 닫을수록 태양열 획득이 차단되어 냉방 부하가 감소합니다.
2. **BIPV 발전량**: 태양광과 패널면의 법선 벡터가 일치할수록 발전량이 증가합니다.
3. **인공 조명 부하**: 차양 각도를 닫을수록 실내 일사 유입이 차단되어 조명 에너지가 급증합니다.

### 4.3 넷 에너지(Net Energy) 최적화 공식
파이썬 API 콜백 함수에서 실시간으로 계산하는 목적 함수는 냉난방 부하와 조명 부하를 합산하고 BIPV 발전량을 차감한 **넷 에너지(Net Energy)**를 최소화하는 방향으로 동작합니다:
$$\text{Net Energy} = \text{Cooling Load} + \text{Heating Load} + \text{Lighting Load} - \text{BIPV Generation}$$

---

## 🛠️ 5. 향후 실행 가동 절차 (Triggering Plan)

사용자님의 동의 및 실행 승인이 떨어지면, **솔루션 A(하이브리드 이산화)**와 **3장의 자동화 아키텍처**를 기반으로 다음과 같이 진행합니다.

### Step 1: `scripts/dynamic_shading_manager.py` 개발
* **환경 구성**: `C:/EnergyPlusV25-2-0` 내부 of `pyenergyplus` 패키지 자동 연동.
* **IDF 기하 변환**: `gl2.idf`를 파싱하여 기존 `BIPV` 객체를 지우고, 회전 기하학 공식($Y(\theta), Z(\theta)$)을 적용한 각도별 10개 Shading 표면과 10개의 PV 제너레이터, 10개의 개별 Availability Schedule 객체, 그리고 `Daylighting:Controls` 주광 센서 연동 설정을 자동으로 증설합니다.
* **실시간 하이브리드 제어 API 구축**: 매 타임스텝마다 현재 태양 위치 기준 최적 Kinetic 각도 연산. 활성 각도 shading만 투과율 `0.0` 제어, 나머지 `1.0` 제어. 활성 BIPV만 Availability `1.0` (다이오드 물리 연산 활성화), 비활성 BIPV 9개는 Availability `0.0` (계통 차단) 제어. 동시에 조도 센서 피드백을 받아 넷 에너지 최적화 각도 판별.
* **부하 데이터 기록**: 시뮬레이션 도중 냉난방 부하, 조명 부하(Interior Lights Electricity Energy), 존 온도, 실내 조도(Daylighting Reference Point 1 Illuminance), 현재 작동 중인 shading의 각도 상태, BIPV 정밀 발전량(셀 온도 가변 효율 수렴치)을 실계열로 수집하여 최종 CSV 결과로 출력합니다.

### Step 2: 시뮬레이션 실행 및 결과 분석
```bash
# uv 가상환경을 사용하여 스크립트 실행 (실제 구동 단계)
uv run python scripts/dynamic_shading_manager.py
```

### Step 3: 부하 데이터 물리적 검증 및 시계열 리포팅
* 각도 제어가 타임스텝별로 제대로 매핑되었는지 검증.
* 상부 힌지 차양의 동적 각도 제어가 건물 전체 냉난방 부하, 조명 부하 및 발전량에 미친 정량적 절감 기여도 분석 및 차트 작성.

---

## 📋 6. 현재 상태 정보

* **대상 IDF 파일**: `models/gl2.idf` (Version 25.2)
* **EnergyPlus 엔진 설치 경로**: `C:/EnergyPlusV25-2-0`
* **현 단계**: **[대기 중]** 사용자의 명시적인 코드 구현 및 실행 승인이 있을 때까지 어떠한 수정이나 시뮬레이션도 기동하지 않음.

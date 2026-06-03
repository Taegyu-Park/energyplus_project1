# PV Module List (Full Data) Parameters

해당 문서는 캘리포니아 에너지 위원회(CEC) 등에서 제공하는 **태양광(PV) 모듈의 상세 성능 및 기술 제원(Parameter) 목록**(`PV_Module_List_Full_Data_ADA.csv`)의 파라미터 설명입니다.

## 1. 기본 정보 (General Information)
* **Manufacturer**: 제조사명
* **Model Number**: 모듈의 고유 모델 번호
* **Description**: 모듈에 대한 간략한 설명 (예: 270W 단결정 모듈)
* **Safety Certification**: 안전 인증 규격 (예: UL 1703)
* **Design Qualification / Performance Evaluation**: 설계 자격 및 성능 평가 인증 (예: IEC 61215, IEC 61853-1)
* **Family / Technology**: 셀의 종류 및 기술 (예: Monocrystalline(단결정), Polycrystalline(다결정), Thin Film(박막형) 등)
* **BIPV**: 건물 일체형 태양광 발전(Building Integrated Photovoltaics) 모듈 여부 (Y/N)
* **CEC Listing Date / Last Update**: CEC 목록 등재일 및 데이터 최근 수정일

## 2. 물리적 제원 (Physical Characteristics)
* **A_c (m²)**: 모듈의 면적
* **N_s**: 직렬로 연결된 태양전지(Cell)의 개수
* **N_p**: 병렬로 연결된 태양전지 스트링의 개수 (보통 1)
* **Short Side (m) / Long Side (m)**: 모듈의 가로, 세로 길이
* **Mounting**: 설치 방식 (예: Rack(랙 마운트))
* **Type**: 모듈의 형태 (예: Flat Plate(평판형))

## 3. 기준 출력 및 테스트 조건 (Power Ratings)
* **Nameplate Pmax (W)**: 명판 출력(최대 전력). 표준 시험 조건(STC: 일사량 1000W/m², 25°C)에서 측정된 정격 출력입니다.
* **PTC (W)**: PVUSA Test Conditions 출력. STC보다 실제 환경에 더 가까운 조건(일사량 1000W/m², 기온 20°C, 풍속 1m/s)에서 측정한 출력으로, 보통 Nameplate Pmax보다 낮게 나옵니다.

## 4. 전기적 특성 (Electrical Characteristics - STC 기준)
* **Nameplate Isc (A)**: 단락 전류 (Short-Circuit Current). 회로가 합선되었을 때 흐르는 최대 전류.
* **Nameplate Voc (V)**: 개방 전압 (Open-Circuit Voltage). 회로가 열려있을 때(전류가 흐르지 않을 때)의 최대 전압.
* **Nameplate Ipmax (A)**: 최대 전력점에서의 전류.
* **Nameplate Vpmax (V)**: 최대 전력점에서의 전압.
*(참고: `Pmax = Ipmax * Vpmax`)*

## 5. 온도 특성 (Temperature Coefficients)
온도가 올라갈수록 태양광 패널의 성능이 어떻게 변하는지를 나타내는 계수입니다.
* **Average NOCT (°C)**: 공칭 태양전지 동작 온도 (Nominal Operating Cell Temperature). 실제 야외 환경과 비슷한 조건에서 모듈이 도달하는 평균 온도입니다.
* **γPmax (%/°C)**: 최대 전력(Pmax)의 온도 계수. 온도가 1도 오를 때 효율(전력)이 얼마나 감소하는지를 보여줍니다. (보통 마이너스 값)
* **αIsc (%/°C)**: 단락 전류(Isc)의 온도 계수.
* **βVoc (%/°C)**: 개방 전압(Voc)의 온도 계수.
* **αIpmax / βVpmax (%/°C)**: 최대 전력점의 전류/전압 온도 계수.

## 6. 특정 조건에서의 성능 데이터 (Performance under specific conditions)
다양한 환경(일사량이 낮거나 온도가 높은 경우 등)에서의 성능 예측을 위해 사용되는 실측 데이터입니다.
* **IPmax, low / VPmax, low (A / V)**: 저일사량(Low Irradiance) 조건에서의 최대 전력점 전류 및 전압.
* **IPmax, NOCT / VPmax, NOCT (A / V)**: NOCT 조건(보통 800W/m², 20°C 대기온도)에서의 최대 전력점 전류 및 전압.
* **P2/Pref**: 성능 저하비율 또는 특정 저일사량 조건 대비 표준 전력의 비율을 나타내는 매개변수입니다. 에너지 시뮬레이션에서 효율 곡선을 그릴 때 사용됩니다.
* **Geometric Multiplier**: 기하학적 형태에 따른 수치 보정 계수로 추정됩니다.

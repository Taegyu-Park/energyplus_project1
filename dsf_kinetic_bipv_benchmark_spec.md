# 광주 기후 기반 Kinetic BIPV + DSF 통합 시스템 Net 에너지 및 경제성 평가 연구 사양서

본 문서는 **광주광역시 기후 조건**에서 **Kinetic BIPV(동적 태양광 외피) 단독 시스템 대비 더블스킨 파사드(DSF) 결합 통합 시스템**의 건물 순(Net) 에너지 사용량 최소화 성능 및 생애주기 경제성(Economic Viability / LCC)을 비교·검증하기 위한 종합 연구 사양서입니다.

---

## 1. 연구의 최종 목표 (Ultimate Research Goal)

1. **에너지 성능 목표 (Net Energy Minimization):**
   * 광주광역시 사계절 기후 특성에 맞춰 **냉난방 부하(HVAC Load) 최소화**와 **Kinetic BIPV 태양광 발전량(PV Yield) 최대화**를 동시에 달성.
   * **건물 순 에너지 사용량 (Net Energy Intensity, $\text{kWh/m}^2\cdot\text{yr}$) 최소화:**
     $$E_{\text{Net}} = E_{\text{Heating}} + E_{\text{Cooling}} + E_{\text{Base}} - E_{\text{BIPV Generation}} \rightarrow \mathbf{\text{Minimize}}$$
2. **경제성 입증 목표 (Economic Feasibility):**
   * 기존 Kinetic BIPV 단독 시스템(Case 2) 대비 DSF 추가 구축 시 발생하는 **추가 초기 투자비(CAPEX)** 대비 **연간 에너지 절감 및 발전 수익(OPEX)**을 바탕으로 **단순 회수기간(Payback Period), 순현재가치(NPV), LCC(Life-Cycle Cost)** 분석 수행.

---

## 2. IDF 모델 작성을 위한 5대 핵심 기술 사양 (IDF Modeling Guidelines)

EnergyPlus 시뮬레이션의 물리적 신뢰성을 극대화하기 위해 아래 5가지 필수 설정 사양을 IDF 모델링에 완벽 반영하였습니다. (대상 파일: [`case4_2story_dsf_bipv_test.idf`](file:///c:/Users/taegyu/Codes/energyplus_project1/case4_2story_dsf_bipv_test.idf))

### 2.1 Geometry: 실내 존과 Cavity 존 분리 생성
* **구조:** $4\text{m}\times4\text{m}\times8\text{m}$ 2층 건물에 대해 실내 핵심 공간(`Core_1F`, `Core_2F`)과 캐비티 공기층 공간(`Cavity_1F_S`, `Cavity_2F_S`)을 독립된 별도의 Thermal Zone으로 분리 구축.
* **경계 연결:** 1층/2층 캐비티 수직 경계($Z=4.0\text{m}$)는 개방형 경계(`Construction:AirBoundary`)를 적용하여 수직 기류 상승 통로 형성.

### 2.2 Constructions: 외피, 내피 및 중공층 블라인드 물성 지정
* **동기화:** [`case3_v3_south.idf`](file:///c:/Users/taegyu/Codes/energyplus_project1/case_idf/case3_v3_KS/case3_v3_south.idf)의 외벽, 지붕, 바닥, 복층유리 및 PV 스펙 100% 동일 적용.
* **외측 스킨 (Outer Skin):** 가동식 Kinetic BIPV 루버 패널 + 투과율 스케줄 연동
* **내측 스킨 (Inner Skin):** `Generic Double Pane` (Low-E 복층유리: `Generic Low-e Glass` + Air Gap + `Clear Glass`, $U \approx 1.5\text{ W/m}^2\text{K}$)

### 2.3 Convection Algorithm: Cavity 표면 대류열전달 알고리즘 최적화
* **설정:** 캐비티 내부 및 외피 표면의 부력 대류열전달 계수($h_c$) 정밀화를 위해 **`AdaptiveConvectionAlgorithm`**을 적용.
  ```idf
  SurfaceConvectionAlgorithm:Inside, AdaptiveConvectionAlgorithm;
  SurfaceConvectionAlgorithm:Outside, AdaptiveConvectionAlgorithm;
  ```

### 2.4 Airflow Network (AFN): 댐퍼 개구부 정의 및 연돌효과 부력 계산 연동
* **개구부 지정:**
  * `Damper_Bottom_1F_S` ($Z = 0.0\text{m} \sim 0.5\text{m}$): 1층 하부 외기 유입 댐퍼
  * `Damper_Middle_1F2F_S` ($Z = 4.0\text{m}$): 1층/2층 캐비티 사이 수직 유동 경계 개구부
  * `Damper_Top_2F_S` ($Z = 7.5\text{m} \sim 8.0\text{m}$): 2층 상부 외기 배기 댐퍼
* **부력 연동:** AFN 노드 압력차 수식($\Delta P = \rho g \Delta Z$)으로 높이 $8\text{m}$ 부력 상승 기류 및 자연 통풍 환기량을 실시간 수두 계산.

### 2.5 Control (EMS/Python Plugin): 계절별 댐퍼/루버 통합 제어 스케줄 및 조건문 적용
* **통합파이썬 모듈:** [`dsf_bipv_integrated_control.py`](file:///c:/Users/taegyu/Codes/energyplus_project1/dsf_bipv_integrated_control.py) 적용.
* **4계절 제어 조건:**
  * **Mode 1 (여름 주간):** 외기온 $\ge 20^\circ\text{C}$ & 일사량 $> 100\text{W/m}^2 \rightarrow$ 댐퍼 1.0 (OPEN) + BIPV 태양 추적 각도 (다점 대류 배기)
  * **Mode 2 (여름 야간):** 외기온 $\ge 18^\circ\text{C}$ & 야간 $\rightarrow$ 댐퍼 1.0 (OPEN) + BIPV $90^\circ$ (Night Flushing)
  * **Mode 3 (겨울 주간):** 외기온 $< 15^\circ\text{C}$ & 일사량 $> 100\text{W/m}^2 \rightarrow$ 댐퍼 0.0 (CLOSED) + BIPV 일사 수직 취득 각도 (온실 축열)
  * **Mode 4 (겨울 야간):** 외기온 $< 10^\circ\text{C}$ & 야간 $\rightarrow$ 댐퍼 0.0 (CLOSED) + BIPV $0^\circ$ (Thermal Buffer 밀폐 단열)

---

## 3. 시뮬레이션 환경 및 벤치마크 건물 모델

| 구분 | 파라미터 규격 | 상세 사양 및 비고 |
| :--- | :--- | :--- |
| **대상 기후** | **광주광역시 (Gwangju, KOR)** | 광주 표준 기상 데이터 (`KOR_Gwangju.471560_IWEC.epw`) |
| **건물 규모** | **2층 적층 큐브 ($4\text{m}\times4\text{m}\times8\text{m}$)** | 바닥면적 $16\text{m}^2$, 연면적 $32\text{m}^2$, 높이 $8.0\text{m}$ |
| **창면적비 (WWR)** | 80 ~ 90% (전면 유리) | 1층 및 2층 N, E, S, W 4면 유리 커튼월 형태 |
| **최신 IDF 모델** | [`case4_2story_dsf_bipv_test.idf`](file:///c:/Users/taegyu/Codes/energyplus_project1/case4_2story_dsf_bipv_test.idf) | **최종 통합 최신화 IDF 모델** |
| **파이썬 제어** | [`dsf_bipv_integrated_control.py`](file:///c:/Users/taegyu/Codes/energyplus_project1/dsf_bipv_integrated_control.py) | BIPV 각도 + DSF 댐퍼 동시 연동 Python Plugin |

---

## 4. 케이스 연구 및 성능 비교 구도 (Case Study Setup)

* **Case 1 (Standard Base):** DSF 및 BIPV가 없는 일반 고정형 유리 외피 건물
* **Case 2 (Current Baseline):** **현재 적용되어 있는 외부 노출 Kinetic BIPV 단독 시스템**
* **Case 3 (Proposed Final System):** **Kinetic BIPV 외피 + 2층 DSF (0.8m 캐비티) + AFN 부력 연동 + Adaptive 대류 + 신규 파이썬 통합 제어 시스템**

---

## 5. 경제성 평가 프레임워크 (Economic Feasibility Analysis)

1. **추가 초기 투자비 ($\Delta\text{CAPEX}$):** Case 2 대비 Case 3 추가 공사비 (DSF 유리 스킨, 프레임, 댐퍼 및 0.8m 캐비티 구조체)
2. **연간 운용비 절감액 ($\Delta\text{OPEX}$):** 냉난방 전력 절감액 + PV 추가 발전 수익
3. **평가 지표:** 단순 회수기간(Payback Period, SPP), 순현재가치(NPV), EnergyPlus LCC(Life-Cycle Cost) 지표 산출

# Building Simulation Schedules Summary (건물 스케줄 요약)

본 문서는 EnergyPlus 건물 에너지 시뮬레이션 모델(`260817.idf`, DOE SmallOffice 기준)에 적용된 **내부 발열(재실자, 조명, 플러그 부하)** 및 **HVAC 냉난방 설정온도(Dual Setpoint & Setback)** 스케줄을 체계적으로 정리한 자료입니다.

---

## 1. 내부 발열 및 재실 스케줄 (Internal Loads & Occupancy)

- **관련 코드**: [`fig41_occupancy_internal_loads_profile.py`](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/code/fig41_occupancy_internal_loads_profile.py)
- **결과 그래프**: [`fig41_occupancy_internal_loads_profile.svg`](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/plot/fig41_occupancy_internal_loads_profile/fig41_occupancy_internal_loads_profile.svg) / [PNG](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/plot/fig41_occupancy_internal_loads_profile/fig41_occupancy_internal_loads_profile.png)

### 1.1 주중 스케줄 (Weekday, Monday – Friday)

시간대별 부하 분율(Load Fraction, `0.0 ~ 1.0`) 상세 내역입니다.

|   시간대 (Hour)   | 재실 (Occupancy)  | 전자기기 (Electric Equipment) |   조명 (Lighting)   | 비고 및 주요 동작 특성                      |
| :---------------: | :---------------: | :---------------------------: | :-----------------: | :------------------------------------------ |
| **00:00 – 05:00** |     0.00 (0%)     |        0.4095 (~41.0%)        |   0.1800 (18.0%)    | 심야 최소 대기전력 및 보안 조명             |
| **05:00 – 06:00** |     0.00 (0%)     |        0.4095 (~41.0%)        |   0.2300 (23.0%)    | 조기 출근 / 건물 관리 준비 조명             |
| **06:00 – 07:00** |   0.11 (11.0%)    |        0.4798 (~48.0%)        |   0.1786 (~17.9%)   | 초기 출근 인원 입실                         |
| **07:00 – 08:00** |   0.21 (21.0%)    |        0.4798 (~48.0%)        |   0.3262 (~32.6%)   | 일반 출근 시간대 부하 상승                  |
| **08:00 – 12:00** | **1.00 (100.0%)** |      **0.9595 (~96.0%)**      | **0.6990 (~69.9%)** | **오전 메인 업무 시간 (Peak Load)**         |
| **12:00 – 13:00** | **0.53 (53.0%)**  |        0.9019 (~90.2%)        | **0.6214 (~62.1%)** | **점심시간 (외출/식사로 인한 일시적 드롭)** |
| **13:00 – 17:00** | **1.00 (100.0%)** |      **0.9595 (~96.0%)**      | **0.6990 (~69.9%)** | **오후 메인 업무 시간 (Peak Load)**         |
| **17:00 – 18:00** |   0.32 (32.0%)    |        0.4798 (~48.0%)        |   0.4738 (~47.4%)   | 퇴근 시작 시간대                            |
| **18:00 – 20:00** |   0.11 (11.0%)    |        0.1919 (~19.2%)        |   0.3262 (~32.6%)   | 잔여 야근 인원                              |
| **20:00 – 22:00** |   0.11 (11.0%)    |        0.1919 (~19.2%)        |   0.2485 (~24.9%)   | 야간 근무 마무리                            |
| **22:00 – 23:00** |    0.05 (5.0%)    |        0.1919 (~19.2%)        |   0.1786 (~17.9%)   | 청소 및 최종 퇴실                           |
| **23:00 – 24:00** |     0.00 (0%)     |        0.1638 (~16.4%)        |   0.1800 (18.0%)    | 심야 완전 비재실 상태 복귀                  |

### 1.2 주말 및 공휴일 스케줄 (Weekend & Holiday)

- **재실 분율 (Occupancy Fraction)**: `0.00 (0%)` (24시간 전일 비재실)
- **조명 분율 (Lighting Fraction)**: `0.1800 (18.0%)` (24시간 보안/비상등 최소 부하 유지)
- **전자기기 분율 (Equipment Fraction)**: `0.1638 (~16.4%)` (24시간 상시 대기전력 유지)

---

## 2. HVAC 설정온도 및 셋백 스케줄 (HVAC Dual Setpoint & Setback)

- **관련 코드**: [`fig42_hvac_setpoint_setback_schedule.py`](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/code/fig42_hvac_setpoint_setback_schedule.py)
- **결과 그래프**: [`fig42_hvac_setpoint_setback_schedule.svg`](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/plot/fig42_hvac_setpoint_setback_schedule/fig42_hvac_setpoint_setback_schedule.svg) / [PNG](file:///c:/Users/taegyu/Codes/energyplus_project1/figure/plot/fig42_hvac_setpoint_setback_schedule/fig42_hvac_setpoint_setback_schedule.png)

### 2.1 주중 스케줄 (Weekday, Monday – Friday)

|   시간대 (Hour)   | 난방 설정온도 (Heating SP) | 냉방 설정온도 (Cooling SP) | 쾌적 불감대 (Deadband) | 운전 모드 및 제어 전략                                                                                                                                |
| :---------------: | :------------------------: | :------------------------: | :--------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **00:00 – 06:00** |         **5.0 °C**         |        **35.0 °C**         |    5.0 °C ~ 35.0 °C    | **야간 비가동 셋백 (Night Setback)**<br>- 실온 5°C 이하 시 동파 방지 난방만 작동<br>- 냉방 사실상 OFF (35°C 초과 시에만 가동)                         |
| **06:00 – 18:00** |        **20.0 °C**         |        **26.0 °C**         | **20.0 °C ~ 26.0 °C**  | **주간 정상 공조 운전 (Occupied Operation)**<br>- 실온 < 20°C: 난방 가동<br>- 실온 > 26°C: 냉방 가동<br>- 20°C ~ 26°C: 냉난방 동시 정지 (쾌적 불감대) |
| **18:00 – 19:00** |        **20.0 °C**         |        **35.0 °C**         |   20.0 °C ~ 35.0 °C    | 냉방 조기 셋백 / 난방 정상 온도 유지                                                                                                                  |
| **19:00 – 24:00** |         **5.0 °C**         |        **35.0 °C**         |    5.0 °C ~ 35.0 °C    | **야간 비가동 셋백 (Night Setback)**<br>- 동파 방지 대기 상태                                                                                         |

### 2.2 주말 및 공휴일 스케줄 (Weekend & Holiday)

- **난방 설정온도 (Heating SP)**: `5.0 °C` (24시간 전일 동파 방지 최소 셋백)
- **냉방 설정온도 (Cooling SP)**: `35.0 °C` (24시간 전일 냉방 정지/셋백)
- **운전 특성**: 전일 완전 셋백(Full Unoccupied Setback) 제어가 적용되어 냉난방 에너지 소비를 최소화합니다.

---

## 3. 스케줄 요약 비교표

| 항목                           | 주중 주간 (08:00~17:00) | 주중 야간 (19:00~06:00) | 주말 / 공휴일 (전일) |
| :----------------------------- | :---------------------: | :---------------------: | :------------------: |
| **재실자 (Occupancy)**         |   **100% (점심 53%)**   |           0%            |          0%          |
| **전자기기 부하 (Equipment)**  |        **~96%**         |       ~16% ~ 41%        |        ~16.4%        |
| **조명 부하 (Lighting)**       |        **~70%**         |        18% ~ 23%        |         18%          |
| **냉방 설정온도 (Cooling SP)** |       **26.0 °C**       |     35.0 °C (셋백)      |    35.0 °C (셋백)    |
| **난방 설정온도 (Heating SP)** |       **20.0 °C**       |      5.0 °C (셋백)      |    5.0 °C (셋백)     |
| **쾌적 불감대 (Deadband)**     |  **20.0 °C ~ 26.0 °C**  |    5.0 °C ~ 35.0 °C     |   5.0 °C ~ 35.0 °C   |

# 96개 최적 PV 패널 배치 명세서 (Optimal 96 PV Layout & Generation Summary)

본 문서는 **동일한 96개 PV 패널 수량 제한 조건**에서 건물 연간 총 발전량을 최대화(Maximize)하기 위해 선정한 **Top 96 최적 PV 패널 배치 목록 및 성능 수치 명세서**입니다.

---

## 1. 향별 (Orientation) 패널 수량 및 발전량 요약

| 향 (Orientation) | 선택된 패널 수 | 연간 총 발전량 (kWh) | 연간 총 발전량 (MWh) | 패널당 평균 발전량 (kWh) | 발전량 범위 (Min ~ Max kWh) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **남향 (SOUTH)** | **78개** | **33,112.92 kWh** | 33.11 MWh | 424.52 kWh/개 | 365.06 ~ 623.88 kWh |
| **동향 (EAST)** | **9개** | **4,313.03 kWh** | 4.31 MWh | 479.23 kWh/개 | 479.05 ~ 479.87 kWh |
| **서향 (WEST)** | **9개** | **4,339.26 kWh** | 4.34 MWh | 482.14 kWh/개 | 481.96 ~ 482.80 kWh |
| **북향 (NORTH)** | **0개** | **0.00 kWh** | 0.00 MWh | - | - |
| **합계 (TOTAL)** | **96개** | **41,765.22 kWh** | **41.77 MWh** | **435.05 kWh/개** | **365.06 ~ 623.88 kWh** |

---

## 2. 배치 비교: South Only 96개 vs Maximize 96개 최적 배치

| 구분 | South 전용 96개 배치 (Case 3 South) | Maximize 96 최적 배치 (South 78 + East 9 + West 9) | 증감 차이 (Gain) |
| :--- | :---: | :---: | :---: |
| **총 PV 패널 수** | **96개** | **96개** | **동일 수량 (96개)** |
| **연간 총 발전량** | **39,660.53 kWh** (39.66 MWh) | **41,765.22 kWh** (41.77 MWh) | **+2,104.69 kWh (+5.31% 상승)** |
| **패널당 평균 발전량** | **413.13 kWh/개** | **435.05 kWh/개** | **+21.92 kWh/개** |

---

## 3. 입면별(Elevation Grid) 3D 공간 배치 현황표

### 1) 남향 입면 (South Facade) - 78개 패널
- **Row 1 (최상단)**: Col 01 ~ Col 16 (16개 전체 / 패널당 ~623 kWh)
- **Row 2**: Col 01 ~ Col 16 (16개 전체 / 패널당 372 ~ 404 kWh)
- **Row 3**: Col 01 ~ Col 16 (16개 전체 / 패널당 367 ~ 399 kWh)
- **Row 4**: Col 01 ~ Col 16 (16개 전체 / 패널당 366 ~ 399 kWh)
- **Row 5**: Col 01, Col 02, Col 03, Col 04, Col 13, Col 14, Col 15, Col 16 (8개)
- **Row 6 (최하단)**: Col 01, Col 02, Col 15, Col 16 (4개)
- *(제거된 패널 18개: Row 5 Col 05~12, Row 6 Col 03~14 중 발전량 365 kWh 이하 18개 제외)*

### 2) 동향 입면 (East Facade) - 9개 패널
- **Row 1 (최상단)**: Col 01 ~ Col 09 (9개 전체 / 패널당 **479.05 ~ 479.87 kWh**)

### 3) 서향 입면 (West Facade) - 9개 패널
- **Row 1 (최상단)**: Col 01 ~ Col 09 (9개 전체 / 패널당 **481.96 ~ 482.80 kWh**)

---

## 4. 선택된 Top 96개 PV 패널 전체 상세 목록 (Rank 1 ~ 96)

| 순위 (Rank) | 향 (Orientation) | 행 (Row) | 열 (Column) | 연간 발전량 (kWh) | 비고 |
| :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | SOUTH | Row 1 | Col 01 | 623.88 | 최상단 좌측 모서리 |
| 2 | SOUTH | Row 1 | Col 16 | 623.88 | 최상단 우측 모서리 |
| 3 | SOUTH | Row 1 | Col 02 | 623.08 | |
| 4 | SOUTH | Row 1 | Col 15 | 623.08 | |
| 5 | SOUTH | Row 1 | Col 03 | 623.06 | |
| 6 | SOUTH | Row 1 | Col 14 | 623.06 | |
| 7 | SOUTH | Row 1 | Col 04 | 623.06 | |
| 8 | SOUTH | Row 1 | Col 05 | 623.05 | |
| 9 | SOUTH | Row 1 | Col 06 | 623.05 | |
| 10 | SOUTH | Row 1 | Col 07 | 623.05 | |
| 11 | SOUTH | Row 1 | Col 08 | 623.05 | |
| 12 | SOUTH | Row 1 | Col 09 | 623.05 | |
| 13 | SOUTH | Row 1 | Col 10 | 623.05 | |
| 14 | SOUTH | Row 1 | Col 11 | 623.05 | |
| 15 | SOUTH | Row 1 | Col 12 | 623.05 | |
| 16 | SOUTH | Row 1 | Col 13 | 623.05 | |
| 17 | WEST | Row 1 | Col 01 | 482.80 | 서향 최상단 |
| 18 | WEST | Row 1 | Col 09 | 482.68 | 서향 최상단 |
| 19 | WEST | Row 1 | Col 02 | 481.99 | |
| 20 | WEST | Row 1 | Col 08 | 481.98 | |
| 21 | WEST | Row 1 | Col 03 | 481.96 | |
| 22 | WEST | Row 1 | Col 04 | 481.96 | |
| 23 | WEST | Row 1 | Col 05 | 481.96 | |
| 24 | WEST | Row 1 | Col 06 | 481.96 | |
| 25 | WEST | Row 1 | Col 07 | 481.96 | |
| 26 | EAST | Row 1 | Col 01 | 479.87 | 동향 최상단 |
| 27 | EAST | Row 1 | Col 09 | 479.77 | 동향 최상단 |
| 28 | EAST | Row 1 | Col 02 | 479.07 | |
| 29 | EAST | Row 1 | Col 08 | 479.07 | |
| 30 | EAST | Row 1 | Col 03 | 479.05 | |
| 31 | EAST | Row 1 | Col 04 | 479.05 | |
| 32 | EAST | Row 1 | Col 05 | 479.05 | |
| 33 | EAST | Row 1 | Col 06 | 479.05 | |
| 34 | EAST | Row 1 | Col 07 | 479.05 | |
| 35 | SOUTH | Row 2 | Col 16 | 403.95 | |
| 36 | SOUTH | Row 2 | Col 01 | 403.66 | |
| 37 | SOUTH | Row 3 | Col 16 | 399.92 | |
| 38 | SOUTH | Row 3 | Col 01 | 399.63 | |
| 39 | SOUTH | Row 4 | Col 16 | 399.26 | |
| 40 | SOUTH | Row 4 | Col 01 | 398.98 | |
| 41 | SOUTH | Row 5 | Col 16 | 398.38 | |
| 42 | SOUTH | Row 5 | Col 01 | 398.10 | |
| 43 | SOUTH | Row 6 | Col 16 | 396.72 | |
| 44 | SOUTH | Row 6 | Col 01 | 396.48 | |
| 45 | SOUTH | Row 2 | Col 02 | 373.34 | |
| 46 | SOUTH | Row 2 | Col 15 | 373.34 | |
| 47 | SOUTH | Row 2 | Col 03 | 372.63 | |
| 48 | SOUTH | Row 2 | Col 04 | 372.63 | |
| 49 | SOUTH | Row 2 | Col 05 | 372.63 | |
| 50 | SOUTH | Row 2 | Col 06 | 372.63 | |
| 51 | SOUTH | Row 2 | Col 07 | 372.63 | |
| 52 | SOUTH | Row 2 | Col 08 | 372.63 | |
| 53 | SOUTH | Row 2 | Col 09 | 372.63 | |
| 54 | SOUTH | Row 2 | Col 10 | 372.63 | |
| 55 | SOUTH | Row 2 | Col 11 | 372.63 | |
| 56 | SOUTH | Row 2 | Col 12 | 372.63 | |
| 57 | SOUTH | Row 2 | Col 13 | 372.63 | |
| 58 | SOUTH | Row 2 | Col 14 | 372.63 | |
| 59 | SOUTH | Row 3 | Col 02 | 368.42 | |
| 60 | SOUTH | Row 3 | Col 15 | 368.42 | |
| 61 | SOUTH | Row 3 | Col 03 | 367.54 | |
| 62 | SOUTH | Row 3 | Col 04 | 367.54 | |
| 63 | SOUTH | Row 3 | Col 05 | 367.54 | |
| 64 | SOUTH | Row 3 | Col 06 | 367.54 | |
| 65 | SOUTH | Row 3 | Col 07 | 367.54 | |
| 66 | SOUTH | Row 3 | Col 08 | 367.54 | |
| 67 | SOUTH | Row 3 | Col 09 | 367.54 | |
| 68 | SOUTH | Row 3 | Col 10 | 367.54 | |
| 69 | SOUTH | Row 3 | Col 11 | 367.54 | |
| 70 | SOUTH | Row 3 | Col 12 | 367.54 | |
| 71 | SOUTH | Row 3 | Col 13 | 367.54 | |
| 72 | SOUTH | Row 3 | Col 14 | 367.54 | |
| 73 | SOUTH | Row 4 | Col 02 | 367.28 | |
| 74 | SOUTH | Row 4 | Col 15 | 367.28 | |
| 75 | SOUTH | Row 4 | Col 03 | 366.30 | |
| 76 | SOUTH | Row 4 | Col 04 | 366.30 | |
| 77 | SOUTH | Row 4 | Col 05 | 366.30 | |
| 78 | SOUTH | Row 4 | Col 06 | 366.24 | |
| 79 | SOUTH | Row 4 | Col 07 | 366.24 | |
| 80 | SOUTH | Row 4 | Col 08 | 366.24 | |
| 81 | SOUTH | Row 4 | Col 09 | 366.24 | |
| 82 | SOUTH | Row 4 | Col 10 | 366.24 | |
| 83 | SOUTH | Row 4 | Col 11 | 366.24 | |
| 84 | SOUTH | Row 4 | Col 12 | 366.30 | |
| 85 | SOUTH | Row 4 | Col 13 | 366.30 | |
| 86 | SOUTH | Row 4 | Col 14 | 366.30 | |
| 87 | SOUTH | Row 5 | Col 02 | 366.24 | |
| 88 | SOUTH | Row 5 | Col 15 | 366.24 | |
| 89 | SOUTH | Row 6 | Col 02 | 364.44 | |
| 90 | SOUTH | Row 6 | Col 15 | 364.44 | |
| 91 | SOUTH | Row 5 | Col 03 | 365.23 | |
| 92 | SOUTH | Row 5 | Col 14 | 365.23 | |
| 93 | SOUTH | Row 5 | Col 04 | 365.12 | |
| 94 | SOUTH | Row 5 | Col 13 | 365.12 | |
| 95 | SOUTH | Row 5 | Col 05 | 365.12 | |
| 96 | SOUTH | Row 5 | Col 12 | 365.12 | 96번째 컷오프 패널 |

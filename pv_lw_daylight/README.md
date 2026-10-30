# pv_lw_daylight — PV 복사(장파) 연동 + 주광 연동 조명 부하

kinetic BIPV 루버의 **PV 온도가 남측 외피로 내보내는 장파복사**와, **PV 각도에 따라 달라지는 주광·조명 부하**를 case2(고정각)·case3(태양추적)에 반영한 작업 폴더.
계획과 구현 경위, 검증 결과는 [`plan_pv_facade_longwave_coupling.md`](plan_pv_facade_longwave_coupling.md)에 있다(8절이 구현 현황).

## 폴더 구성
| 경로 | 내용 |
|---|---|
| `plan_pv_facade_longwave_coupling.md` | 계획서 + 구현 현황·검증·결정 사항 |
| `compute_view_factors.py` → `view_factors.csv` | 각도별 PV 6단 ↔ 남측 창·외벽 뷰팩터 |
| `pv_lw_plugin.py` | PV 셀 온도 → 외피 주변 표면 온도 연동, case3 조명 배율 적용, case2용 플러그인 |
| `bipv_schedule_lw_plugin.py` | case3 각도 제어 플러그인(`bipv_experiments/bipv_schedule_plugin.py`) 확장 |
| `run_pvlw.py` | IDF 사본 생성·패치·실행 러너 (`bipv_experiments/runner.py` 재사용) |
| `build_daylight_table.py` → `daylight_tables/` | case3용 각도별 조명 전력 배율 표 (case2 주광 실행 짜깁기) |
| `analyze_results.py` → `results/` | 효과 정리표 (PV 복사, 조명, 합계, 설정조도 민감도; 연간·난방기 평일) |
| `schedules/` | 테스트용 각도 스케줄 (0°/90° 매시 교대) |
| `batches/` | 실행 배치 JSON과 로그 |
| `runs/tests/` | 0단계 검증 실행 (t0~t5: PV 복사, d0~d5: 주광) |
| `runs/daylight_table/` | 배율 표용 case2 주광 연간 실행 (`tbl_FE_L<lx>_A<각도>`) |
| `runs/annual/` | 본 연간 실행 (`c2_RF_<변형>_A<각도>`, `c3_FE_ST_<변형>`) — 이코노마이저 Enthalpy, Eg 1.25 |
| `runs/annual_drybulb/` | 이전 연간 실행 (원본 DryBulb 이코노마이저, 여름 고착 포함 — 보관용) |
| `figures/` | 결과 그림 (PV 복사 효과 vs 각도) |
| `move_finished_runs.py` | 폴더 이전 중 실행 결과 이동용 (일회성) |

외부 의존(이동하지 않음): `bipv_experiments/runner.py`, `bipv_experiments/bipv_schedule_plugin.py`, `bipv_experiments/idf/case3_v3_south_fixed.idf`, `bipv_experiments/sizing/`, `bipv_experiments/schedules/`, case3 기준안 `bipv_experiments/runs/c3_FE_suntracking_od`, `case_idf/case2_KS/`.

## 실행
```bash
python pv_lw_daylight/run_pvlw.py --batch pv_lw_daylight/batches/case2_annual_batch.json --jobs 14
python pv_lw_daylight/build_daylight_table.py --lx 300 400 600
python pv_lw_daylight/analyze_results.py
```

## 핵심 사항
- PV는 `Decoupled` 유지. 차양 표면에는 Integrated 모드를 쓸 수 없다(Severe).
- case3에 `Daylighting:Controls`를 넣으면 PV 루버를 무시한다. 그래서 case3 조명은 반드시 `daylight_table`(case2 배율 표)을 쓴다.
- 재시뮬레이션 조건(사용자 결정): 수요 = HVAC + 전체 조명, `Continuous`, 400 lx, PV Eg 1.25(`pv_bandgap`), 이코노마이저 `DifferentialEnthalpy`(`economizer`). 원본 DryBulb는 습한 여름에 외기 냉방이 고착된다(계획서 9절).

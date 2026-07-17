"""
Figure 14: Time-Series Mismatch Analysis between HVAC Load and PV Generation (Case 2 - 90 deg)
Case 2 (Fixed 90° BIPV) 조건의 대표 여름(8/1~8/7) 및 겨울(1/29~2/4) 주간의 HVAC 전기 부하와 BIPV 발전량 시계열 비교 분석
"""

import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import dartwork_mpl as dm
mpl.rcParams['svg.fonttype'] = 'none'

def main():
    # ── 경로 설정 ────────────────────────────────────────────────────────
    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    case2_sql    = os.path.join(project_root, "case_analysis", "normal", "case2", "90", "eplusout.sql")
    
    if not os.path.exists(case2_sql):
        raise FileNotFoundError(f"Case 2 90deg SQL file not found: {case2_sql}")
        
    # ── 데이터 로드 (SQLite) ────────────────────────────────────────────────
    print("Loading Case 2 (90deg) simulation data from eplusout.sql...")
    conn = sqlite3.connect(case2_sql)
    df_data = pd.read_sql_query("""
        SELECT r.TimeIndex, rd.Name, r.Value
        FROM ReportData r
        JOIN ReportDataDictionary rd ON r.ReportDataDictionaryIndex = rd.ReportDataDictionaryIndex
        JOIN Time t ON r.TimeIndex = t.TimeIndex
        WHERE rd.Name IN (
            'Zone Ideal Loads Supply Air Total Heating Energy',
            'Zone Ideal Loads Supply Air Total Cooling Energy',
            'Facility Total Produced Electricity Energy'
        ) AND t.WarmupFlag = 0
    """, conn)
    conn.close()
    
    # 시간별 Pivot 및 인덱싱
    print("Pivoting and mapping 10-minute datetime index...")
    df = df_data.groupby(['TimeIndex', 'Name'])['Value'].sum().unstack(fill_value=0.0)
    df.columns = df.columns.str.strip()
    
    # 시간 인덱스 생성 (10분 간격, 365일 = 52560개)
    datetime_index = pd.date_range(start='2026-01-01 00:10:00', periods=52560, freq='10min')
    df.index = datetime_index
    
    # ── 변수 정의 및 단위 환산 ──────────────────────────────────────────
    heat_col = 'Zone Ideal Loads Supply Air Total Heating Energy'
    cool_col = 'Zone Ideal Loads Supply Air Total Cooling Energy'
    pv_col   = 'Facility Total Produced Electricity Energy'
    
    # COP 정의
    COP_HEATING = 2.5
    COP_COOLING = 3.0
    
    # Joules -> kW 환산
    # Power [kW] = Energy [J] / (COP * TimeStep[sec] * 1000)
    # TimeStep = 10분 = 600초
    df['HVAC_Heating_kW'] = df[heat_col] / (COP_HEATING * 600.0 * 1000.0)
    df['HVAC_Cooling_kW'] = df[cool_col] / (COP_COOLING * 600.0 * 1000.0)
    df['HVAC_Total_kW']   = df['HVAC_Heating_kW'] + df['HVAC_Cooling_kW']
    
    df['PV_Generation_kW'] = df[pv_col] / (600.0 * 1000.0)
    
    # ── 기간 슬라이싱 (대표 여름/겨울 주간) ──────────────────────────────
    # 여름: 8/1 00:00 ~ 8/7 23:50
    # 겨울: 1/29 00:00 ~ 2/4 23:50
    summer_df = df.loc['2026-08-01 00:00:00':'2026-08-07 23:50:00']
    winter_df = df.loc['2026-01-29 00:00:00':'2026-02-04 23:50:00']
    
    # ── 스타일 및 레이아웃 설정 ──────────────────────────────────────────
    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 11, "ytick.labelsize": 11})
    
    fig, (ax_sum, ax_win) = plt.subplots(2, 1, figsize=(28 / 2.54, 20 / 2.54), sharey=True)
    
    # 컬러 정의
    color_hvac = "#1e40af"       # Deep Blue (HVAC Load)
    color_pv   = "#ea580c"       # Warm Orange (PV Gen)
    color_surplus = "#10b981"    # Green (Surplus)
    color_deficit = "#ef4444"    # Red (Deficit)
    
    # ── 1. 여름 대표주 시각화 ─────────────────────────────────────────────
    time_sum = summer_df.index
    hvac_sum = summer_df['HVAC_Total_kW']
    pv_sum   = summer_df['PV_Generation_kW']
    
    ax_sum.plot(time_sum, hvac_sum, color=color_hvac, linewidth=1.5, label="HVAC Electricity Load")
    ax_sum.plot(time_sum, pv_sum, color=color_pv, linewidth=1.5, label="BIPV PV Generation")
    
    # 미스매치 면적 채우기
    ax_sum.fill_between(time_sum, pv_sum, hvac_sum, where=(pv_sum > hvac_sum), 
                        interpolate=True, color=color_surplus, alpha=0.25, label="Generation Surplus")
    ax_sum.fill_between(time_sum, pv_sum, hvac_sum, where=(pv_sum <= hvac_sum), 
                        interpolate=True, color=color_deficit, alpha=0.15, label="Load Deficit")
                        
    ax_sum.set_title("Summer Representative Week (Aug 1 - Aug 7)", fontsize=13, fontweight="bold", loc="left")
    ax_sum.xaxis.set_major_locator(mdates.DayLocator())
    ax_sum.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax_sum.grid(True, linestyle="--", alpha=0.5)
    ax_sum.legend(loc="upper right", framealpha=0, fontsize=9.5, ncol=2)
    
    # ── 2. 겨울 대표주 시각화 ─────────────────────────────────────────────
    time_win = winter_df.index
    hvac_win = winter_df['HVAC_Total_kW']
    pv_win   = winter_df['PV_Generation_kW']
    
    ax_win.plot(time_win, hvac_win, color=color_hvac, linewidth=1.5, label="HVAC Electricity Load")
    ax_win.plot(time_win, pv_win, color=color_pv, linewidth=1.5, label="BIPV PV Generation")
    
    # 미스매치 면적 채우기
    ax_win.fill_between(time_win, pv_win, hvac_win, where=(pv_win > hvac_win), 
                        interpolate=True, color=color_surplus, alpha=0.25, label="Generation Surplus")
    ax_win.fill_between(time_win, pv_win, hvac_win, where=(pv_win <= hvac_win), 
                        interpolate=True, color=color_deficit, alpha=0.15, label="Load Deficit")
                        
    ax_win.set_title("Winter Representative Week (Jan 29 - Feb 4)", fontsize=13, fontweight="bold", loc="left")
    ax_win.xaxis.set_major_locator(mdates.DayLocator())
    ax_win.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax_win.grid(True, linestyle="--", alpha=0.5)
    ax_win.legend(loc="upper right", framealpha=0, fontsize=9.5, ncol=2)
    
    # ── 공통 축 서식 ─────────────────────────────────────────────────────
    # Y축 라벨
    ax_sum.set_ylabel("Power [kW]", fontweight="bold", labelpad=8)
    ax_win.set_ylabel("Power [kW]", fontweight="bold", labelpad=8)
    ax_win.set_xlabel("Time", fontweight="bold", labelpad=8)
    
    # Y축 범위 조정 (자동 스케일에 상단 여백 추가)
    max_val = max(hvac_sum.max(), pv_sum.max(), hvac_win.max(), pv_win.max())
    ax_sum.set_ylim(0, max_val * 1.15)
    
    # ── 이미지 저장 처리 ─────────────────────────────────────────────────
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    
    output_png = os.path.join(figure_dir, f"{script_name}.png")
    output_svg = os.path.join(figure_dir, f"{script_name}.svg")
    
    dm.simple_layout(fig, margins=(0.1, 0.1, 0.08, 0.6))
    fig.suptitle("HVAC Electricity Load vs. BIPV PV Generation (Case 2 - 90 deg)", fontsize=15, fontweight="bold", y=0.95)
    
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)
    plt.close(fig)
    
    print(f"\nSaved Code   → {__file__}")
    print(f"Saved Plot   → {output_png}")
    print(f"Saved Plot   → {output_svg}")

if __name__ == "__main__":
    main()

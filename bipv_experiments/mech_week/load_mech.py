"""mech_week 실행(추적·TiDE, 같은 설정·같은 시작일) SQL 에서 메커니즘 그래프용 10분 자료를 읽는다."""
import sqlite3
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
RUNS = {"st": HERE / "runs" / "mech_st" / "eplusout.sql", "tide": HERE / "runs" / "mech_tide" / "eplusout.sql"}


def load(sql, d0, d1):
    q = f"""SELECT t.Month, t.Day, t.Hour, t.Minute, d.Name, d.KeyValue, v.Value
            FROM ReportData v JOIN ReportDataDictionary d ON v.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex
            JOIN Time t ON v.TimeIndex = t.TimeIndex
            WHERE d.ReportingFrequency = 'Zone Timestep' AND t.Month = 1 AND t.Day BETWEEN {d0} AND {d1}
              AND (t.WarmupFlag IS NULL OR t.WarmupFlag = 0)"""
    with sqlite3.connect(sql) as con:
        r = pd.read_sql(q, con)
    r["t"] = (pd.to_datetime(dict(year=2006, month=r.Month, day=r.Day)) + pd.to_timedelta(r.Hour, "h")
              + pd.to_timedelta(r.Minute, "m") - pd.Timedelta(minutes=10))
    g = lambda m: r[m].pivot_table(index="t", columns="KeyValue", values="Value")  # noqa: E731
    n, k = r.Name, r.KeyValue
    out = pd.DataFrame({
        "pv": g(n == "Generator Produced DC Electricity Energy").sum(1) / 3.6e6,
        "heat": g(n == "Zone Ideal Loads Supply Air Total Heating Energy").sum(1) / 3.6e6 / 2.5,
        "cool": g(n == "Zone Ideal Loads Supply Air Total Cooling Energy").sum(1) / 3.6e6 / 3.0,
        "lights": g(n == "Zone Lights Electricity Energy").sum(1) / 3.6e6,
        "sol_s": g((n == "Surface Window Transmitted Solar Radiation Energy") & k.str.contains("_S..WALL_S_GLZ0", regex=False)).sum(1) / 3.6e6,
    })
    sz = k.str.match(r"BIPV_OFFICE_\d_S\.\.") & ~k.str.contains("GLZ") & ~k.str.contains("WALL_S$")
    cond = g((n == "Surface Inside Face Conduction Heat Transfer Energy") & sz)
    out["store"] = -cond.sum(1) / 3.6e6  # 남측 존 내부 표면(바닥·천장·내벽)으로 들어가 저장되는 열, kWh/10분 (+ 충전, - 방출)
    tf = g((n == "Surface Inside Face Temperature") & k.str.match(r"BIPV_OFFICE_\d_S\.\.FLOOR"))
    out["t_floor"] = tf.mean(1)
    out["t_air_s"] = g((n == "Zone Mean Air Temperature") & k.str.match(r"BIPV_OFFICE_\d_S$")).mean(1)
    out["load"] = out.heat + out.cool + out.lights
    out["purchase"] = (out.load - out.pv).clip(lower=0)
    out["surplus"] = (out.pv - out.load).clip(lower=0)
    return out

import os
import sqlite3

import dartwork_mpl as dm
import matplotlib.pyplot as plt

plt.rcParams["svg.fonttype"] = "none"

HEATING_VAR = "Zone Ideal Loads Supply Air Total Heating Energy"
COOLING_VAR = "Zone Ideal Loads Supply Air Total Cooling Energy"
J_TO_MWH = 1 / 3.6e9


def load_annual_loads_mwh(sql_path):
    if not os.path.exists(sql_path):
        print(f"Missing SQL file: {sql_path}")
        return None

    query = """
        SELECT rdd.Name, SUM(rd.Value) AS TotalJ
        FROM ReportData rd
        JOIN ReportDataDictionary rdd
          ON rd.ReportDataDictionaryIndex = rdd.ReportDataDictionaryIndex
        JOIN Time t
          ON rd.TimeIndex = t.TimeIndex
        WHERE rdd.Name IN (?, ?)
          AND t.WarmupFlag = 0
        GROUP BY rdd.Name
    """

    with sqlite3.connect(sql_path) as conn:
        rows = conn.execute(query, (HEATING_VAR, COOLING_VAR)).fetchall()

    totals = {name: (value or 0.0) * J_TO_MWH for name, value in rows}
    return totals.get(HEATING_VAR, 0.0), totals.get(COOLING_VAR, 0.0)


def add_case(cases, heating, cooling, label, sql_path):
    annual = load_annual_loads_mwh(sql_path)
    if annual is None:
        return

    h_mwh, c_mwh = annual
    cases.append(label)
    heating.append(h_mwh)
    cooling.append(c_mwh)
    print(f"{label.replace(chr(10), ' ')}: Heating={h_mwh:.2f} MWh, Cooling={c_mwh:.2f} MWh")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))

    case1_sql = os.path.join(project_root, "case_analysis", "normal", "case1_KS", "eplusout.sql")
    case2_base = os.path.join(project_root, "case_analysis", "normal", "case2_KS")
    case3_sql = os.path.join(
        project_root,
        "case_analysis",
        "bipv_variation",
        "5zone_NSEW_korean",
        "case3_v3_south",
        "eplusout.sql",
    )

    cases = []
    heating = []
    cooling = []

    add_case(cases, heating, cooling, "Case 1\n(Base)", case1_sql)

    for angle in range(0, 100, 10):
        sql_path = os.path.join(case2_base, f"case2_{angle}", "eplusout.sql")
        add_case(cases, heating, cooling, f"Fixed-{angle}deg", sql_path)

    add_case(cases, heating, cooling, "Case 3\n(Kinetic South)", case3_sql)

    if not cases:
        raise RuntimeError("No annual load data was loaded.")

    totals = [h + c for h, c in zip(heating, cooling)]

    dm.style.use("presentation")
    plt.rcParams.update({"xtick.labelsize": 12, "ytick.labelsize": 12})

    fig, ax = plt.subplots(figsize=(29 / 2.54, 16 / 2.54))
    bar_width = 0.6

    ax.bar(cases, heating, color="oc.red4", label="Heating Load", width=bar_width, alpha=0.85)
    ax.bar(cases, cooling, bottom=heating, color="oc.blue4", label="Cooling Load", width=bar_width, alpha=0.85)

    y_offset = max(totals) * 0.02
    for i, total in enumerate(totals):
        ax.text(
            i,
            total + y_offset,
            f"Total:\n{total:.1f}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="black",
        )

    for i, (h_val, c_val) in enumerate(zip(heating, cooling)):
        if h_val > 0:
            ax.text(
                i,
                h_val / 2,
                f"H:\n{h_val:.1f}",
                ha="center",
                va="center",
                color="white",
                fontsize=14,
                fontweight="bold",
            )

        if c_val > 0:
            ax.text(
                i,
                h_val + c_val / 2,
                f"C:\n{c_val:.1f}",
                ha="center",
                va="center",
                color="white",
                fontsize=14,
                fontweight="bold",
            )

    ax.set_ylabel("Annual Cumulative Load [MWh]")
    ax.set_title("Annual Thermal Load Comparison (Heating + Cooling)", fontsize=17, fontweight="bold")
    ax.set_ylim(0, max(totals) * 1.18)
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: f"{x:,.0f}"))
    ax.legend(loc="upper right")

    script_name = os.path.splitext(os.path.basename(__file__))[0]
    figure_dir = os.path.normpath(os.path.join(script_dir, "..", "plot", script_name))
    os.makedirs(figure_dir, exist_ok=True)
    output_png = os.path.join(figure_dir, "annual_total_comparison_fixed.png")
    output_svg = os.path.join(figure_dir, "annual_total_comparison_fixed.svg")

    dm.simple_layout(fig)
    fig.savefig(output_png, dpi=300, transparent=True)
    fig.savefig(output_svg, transparent=True)

    print(f"Comparison plot saved to: {output_png} and {output_svg}")


if __name__ == "__main__":
    main()

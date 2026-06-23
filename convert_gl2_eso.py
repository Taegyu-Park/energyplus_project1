"""gl2out.eso → gl2out.csv 변환 스크립트 (프로젝트 루트 보관용)

- 10분 타임스텝 데이터를 시간별로 합산/평균 처리
- Generator Produced DC Electricity Energy [J] → Generator Produced DC Electricity Rate [W] 변환
  (J를 타임스텝 초(600s)로 나누어 W로 변환)
"""
import sys
import os
import csv

TIMESTEP_SECONDS = 600  # 10분 = 600초


def convert_eso_to_csv(eso_path, csv_path):
    if not os.path.exists(eso_path):
        print(f"Error: {eso_path} does not exist.")
        return False

    print(f"Parsing ESO file: {eso_path}")

    # Dictionary: code → (full_name, unit_type)
    var_dict = {}
    headers_list = []
    energy_to_rate_codes = set()
    energy_sum_only_codes = set()

    with open(eso_path, "r", encoding="utf-8") as f:
        in_dictionary = True
        current_time_info = None
        current_values = {}

        # 시간별 서브스텝 모음
        hourly_substeps = []  # list of current_values dicts
        rows = []

        for line in f:
            line = line.strip()
            if not line:
                continue

            if line == "End of Data Dictionary":
                in_dictionary = False
                name_to_code = {v: k for k, v in var_dict.items()}
                continue

            if in_dictionary:
                parts = line.split(",")
                if len(parts) >= 3:
                    try:
                        code = parts[0].strip()
                        num_vars = int(parts[1].strip())
                        if num_vars == 1:
                            if len(parts) >= 4:
                                key_val = parts[2].strip()
                                var_name_raw = parts[3].strip()
                                if "!" in var_name_raw:
                                    var_name_raw = var_name_raw.split("!")[0].strip()
                                full_name = f"{key_val}:{var_name_raw}"
                            else:
                                var_name_raw = parts[2].strip()
                                if "!" in var_name_raw:
                                    var_name_raw = var_name_raw.split("!")[0].strip()
                                full_name = var_name_raw

                            # Generator Produced DC Electricity Energy [J] → Rate [W] 변환
                            if "Generator Produced DC Electricity Energy [J]" in full_name:
                                energy_to_rate_codes.add(code)
                                full_name = full_name.replace(
                                    "Generator Produced DC Electricity Energy [J]",
                                    "Generator Produced DC Electricity Rate [W]",
                                )
                            elif "[J]" in full_name:
                                energy_sum_only_codes.add(code)

                            var_dict[code] = full_name
                            headers_list.append(full_name)
                    except ValueError:
                        continue
            else:
                parts = line.split(",")
                if not parts:
                    continue

                code = parts[0].strip()
                if code == "2":
                    # 타임스텝 라인
                    try:
                        month = int(parts[2].strip())
                        day = int(parts[3].strip())
                        hour = int(parts[5].strip())
                        start_min = float(parts[6].strip())
                        day_type = parts[8].strip()
                    except (IndexError, ValueError) as e:
                        print(f"Warning: Failed to parse '{line}': {e}")
                        continue

                    new_time = {"Month": month, "Day": day, "Hour": hour, "DayType": day_type}

                    if current_time_info is not None:
                        # 이전 서브스텝 저장
                        hourly_substeps.append(dict(current_values))

                    # 시간이 바뀌었으면 이전 시간 데이터 집계
                    if (
                        current_time_info is not None
                        and (
                            new_time["Month"] != current_time_info["Month"]
                            or new_time["Day"] != current_time_info["Day"]
                            or new_time["Hour"] != current_time_info["Hour"]
                            or new_time["DayType"] != current_time_info["DayType"]
                        )
                        and hourly_substeps
                    ):
                        row_dict = _aggregate_hour(
                            current_time_info,
                            hourly_substeps,
                            name_to_code,
                            headers_list,
                            energy_to_rate_codes,
                            energy_sum_only_codes,
                        )
                        rows.append(row_dict)
                        hourly_substeps = []

                    current_time_info = new_time
                    current_values = {}

                elif code in var_dict:
                    if current_time_info is not None:
                        try:
                            val = float(parts[1].strip())
                            current_values[code] = val
                        except (IndexError, ValueError):
                            pass

        # 마지막 서브스텝 저장
        if current_time_info is not None and current_values:
            hourly_substeps.append(dict(current_values))

        # 마지막 시간 집계
        if current_time_info is not None and hourly_substeps:
            row_dict = _aggregate_hour(
                current_time_info,
                hourly_substeps,
                name_to_code,
                headers_list,
                energy_to_rate_codes,
                energy_sum_only_codes,
            )
            rows.append(row_dict)

    # CSV 쓰기
    csv_headers = ["Month", "Day", "Hour", "DayType"] + headers_list
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Successfully converted ESO to CSV. Rows: {len(rows)}")
    print(f"Output saved to: {csv_path}")
    return True


def _aggregate_hour(time_info, substeps, name_to_code, headers_list, energy_to_rate_codes, energy_sum_only_codes):
    """시간 단위로 서브스텝 집계: 에너지(J)→합산 혹은 합산 후 W 변환, 나머지→평균"""
    row_dict = {
        "Month": time_info["Month"],
        "Day": time_info["Day"],
        "Hour": time_info["Hour"],
        "DayType": time_info["DayType"],
    }
    n = len(substeps)

    for h in headers_list:
        code_for_h = name_to_code[h]

        if code_for_h in energy_to_rate_codes:
            # J→W: 서브스텝의 J 값을 합산 후, 3600초(1시간)로 나눠서 시간평균 W
            total_j = sum(step.get(code_for_h, 0.0) for step in substeps)
            row_dict[h] = total_j / 3600.0  # J / 3600s = W
        elif code_for_h in energy_sum_only_codes:
            # 에너지 J 단위 합산 유지 (평균내지 않고 그대로 합산)
            total_j = sum(step.get(code_for_h, 0.0) for step in substeps)
            row_dict[h] = total_j
        else:
            # 평균
            total = sum(step.get(code_for_h, 0.0) for step in substeps)
            row_dict[h] = total / n if n > 0 else 0.0

    return row_dict


if __name__ == "__main__":
    eso_file = sys.argv[1] if len(sys.argv) > 1 else "runs/gl2/gl2out.eso"
    csv_file = sys.argv[2] if len(sys.argv) > 2 else eso_file.replace(".eso", ".csv")
    convert_eso_to_csv(eso_file, csv_file)

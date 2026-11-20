from app.modules.m2_calibration.register import register
from app.quality import issue, rows


def calibrate(data, intake):
    plan = intake["plan"]
    registers, isolated = register(rows(data, "calibrations"), plan["zones"])
    corrected, markers = [], list(intake["markers"])
    for point in intake["points"]:
        time = point["time"]
        schedule = registers[point["zone"]]
        active = [item for item in schedule if item["start"] <= time < item["end"]]
        code = None
        if not active:
            code = "CALIBRATION_GAP"
        elif len(active) > 1:
            code = "CALIBRATION_OVERLAP"
        elif abs(active[0]["offset_mc"]) > plan["max_drift_mc"]:
            code = "DRIFT_LIMIT"
        if code:
            evidence = issue(
                code,
                point["row"],
                point["raw"],
                calibration_rows=[item["row"] for item in active],
            )
            isolated.append(evidence)
            markers.append(
                dict(
                    point,
                    **{key: value for key, value in evidence.items() if key != "raw"},
                )
            )
            continue
        choice = active[0]
        next_change = min(
            (
                item["start"]
                for item in schedule
                if time < item["start"] < choice["end"]
            ),
            default=choice["end"],
        )
        corrected.append(
            dict(
                point,
                corrected_mc=point["value_mc"] + choice["offset_mc"],
                calibration_row=choice["row"],
                valid_until=next_change,
            )
        )
    return {
        "corrected": corrected,
        "markers": markers,
        "isolated": isolated,
        "register": dict(registers),
    }

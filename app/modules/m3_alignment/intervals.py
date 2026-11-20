from collections import defaultdict


def zone_spans(plan, calibrated):
    points = defaultdict(list)
    for item in calibrated["corrected"] + calibrated["markers"]:
        points[item["zone"]].append(item)
    spans = {}
    for zone in plan["zones"]:
        ordered = sorted(points[zone], key=lambda point: point["time"])
        zone_rows = []
        for index, point in enumerate(ordered):
            time = point["time"]
            next_time = (
                ordered[index + 1]["time"] if index + 1 < len(ordered) else plan["end"]
            )
            expiry = min(
                time + plan["max_age_s"], point.get("valid_until", plan["end"])
            )
            start, end = max(time, plan["start"]), min(next_time, expiry, plan["end"])
            if start >= end:
                continue
            zone_rows.append(
                {
                    "start": start,
                    "end": end,
                    "value_mc": point.get("corrected_mc"),
                    "code": point.get("code"),
                    "reading_rows": point["rows"],
                    "calibration_row": point.get("calibration_row"),
                }
            )
        spans[zone] = zone_rows
    return spans

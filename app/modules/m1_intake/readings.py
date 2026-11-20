from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.quality import instant, issue, number, token


def temperature(value, unit):
    quantity = number(value)
    if abs(quantity) > 10000:
        raise ValueError
    if unit == "F":
        quantity = (quantity - 32) * 5 / 9
    elif unit != "C":
        raise ValueError
    return int((quantity * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def collect_readings(records, zones):
    buckets = defaultdict(list)
    watermark = {}
    rejected, notices = [], []
    for row, raw in records:
        try:
            zone = token(raw["zone"])
            time = instant(raw["time"])
            if zone not in zones:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            rejected.append(issue("BAD_READING", row, raw))
            continue
        if time < watermark.get(zone, time):
            notices.append(issue("OUT_OF_ORDER", row, raw))
        watermark[zone] = max(time, watermark.get(zone, time))
        try:
            value = temperature(raw["value"], raw["unit"])
        except (KeyError, TypeError, ValueError):
            value = None
            rejected.append(issue("BAD_READING", row, raw))
        buckets[zone, time].append({"row": row, "raw": raw, "value_mc": value})

    accepted, markers = [], []
    for (zone, time), points in sorted(buckets.items()):
        values = {point["value_mc"] for point in points}
        key = {"zone": zone, "time": time, "rows": [point["row"] for point in points]}
        if len(values) != 1 or None in values:
            code = "READING_CONFLICT" if len(values) != 1 else "BAD_READING"
            markers.append(dict(key, code=code))
            rejected.extend(
                issue(code, point["row"], point["raw"])
                for point in points
                if point["value_mc"] is not None
            )
            continue
        first, *duplicates = points
        accepted.append(dict(key, **first))
        notices.extend(
            issue("DUPLICATE_READING", point["row"], point["raw"], kept=first["row"])
            for point in duplicates
        )
    return accepted, markers, rejected, notices

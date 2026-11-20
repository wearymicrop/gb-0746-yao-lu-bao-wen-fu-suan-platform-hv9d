from collections import defaultdict

from app.quality import instant, integer, issue, token


def register(records, zones):
    by_zone = defaultdict(list)
    isolated = []
    for row, raw in records:
        try:
            zone = token(raw["zone"])
            start, end = instant(raw["start"]), instant(raw["end"])
            if zone not in zones or start >= end:
                raise ValueError
            by_zone[zone].append(
                {
                    "row": row,
                    "start": start,
                    "end": end,
                    "offset_mc": integer(raw["offset_mc"], -100000, 100000),
                }
            )
        except (KeyError, TypeError, ValueError):
            isolated.append(issue("BAD_CALIBRATION", row, raw))
    return by_zone, isolated

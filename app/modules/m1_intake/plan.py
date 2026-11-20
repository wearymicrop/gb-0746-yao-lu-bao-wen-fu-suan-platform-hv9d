from app.errors import BusinessError
from app.quality import instant, integer, token


def inspect_plan(raw):
    try:
        zones = [token(zone) for zone in raw["zones"]]
        start, end = instant(raw["start"]), instant(raw["end"])
        if (
            not isinstance(raw["zones"], list)
            or not 1 <= len(zones) <= 16
            or len(set(zones)) != len(zones)
        ):
            raise ValueError
        if not 0 < end - start <= 86400:
            raise ValueError
        return {
            "batch": token(raw["batch"]),
            "zones": zones,
            "start": start,
            "end": end,
            "max_age_s": integer(raw["max_age_s"], 1, 600),
            "goal_s": integer(raw["goal_s"], 1, end - start),
            "max_drift_mc": integer(raw["max_drift_mc"], 0, 50000),
        }
    except (KeyError, TypeError, ValueError) as error:
        raise BusinessError("BAD_PLAN", "炉单须有唯一热区和有效计划时间") from error

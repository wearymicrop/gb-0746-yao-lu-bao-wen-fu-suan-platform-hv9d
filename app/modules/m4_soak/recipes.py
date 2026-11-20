from app.quality import instant, integer, issue, token


def recipe_windows(records, zones):
    versions, isolated = [], []
    for row, raw in records:
        try:
            start, end = instant(raw["start"]), instant(raw["end"])
            if (
                start >= end
                or not isinstance(raw["target_mc"], dict)
                or set(raw["target_mc"]) != set(zones)
            ):
                raise ValueError
            versions.append(
                {
                    "row": row,
                    "version": token(raw["version"]),
                    "start": start,
                    "end": end,
                    "target_mc": {
                        z: integer(raw["target_mc"][z], 0, 1600000) for z in zones
                    },
                }
            )
        except (KeyError, TypeError, ValueError):
            isolated.append(issue("BAD_RECIPE", row, raw))
    return versions, isolated

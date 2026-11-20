def gap_windows(sections):
    gaps = []
    for item in sections:
        if item["state"] != "unproven":
            continue
        zones = sorted(
            zone["zone"] for zone in item["zones"] if zone["value_mc"] is None
        )
        causes = item["codes"]
        if (
            gaps
            and gaps[-1]["end"] == item["start"]
            and gaps[-1]["codes"] == causes
            and gaps[-1]["zones"] == zones
        ):
            current = gaps[-1]
            current["end"] = item["end"]
            current["seconds"] += item["seconds"]
        else:
            current = {
                "start": item["start"],
                "end": item["end"],
                "seconds": item["seconds"],
                "time": item["time"],
                "codes": causes,
                "zones": zones,
                "recipe_rows": [],
                "reading_rows": [],
            }
            gaps.append(current)
        current["recipe_rows"] = sorted(
            set(current["recipe_rows"] + item["recipe_rows"])
        )
        current["reading_rows"] = sorted(
            set(
                current["reading_rows"]
                + [row for zone in item["zones"] for row in zone["reading_rows"]]
            )
        )
    return gaps

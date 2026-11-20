from app.modules.m4_soak.recipes import recipe_windows
from app.quality import rows, utc


def measure(data, plan, alignment):
    versions, isolated = recipe_windows(rows(data, "recipes"), plan["zones"])
    edges = set(alignment["breakpoints"])
    edges.update(
        edge
        for version in versions
        for edge in (version["start"], version["end"])
        if plan["start"] < edge < plan["end"]
    )
    sorted_edges = sorted(edges)
    counters = dict.fromkeys(plan["zones"], 0)
    sections, streaks = [], []
    for start, end in zip(sorted_edges, sorted_edges[1:]):
        recipes = [
            recipe for recipe in versions if recipe["start"] <= start < recipe["end"]
        ]
        chosen = recipes[0] if len(recipes) == 1 else None
        zone_rows, codes = [], []
        if chosen is None:
            codes.append("RECIPE_OVERLAP" if recipes else "RECIPE_GAP")
        for zone, bands in alignment["zones"].items():
            while counters[zone] < len(bands) and bands[counters[zone]]["end"] <= start:
                counters[zone] += 1
            index = counters[zone]
            band = (
                bands[index]
                if index < len(bands) and bands[index]["start"] <= start
                else None
            )
            value = band["value_mc"] if band else None
            target = chosen["target_mc"][zone] if chosen else None
            absent = (band["code"] if band else "NO_READING") if value is None else None
            below = value is not None and target is not None and value < target
            if absent:
                codes.append(absent)
            zone_rows.append(
                {
                    "zone": zone,
                    "value_mc": value,
                    "target_mc": target,
                    "reading_rows": band["reading_rows"] if band else [],
                    "calibration_row": band["calibration_row"] if band else None,
                    "code": absent or ("BELOW_TARGET" if below else None),
                }
            )
        below_target = any(item["code"] == "BELOW_TARGET" for item in zone_rows)
        state = "unproven" if codes else "cold" if below_target else "proven"
        seconds = end - start
        section = {
            "start": start,
            "end": end,
            "time": utc(start),
            "seconds": seconds,
            "state": state,
            "version": chosen["version"] if chosen else None,
            "recipe_rows": [item["row"] for item in recipes],
            "codes": sorted(set(codes))
            or (["BELOW_TARGET"] if below_target else ["PROVEN"]),
            "zones": zone_rows,
        }
        sections.append(section)
        if state == "proven":
            if (
                streaks
                and streaks[-1]["end"] == start
                and streaks[-1]["version"] == section["version"]
            ):
                streaks[-1]["end"] = end
                streaks[-1]["seconds"] += seconds
            else:
                streaks.append(
                    {
                        "start": start,
                        "end": end,
                        "seconds": seconds,
                        "version": section["version"],
                    }
                )
    longest = max((item["seconds"] for item in streaks), default=0)
    return {
        "sections": sections,
        "streaks": streaks,
        "recipes": versions,
        "isolated": isolated,
        "longest_s": longest,
        "goal_s": plan["goal_s"],
        "goal_met": longest >= plan["goal_s"],
    }

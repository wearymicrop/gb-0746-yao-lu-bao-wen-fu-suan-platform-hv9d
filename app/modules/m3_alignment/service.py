from app.modules.m3_alignment.intervals import zone_spans


def align(plan, calibration):
    zones = zone_spans(plan, calibration)
    edges = {plan["start"], plan["end"]}
    for spans in zones.values():
        edges.update(edge for row in spans for edge in (row["start"], row["end"]))
    return {"zones": zones, "breakpoints": sorted(edges)}

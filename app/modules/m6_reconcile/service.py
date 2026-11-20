from collections import Counter


def reconcile(intake, soak, gaps):
    plan = intake["plan"]
    seconds = Counter()
    for row in soak["sections"]:
        seconds[row["state"]] += row["seconds"]
    planned = plan["end"] - plan["start"]
    counts = intake["counts"]
    difference = planned - sum(seconds.values())
    row_difference = (
        counts["input"] - counts["accepted"] - counts["isolated"] - counts["duplicate"]
    )
    continuity = all(
        before["end"] == after["start"]
        for before, after in zip(soak["sections"], soak["sections"][1:])
    )
    continuity &= bool(
        soak["sections"]
        and soak["sections"][0]["start"] == plan["start"]
        and soak["sections"][-1]["end"] == plan["end"]
    )
    return {
        "status": "MATCHED"
        if difference == row_difference == 0
        and continuity
        and gaps["unproven_s"] == seconds["unproven"]
        else "MISMATCH",
        "planned_s": planned,
        "proven_s": seconds["proven"],
        "cold_s": seconds["cold"],
        "unproven_s": seconds["unproven"],
        "difference_s": difference,
        "reading_difference": row_difference,
        "longest_s": soak["longest_s"],
        "goal_met": soak["goal_met"],
        "continuous_partition": continuity,
    }

from bisect import bisect_left

from app.modules.m5_gaps.grouping import gap_windows


def revisit(soak):
    gaps = gap_windows(soak["sections"])
    proven_starts = [streak["start"] for streak in soak["streaks"]]
    for gap in gaps:
        index = bisect_left(proven_starts, gap["end"])
        gap["next_proven"] = (
            proven_starts[index] if index < len(proven_starts) else None
        )
        gap["decision"] = (
            "配方待核"
            if any(code.startswith("RECIPE_") for code in gap["codes"])
            else "断档重计"
        )
    return {
        "gaps": gaps,
        "gap_count": len(gaps),
        "unproven_s": sum(gap["seconds"] for gap in gaps),
    }

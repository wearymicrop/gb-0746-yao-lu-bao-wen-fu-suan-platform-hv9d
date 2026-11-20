from app.pipeline import calculate


def test_version_break_beats_sum(clean_result):
    # TRAP-23
    data = clean_result["soak"]
    assert [(r["version"], r["seconds"]) for r in data["streaks"]] == [
        ("R17", 1200),
        ("R18", 1320),
    ]


def test_all_zones_must_pass_during_same_time(dirty_result):
    cold = [row for row in dirty_result["soak"]["sections"] if row["state"] == "cold"]
    assert (
        len(cold) == 1
        and sum(z["code"] == "BELOW_TARGET" for z in cold[0]["zones"]) == 1
    )
    assert cold[0]["seconds"] == 120


def test_recipe_overlap_cannot_choose_last(dirty_result):
    # TRAP-25
    rows = [
        r for r in dirty_result["soak"]["sections"] if "RECIPE_OVERLAP" in r["codes"]
    ]
    assert all(r["recipe_rows"] == [1, 3] and r["version"] is None for r in rows)
    assert sum(r["seconds"] for r in rows) == 240


def test_early_recipe_with_wrong_zones_isolated(clean):
    clean["recipes"][0]["target_mc"].pop("南墙")
    result = calculate(clean)["soak"]
    assert result["isolated"][0]["code"] == "BAD_RECIPE" and result["sections"][0][
        "codes"
    ] == ["RECIPE_GAP"]


def test_threshold_equal_attains(clean):
    clean["recipes"][0]["target_mc"]["北墙"] = 1146500
    assert calculate(clean)["soak"]["sections"][0]["state"] == "proven"


def test_unknown_thermal_state_counts_before_cold(dirty):
    # TRAP-19
    dirty["readings"] = [
        r
        for r in dirty["readings"]
        if not (r["zone"] == "南墙" and "09:04:" in r["time"])
    ]
    row = next(
        x
        for x in calculate(dirty)["soak"]["sections"]
        if x["time"] == "2026-11-20T01:04:00Z"
    )
    assert row["state"] == "unproven" and row["zones"][0]["code"] == "BELOW_TARGET"

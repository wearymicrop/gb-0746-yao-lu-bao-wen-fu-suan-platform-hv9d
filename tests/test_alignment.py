from app.pipeline import calculate


def test_missing_window_is_not_interpolated(dirty_result):
    starts = [
        (row["start"], row["end"]) for row in dirty_result["alignment"]["zones"]["窑心"]
    ]
    assert starts[4][0] - starts[3][1] == 240


def test_alignment_continuous_for_clean(clean_result):
    north = clean_result["alignment"]["zones"]["北墙"]
    assert len(north) == 21 and all(
        a["end"] == b["start"] for a, b in zip(north, north[1:])
    )


def test_sentinel_cuts_band(dirty_result):
    # TRAP-07
    invalid = [
        row
        for row in dirty_result["alignment"]["zones"]["南墙"]
        if row["code"] == "BAD_READING"
    ]
    assert len(invalid) == 1 and invalid[0]["value_mc"] is None


def test_clip_plan_start(clean):
    clean["plan"]["start"] = "2026-11-20T09:01:00+08:00"
    spans = calculate(clean)["alignment"]["zones"]["北墙"]
    assert spans[0]["end"] - spans[0]["start"] == 60


def test_no_reading_after_plan_in_alignment(clean):
    clean["readings"].append(dict(clean["readings"][0], time=clean["plan"]["end"]))
    assert len(calculate(clean)["alignment"]["zones"]["北墙"]) == 21


def test_zone_empty_retains_missing_lane(clean):
    clean["readings"] = [r for r in clean["readings"] if r["zone"] != "窑心"]
    result = calculate(clean)
    assert (
        result["alignment"]["zones"]["窑心"] == []
        and result["reconcile"]["unproven_s"] == 2520
    )

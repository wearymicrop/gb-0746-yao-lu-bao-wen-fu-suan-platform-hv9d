from app.pipeline import calculate


def test_gap_counts(dirty_result):
    assert (
        dirty_result["gaps"]["gap_count"] == 5
        and dirty_result["gaps"]["unproven_s"] == 840
    )


def test_revisit_groups_contiguous_missing_items(dirty_result):
    gap = dirty_result["gaps"]["gaps"][0]
    assert (
        gap["seconds"] == 240
        and gap["zones"] == ["窑心"]
        and gap["next_proven"] == gap["end"]
    )


def test_recipe_evidence_retains_both_sources(dirty_result):
    recipe = dirty_result["gaps"]["gaps"][1]
    assert recipe["recipe_rows"] == [1, 3] and recipe["decision"] == "配方待核"


def test_distinct_causes_are_not_merged(dirty_result):
    assert [row["codes"][0] for row in dirty_result["gaps"]["gaps"]] == [
        "NO_READING",
        "RECIPE_OVERLAP",
        "BAD_READING",
        "READING_CONFLICT",
        "DRIFT_LIMIT",
    ]


def test_no_recovery_after_final_gap(clean):
    clean["readings"] = clean["readings"][:-1]
    assert calculate(clean)["gaps"]["gaps"][-1]["next_proven"] is None


def test_clean_batch_no_review_windows(clean_result):
    assert clean_result["gaps"] == {"gaps": [], "gap_count": 0, "unproven_s": 0}

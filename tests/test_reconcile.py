import pytest
from app.errors import BusinessError
from app.modules.m6_reconcile.service import reconcile
from app.modules.m7_archive.signoff import approval


def test_dirty_totals_partition_plan(dirty_result):
    r = dirty_result["reconcile"]
    assert (r["planned_s"], r["proven_s"], r["cold_s"], r["unproven_s"]) == (
        2520,
        1560,
        120,
        840,
    )


def test_clean_longest_passes_goal(clean_result):
    assert (
        clean_result["reconcile"]["longest_s"] == 1320
        and clean_result["reconcile"]["goal_met"]
    )


def test_interval_discontinuity_detected(clean_result):
    clean_result["soak"]["sections"][1]["start"] += 1
    r = reconcile(clean_result["intake"], clean_result["soak"], clean_result["gaps"])
    assert not r["continuous_partition"] and r["status"] == "MISMATCH"


def test_seconds_and_gap_totals_must_agree(dirty_result):
    dirty_result["gaps"]["unproven_s"] -= 1
    assert (
        reconcile(dirty_result["intake"], dirty_result["soak"], dirty_result["gaps"])[
            "status"
        ]
        == "MISMATCH"
    )


def test_duplicate_is_in_reading_balance(dirty_result):
    dirty_result["intake"]["counts"]["duplicate"] = 0
    r = reconcile(dirty_result["intake"], dirty_result["soak"], dirty_result["gaps"])
    assert r["reading_difference"] == 1 and r["status"] == "MISMATCH"


def test_no_publish_on_mismatched_balance(clean_result):
    clean_result["reconcile"]["status"] = "MISMATCH"
    with pytest.raises(BusinessError, match="尚未对平"):
        approval(clean_result)


def test_archive_business_decisions(clean_result, dirty_result):
    assert (
        approval(clean_result)["status"] == "RELEASED"
        and approval(dirty_result)["status"] == "REVIEW"
    )

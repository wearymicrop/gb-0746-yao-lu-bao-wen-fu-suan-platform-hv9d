import pytest
from app.errors import BusinessError
from app.modules.m1_intake.plan import inspect_plan
from app.modules.m1_intake.readings import temperature
from app.modules.m1_intake.service import intake


def test_clean_rows_are_normalized(clean_result):
    assert clean_result["intake"]["counts"] == {
        "input": 63,
        "accepted": 63,
        "isolated": 0,
        "duplicate": 0,
    }


def test_dirty_out_of_order_kept(dirty_result):
    # TRAP-13
    intake_result = dirty_result["intake"]
    assert "OUT_OF_ORDER" in {item["code"] for item in intake_result["notices"]}
    times = [p["time"] for p in intake_result["points"] if p["zone"] == "北墙"]
    assert times == sorted(times) and len(times) == 21


def test_offset_duplicate(dirty_result):
    # TRAP-11
    assert dirty_result["intake"]["counts"]["duplicate"] == 1
    marker = next(
        row
        for row in dirty_result["intake"]["notices"]
        if row["code"] == "DUPLICATE_READING"
    )
    assert marker["kept"] == 1 and marker["raw"]["time"].endswith("Z")


def test_conflicting_duplicate_quarantines_both(dirty_result):
    # TRAP-14
    conflicts = [
        row
        for row in dirty_result["intake"]["isolated"]
        if row["code"] == "READING_CONFLICT"
    ]
    assert (
        len(conflicts) == 2 and len(dirty_result["intake"]["markers"][-1]["rows"]) == 2
    )


def test_temperature_conversion_and_lexical_bound():
    # TRAP-06、TRAP-15
    assert temperature("2,111", "F") == 1155000
    with pytest.raises(ValueError):
        temperature("21,11", "F")


def test_invalid_plan_zone_names(clean):
    clean["plan"]["zones"] = ["北墙", "北墙"]
    with pytest.raises(BusinessError, match="唯一热区"):
        inspect_plan(clean["plan"])


def test_unknown_zone_isolated(clean):
    clean["readings"].append(dict(clean["readings"][0], zone="外墙"))
    assert intake(clean)["isolated"][-1]["row"] == 64

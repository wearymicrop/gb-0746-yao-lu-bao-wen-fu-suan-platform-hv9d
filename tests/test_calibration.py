from app.pipeline import calculate


def test_apply_signed_calibration(clean_result):
    point = next(
        x for x in clean_result["calibration"]["corrected"] if x["zone"] == "窑心"
    )
    assert point["corrected_mc"] == point["value_mc"] - 600


def test_drift_isolated(dirty_result):
    row = next(
        x for x in dirty_result["calibration"]["isolated"] if x["code"] == "DRIFT_LIMIT"
    )
    assert row["calibration_rows"] == [4]


def test_conflicting_calibrations_do_not_apply(clean):
    clean["calibrations"].append(dict(clean["calibrations"][0], offset_mc=200))
    isolated = calculate(clean)["calibration"]["isolated"]
    assert len(isolated) == 21 and isolated[0]["calibration_rows"] == [1, 4]


def test_calibration_end_is_exclusive(clean):
    clean["calibrations"][0]["end"] = clean["plan"]["start"]
    assert (
        sum(
            x["code"] == "CALIBRATION_GAP"
            for x in calculate(clean)["calibration"]["isolated"]
        )
        == 21
    )


def test_bad_register_kept_as_evidence(clean):
    clean["calibrations"].append({"zone": "北墙", "start": "昨天"})
    assert calculate(clean)["calibration"]["isolated"][0]["code"] == "BAD_CALIBRATION"


def test_expiry_stops_on_upcoming_overlap(clean):
    clean["calibrations"].append(
        dict(clean["calibrations"][0], start="2026-11-20T09:01:00+08:00")
    )
    result = calculate(clean)
    first = result["alignment"]["zones"]["北墙"][0]
    assert first["end"] - first["start"] == 60

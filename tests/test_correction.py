import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.manifest import digest
from app.modules.m8_correction.schema import consistent_correction
from app.store import Ledger

SIGN = {"source": "dirty", "operator": "值班员"}
FIX = {
    "zone": "南墙",
    "start": "2026-11-20T09:34:00+08:00",
    "end": "2026-11-20T09:36:00+08:00",
    "offset_mc": 1100,
    "replaces_row": 4,
    "reason": "探头校验证实热区单偏移误录",
    "document": "CAL-1120-04",
    "received_at": "2026-11-20T09:50:00+08:00",
}
BODY = {"recorder": "值班员", "corrections": [FIX]}


def sign(client):
    return client.post("/api/runs", json=SIGN).json()


def submit(client, run, body=BODY):
    return client.post("/api/corrections", json=dict(body, base_run=run["id"]))


def test_correction_recalculates_whole_chain(client, dirty):
    run = sign(client)
    response = submit(client, run)
    assert response.status_code == 200
    record = response.json()

    assert record["status"] == "FORMAL" and record["reused"] is False
    assert record["approval"]["status"] == "REVIEW"
    balance = record["result"]["reconcile"]
    assert balance["status"] == "MATCHED"
    assert (balance["proven_s"], balance["unproven_s"], balance["longest_s"]) == (
        1680,
        720,
        720,
    )
    assert record["result"]["gaps"]["gap_count"] == 4

    register = record["result"]["calibration"]["register"]["南墙"]
    assert next(row for row in register if row["row"] == 4)["offset_mc"] == 1100
    window = next(
        row
        for row in record["result"]["alignment"]["zones"]["南墙"]
        if row["reading_rows"] == [58]
    )
    assert window["calibration_row"] == 4 and window["code"] is None
    section = next(
        row for row in record["result"]["soak"]["sections"] if row["start"] == window["start"]
    )
    assert section["state"] == "proven"

    # 炉单与同批读数原样沿用，只在校准段改写。
    assert record["result"]["intake"]["counts"] == run["result"]["intake"]["counts"]
    assert record["result"]["intake"]["plan"] == run["result"]["intake"]["plan"]
    assert record["plan_sha256"] == digest(run["input"]["plan"])
    assert record["readings_sha256"] == digest(run["input"]["readings"])
    assert record["base_input_sha256"] == run["manifest"]["input_sha256"]
    assert record["input_sha256"] != run["manifest"]["input_sha256"]


def test_original_signed_bundle_stays_untouched(client):
    run = sign(client)
    submit(client, run)
    again = client.get(f"/api/runs/{run['id']}").json()
    assert again["id"] == run["id"]
    for field in ("manifest", "approval", "result", "input"):
        assert again[field] == run[field]


def test_diff_shows_evidence_superseded_and_before_after(client):
    run = sign(client)
    record = submit(client, run).json()
    assert record["supersedes"] == run["id"]
    assert record["supersedes_kind"] == "run"
    assert record["base_approval"] == run["approval"]
    assert record["corrections"][0]["document"] == "CAL-1120-04"
    assert record["corrections"][0]["received_at"] == "2026-11-20T01:50:00Z"

    diff = record["diff"]
    assert diff["before"]["proven_s"] == 1560 and diff["before"]["unproven_s"] == 840
    assert diff["after"]["proven_s"] == 1680 and diff["after"]["unproven_s"] == 720
    assert diff["calibration"]["replaced"] == [
        {"row": 4, "zone": "南墙", "before_mc": 4700, "after_mc": 1100}
    ]
    assert "南墙" in diff["alignment"]
    assert diff["soak"]["sections"][0]["before"]["state"] == "unproven"
    assert diff["soak"]["totals"]["longest_s"] == {
        "before": 360,
        "after": 720,
        "changed": True,
    }
    assert diff["soak"]["streaks"]["changed"] is True
    assert diff["gaps"] and diff["gaps"][0]["after"] is None
    assert diff["reconcile"]["proven_s"] == {"before": 1560, "after": 1680}


def test_repeat_submission_is_one_conclusion_without_stacking(client):
    run = sign(client)
    first = submit(client, run).json()
    again = submit(client, run).json()
    assert again["id"] == first["id"] and again["reused"] is True
    assert again["repeated"] is True
    assert again["evidence_changed"] is False
    assert again["result"]["reconcile"]["proven_s"] == 1680

    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert len(chain["corrections"]) == 1
    assert chain["current"] == first["id"] and chain["current_kind"] == "correction"


def test_repeat_with_new_evidence_reuses_conclusion_but_flags_it(client):
    run = sign(client)
    first = submit(client, run).json()
    again = submit(
        client,
        run,
        {
            "recorder": "复核员",
            "corrections": [dict(FIX, document="CAL-1120-04A", reason="补送原件")],
        },
    ).json()
    assert again["id"] == first["id"] and again["reused"] is True
    assert again["evidence_changed"] is True
    assert "1" in again["evidence_note"]
    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert len(chain["corrections"]) == 1
    assert chain["corrections"][0]["received_at"] == ["2026-11-20T01:50:00Z"]


def test_concurrent_repeat_submission_creates_one_formal(client):
    run = sign(client)
    with ThreadPoolExecutor(4) as pool:
        records = list(pool.map(lambda _: submit(client, run).json(), range(4)))
    assert len({row["id"] for row in records}) == 1
    assert sum(row["reused"] for row in records) == 3
    assert {row["result"]["reconcile"]["proven_s"] for row in records} == {1680}
    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert len(chain["corrections"]) == 1


def test_later_correction_supersedes_earlier_and_is_not_accumulated(client):
    run = sign(client)
    first = submit(client, run).json()
    second = submit(
        client,
        run,
        {
            "recorder": "复核员",
            "corrections": [dict(FIX, offset_mc=1200, received_at=None)],
        },
    ).json()
    assert second["id"] != first["id"]
    assert second["supersedes"] == first["id"]
    assert second["supersedes_kind"] == "correction"
    assert second["diff"]["before"] == dict(
        first["diff"]["after"], approval=first["approval"]["status"]
    )
    balance = second["result"]["reconcile"]
    assert (balance["proven_s"], balance["unproven_s"]) == (1680, 720)

    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert [row["id"] for row in chain["corrections"]] == [first["id"], second["id"]]
    assert chain["current"] == second["id"]


def test_unbalanced_result_cannot_become_formal(client, monkeypatch):
    run = sign(client)
    module = __import__("app.modules.m8_correction.service", fromlist=["approval"])
    from app.errors import BusinessError

    def unbalanced(result):
        raise BusinessError("UNBALANCED", "炉批尚未对平", 409)

    monkeypatch.setattr(module, "approval", unbalanced)
    record = submit(client, run).json()
    monkeypatch.undo()

    assert record["status"] == "PENDING" and record["approval"] is None
    assert record["pending"]["code"] == "UNBALANCED"
    assert client.get(f"/api/corrections/{record['id']}/export").status_code == 409

    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert chain["current"] == run["id"] and chain["current_kind"] == "run"

    # 修正后的下一次更正仍可正式化，并把待核尝试留在链上供追溯。
    fixed = submit(client, run, {"recorder": "值班员", "corrections": [FIX]}).json()
    assert fixed["status"] == "FORMAL" and fixed["supersedes"] == run["id"]
    assert fixed["previous_attempt"] == record["id"]
    chain = client.get(f"/api/runs/{run['id']}/corrections").json()
    assert [row["status"] for row in chain["corrections"]] == ["PENDING", "FORMAL"]
    assert chain["current"] == fixed["id"]


def test_interrupted_recalculation_leaves_no_conclusion_and_retries(tmp_path):
    ledger = Ledger(tmp_path / "retry.sqlite3")
    app_runner = TestClient(create_app(tmp_path / "retry.sqlite3"))
    with app_runner as client:
        run = sign(client)

    service = __import__("app.modules.m8_correction.service", fromlist=["submit"])
    real = service.snapshot
    calls = {"n": 0}

    def broken(serialized):
        calls["n"] += 1
        raise RuntimeError("复算中断")

    service.snapshot = broken
    try:
        with pytest.raises(RuntimeError):
            service.submit(ledger, run["id"], [FIX], "值班员")
    finally:
        service.snapshot = real
    assert calls["n"] == 1
    assert ledger.correction_chain(run["manifest"]["input_sha256"]) == []

    record = service.submit(ledger, run["id"], [FIX], "值班员")
    again = service.submit(ledger, run["id"], [FIX], "值班员")
    assert record["status"] == "FORMAL" and record["reused"] is False
    assert again["id"] == record["id"] and again["reused"] is True
    assert len(ledger.correction_chain(run["manifest"]["input_sha256"])) == 1


def test_invalid_corrections_are_rejected(client):
    run = sign(client)
    cases = [
        {"corrections": []},
        {"corrections": [dict(FIX, zone="外墙")]},
        {"corrections": [dict(FIX, replaces_row=99)]},
        {"corrections": [dict(FIX, zone="北墙")]},
        {"corrections": [dict(FIX, start=FIX["end"])]},
        {"corrections": [dict(FIX, offset_mc=200000)]},
        {"corrections": [dict(FIX), dict(FIX)]},
    ]
    for case in cases:
        response = submit(client, run, dict(BODY, **case))
        assert response.status_code == 422, case
        assert response.json()["code"].startswith("CORRECTION") or response.json()[
            "code"
        ] == "BAD_CORRECTION"
    assert client.get(f"/api/runs/{run['id']}/corrections").json()["corrections"] == []


def test_unknown_base_and_missing_recorder(client):
    assert (
        submit(client, {"id": "run-absent"}).json()["code"] == "RUN_NOT_FOUND"
    )
    run = sign(client)
    response = submit(client, run, {"corrections": [FIX], "recorder": ""})
    assert response.status_code == 422 and response.json()["code"] == "RECORDER_REQUIRED"


def test_correction_export_is_verifiable_and_tamper_evident(client, tmp_path):
    run = sign(client)
    record = submit(client, run).json()
    assert consistent_correction(record)

    export = client.get(f"/api/corrections/{record['id']}/export")
    assert export.status_code == 200
    assert export.headers["content-disposition"].startswith("attachment")
    assert export.json()["id"] == record["id"]

    tampered = json.loads(json.dumps(record))
    tampered["approval"]["status"] = "RELEASED"
    assert not consistent_correction(tampered)

    file = tmp_path / "更正.json"
    file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    command = [sys.executable, "-m", "app.modules.m7_archive.verify", str(file)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    assert result.returncode == 0 and result.stdout.strip() == "摘要一致"


def test_clean_batch_correction_keeps_release(client, clean):
    source = client.post("/api/sources", json=clean).json()["source"]
    run = client.post("/api/runs", json={"source": source, "operator": "值班员"}).json()
    assert run["approval"]["status"] == "RELEASED"
    record = submit(
        client,
        run,
        {
            "recorder": "值班员",
            "corrections": [
                {
                    "zone": "南墙",
                    "start": "2026-11-20T09:00:00+08:00",
                    "end": "2026-11-20T09:42:00+08:00",
                    "offset_mc": 1100,
                    "replaces_row": 3,
                    "reason": "按校验单原件抄录",
                    "document": "CAL-1120-03",
                }
            ],
        },
    ).json()
    assert record["status"] == "FORMAL"
    assert record["approval"]["status"] == "RELEASED"
    assert record["result"]["reconcile"]["longest_s"] == 1320


def test_appended_calibration_window_closes_gap_and_releases(client, clean):
    clean["calibrations"][0]["end"] = "2026-11-20T09:20:00+08:00"
    source = client.post("/api/sources", json=clean).json()["source"]
    run = client.post("/api/runs", json={"source": source, "operator": "值班员"}).json()
    assert run["approval"]["status"] == "REVIEW"
    assert run["result"]["reconcile"]["unproven_s"] == 1320

    record = submit(
        client,
        run,
        {
            "recorder": "值班员",
            "corrections": [
                {
                    "zone": "北墙",
                    "start": "2026-11-20T09:20:00+08:00",
                    "end": "2026-11-20T09:50:00+08:00",
                    "offset_mc": 500,
                    "reason": "补录换探头后的校准单",
                    "document": "CAL-1120-09",
                    "received_at": "2026-11-20T09:48:00+08:00",
                }
            ],
        },
    ).json()
    assert record["status"] == "FORMAL"
    assert record["approval"]["status"] == "RELEASED"
    balance = record["result"]["reconcile"]
    assert (balance["unproven_s"], balance["proven_s"]) == (0, 2520)
    diff = record["diff"]
    assert diff["calibration"]["appended"][0]["zone"] == "北墙"
    first = diff["alignment"]["北墙"][0]
    assert first["before"]["code"] == "CALIBRATION_GAP"
    assert first["after"]["code"] is None and first["after"]["calibration_row"] == 4

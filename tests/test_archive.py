from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app
from app.manifest import digest


SIGN = {"source": "dirty", "operator": "值班员"}


def test_manifest_tracks_input_and_result(client, dirty):
    record = client.post("/api/runs", json=SIGN).json()
    assert record["manifest"]["input_sha256"] == digest(dirty)
    assert record["manifest"]["result_sha256"] == digest(record["result"])


def test_idempotent_concurrent_archive(client):
    with ThreadPoolExecutor(4) as pool:
        records = list(
            pool.map(lambda _: client.post("/api/runs", json=SIGN).json(), range(4))
        )
    assert len({row["id"] for row in records}) == 1
    assert sum(row["reused"] for row in records) == 3


def test_rerun_same_digest(client):
    first = client.post("/api/runs", json=SIGN).json()
    again = client.post(f"/api/runs/{first['id']}/rerun").json()
    assert again == dict(first, reused=True)


def test_export_attachment(client):
    first = client.post("/api/runs", json=SIGN).json()
    export = client.get(f"/api/runs/{first['id']}/export")
    assert export.headers["content-disposition"].startswith("attachment")
    assert export.json()["result"] == first["result"]
    assert export.json()["input"] == first["input"]


def test_reopen_persistent_input_and_run(tmp_path, dirty):
    file = tmp_path / "state.sqlite3"
    with TestClient(create_app(file)) as client:
        source = client.post("/api/sources", json=dirty).json()["source"]
        record = client.post("/api/runs", json=dict(SIGN, source=source)).json()
    with TestClient(create_app(file)) as client:
        stored = client.get(f"/api/runs/{record['id']}").json()
        assert stored["id"] == record["id"]
        assert stored["approval"] == record["approval"]
        assert client.post(f"/api/runs/{record['id']}/rerun").json()["reused"] is True
        assert client.post("/api/sources", json=dirty).json()["reused"] is True


def test_missing_signer_and_unknown_records(client):
    response = client.post("/api/runs", json={"source": "dirty"})
    assert (
        response.status_code == 422 and response.json()["code"] == "OPERATOR_REQUIRED"
    )
    assert client.get("/api/runs/absent").json()["code"] == "RUN_NOT_FOUND"


def test_operator_is_part_of_signoff_identity(client):
    first = client.post("/api/runs", json=SIGN).json()
    second = client.post("/api/runs", json=dict(SIGN, operator="复核员")).json()
    assert first["id"] != second["id"]
    assert second["manifest"]["operator"] == "复核员"

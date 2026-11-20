import json
import os
import subprocess
import sys

from app.modules.m7_archive.bundle import consistent


def test_digest_detects_signed_decision_edit(client):
    record = client.post(
        "/api/runs", json={"source": "dirty", "operator": "值班员"}
    ).json()
    assert consistent(record)
    record["approval"]["status"] = "edited"
    assert not consistent(record)


def test_offline_verifier_roundtrip(client, tmp_path):
    record = client.post(
        "/api/runs", json={"source": "dirty", "operator": "值班员"}
    ).json()
    file = tmp_path / "证据.json"
    file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    command = [sys.executable, "-m", "app.modules.m7_archive.verify", str(file)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode == 0 and result.stdout.strip() == "摘要一致"
    assert not consistent({"manifest": []})

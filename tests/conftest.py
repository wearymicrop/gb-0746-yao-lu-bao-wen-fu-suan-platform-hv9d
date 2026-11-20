import json

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT
from app.main import create_app
from app.pipeline import calculate


def sample(key):
    return json.loads(
        (ROOT / "sample_data" / f"{key}.json").read_text(encoding="utf-8-sig")
    )


@pytest.fixture
def clean():
    return sample("clean")


@pytest.fixture
def dirty():
    return sample("dirty")


@pytest.fixture
def clean_result(clean):
    return calculate(clean)


@pytest.fixture
def dirty_result(dirty):
    return calculate(dirty)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as session:
        yield session

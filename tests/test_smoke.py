"""Smoke test: every workspace package imports and the services expose /healthz."""

import importlib

import pytest
from fastapi.testclient import TestClient

PACKAGES = [
    "neet_common",
    "neet_retrieval",
    "neet_answer",
    "neet_predictor",
    "neet_ingest",
    "neet_eval",
    "neet_bench",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    importlib.import_module(name)


@pytest.mark.parametrize("service", ["retrieval", "answer", "predictor"])
def test_healthz(service: str) -> None:
    app = importlib.import_module(f"neet_{service}.app").app
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == service

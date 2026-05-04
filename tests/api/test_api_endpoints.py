from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    os.environ["BH_API_KEY"] = "test-key"
    os.environ["BH_API_RATE_LIMIT_ENABLED"] = "0"
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"x-api-key": "test-key", "x-request-id": "pytest-request-001"}


def test_health_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_periods_requires_api_key(client: TestClient):
    resp = client.get("/periods")
    assert resp.status_code == 401
    payload = resp.json()
    assert payload["code"] == "UNAUTHORIZED"
    assert "request_id" in payload["details"]


def test_periods_with_api_key_ok(client: TestClient):
    resp = client.get("/periods", headers=_auth_headers())
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_period_summary_validation_error_for_bad_year(client: TestClient):
    resp = client.get("/period/1800/Abril", headers=_auth_headers())
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "request_id" in payload["details"]


def test_rate_limit_disabled_does_not_block(client: TestClient):
    for _ in range(3):
        resp = client.get("/periods", headers=_auth_headers())
        assert resp.status_code == 200


def test_period_based_endpoints_if_data_exists(client: TestClient):
    periods_resp = client.get("/periods", headers=_auth_headers())
    assert periods_resp.status_code == 200
    periods = periods_resp.json()
    if not periods:
        pytest.skip("No hay periodos cargados en la BD para validar endpoints por periodo.")

    year = periods[0]["year"]
    month = periods[0]["month_name"]

    summary_resp = client.get(f"/period/{year}/{month}", headers=_auth_headers())
    assert summary_resp.status_code == 200
    assert "metrics" in summary_resp.json()

    boletas_resp = client.get(f"/period/{year}/{month}/boletas?limit=10&offset=0", headers=_auth_headers())
    assert boletas_resp.status_code == 200
    assert "data" in boletas_resp.json()

    search_bad = client.get(
        f"/period/{year}/{month}/search/boletas?q=a&limit=10&offset=0",
        headers=_auth_headers(),
    )
    assert search_bad.status_code == 422

    search_ok = client.get(
        f"/period/{year}/{month}/search/boletas?q={month[:2]}&limit=10&offset=0",
        headers=_auth_headers(),
    )
    assert search_ok.status_code == 200
    assert "data" in search_ok.json()

    runs_resp = client.get("/runs?limit=5&offset=0", headers=_auth_headers())
    assert runs_resp.status_code == 200
    assert "data" in runs_resp.json()

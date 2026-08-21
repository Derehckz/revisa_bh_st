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
    body = resp.json()
    assert body["status"] == "ok"
    assert body.get("capabilities_version", 0) >= 1
    assert body.get("capabilities", {}).get("glosa_estricta") is True


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


def test_db_migrate_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "api.operations.db_migrate",
        lambda: {"ok": True, "message": "Migraciones aplicadas (head)"},
    )
    resp = client.post("/operations/db/migrate", headers=_auth_headers(), json={})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_db_consistency_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "api.operations.db_consistency_check",
        lambda limit=20: {"ok": True, "findings": [], "critical_count": 0, "warning_count": 0},
    )
    resp = client.post(
        "/operations/db/consistency-check",
        headers=_auth_headers(),
        json={"limit": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_server_restart_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "api.operations.server_restart",
        lambda port=8000: {"ok": True, "message": "Reiniciando"},
    )
    resp = client.post("/operations/server/restart", headers=_auth_headers(), json={})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_step0_arrastre_preview_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    fake = {
        "year": 2026,
        "month": "Agosto",
        "lookback": [{"month": "Julio", "year": 2026, "closed": True, "has_solicitud": True}],
        "previous_closed": True,
        "count": 1,
        "total_monto": 30000.0,
        "rows": [{"emplid": "1-9", "name": "Demo", "institucion": "IP", "monto": 30000, "glosa": "x", "email": "a@b.cl", "rut_razon": "1-9"}],
        "message": "Al generar se agregará 1 fila.",
    }
    monkeypatch.setattr("api.operations.preview_step0_arrastre", lambda year, month: fake)
    resp = client.get("/operations/step0/arrastre-preview?year=2026&month=Agosto", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["previous_closed"] is True
    assert body["rows"][0]["name"] == "Demo"

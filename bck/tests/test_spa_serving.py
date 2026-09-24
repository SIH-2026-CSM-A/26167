"""Tests for FastAPI static file serving and SPA catch-all routing."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import _resolve_frontend_dist, app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_serve_root_returns_index_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SatQuery AI" in response.text


def test_serve_spa_client_routes(client: TestClient) -> None:
    for route in ["/upload", "/chat", "/login", "/auth/callback"]:
        response = client.get(route)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "SatQuery AI" in response.text


def test_serve_static_assets(client: TestClient) -> None:
    dist_dir = _resolve_frontend_dist()
    js_file = next((dist_dir / "assets").glob("*.js"), None)
    if js_file is None:
        pytest.skip("No compiled JS assets found in frontend dist")
    response = client.get(f"/assets/{js_file.name}")
    assert response.status_code == 200
    assert (
        "javascript" in response.headers.get("content-type", "")
        or "text/" in response.headers.get("content-type", "")
    )


def test_unknown_api_routes_return_404(client: TestClient) -> None:
    response = client.get("/api/unknown_subpath")
    assert response.status_code == 404
    assert response.json() == {"detail": "API endpoint not found"}

    response_bare = client.get("/api")
    assert response_bare.status_code == 404
    assert response_bare.json() == {"detail": "API endpoint not found"}


def test_api_query_endpoint_takes_precedence(client: TestClient) -> None:
    # POST to /api/query with no body triggers FastAPI validation (422) or auth (401), not SPA HTML
    response = client.post("/api/query")
    assert response.status_code in (401, 422)
    assert "detail" in response.json()


def test_missing_frontend_build_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty_dist = tmp_path / "empty_dist"
    empty_dist.mkdir()
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(empty_dist))

    response = client.get("/")
    assert response.status_code == 404
    assert "Frontend build not found" in response.json().get("detail", "")

    response_route = client.get("/dashboard")
    assert response_route.status_code == 404
    assert "Frontend build not found" in response_route.json().get("detail", "")


def test_dynamic_frontend_dist_serves_custom_files(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_dist = tmp_path / "custom_dist"
    custom_dist.mkdir()
    assets_dir = custom_dist / "assets"
    assets_dir.mkdir()

    (custom_dist / "index.html").write_text(
        "<!doctype html><html>Custom SPA</html>", encoding="utf-8"
    )
    (assets_dir / "custom.js").write_text(
        "console.log('custom');", encoding="utf-8"
    )

    monkeypatch.setenv("FRONTEND_DIST_DIR", str(custom_dist))
    custom_client = TestClient(app)

    response_root = custom_client.get("/")
    assert response_root.status_code == 200
    assert "Custom SPA" in response_root.text

    response_asset = custom_client.get("/assets/custom.js")
    assert response_asset.status_code == 200
    assert "console.log('custom');" in response_asset.text


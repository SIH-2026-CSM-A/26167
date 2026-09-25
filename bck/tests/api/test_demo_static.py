"""/data/demo is served read-only; nothing else under data/ is reachable."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_demo_manifest_and_assets_are_served():
    manifest = client.get("/data/demo/manifest.json")
    assert manifest.status_code == 200
    assert manifest.json()["presets"]
    asset = client.get("/data/demo/assets/levir_cd_train_103_9_before.png")
    assert asset.status_code == 200
    assert asset.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        "/data/demo/",
        "/data/demo/assets/",
        "/data/demo/../demo/manifest.json/../../rasters/x.tif",
        "/data/demo/%2e%2e/rasters/x.tif",
        "/data/demo/..%2f..%2fbck/pyproject.toml",
        "/data/rasters/x.tif",
        "/data/",
        "/data",
    ],
)
def test_directories_and_other_data_paths_are_404(path):
    response = client.get(path)
    assert response.status_code == 404, (path, response.status_code, response.text[:80])

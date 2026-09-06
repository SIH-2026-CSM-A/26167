"""Unit tests for TiTiler XYZ tile URL templating helpers."""

from urllib.parse import parse_qs, unquote_plus, urlsplit

import pytest

from app.core.config import Settings
from app.core.tiles import get_cog_tile_url


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://satquery:satquery_local_dev@localhost:5432/satquery",
        cost_ceiling=10.0,
        titiler_base_url="http://localhost:8001",
        _env_file=None,
    )


def test_get_cog_tile_url_local_path(mock_settings: Settings) -> None:
    local_path = "/var/data/cogs/scene_optical_2026.tif"
    url = get_cog_tile_url(local_path, settings=mock_settings)

    expected_prefix = "http://localhost:8001/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?url="
    assert url.startswith(expected_prefix)

    # Validate literal curly braces
    assert "/{z}/{x}/{y}?" in url
    assert "{z}" in url
    assert "{x}" in url
    assert "{y}" in url

    # Validate query parameter encoding converts slashes safely
    parsed = urlsplit(url)
    query_params = parse_qs(parsed.query)
    assert "url" in query_params
    assert query_params["url"][0] == local_path
    assert "%2Fvar%2Fdata%2Fcogs%2Fscene_optical_2026.tif" in url


def test_get_cog_tile_url_remote_url(mock_settings: Settings) -> None:
    remote_cog = (
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
        "11/S/KV/2026/6/S2B_11SKV_20260614_0_L2A/B04.tif"
    )
    url = get_cog_tile_url(remote_cog, settings=mock_settings)

    expected_prefix = "http://localhost:8001/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?url="
    assert url.startswith(expected_prefix)

    # Literal placeholders
    assert "/{z}/{x}/{y}?" in url

    # Encoded query parameter
    assert "%3A%2F%2F" in url
    assert "https://" not in url.split("?url=")[1]

    # Decodes back to original URL
    encoded_part = url.split("?url=")[1]
    assert unquote_plus(encoded_part) == remote_cog


def test_get_cog_tile_url_custom_tile_matrix_set(mock_settings: Settings) -> None:
    local_path = "/data/imagery/cog.tif"
    custom_tms = "WorldCRS84Quad"
    url = get_cog_tile_url(local_path, tile_matrix_set=custom_tms, settings=mock_settings)

    assert f"/cog/tiles/{custom_tms}/{{z}}/{{x}}/{{y}}?url=" in url


def test_get_cog_tile_url_special_characters_encoded(mock_settings: Settings) -> None:
    path_with_specials = "/data/my tests & samples/scene#1 (high-res)+v2.tif?token=abc&flag=1"
    url = get_cog_tile_url(path_with_specials, settings=mock_settings)

    # Literal placeholders preserved
    assert "/{z}/{x}/{y}?" in url

    # Query string must encode spaces, ampersands, hashes, questions marks, and plusses
    encoded_query = url.split("?url=")[1]
    assert " " not in encoded_query
    assert "&" not in encoded_query
    assert "#" not in encoded_query
    assert "?" not in encoded_query

    assert unquote_plus(encoded_query) == path_with_specials


def test_get_cog_tile_url_handles_base_url_trailing_slash() -> None:
    custom_settings = Settings(
        database_url="postgresql+psycopg://satquery:satquery_local_dev@localhost:5432/satquery",
        cost_ceiling=5.0,
        titiler_base_url="http://titiler.internal:8001/",
        _env_file=None,
    )
    url = get_cog_tile_url("/path/to/cog.tif", settings=custom_settings)
    assert url.startswith("http://titiler.internal:8001/cog/tiles/WebMercatorQuad/{z}/{x}/{y}")
    assert "8001//cog" not in url


def test_get_cog_tile_url_empty_arguments(mock_settings: Settings) -> None:
    with pytest.raises(ValueError, match="cog_path cannot be empty"):
        get_cog_tile_url("", settings=mock_settings)

    with pytest.raises(ValueError, match="cog_path cannot be empty"):
        get_cog_tile_url("   ", settings=mock_settings)

    with pytest.raises(ValueError, match="tile_matrix_set cannot be empty"):
        get_cog_tile_url("/path/to/cog.tif", tile_matrix_set="", settings=mock_settings)

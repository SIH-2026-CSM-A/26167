"""TiTiler XYZ tile URL templating helpers."""

from urllib.parse import quote_plus

from app.core.config import Settings, get_settings


def get_cog_tile_url(
    cog_path: str,
    tile_matrix_set: str = "WebMercatorQuad",
    settings: Settings | None = None,
) -> str:
    """Construct an XYZ tile URL template for a Cloud-Optimized GeoTIFF (COG) via TiTiler.

    Args:
        cog_path: Local file path or remote URL to the COG asset.
        tile_matrix_set: TileMatrixSet name (defaults to "WebMercatorQuad").
        settings: Optional Settings instance; defaults to get_settings().

    Returns:
        XYZ tile URL template string with literal {z}, {x}, and {y} placeholders.

    Raises:
        ValueError: If cog_path or tile_matrix_set is empty or whitespace.
    """
    if not cog_path or not cog_path.strip():
        raise ValueError("cog_path cannot be empty")
    if not tile_matrix_set or not tile_matrix_set.strip():
        raise ValueError("tile_matrix_set cannot be empty")

    cfg = settings or get_settings()
    base_url = cfg.titiler_base_url.rstrip("/")
    encoded_path = quote_plus(cog_path)
    return f"{base_url}/cog/tiles/{tile_matrix_set}/{{z}}/{{x}}/{{y}}?url={encoded_path}"

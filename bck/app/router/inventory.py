"""Deterministic structural summary of QueryRequest image inputs."""

from __future__ import annotations

from app.contracts import ImageInput, Modality
from app.router.schemas import InputInventory


def extract_inventory(images: list[ImageInput]) -> InputInventory:
    """Extract structural inventory metrics from input image descriptors.

    Categorizes images by modality (optical vs. SAR) and extracts their IDs
    without altering contracts or loading heavy raster data.
    """
    optical_ids: list[str] = []
    sar_ids: list[str] = []

    for img in images:
        if img.modality == Modality.OPTICAL:
            optical_ids.append(img.id)
        elif img.modality == Modality.SAR:
            sar_ids.append(img.id)

    return InputInventory(
        total_images=len(images),
        has_optical=len(optical_ids) > 0,
        has_sar=len(sar_ids) > 0,
        optical_ids=optical_ids,
        sar_ids=sar_ids,
    )

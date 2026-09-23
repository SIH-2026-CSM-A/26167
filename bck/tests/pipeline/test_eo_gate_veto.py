"""A failing EO gate vetoes through pipeline.run before routing, with gate steps traced."""

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds, from_origin
from rasterio.warp import transform_bounds

from app.contracts import Modality
from app.pipeline import PipelineError, PipelineUpload, run


def _geotiff(crs: str, transform) -> bytes:
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=4,
            height=4,
            count=1,
            dtype="uint8",
            crs=crs,
            transform=transform,
        ) as dataset:
            dataset.write(np.full((1, 4, 4), 7, dtype=np.uint8))
        return memory_file.read()


def _upload(asset_id: str, content: bytes) -> PipelineUpload:
    return PipelineUpload(
        id=asset_id,
        filename=f"{asset_id}.tif",
        content_type="image/tiff",
        content=content,
        modality=Modality.OPTICAL,
    )


def test_crs_mismatch_is_vetoed_before_routing() -> None:
    wgs84 = _geotiff("EPSG:4326", from_origin(77.0, 13.0, 0.01, 0.01))
    utm_bounds = transform_bounds("EPSG:4326", "EPSG:32643", 77.0, 12.96, 77.04, 13.0)
    utm = _geotiff("EPSG:32643", from_bounds(*utm_bounds, 4, 4))

    with pytest.raises(PipelineError) as caught:
        run(query="What is in these images?", uploads=[_upload("a", wgs84), _upload("b", utm)])

    error = caught.value
    assert error.stage == "validation"
    assert error.status_code == 422
    assert error.reason_code == "EO_CRS_MISMATCH"
    assert error.suggested_action

    steps = error.trace.steps
    gate_steps = [
        step for step in steps if (step.module, step.action) == ("validation", "eo_gates")
    ]
    assert [step.params["gate"] for step in gate_steps] == [
        "crs_consistency",
        "geographic_overlap",
        "gsd_match",
        "acquisition_order",
    ]
    assert gate_steps[0].params["status"] == "FAIL"
    assert not any(step.module == "router" for step in steps)

"""Tests for the curated, offline F24 demo manifest package."""

from __future__ import annotations

import copy
import json
import os
import socket
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import ImageInput, Modality, QueryRequest
from app.core.demo_manifest import (
    DEMO_MANIFEST_PATH,
    DEMO_ROOT,
    DemoManifest,
    DemoManifestError,
    DemoPreset,
    load_demo_manifest,
)
from app.db.models import Base
from app.pipeline import PipelineUpload, run
from app.router import route
from tests.helpers import DeterministicVqaModel


@pytest.fixture(autouse=True)
def sqlite_db() -> Iterator[None]:
    """Provide an in-memory SQLite database sessionmaker for pipeline persistence."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with patch("app.db.session.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


PS_QUERIES = (
    "Describe the land-cover and major objects visible in this image.",
    "Highlight the water body referred to in the query.",
    "What changed between these two dates, and where did the change occur?",
    "Use the optical and SAR images together to identify built-up and water-covered regions.",
    "Has the built-up area increased, decreased, or remained unchanged?",
)

EXPECTED_PRESETS = (
    (
        "single-image-land-cover",
        PS_QUERIES[0],
        "vqa",
        "vqa_grounding",
        "single_image",
        (("image", "optical"),),
    ),
    (
        "flood-water-grounding",
        PS_QUERIES[1],
        "grounding",
        "vqa_grounding",
        "flood_water",
        (("image", "optical"),),
    ),
    (
        "bi-temporal-change-location",
        PS_QUERIES[2],
        "change_vqa",
        "change_detection",
        "bi_temporal_change",
        (("pre_image", "optical"), ("post_image", "optical")),
    ),
    (
        "cross-modal-built-up-water",
        PS_QUERIES[3],
        "fusion",
        "fusion",
        "cross_modal",
        (("optical_image", "optical"), ("sar_image", "sar")),
    ),
    (
        "bi-temporal-built-up-direction",
        PS_QUERIES[4],
        "change_vqa",
        "change_detection",
        "bi_temporal_change",
        (("pre_image", "optical"), ("post_image", "optical")),
    ),
)


@pytest.fixture
def valid_manifest_path(tmp_path: Path) -> Path:
    """Create one valid local single-image manifest and raster."""
    asset_path = tmp_path / "assets" / "valid.tif"
    _write_test_raster(asset_path)
    return _write_manifest(tmp_path, _valid_manifest_payload())


@pytest.fixture
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if Python code attempts to establish a network connection."""

    def deny_network(*_args: object, **_kwargs: object) -> None:
        """Reject every attempted socket connection during an offline test."""
        raise AssertionError("external network access attempted during offline demo execution")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)


def _valid_manifest_payload() -> dict[str, Any]:
    """Return a literal minimal manifest payload accepted by the v1 contract."""
    return {
        "schema_version": "1.0",
        "presets": [
            {
                "id": "local-vqa",
                "label": "Local VQA",
                "query": PS_QUERIES[0],
                "intent": "vqa",
                "tool": "vqa_grounding",
                "scenario": "single_image",
                "assets": [
                    {
                        "id": "local-optical",
                        "path": "assets/valid.tif",
                        "modality": "optical",
                        "role": "image",
                    }
                ],
            }
        ],
    }


def _write_manifest(root: Path, payload: dict[str, Any]) -> Path:
    """Write a JSON manifest beneath the supplied temporary package root."""
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path


def _write_test_raster(path: Path) -> None:
    """Write a small valid GeoTIFF used only by temporary validation cases."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.arange(12, dtype=np.uint8).reshape(3, 2, 2)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=3,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(0, 2, 1, 1),
    ) as dataset:
        dataset.write(data)


def _assert_manifest_error(
    manifest_path: Path,
    *message_fragments: str,
) -> None:
    """Assert validation fails and reports every required context fragment."""
    with pytest.raises(DemoManifestError) as caught:
        load_demo_manifest(manifest_path)
    message = str(caught.value)
    for fragment in message_fragments:
        assert fragment in message


def _query_request(manifest: DemoManifest, preset: DemoPreset) -> QueryRequest:
    """Build the existing router contract from one validated production manifest preset."""
    images = []
    for asset in preset.assets:
        resolved_path = manifest.resolve_asset(asset)
        with rasterio.open(resolved_path) as dataset:
            driver = dataset.driver
        images.append(
            ImageInput(
                id=asset.id,
                modality=Modality(asset.modality),
                format=driver,
                path=str(resolved_path),
            )
        )
    return QueryRequest(query=preset.query, images=images)


def test_canonical_manifest_has_five_ordered_ps_presets() -> None:
    """The canonical package must preserve the five PRD queries and their order."""
    manifest = load_demo_manifest()

    assert DEMO_MANIFEST_PATH == DEMO_ROOT / "manifest.json"
    assert manifest.schema_version == "1.0"
    assert len(manifest.presets) == 5
    assert tuple(preset.query for preset in manifest.presets) == PS_QUERIES
    assert (
        tuple(
            (
                preset.id,
                preset.query,
                preset.intent,
                preset.tool,
                preset.scenario,
                tuple((asset.role, asset.modality) for asset in preset.assets),
            )
            for preset in manifest.presets
        )
        == EXPECTED_PRESETS
    )


def test_canonical_manifest_covers_all_required_f24_scenarios() -> None:
    """The canonical presets must cover every approved F24 scenario."""
    manifest = load_demo_manifest()

    assert {preset.scenario for preset in manifest.presets} == {
        "single_image",
        "flood_water",
        "bi_temporal_change",
        "cross_modal",
    }


def test_get_preset_is_deterministic_and_unknown_id_fails() -> None:
    """Exact preset IDs must resolve deterministically and unknown IDs must fail usefully."""
    manifest = load_demo_manifest()

    first = manifest.get_preset("cross-modal-built-up-water")
    second = manifest.get_preset("cross-modal-built-up-water")

    assert first is second
    assert first.query == PS_QUERIES[3]
    with pytest.raises(DemoManifestError, match="unknown-preset"):
        manifest.get_preset("unknown-preset")


def test_every_canonical_asset_is_local_readable_and_rasterio_openable() -> None:
    """Every canonical asset must remain under DEMO_ROOT and expose valid raster metadata."""
    manifest = load_demo_manifest()
    unique_paths = {
        manifest.resolve_asset(asset) for preset in manifest.presets for asset in preset.assets
    }

    assert len(unique_paths) == 4
    for path in unique_paths:
        assert path.is_relative_to(DEMO_ROOT.resolve())
        assert path.is_file()
        with path.open("rb") as stream:
            assert stream.read(1)
        with rasterio.open(path) as dataset:
            assert dataset.width > 0
            assert dataset.height > 0
            assert dataset.count > 0
            assert all(dataset.dtypes)


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    """Malformed JSON must fail with the manifest path in the error."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{not-json", encoding="utf-8")

    _assert_manifest_error(manifest_path, str(manifest_path), "JSON")


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    [
        (lambda data: data.update(schema_version="2.0"), "schema_version"),
        (lambda data: data.update(unexpected=True), "unexpected"),
        (lambda data: data["presets"][0].update(unexpected=True), "unexpected"),
        (lambda data: data["presets"][0]["assets"][0].update(unexpected=True), "unexpected"),
        (lambda data: data["presets"][0].update(intent="invalid"), "intent"),
        (lambda data: data["presets"][0].update(tool="invalid"), "tool"),
        (lambda data: data["presets"][0].update(scenario="invalid"), "scenario"),
        (
            lambda data: data["presets"][0]["assets"][0].update(modality="invalid"),
            "modality",
        ),
        (lambda data: data["presets"][0]["assets"][0].update(role="invalid"), "role"),
    ],
    ids=(
        "unsupported-version",
        "unknown-top-level-field",
        "unknown-preset-field",
        "unknown-asset-field",
        "invalid-intent",
        "invalid-tool",
        "invalid-scenario",
        "invalid-modality",
        "invalid-role",
    ),
)
def test_invalid_schema_values_are_rejected(
    valid_manifest_path: Path,
    mutation: Callable[[dict[str, Any]], None],
    expected_fragment: str,
) -> None:
    """Unsupported enums, versions, and unknown fields must fail strict validation."""
    payload = _valid_manifest_payload()
    mutation(payload)
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), expected_fragment)


def test_duplicate_preset_ids_are_rejected(valid_manifest_path: Path) -> None:
    """Duplicate lookup keys must be rejected instead of making selection ambiguous."""
    payload = _valid_manifest_payload()
    payload["presets"].append(copy.deepcopy(payload["presets"][0]))
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), "local-vqa", "duplicate")


def test_duplicate_asset_ids_within_preset_are_rejected(valid_manifest_path: Path) -> None:
    """Duplicate asset IDs in one preset must be rejected before role binding."""
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"].append(copy.deepcopy(payload["presets"][0]["assets"][0]))
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), "local-vqa", "local-optical")


@pytest.mark.parametrize(
    ("preset_update", "asset_updates", "expected_fragment"),
    [
        ({"tool": "fusion"}, (), "vqa_grounding"),
        ({"scenario": "cross_modal"}, (), "single_image"),
        ({}, ({"role": "optical_image"},), "image"),
        ({}, ({"role": "image", "modality": "sar"},), "optical"),
    ],
    ids=(
        "wrong-tool-for-intent",
        "wrong-scenario-for-vqa",
        "wrong-role-for-vqa",
        "wrong-modality-for-single-image",
    ),
)
def test_invalid_single_image_combinations_are_rejected(
    valid_manifest_path: Path,
    preset_update: dict[str, str],
    asset_updates: tuple[dict[str, str], ...],
    expected_fragment: str,
) -> None:
    """Single-image presets must use the approved tool, scenario, role, and modality."""
    payload = _valid_manifest_payload()
    payload["presets"][0].update(preset_update)
    for update in asset_updates:
        payload["presets"][0]["assets"][0].update(update)
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), "local-vqa", expected_fragment)


@pytest.mark.parametrize(
    ("preset", "expected_fragment"),
    [
        (
            {
                "id": "bad-change",
                "label": "Bad change",
                "query": PS_QUERIES[2],
                "intent": "change_vqa",
                "tool": "change_detection",
                "scenario": "bi_temporal_change",
                "assets": [
                    {
                        "id": "before",
                        "path": "assets/valid.tif",
                        "modality": "optical",
                        "role": "pre_image",
                    }
                ],
            },
            "post_image",
        ),
        (
            {
                "id": "bad-fusion",
                "label": "Bad fusion",
                "query": PS_QUERIES[3],
                "intent": "fusion",
                "tool": "fusion",
                "scenario": "cross_modal",
                "assets": [
                    {
                        "id": "optical",
                        "path": "assets/valid.tif",
                        "modality": "optical",
                        "role": "optical_image",
                    }
                ],
            },
            "sar_image",
        ),
        (
            {
                "id": "bad-fusion-modality",
                "label": "Bad fusion modality",
                "query": PS_QUERIES[3],
                "intent": "fusion",
                "tool": "fusion",
                "scenario": "cross_modal",
                "assets": [
                    {
                        "id": "optical",
                        "path": "assets/valid.tif",
                        "modality": "sar",
                        "role": "optical_image",
                    },
                    {
                        "id": "sar",
                        "path": "assets/valid.tif",
                        "modality": "sar",
                        "role": "sar_image",
                    },
                ],
            },
            "optical_image",
        ),
    ],
    ids=("missing-change-role", "missing-fusion-role", "fusion-role-modality-mismatch"),
)
def test_missing_or_mismatched_multi_asset_roles_are_rejected(
    valid_manifest_path: Path,
    preset: dict[str, Any],
    expected_fragment: str,
) -> None:
    """Change and fusion presets must provide complete authoritative role bindings."""
    payload = _valid_manifest_payload()
    payload["presets"] = [preset]
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), preset["id"], expected_fragment)


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "C:/outside.tif",
        "/outside.tif",
        "//server/share/scene.tif",
        "https://example.test/scene.tif",
        "../outside.tif",
        "assets\\scene.tif",
        "assets/\x00scene.tif",
    ),
    ids=(
        "windows-absolute",
        "posix-absolute",
        "unc-like",
        "url",
        "traversal",
        "backslash",
        "embedded-nul",
    ),
)
def test_unsafe_asset_paths_are_rejected(
    valid_manifest_path: Path,
    unsafe_path: str,
) -> None:
    """Non-local or non-POSIX paths must be rejected with preset and asset context."""
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"][0]["path"] = unsafe_path
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(
        manifest_path,
        str(manifest_path),
        "local-vqa",
        "local-optical",
        unsafe_path,
    )


def test_missing_asset_is_rejected(valid_manifest_path: Path) -> None:
    """A missing referenced raster must fail with complete asset context."""
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"][0]["path"] = "assets/missing.tif"
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(
        manifest_path,
        str(manifest_path),
        "local-vqa",
        "local-optical",
        "assets/missing.tif",
    )


def test_non_file_asset_is_rejected(valid_manifest_path: Path) -> None:
    """A referenced directory must fail rather than being treated as a raster."""
    directory_path = valid_manifest_path.parent / "assets" / "directory.tif"
    directory_path.mkdir()
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"][0]["path"] = "assets/directory.tif"
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(manifest_path, str(manifest_path), "local-vqa", "local-optical")


def test_corrupt_raster_is_rejected(valid_manifest_path: Path) -> None:
    """A present but corrupt raster must fail during Rasterio validation."""
    corrupt_path = valid_manifest_path.parent / "assets" / "corrupt.tif"
    corrupt_path.write_bytes(b"not a raster")
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"][0]["path"] = "assets/corrupt.tif"
    manifest_path = _write_manifest(valid_manifest_path.parent, payload)

    _assert_manifest_error(
        manifest_path,
        str(manifest_path),
        "local-vqa",
        "local-optical",
        "assets/corrupt.tif",
    )


def test_unreadable_asset_is_rejected_when_permissions_are_enforced(
    valid_manifest_path: Path,
) -> None:
    """A file denied by filesystem permissions must fail instead of being skipped."""
    asset_path = valid_manifest_path.parent / "assets" / "valid.tif"
    original_mode = asset_path.stat().st_mode
    try:
        asset_path.chmod(0)
        if os.access(asset_path, os.R_OK):
            pytest.skip("filesystem does not enforce an unreadable chmod mode for this process")
        _assert_manifest_error(
            valid_manifest_path,
            str(valid_manifest_path),
            "local-vqa",
            "local-optical",
        )
    finally:
        asset_path.chmod(original_mode)


def test_symlink_escape_is_rejected_when_symlinks_are_available(tmp_path: Path) -> None:
    """A symlink inside the package must not resolve to a raster outside its root."""
    package_root = tmp_path / "package"
    outside_raster = tmp_path / "outside.tif"
    link_path = package_root / "assets" / "link.tif"
    _write_test_raster(outside_raster)
    link_path.parent.mkdir(parents=True)
    try:
        link_path.symlink_to(outside_raster)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable in this environment: {error}")
    payload = _valid_manifest_payload()
    payload["presets"][0]["assets"][0]["path"] = "assets/link.tif"
    manifest_path = _write_manifest(package_root, payload)

    _assert_manifest_error(
        manifest_path,
        str(manifest_path),
        "local-vqa",
        "local-optical",
        "assets/link.tif",
    )


def test_all_presets_route_offline_to_declared_intent_tool_and_roles(
    block_external_network: None,
) -> None:
    """Validated local presets must reach the real router without a network connection."""
    manifest = load_demo_manifest()

    for preset in manifest.presets:
        request = _query_request(manifest, preset)
        decision = route(request)

        assert decision.is_dispatched
        assert decision.intent.task_type.value == preset.intent
        assert decision.dispatch_plan is not None
        assert decision.dispatch_plan.tool_name == preset.tool
        assert decision.dispatch_plan.image_bindings == {
            asset.role: asset.id for asset in preset.assets
        }


def test_single_image_cached_tiff_reaches_executable_pipeline_offline(
    block_external_network: None,
) -> None:
    """The executable VQA slice must consume the cached TIFF with a local model boundary."""
    manifest = load_demo_manifest()
    preset = manifest.get_preset("single-image-land-cover")
    asset = preset.assets[0]
    asset_path = manifest.resolve_asset(asset)
    upload = PipelineUpload(
        id=asset.id,
        filename=asset_path.name,
        content_type="image/tiff",
        content=asset_path.read_bytes(),
        modality=Modality(asset.modality),
    )
    model = DeterministicVqaModel(
        answer="A river is visible.",
        grounding="A river is visible in the scene.",
    )

    answer = run(query=preset.query, uploads=[upload], model=model)

    assert answer.abstained is False
    assert answer.evidence[0].payload["source_asset_id"] == asset.id
    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["intent"] == "vqa"
    assert route_step.params["tool"] == "vqa_grounding"

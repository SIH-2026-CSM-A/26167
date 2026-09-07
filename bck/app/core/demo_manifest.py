"""Strict loader for the local F24 demo dataset manifest."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self
from urllib.parse import urlsplit

import rasterio
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator
from rasterio.errors import RasterioError

CORE_DIRECTORY = Path(__file__).resolve().parent
BACKEND_ROOT = CORE_DIRECTORY.parent.parent
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEMO_ROOT = REPOSITORY_ROOT / "data" / "demo"
DEMO_MANIFEST_PATH = DEMO_ROOT / "manifest.json"

Intent = Literal["vqa", "grounding", "change_vqa", "fusion"]
Tool = Literal["vqa_grounding", "change_detection", "fusion"]
Scenario = Literal["single_image", "flood_water", "bi_temporal_change", "cross_modal"]
Modality = Literal["optical", "sar"]
AssetRole = Literal["image", "pre_image", "post_image", "optical_image", "sar_image"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True, str_strip_whitespace=True)
_RASTERIO_ENVIRONMENT = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "PROJ_NETWORK": "OFF",
}


class DemoManifestError(ValueError):
    """Raised when the demo manifest or one of its local raster assets is invalid."""


class DemoAsset(BaseModel):
    """One role-bound local raster reference in a demo preset."""

    model_config = _MODEL_CONFIG

    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    modality: Modality
    role: AssetRole


class DemoPreset(BaseModel):
    """One deterministic query preset and its required local imagery."""

    model_config = _MODEL_CONFIG

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    query: str = Field(min_length=1)
    intent: Intent
    tool: Tool
    scenario: Scenario
    assets: list[DemoAsset] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_workflow_contract(self) -> Self:
        """Enforce the tool, scenario, role, and modality contract for this intent."""
        asset_ids = [asset.id for asset in self.assets]
        duplicate_asset_id = _first_duplicate(asset_ids)
        if duplicate_asset_id is not None:
            raise ValueError(f"preset '{self.id}' has duplicate asset id '{duplicate_asset_id}'")

        if self.intent == "vqa":
            self._require_single_image(tool="vqa_grounding", scenario="single_image")
        elif self.intent == "grounding":
            self._require_single_image(tool="vqa_grounding", scenario="flood_water")
        elif self.intent == "change_vqa":
            self._require_change_pair()
        else:
            self._require_fusion_pair()
        return self

    def _require_single_image(self, *, tool: Tool, scenario: Scenario) -> None:
        """Require one optical image for a single-image workflow."""
        self._require_tool_and_scenario(tool=tool, scenario=scenario)
        roles = {asset.role for asset in self.assets}
        if len(self.assets) != 1 or roles != {"image"}:
            raise ValueError(f"preset '{self.id}' must contain exactly the role 'image'")
        if self.assets[0].modality != "optical":
            raise ValueError(f"preset '{self.id}' role 'image' must use modality 'optical'")

    def _require_change_pair(self) -> None:
        """Require a same-modality pre/post pair for change analysis."""
        self._require_tool_and_scenario(
            tool="change_detection",
            scenario="bi_temporal_change",
        )
        assets_by_role = {asset.role: asset for asset in self.assets}
        required_roles = {"pre_image", "post_image"}
        if len(self.assets) != 2 or set(assets_by_role) != required_roles:
            missing_roles = sorted(required_roles - set(assets_by_role))
            detail = f"; missing roles: {', '.join(missing_roles)}" if missing_roles else ""
            raise ValueError(
                f"preset '{self.id}' must contain exactly pre_image and post_image{detail}"
            )
        if assets_by_role["pre_image"].modality != assets_by_role["post_image"].modality:
            raise ValueError(
                f"preset '{self.id}' pre_image and post_image must use the same modality"
            )

    def _require_fusion_pair(self) -> None:
        """Require correctly typed optical and SAR role bindings for fusion."""
        self._require_tool_and_scenario(tool="fusion", scenario="cross_modal")
        assets_by_role = {asset.role: asset for asset in self.assets}
        required_roles = {"optical_image", "sar_image"}
        if len(self.assets) != 2 or set(assets_by_role) != required_roles:
            missing_roles = sorted(required_roles - set(assets_by_role))
            detail = f"; missing roles: {', '.join(missing_roles)}" if missing_roles else ""
            raise ValueError(
                f"preset '{self.id}' must contain exactly optical_image and sar_image{detail}"
            )
        expected_modalities = {"optical_image": "optical", "sar_image": "sar"}
        for role, expected_modality in expected_modalities.items():
            if assets_by_role[role].modality != expected_modality:
                raise ValueError(
                    f"preset '{self.id}' role '{role}' must use modality '{expected_modality}'"
                )

    def _require_tool_and_scenario(self, *, tool: Tool, scenario: Scenario) -> None:
        """Require the exact tool and scenario selected for an intent."""
        if self.tool != tool:
            raise ValueError(f"preset '{self.id}' intent '{self.intent}' requires tool '{tool}'")
        if self.scenario != scenario:
            raise ValueError(
                f"preset '{self.id}' intent '{self.intent}' requires scenario '{scenario}'"
            )


class DemoManifest(BaseModel):
    """Validated v1 demo manifest with deterministic lookup and safe path resolution."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"]
    presets: list[DemoPreset] = Field(min_length=1)
    _demo_root: Path | None = PrivateAttr(default=None)
    _manifest_path: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_unique_preset_ids(self) -> Self:
        """Reject duplicate stable lookup keys."""
        duplicate_preset_id = _first_duplicate([preset.id for preset in self.presets])
        if duplicate_preset_id is not None:
            raise ValueError(f"duplicate preset id '{duplicate_preset_id}'")
        return self

    def get_preset(self, preset_id: str) -> DemoPreset:
        """Return the preset matching an exact stable ID or raise a useful error."""
        for preset in self.presets:
            if preset.id == preset_id:
                return preset
        manifest_path = self._manifest_path or DEMO_MANIFEST_PATH
        raise DemoManifestError(
            f"Preset '{preset_id}' was not found in demo manifest '{manifest_path}'"
        )

    def resolve_asset(self, asset: DemoAsset) -> Path:
        """Resolve and revalidate one asset beneath this manifest's package root."""
        if self._demo_root is None or self._manifest_path is None:
            raise DemoManifestError("Demo manifest has no bound package root")
        return _validate_asset(
            demo_root=self._demo_root,
            manifest_path=self._manifest_path,
            preset_id=_find_asset_preset_id(self.presets, asset),
            asset=asset,
        )

    def _bind_package(self, *, demo_root: Path, manifest_path: Path) -> None:
        """Bind runtime-only canonical paths after schema validation."""
        self._demo_root = demo_root
        self._manifest_path = manifest_path


def load_demo_manifest(
    manifest_path: str | Path = DEMO_MANIFEST_PATH,
) -> DemoManifest:
    """Parse, strictly validate, and fully open every referenced local raster."""
    requested_path = Path(manifest_path)
    try:
        resolved_manifest_path = requested_path.resolve(strict=True)
        if not resolved_manifest_path.is_file():
            raise DemoManifestError(f"Demo manifest '{resolved_manifest_path}' is not a file")
        raw_text = resolved_manifest_path.read_text(encoding="utf-8")
    except DemoManifestError:
        raise
    except OSError as error:
        raise DemoManifestError(
            f"Demo manifest '{requested_path}' could not be read: {error}"
        ) from error

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise DemoManifestError(
            f"Demo manifest '{resolved_manifest_path}' contains invalid JSON: {error.msg}"
        ) from error

    try:
        manifest = DemoManifest.model_validate(payload)
    except ValidationError as error:
        details = _format_schema_errors(payload, error)
        raise DemoManifestError(
            f"Demo manifest '{resolved_manifest_path}' failed schema validation: {details}"
        ) from error

    demo_root = resolved_manifest_path.parent.resolve(strict=True)
    manifest._bind_package(demo_root=demo_root, manifest_path=resolved_manifest_path)
    for preset in manifest.presets:
        for asset in preset.assets:
            _validate_asset(
                demo_root=demo_root,
                manifest_path=resolved_manifest_path,
                preset_id=preset.id,
                asset=asset,
            )
    return manifest


def _first_duplicate(values: list[str]) -> str | None:
    """Return the first repeated string while preserving input order."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None


def _find_asset_preset_id(presets: list[DemoPreset], target: DemoAsset) -> str:
    """Return deterministic preset context for a validated asset object."""
    for preset in presets:
        for asset in preset.assets:
            if asset is target:
                return preset.id
    raise DemoManifestError(f"Asset '{target.id}' does not belong to this demo manifest")


def _validate_asset(
    *,
    demo_root: Path,
    manifest_path: Path,
    preset_id: str,
    asset: DemoAsset,
) -> Path:
    """Validate one relative local path and open its raster metadata offline."""
    context = (
        f"manifest '{manifest_path}', preset '{preset_id}', asset '{asset.id}', path '{asset.path}'"
    )
    relative_path = _parse_relative_posix_path(asset.path, context=context)
    resolved_path = (demo_root / Path(*relative_path.parts)).resolve(strict=False)
    try:
        resolved_path.relative_to(demo_root)
    except ValueError as error:
        raise DemoManifestError(
            f"Invalid demo asset in {context}: path escapes demo root"
        ) from error

    if not resolved_path.exists():
        raise DemoManifestError(f"Invalid demo asset in {context}: file does not exist")
    if not resolved_path.is_file():
        raise DemoManifestError(f"Invalid demo asset in {context}: path is not a regular file")

    try:
        with resolved_path.open("rb") as stream:
            if not stream.read(1):
                raise DemoManifestError(f"Invalid demo asset in {context}: file is empty")
        with rasterio.Env(**_RASTERIO_ENVIRONMENT):
            with rasterio.open(resolved_path) as dataset:
                width = dataset.width
                height = dataset.height
                band_count = dataset.count
                data_types = dataset.dtypes
        if width <= 0 or height <= 0 or band_count <= 0:
            raise DemoManifestError(
                f"Invalid demo asset in {context}: raster has empty dimensions or bands"
            )
        if len(data_types) != band_count or any(not data_type for data_type in data_types):
            raise DemoManifestError(
                f"Invalid demo asset in {context}: raster dtype metadata is invalid"
            )
    except DemoManifestError:
        raise
    except (OSError, RasterioError, ValueError) as error:
        raise DemoManifestError(
            f"Invalid demo asset in {context}: raster could not be read: {error}"
        ) from error
    return resolved_path


def _parse_relative_posix_path(value: str, *, context: str) -> PurePosixPath:
    """Parse a safe relative POSIX asset path without URL or traversal semantics."""
    if "\x00" in value:
        raise DemoManifestError(f"Invalid demo asset in {context}: NUL characters are not allowed")
    if "\\" in value:
        raise DemoManifestError(f"Invalid demo asset in {context}: backslashes are not allowed")
    if urlsplit(value).scheme:
        raise DemoManifestError(
            f"Invalid demo asset in {context}: URLs and drive paths are not allowed"
        )
    path = PurePosixPath(value)
    if path.is_absolute():
        raise DemoManifestError(f"Invalid demo asset in {context}: absolute paths are not allowed")
    if any(part in {".", ".."} for part in path.parts):
        raise DemoManifestError(
            f"Invalid demo asset in {context}: traversal segments are not allowed"
        )
    return path


def _format_schema_errors(payload: Any, error: ValidationError) -> str:
    """Attach available preset and asset identifiers to Pydantic errors."""
    formatted_errors = []
    for item in error.errors(include_url=False):
        location = item["loc"]
        context = _schema_location_context(payload, location)
        location_text = ".".join(str(part) for part in location) or "manifest"
        formatted_errors.append(f"{context}{location_text}: {item['msg']}")
    return "; ".join(formatted_errors)


def _schema_location_context(payload: Any, location: tuple[int | str, ...]) -> str:
    """Describe the raw preset and asset associated with a validation location."""
    if not isinstance(payload, dict):
        return ""
    presets = payload.get("presets")
    if not isinstance(presets, list) or "presets" not in location:
        return ""
    preset_position = location.index("presets") + 1
    if preset_position >= len(location) or not isinstance(location[preset_position], int):
        return ""
    preset_index = location[preset_position]
    if not 0 <= preset_index < len(presets) or not isinstance(presets[preset_index], dict):
        return ""
    preset = presets[preset_index]
    context = f"preset '{preset.get('id', '<unknown>')}'"
    assets = preset.get("assets")
    if "assets" not in location or not isinstance(assets, list):
        return f"{context}, "
    asset_position = location.index("assets") + 1
    if asset_position >= len(location) or not isinstance(location[asset_position], int):
        return f"{context}, "
    asset_index = location[asset_position]
    if not 0 <= asset_index < len(assets) or not isinstance(assets[asset_index], dict):
        return f"{context}, "
    asset = assets[asset_index]
    return (
        f"{context}, asset '{asset.get('id', '<unknown>')}', "
        f"path '{asset.get('path', '<unknown>')}', "
    )

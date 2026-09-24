"""FastAPI boundary for the real multipart single-image VQA pipeline."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.api import auth as auth_routes
from app.api import history as history_routes
from app.api import oauth as oauth_routes
from app.api.deps import get_current_user
from app.auth import User
from app.contracts import Answer, Modality
from app.core.config import get_settings
from app.evidence.report import (
    NotGeoreferencedError,
    generate_evidence_geojson,
    generate_evidence_pdf,
)
from app.pipeline import PipelineError, PipelineUpload, run

app = FastAPI(title="SatQuery AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(oauth_routes.router)
app.include_router(history_routes.router)


@app.post("/query", response_model=Answer)
async def submit_query(
    request: Request,
    query: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()],
    modality: Annotated[list[Modality] | None, Form()] = None,
    capture_order: Annotated[list[int] | None, Form()] = None,
    _user: User | None = Depends(get_current_user),
) -> Answer:
    """Validate multipart shape, retain bytes, and delegate all processing to the pipeline."""
    if not query.strip():
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not images:
        raise HTTPException(status_code=422, detail="at least one image is required")

    # B4: no modality default. A client-supplied `modality` form field is an
    # explicit override, used as-is; omitting it means "classify from raster
    # metadata" (app.ingestion.raster.classify_modality), not "assume Optical".
    modalities: list[Modality | None] = modality if modality is not None else [None] * len(images)
    if len(images) != len(modalities):
        raise HTTPException(status_code=422, detail="images and modality must have the same length")

    # Temporal order fix: a client-supplied `capture_order` form field is an explicit
    # 0=pre/1=post signal (from the Upload page's bi-temporal slots); omitting it means
    # the router cannot trust arrival order and must abstain for CHANGE_VQA instead of
    # guessing images[0]/images[1].
    capture_orders: list[int | None] = (
        capture_order if capture_order is not None else [None] * len(images)
    )
    if len(images) != len(capture_orders):
        raise HTTPException(
            status_code=422, detail="images and capture_order must have the same length"
        )

    uploads: list[PipelineUpload] = []
    for image, image_modality, image_capture_order in zip(
        images, modalities, capture_orders, strict=True
    ):
        try:
            content = await image.read()
        except OSError as error:
            raise HTTPException(
                status_code=400, detail="uploaded image could not be read"
            ) from error
        finally:
            await image.close()
        uploads.append(
            PipelineUpload(
                id=str(uuid.uuid4()),
                filename=image.filename or "",
                content_type=image.content_type or "application/octet-stream",
                content=content,
                modality=image_modality,
                capture_order=image_capture_order,
            )
        )

    model = getattr(request.app.state, "vqa_model", None)
    try:
        return await run_in_threadpool(
            run,
            query=query,
            uploads=uploads,
            model=model,
            user_id=_user.id if _user is not None else None,
        )
    except PipelineError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={
                "message": error.message,
                "stage": error.stage,
                "reason_code": error.reason_code,
                "suggested_action": error.suggested_action,
                "trace": error.trace.model_dump(mode="json"),
            },
        ) from error


@app.post("/api/evidence/export-pdf")
async def export_evidence_pdf(payload: Answer) -> StreamingResponse:
    pdf_buffer = generate_evidence_pdf(payload)
    query_id = getattr(payload, "query_id", None) or payload.trace.trace_id
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=evidence-{query_id}.pdf"},
    )


@app.post("/api/evidence/export-geojson")
async def export_evidence_geojson(payload: Answer) -> Response:
    try:
        geojson_str, filename = generate_evidence_geojson(payload)
    except NotGeoreferencedError as error:
        raise HTTPException(status_code=422, detail={"message": str(error)}) from error
    return Response(
        content=geojson_str,
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


app.post("/api/query", response_model=Answer, include_in_schema=False)(submit_query)


def _resolve_frontend_dist() -> Path:
    env_dist = os.environ.get("FRONTEND_DIST_DIR")
    if env_dist:
        return Path(env_dist).resolve()
    repo_root = Path(__file__).resolve().parents[3]
    for candidate in [
        repo_root / "fnt" / "dist",
        repo_root / "frontend" / "dist",
        Path.cwd() / "fnt" / "dist",
        Path.cwd() / "dist",
    ]:
        if candidate.is_dir():
            return candidate.resolve()
    return (repo_root / "fnt" / "dist").resolve()


FRONTEND_DIST_DIR = _resolve_frontend_dist()


class DynamicStaticFiles(StaticFiles):
    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        assets_dir = _resolve_frontend_dist() / "assets"
        self.directory = str(assets_dir)
        self.all_directories = [assets_dir.resolve()]
        return super().lookup_path(path)


app.mount(
    "/assets",
    DynamicStaticFiles(directory=str(FRONTEND_DIST_DIR / "assets"), check_dir=False),
    name="assets",
)


@app.get("/", include_in_schema=False)
async def serve_root() -> FileResponse:
    dist_dir = _resolve_frontend_dist()
    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run 'npm run build' in fnt/.",
        )
    return FileResponse(index_file)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str) -> FileResponse:
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    dist_dir = _resolve_frontend_dist()
    if full_path:
        candidate_file = (dist_dir / full_path).resolve()
        try:
            candidate_file.relative_to(dist_dir.resolve())
            if candidate_file.is_file():
                return FileResponse(candidate_file)
        except ValueError:
            pass

    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run 'npm run build' in fnt/.",
        )
    return FileResponse(index_file)


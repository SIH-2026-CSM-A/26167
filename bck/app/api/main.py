"""FastAPI boundary for the real multipart single-image VQA pipeline."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.contracts import Answer, Modality
from app.pipeline import PipelineError, PipelineUpload, run

app = FastAPI(title="SatQuery AI")


@app.post("/query", response_model=Answer)
async def submit_query(
    request: Request,
    query: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()],
    modality: Annotated[list[Modality] | None, Form()] = None,
) -> Answer:
    """Validate multipart shape, retain bytes, and delegate all processing to the pipeline."""
    if not query.strip():
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not images:
        raise HTTPException(status_code=422, detail="at least one image is required")

    modalities = modality or [Modality.OPTICAL for _ in images]
    if len(images) != len(modalities):
        raise HTTPException(status_code=422, detail="images and modality must have the same length")

    uploads: list[PipelineUpload] = []
    for image, image_modality in zip(images, modalities, strict=True):
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
            )
        )

    model = getattr(request.app.state, "vqa_model", None)
    try:
        return await run_in_threadpool(run, query=query, uploads=uploads, model=model)
    except PipelineError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={
                "message": error.message,
                "stage": error.stage,
                "trace": error.trace.model_dump(mode="json"),
            },
        ) from error

"""FastAPI app. One route: POST /query. Thin — builds the request, calls pipeline.run()."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.contracts import Answer, ImageInput, Modality, QueryRequest
from app.pipeline.pipeline import run

app = FastAPI(title="SatQuery AI")


@app.post("/query", response_model=Answer)
async def submit_query(
    query: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()],
    modality: Annotated[list[Modality], Form()],
) -> Answer:
    """Accepts the query text plus one or more images, each with its own modality.

    `modality` is a temporary per-image form field: app.ingestion doesn't exist yet to derive
    it from the file itself, so the caller states it explicitly until that lands.
    """
    if not images:
        raise HTTPException(status_code=422, detail="at least one image is required")
    if len(images) != len(modality):
        raise HTTPException(status_code=422, detail="images and modality must have the same length")

    image_inputs = []
    for image, image_modality in zip(images, modality, strict=True):
        content = await image.read()
        image_inputs.append(
            ImageInput(
                id=str(uuid.uuid4()),
                modality=image_modality,
                format=image.content_type or "application/octet-stream",
                metadata={"filename": image.filename, "size_bytes": len(content)},
            )
        )

    request = QueryRequest(query=query, images=image_inputs)
    return run(request)

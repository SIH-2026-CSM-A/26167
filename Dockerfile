# Multi-stage Dockerfile for unified SatQuery AI single-service deployment

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/fnt

COPY fnt/package*.json ./
RUN npm ci

COPY fnt/ ./
RUN npm run build

# Stage 2: Runtime image with Python 3.11 and uv
FROM python:3.11-slim AS runner
WORKDIR /app

# Install system dependencies required for geospatial/C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python backend dependencies
WORKDIR /app/bck
COPY bck/pyproject.toml bck/uv.lock* /app/bck/
RUN uv sync --no-dev --frozen

# Copy backend application source
COPY bck/ /app/bck/

# Demo presets and their recorded answers (served at /data/demo, read by app.core.demo_manifest)
COPY data/demo/ /app/data/demo/

# Copy built frontend assets from frontend-builder stage
COPY --from=frontend-builder /app/fnt/dist /app/fnt/dist

ENV HOST=0.0.0.0
ENV PORT=8000
ENV FRONTEND_DIST_DIR=/app/fnt/dist
# Requests run in a threadpool; glibc's default per-thread malloc arenas kept ~70 MiB of freed
# memory resident after each fusion query. Two arenas: anon peak 359 -> 320 MiB, cgroup peak
# 426 -> 388 MiB on the 512 MB instance (measured, see PR #77).
ENV MALLOC_ARENA_MAX=2

EXPOSE 8000

CMD ["sh", "-c", "exec .venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}"]

#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
HOST="0.0.0.0"

echo "=== Starting FastAPI Server on $HOST:$PORT ==="
cd bck
exec uv run uvicorn app.api.main:app --host "$HOST" --port "$PORT"

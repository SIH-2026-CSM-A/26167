#!/usr/bin/env bash
set -euo pipefail

echo "=== Building Frontend (fnt) ==="
cd fnt
npm ci
npm run build
cd ..

echo "=== Setting up Backend (bck) ==="
cd bck
if ! command -v uv &> /dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

uv sync --no-dev
cd ..

echo "=== Build Complete ==="

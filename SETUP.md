# SETUP.md — per-project checklist (SIH26167)

Complete your general machine setup first (`T1-Antigravity-Setup.md` or `T2-Codex-Setup.md`,
plus `T3-Coding-Standards.md`) before any of this. This file is what's specific to *this*
repository, not your machine in general.

## 1. Clone
```bash
mkdir -p ~/NewProjects && cd ~/NewProjects
git clone git@github.com:SIH-2026-CSM-A/26167.git
cd 26167
```
Clone into the Linux filesystem, not `/mnt/c/` — git across the Windows mount is several times
slower.

## 2. Commit identity (per-clone, do this every time you clone fresh)
```bash
git config user.name "Your Full Name"
git config user.email "ID+username@users.noreply.github.com"   # your GitHub no-reply alias
git config --get user.email
```
Find your alias at github.com/settings/emails. The repo is public; real emails get scraped.

## 3. Backend
```bash
cd bck
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv isn't installed yet
uv sync --all-extras --dev
uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest
```
All four must pass on a clean clone. If `lint-imports` finishes suspiciously fast, the package
isn't installed and it's checking nothing — re-run `uv sync`.

## 4. Frontend
```bash
cd fnt
npm install
npm run dev
```

## 5. Read before writing any code
```bash
cat AGENTS.md        # cross-tool rules, module ownership, git protocol
cat CLAUDE.md         # Claude Code specifics, current phase, gotchas
cat ARCHITECTURE.md   # stack, folder structure, data flow, locked decisions
```

## 6. Verification block — run this, paste output in the team channel
```bash
echo "=== git ===" && git --version && git config --get user.email
echo "=== python/uv ===" && cd bck && uv --version && uv run python --version
echo "=== backend checks ===" && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest -q
echo "=== node ===" && cd ../fnt && node --version && npm --version
```

## 7. GitHub CLI (for PRs)
```bash
gh --version || sudo apt install -y gh
gh auth login          # GitHub.com -> HTTPS -> Y -> Login with a web browser
```

Do not start any ticket until section 6 passes clean.

## 8. Local PostgreSQL and TiTiler

Docker Desktop or another Docker engine must be running. From the repository root:

```bash
cd infra
docker-compose up -d
docker-compose ps
```

The Compose project is named `satquery-local` so it cannot collide with other projects whose
Compose file also lives in a directory named `infra`. Both services must report `healthy`.

| Service | Connection |
|---|---|
| PostgreSQL | `localhost:5432`, database `satquery`, user `satquery`, password `satquery_local_dev` |
| Backend database URL | `postgresql+psycopg://satquery:satquery_local_dev@localhost:5432/satquery` |
| TiTiler | `http://localhost:8001` |

These credentials are for local development only. Do not reuse them outside this Compose stack.
TiTiler uses host port `8001` because the backend already uses `8000`.

Verify PostgreSQL with a real connection:

```bash
docker-compose exec -T postgres psql -U satquery -d satquery \
  -c "SELECT current_database(), current_user;"
```

Verify TiTiler with this real Sentinel-2 Cloud-Optimized GeoTIFF from the public, unsigned AWS
Open Data bucket:

```bash
COG_URL='https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/11/S/KV/2026/6/S2B_11SKV_20260614_0_L2A/B04.tif'

curl --fail --get \
  --data-urlencode "url=${COG_URL}" \
  --output /tmp/satquery-sentinel-tile.png \
  --write-out 'HTTP %{http_code} %{content_type} %{size_download} bytes\n' \
  'http://localhost:8001/cog/tiles/WebMercatorQuad/12/685/1616.png'
```

The request must return `HTTP 200`, an `image/png` content type, and a non-zero byte count. No AWS
credentials are required. Stop the services without deleting PostgreSQL data with:

```bash
docker-compose down
```

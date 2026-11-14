#!/usr/bin/env bash
# Boots FlipScout UK: FastAPI backend on :8000 and Vite frontend on :5173.
#   ./start.sh          dev mode (hot reload) — open http://localhost:5173
#   ./start.sh --prod   build the frontend once and serve everything from http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }

# ---- backend ---------------------------------------------------------------
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "Creating Python virtualenv…"
  if command -v uv >/dev/null 2>&1; then uv venv .venv -q; else python3 -m venv .venv; fi
fi
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=.venv/Scripts/python.exe; fi
if [ ! -f .venv/.deps-installed ] || [ requirements.txt -nt .venv/.deps-installed ]; then
  echo "Installing Python dependencies…"
  if command -v uv >/dev/null 2>&1; then uv pip install --python "$PY" -q -r requirements.txt; else "$PY" -m pip install -q -r requirements.txt; fi
  "$PY" -m playwright install chromium || echo "⚠ Playwright Chromium install failed — FB Marketplace will report 'unavailable'."
  touch .venv/.deps-installed
fi

# ---- frontend --------------------------------------------------------------
cd "$ROOT/frontend"
[ -d node_modules ] || { echo "Installing frontend dependencies…"; npm install --no-audit --no-fund; }

cd "$ROOT/backend"
if [ "${1:-}" = "--prod" ]; then
  (cd "$ROOT/frontend" && npm run build)
  echo "▶ FlipScout UK on http://localhost:8000"
  exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
fi

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app &
BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT INT TERM
cd "$ROOT/frontend"
echo "▶ Backend http://127.0.0.1:8000  ·  Frontend http://localhost:5173"
npm run dev

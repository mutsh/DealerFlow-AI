#!/usr/bin/env bash
set -euo pipefail
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Update MANAGER_API_KEY if desired."
fi
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

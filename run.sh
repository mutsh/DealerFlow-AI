#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-demo}"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip

if [ "$MODE" = "--llm" ] || [ "$MODE" = "llm" ]; then
  echo "Installing optional local-LLM dependencies..."
  python -m pip install -r requirements-llm.txt
  export ROUTER_MODE=local_llm
  echo "Starting DealerFlow with local LLM routing."
else
  python -m pip install -r requirements.txt
  export ROUTER_MODE=rules
  echo "Starting DealerFlow in lightweight demo mode."
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

echo
echo "Customer UI: http://127.0.0.1:8000/"
echo "Manager UI : http://127.0.0.1:8000/manager"
echo "API docs   : http://127.0.0.1:8000/docs"
echo

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

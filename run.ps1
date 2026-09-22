param(
    [switch]$LLM
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

if ($LLM) {
    Write-Host "Installing optional local-LLM dependencies..."
    python -m pip install -r requirements-llm.txt
    $env:ROUTER_MODE = "local_llm"
    Write-Host "Starting DealerFlow with local LLM routing."
} else {
    python -m pip install -r requirements.txt
    $env:ROUTER_MODE = "rules"
    Write-Host "Starting DealerFlow in lightweight demo mode."
}

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example."
}

Write-Host ""
Write-Host "Customer UI: http://127.0.0.1:8000/"
Write-Host "Manager UI : http://127.0.0.1:8000/manager"
Write-Host "API docs   : http://127.0.0.1:8000/docs"
Write-Host ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

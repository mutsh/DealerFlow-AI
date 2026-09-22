$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "No .venv found. Run .\run.ps1 once or create the environment first."
    exit 1
}

.\.venv\Scripts\Activate.ps1
$env:ROUTER_MODE = "rules"

Write-Host "Running DealerFlow unit + smoke tests..."
python -m pytest -q

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "DealerFlow demo verification passed."

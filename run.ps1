$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Nie znaleziono .venv. Utworz je: python -m venv .venv"
    exit 1
}

& $python "$PSScriptRoot\main.py"

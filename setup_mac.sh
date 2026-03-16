#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN="python3.10"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Nie znaleziono Pythona. Zainstaluj Python 3.10 i sprobuj ponownie."
  exit 1
fi

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ ! "$PY_VERSION" =~ ^3\.(10|11|12|13)$ ]]; then
  echo "Wykryto Python $PY_VERSION ($PYTHON_BIN)."
  echo "Ten projekt wspiera Python 3.10-3.13 (PySide6)."
  echo
  echo "Uzyj np.:"
  echo "  python3.10 -m venv .venv"
  echo "  .venv/bin/python -m pip install -U pip"
  echo "  .venv/bin/python -m pip install -r requirements.txt"
  echo "  .venv/bin/python main.py"
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Gotowe."
echo "Uruchom aplikacje:"
echo "  .venv/bin/python main.py"

# Drone 360 File Sorter

Prosta aplikacja desktopowa (PySide2), ktora porzadkuje pliki wedlug daty modyfikacji.

## Wymagania

- Python 3.10

## Szybki start (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\main.py
```

## Uruchamianie bez aktywacji venv

```powershell
.\run.ps1
```

albo:

```bat
run.bat
```

## Setup na macOS

```bash
chmod +x setup_mac.sh
./setup_mac.sh
```

Uruchamianie:

```bash
.venv/bin/python main.py
```

## Build portable EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

## Git + GitHub

Lokalne repo jest juz zainicjalizowane. Aby podpiac GitHub:

```powershell
git remote add origin <URL_TWOJEGO_REPO>
git push -u origin main
```

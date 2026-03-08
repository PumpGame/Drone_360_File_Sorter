@echo off
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Nie znaleziono .venv. Utworz je: python -m venv .venv
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0main.py"

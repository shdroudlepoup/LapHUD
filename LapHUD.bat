@echo off
rem Lance LapHUD depuis les sources (environnement .venv du projet)
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Premiere installation...
    python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" -m laphud %*

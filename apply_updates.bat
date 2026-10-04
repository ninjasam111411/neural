@echo off
cd /d "%~dp0"
if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe apply_updates.py
) else (
  python apply_updates.py
)
pause

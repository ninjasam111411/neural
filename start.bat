@echo off
setlocal
cd /d "%~dp0"
title Neural

if not exist venv\Scripts\activate.bat (
  echo Run setup.bat first.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat

REM Keep models inside this project folder.
set "OLLAMA_MODELS=%~dp0models"

curl -s http://127.0.0.1:11434 >nul 2>&1
if errorlevel 1 (
  echo Starting Ollama...
  start "Ollama" /min ollama serve
  timeout /t 4 /nobreak >nul
)

python app.py
pause

@echo off
setlocal
cd /d "%~dp0"
title Neural setup

echo === Neural setup ===
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ from python.org and tick "Add to PATH", then run this again.
  pause
  exit /b 1
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama was not found. Install it from https://ollama.com/download , then run this again.
  pause
  exit /b 1
)

if not exist venv (
  echo Creating Python environment...
  python -m venv venv
)
call venv\Scripts\activate.bat
echo Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
  echo Package install failed.
  pause
  exit /b 1
)

REM Keep the AI models inside this project folder.
set "OLLAMA_MODELS=%~dp0models"

curl -s http://127.0.0.1:11434 >nul 2>&1
if not errorlevel 1 (
  echo.
  echo Ollama is already running from its normal location, so models would NOT
  echo be saved in this folder. Right-click the Ollama icon in the system tray,
  echo choose Quit, then run setup.bat again.
  pause
  exit /b 1
)

echo Starting Ollama with models stored in: %OLLAMA_MODELS%
start "Ollama" /min ollama serve
timeout /t 5 /nobreak >nul

set "MODEL=llama3.2:3b"
echo.
echo Downloading the AI model (%MODEL%). This can take a few minutes...
ollama pull %MODEL%
if errorlevel 1 (
  echo Model download failed. Check your internet and run setup.bat again.
  pause
  exit /b 1
)

set "VISION=gemma3:4b"
echo.
echo Downloading the vision model (%VISION%) so Neural can see through your camera...
ollama pull %VISION%
if errorlevel 1 (
  echo Vision model download failed. Chat still works; run setup.bat again later for camera features.
)

echo.
echo Downloading the local speech-recognition model (one time, about 150 MB)...
python -c "import config, voice; voice._get_model(config.load())"
if errorlevel 1 (
  echo Speech model download failed. Typing still works; run setup.bat again later for voice input.
)

echo.
echo Setup complete! Double-click start.bat to launch Neural.
pause

@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Pikopikopi — Local development server
echo ============================================

:: Setup virtual environment
if not exist .venv\Scripts\python.exe (
  echo [setup] Creating virtual environment...
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
echo [setup] Installing dependencies...
python -m pip install -r requirements.txt --quiet

:: Credentials
if "%ADMIN_PASSWORD%"=="" (
  set /p ADMIN_PASSWORD=Set admin password for this local run: 
)
if "%SECRET_KEY%"=="" set SECRET_KEY=%RANDOM%-%RANDOM%-%RANDOM%-pikopikopi-local
set DATA_DIR=data

:: Download coffee images if not already downloaded
if not exist data\.images_downloaded (
  echo [images] Downloading coffee images from Wikimedia Commons...
  python scripts\download_coffee_images.py --per-class 3 --pause 0.5
  if not exist data mkdir data
  echo. > data\.images_downloaded
  echo [images] Done.
) else (
  echo [images] Coffee images already present — skipping download.
)

echo.
echo [server] Starting server at http://localhost:8000
echo [server] Admin panel: http://localhost:8000/admin
echo [server] Press Ctrl+C to stop
echo.
python -m uvicorn app:app --host 127.0.0.1 --port 8000

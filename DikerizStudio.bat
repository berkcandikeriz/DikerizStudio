@echo off
chcp 65001 >nul
setlocal
title Dikeriz Studio
cd /d "%~dp0"

set "PY="
for /f "delims=" %%i in ('python -c "import sys;print(sys.executable) if sys.version_info>=(3,9) else None" 2^>nul') do set "PY=%%i"
if not defined PY for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable) if sys.version_info>=(3,9) else None" 2^>nul') do set "PY=%%i"
if "%PY%"=="None" set "PY="
if not defined PY (
  echo.
  echo  Python 3.9+ bulunamadi.
  echo  Kurulum: https://www.python.org/downloads/  ^(kurarken "Add python.exe to PATH" isaretleyin^)
  echo  ya da:   winget install -e --id Python.Python.3.12
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Ilk kurulum: sanal ortam olusturuluyor...
  "%PY%" -m venv .venv || (echo  venv olusturulamadi & pause & exit /b 1)
)
fc /b requirements.txt ".venv\.requirements.txt" >nul 2>&1
if errorlevel 1 (
  echo  Paketler kuruluyor ^(ilk seferde birkac dakika surebilir^)...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo  Paket kurulumu basarisiz & pause & exit /b 1)
  copy /y requirements.txt ".venv\.requirements.txt" >nul
)

echo  Dikeriz Studio aciliyor... Tarayicida acilmazsa: http://127.0.0.1:8765/
".venv\Scripts\python.exe" dikeriz_studio.py %*
if errorlevel 1 pause

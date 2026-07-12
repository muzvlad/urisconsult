@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Install Telegram Bot
echo ========================================
echo       INSTALL TELEGRAM BOT
echo ========================================
echo.

echo [1/6] Check Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Installing Python 3.11.9...
    echo Downloading...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    if errorlevel 1 (
        echo ERROR: Failed to download Python
        pause
        exit /b 1
    )
    echo Installing...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1
    if errorlevel 1 (
        echo ERROR: Failed to install Python
        del "%TEMP%\python_installer.exe" >nul 2>&1
        pause
        exit /b 1
    )
    del "%TEMP%\python_installer.exe" >nul 2>&1
    echo Python installed. Restarting script...
    call "%~f0"
    exit /b
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VERSION=%%i
echo OK: %PY_VERSION%
echo.

echo [2/6] Create venv...
if exist venv (
    echo Remove old venv...
    rmdir /s /q venv
)
python -m venv venv
if not exist venv\Scripts\activate (
    echo ERROR: Failed to create venv
    pause
    exit /b 1
)
call venv\Scripts\activate
echo OK
echo.

echo [3/6] Update pip...
python -m pip install --upgrade pip >nul 2>&1
echo OK
echo.

echo [4/6] Install dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo OK
echo.

echo [5/6] Create .env...
if not exist .env (
    echo BOT_TOKEN=YOUR_BOT_TOKEN_HERE > .env
    echo .env created. Replace the token!
) else (
    echo .env already exists
)
echo.

echo [6/6] Create folders...
if not exist Users\docs mkdir Users\docs
echo OK
echo.

echo ========================================
echo INSTALLATION COMPLETE
echo.
echo Replace token in .env file
echo Run: start_bot.bat
echo ========================================
echo.
pause

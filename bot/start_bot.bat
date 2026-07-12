@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Start Telegram Bot
echo ========================================
echo        START TELEGRAM BOT
echo ========================================
echo.

if not exist venv\Scripts\activate (
    echo ERROR: venv not found.
    echo Run install_bot.bat first
    pause
    exit /b 1
)

call venv\Scripts\activate

if not exist .env (
    echo .env not found!
    echo Run install_bot.bat first
    pause
    exit /b 1
)

findstr /C:"YOUR_BOT_TOKEN_HERE" .env >nul 2>&1
if not errorlevel 1 (
    echo Token not replaced in .env!
    echo Open .env and paste your token from @BotFather
    pause
    exit /b 1
)

if not exist Users\docs mkdir Users\docs

echo Starting bot...
echo ========================================
echo.

python bot.py

if errorlevel 1 (
    echo.
    echo Bot crashed with an error.
)

echo.
pause

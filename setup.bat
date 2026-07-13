@echo off
setlocal enabledelayedexpansion
title URIS Consult Setup

echo ========================================
echo      URIS CONSULT - SETUP
echo ========================================
echo.

REM --- Check Git ---
echo [1/5] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not installed!
    echo Download: https://git-scm.com/download/win
    goto :end
)
echo    OK
echo.

REM --- Check Python ---
echo [2/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not installed!
    echo Download: https://www.python.org/downloads/
    goto :end
)
echo    OK
echo.

REM --- Clone or pull ---
echo [3/5] Cloning repository...
set "REPO_DIR=%~dp0urisconsult"
set "TOKEN_FILE=%~dp0.token"
if not exist "!REPO_DIR!\bot\bot.py" goto :clone

REM --- Pull ---
if not exist "!TOKEN_FILE!" goto :pull_public
set /p GITHUB_TOKEN=<"!TOKEN_FILE!"
git -C "!REPO_DIR!" pull --quiet 2>nul
if errorlevel 1 (
    echo    [WARN] Pull failed, trying fetch+reset...
    git -C "!REPO_DIR!" fetch --quiet 2>nul
    git -C "!REPO_DIR!" reset --hard origin/master --quiet 2>nul
)
goto :clone_done

:pull_public
git -C "!REPO_DIR!" pull --quiet 2>nul
if errorlevel 1 (
    echo    [WARN] Pull failed, trying fetch+reset...
    git -C "!REPO_DIR!" fetch --quiet 2>nul
    git -C "!REPO_DIR!" reset --hard origin/master --quiet 2>nul
)
goto :clone_done

REM --- Clone ---
:clone
if not exist "!TOKEN_FILE!" goto :clone_public
set /p GITHUB_TOKEN=<"!TOKEN_FILE!"
echo    Cloning with token...
git clone --quiet "https://x-access-token:!GITHUB_TOKEN!@github.com/muzvlad/urisconsult.git" "!REPO_DIR!" 2>nul
if errorlevel 1 (
    echo    [ERROR] Clone failed. Check internet connection and token.
    goto :end
)
goto :clone_done

:clone_public
echo    Cloning (public)...
git clone --quiet "https://github.com/muzvlad/urisconsult.git" "!REPO_DIR!" 2>nul
if errorlevel 1 (
    echo    [ERROR] Clone failed. Check internet connection.
    goto :end
)
goto :clone_done

:clone_done
if errorlevel 1 (
    echo [ERROR] Clone/pull failed!
    goto :end
)
echo    OK
echo.

REM --- Install dependencies ---
echo [4/5] Installing dependencies...

if not exist "!REPO_DIR!\bot\.venv" python -m venv "!REPO_DIR!\bot\.venv"
"!REPO_DIR!\bot\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\bot\requirements.txt" 2>nul
echo    Bot: done

if not exist "!REPO_DIR!\UI\.venv" python -m venv "!REPO_DIR!\UI\.venv"
"!REPO_DIR!\UI\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\UI\requirements.txt" 2>nul
echo    UI: done
echo.

REM --- Configure .env ---
echo [5/5] Configuration...
if exist "!REPO_DIR!\bot\.env" (
    echo    bot.env exists, skip
    goto :done
)
echo.
set /p BOT_TOKEN="    Enter bot token from @BotFather (or Enter to skip): "
if "%BOT_TOKEN%"=="" (
    echo BOT_TOKEN=YOUR_TOKEN_HERE> "!REPO_DIR!\bot\.env"
    echo    [WARN] Edit bot.env before running bot
) else (
    echo BOT_TOKEN=%BOT_TOKEN%> "!REPO_DIR!\bot\.env"
    echo    OK
)

:done
echo.
echo ========================================
echo      SETUP COMPLETE
echo ========================================
echo.

:end
echo.
pause
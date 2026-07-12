@echo off
setlocal enabledelayedexpansion
title URIS Consult Setup

echo ========================================
echo      URIS CONSULT - SETUP
echo ========================================
echo.

echo [1/5] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not installed!
    echo Download: https://git-scm.com/download/win
    goto :end
)
for /f "tokens=*" %%i in ('git --version') do set GIT_VER=%%i
echo    OK: %GIT_VER%
echo.

echo [2/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not installed!
    echo Download: https://www.python.org/downloads/
    goto :end
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo    OK: %PY_VER%
echo.

echo [3/5] Cloning repository...
set "REPO_DIR=%~dp0urisconsult"
set "TOKEN_FILE=%~dp0.token"
if exist "!REPO_DIR!\bot\bot.py" (
    echo    Folder exists, pulling latest...
    git -C "!REPO_DIR!" pull --quiet
    if errorlevel 1 (
        echo    [WARN] Could not pull, using current version
    ) else (
        echo    OK: Repository updated
    )
) else (
    set "CLONE_URL=https://github.com/muzvlad/urisconsult.git"
    if exist "!TOKEN_FILE!" (
        set /p GITHUB_TOKEN=<"!TOKEN_FILE!"
        set "CLONE_URL=https://x-access-token:!GITHUB_TOKEN!@github.com/muzvlad/urisconsult.git"
        echo    Cloning with token...
    ) else (
        echo    Cloning (public)...
    )
    git clone --quiet "!CLONE_URL!" "!REPO_DIR!"
    if errorlevel 1 (
        echo [ERROR] Clone failed. Check internet or token.
        goto :end
    )
    echo    OK: Repository downloaded
)
echo.

echo [4/5] Installing dependencies...

if not exist "!REPO_DIR!\bot\.venv" (
    echo    Creating venv for bot...
    python -m venv "!REPO_DIR!\bot\.venv"
)
echo    Installing packages (bot)...
"!REPO_DIR!\bot\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip 2>nul
"!REPO_DIR!\bot\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\bot\requirements.txt"
if errorlevel 1 (
    echo    [WARN] Bot dependencies install failed
) else (
    echo    OK: Bot dependencies installed
)

if not exist "!REPO_DIR!\UI\.venv" (
    echo    Creating venv for UI...
    python -m venv "!REPO_DIR!\UI\.venv"
)
echo    Installing packages (UI)...
"!REPO_DIR!\UI\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip 2>nul
"!REPO_DIR!\UI\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\UI\requirements.txt"
if errorlevel 1 (
    echo    [WARN] UI dependencies install failed
) else (
    echo    OK: UI dependencies installed
)
echo.

echo [5/5] Configuration...
if not exist "!REPO_DIR!\bot\.env" (
    echo.
    echo    Bot token needed from @BotFather
    echo.
    set /p BOT_TOKEN="    Enter token (or press Enter to skip): "
    if "!BOT_TOKEN!"=="" (
        echo BOT_TOKEN=YOUR_TOKEN_HERE> "!REPO_DIR!\bot\.env"
        echo    [WARN] No token. Edit bot\.env before running bot.
    ) else (
        echo BOT_TOKEN=!BOT_TOKEN!> "!REPO_DIR!\bot\.env"
        echo    OK: bot\.env created
    )
) else (
    echo    OK: bot\.env already exists
)
echo.

echo ========================================
echo      SETUP COMPLETE
echo ========================================
echo.
echo Run bot:   !REPO_DIR!\bot\bot.py
echo Run UI:    !REPO_DIR!\UI\db_viewer.py
echo.

:end
echo.
pause

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title URIS Consult Setup

echo ========================================
echo      URIS CONSULT - SETUP
echo ========================================
echo.

REM --- PyPI mirror (pypi.org may be unreachable) ---
set "PIP_MIRROR=-i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com"

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
echo [3/5] Getting repository...
set "REPO_DIR=%~dp0urisconsult"
set "TOKEN_FILE=%~dp0.token"

if not exist "!REPO_DIR!\bot\bot.py" goto :clone

REM --- Pull existing ---
echo    Pulling latest changes...

REM Сначала откатываем локальные изменения чтобы pull не упал
git -C "!REPO_DIR!" checkout -- . 2>nul

if exist "!TOKEN_FILE!" (
    set /p GITHUB_TOKEN=<"!TOKEN_FILE!"
    git -C "!REPO_DIR!" pull --quiet 2>nul
) else (
    git -C "!REPO_DIR!" pull --quiet 2>nul
)
if errorlevel 1 (
    echo    [WARN] Pull failed, trying fetch+reset...
    git -C "!REPO_DIR!" fetch --quiet 2>nul
    git -C "!REPO_DIR!" reset --hard origin/master --quiet 2>nul
)
goto :clone_done

REM --- Clone ---
:clone
echo    Cloning repository...
if exist "!TOKEN_FILE!" (
    set /p GITHUB_TOKEN=<"!TOKEN_FILE!"
    git clone --quiet "https://x-access-token:!GITHUB_TOKEN!@github.com/muzvlad/urisconsult.git" "!REPO_DIR!" 2>nul
) else (
    git clone --quiet "https://github.com/muzvlad/urisconsult.git" "!REPO_DIR!" 2>nul
)
if errorlevel 1 (
    echo [ERROR] Clone failed. Check internet connection.
    goto :end
)

:clone_done
echo    OK
echo.

REM --- Install dependencies ---
echo [4/5] Installing dependencies...

REM Bot venv
if not exist "!REPO_DIR!\bot\.venv" (
    echo    Creating bot venv...
    python -m venv "!REPO_DIR!\bot\.venv"
)
echo    Installing bot packages...
"!REPO_DIR!\bot\.venv\Scripts\pip.exe" install -r "!REPO_DIR!\bot\requirements.txt" %PIP_MIRROR% --retries 5 --timeout 120
if errorlevel 1 (
    echo [ERROR] Bot dependencies install failed!
    echo    Try manually: .venv\Scripts\pip install -r requirements.txt %PIP_MIRROR%
) else (
    echo    Bot: OK
)

REM UI venv
if not exist "!REPO_DIR!\UI\.venv" (
    echo    Creating UI venv...
    python -m venv "!REPO_DIR!\UI\.venv"
)
echo    Installing UI packages...
"!REPO_DIR!\UI\.venv\Scripts\pip.exe" install -r "!REPO_DIR!\UI\requirements.txt" %PIP_MIRROR% --retries 5 --timeout 120
if errorlevel 1 (
    echo [ERROR] UI dependencies install failed!
) else (
    echo    UI: OK
)
echo.

REM --- Configure .env ---
echo [5/5] Configuration...
if exist "!REPO_DIR!\bot\.env" (
    REM Проверяем есть ли NETWORK_SERVER в .env
    findstr /C:"NETWORK_SERVER" "!REPO_DIR!\bot\.env" >nul 2>&1
    if errorlevel 1 (
        echo    Adding NETWORK_SERVER to bot.env...
        echo.>> "!REPO_DIR!\bot\.env"
        set /p NETWORK_SRV="    Enter network server (e.g. \\192.168.1.100\share) or Enter to skip: "
        if "!NETWORK_SRV!"=="" (
            echo NETWORK_SERVER=>> "!REPO_DIR!\bot\.env"
        ) else (
            echo NETWORK_SERVER=!NETWORK_SRV!>> "!REPO_DIR!\bot\.env"
        )
    ) else (
        echo    bot.env exists, skip
    )
    goto :done
)
echo.
set /p BOT_TOKEN="    Enter bot token from @BotFather (or Enter to skip): "
set /p NETWORK_SRV="    Enter network server (e.g. \\192.168.1.100\share) or Enter to skip: "
if "%BOT_TOKEN%"=="" (
    >"!REPO_DIR!\bot\.env" (
        echo BOT_TOKEN=YOUR_TOKEN_HERE
        echo NETWORK_SERVER=%NETWORK_SRV%
    )
    echo    [WARN] Edit bot.env before running bot
) else (
    >"!REPO_DIR!\bot\.env" (
        echo BOT_TOKEN=%BOT_TOKEN%
        echo NETWORK_SERVER=%NETWORK_SRV%
    )
    echo    OK
)

:done
echo.
echo ========================================
echo      SETUP COMPLETE
echo ========================================
echo.
echo    Bot:   !REPO_DIR!\bot\bot.py
echo    UI:    !REPO_DIR!\UI\run.bat
echo    EXE:   !REPO_DIR!\UI\build_exe.bat
echo.

:end
echo.
pause

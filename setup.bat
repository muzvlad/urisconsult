@echo off
title URIS Consult Setup

echo ========================================
echo      URIS CONSULT - SETUP
echo ========================================
echo.

REM --- PyPI mirror ---
set PIP_MIRROR=-i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

REM --- Check Git ---
echo [1/5] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not installed!
    echo Download: https://git-scm.com/download/win
    goto :fail
)
echo    OK

REM --- Check Python ---
echo [2/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not installed!
    echo Download: https://www.python.org/downloads/
    goto :fail
)
echo    OK

REM --- Paths ---
set REPO_DIR=%~dp0urisconsult
set TOKEN_FILE=%~dp0.token

REM --- Clone or pull ---
echo [3/5] Getting repository...
if exist "%REPO_DIR%\bot\bot.py" goto :pull

REM Clone
echo    Cloning repository...
if exist "%TOKEN_FILE%" (
    set /p GITHUB_TOKEN=<"%TOKEN_FILE%"
    git clone --quiet "https://x-access-token:!GITHUB_TOKEN!@github.com/muzvlad/urisconsult.git" "%REPO_DIR%" 2>nul
) else (
    git clone --quiet "https://github.com/muzvlad/urisconsult.git" "%REPO_DIR%" 2>nul
)
if errorlevel 1 (
    echo [ERROR] Clone failed. Check internet.
    goto :fail
)
goto :clone_done

:pull
echo    Pulling latest changes...
for /f %%i in ('git -C "%REPO_DIR%" rev-parse HEAD 2^>nul') do set OLD_COMMIT=%%i
git -C "%REPO_DIR%" checkout -- . 2>nul
if exist "%TOKEN_FILE%" (
    set /p GITHUB_TOKEN=<"%TOKEN_FILE%"
    git -C "%REPO_DIR%" pull --quiet 2>nul
) else (
    git -C "%REPO_DIR%" pull --quiet 2>nul
)
if errorlevel 1 (
    echo    [WARN] Pull failed, trying fetch+reset...
    git -C "%REPO_DIR%" fetch --quiet 2>nul
    git -C "%REPO_DIR%" reset --hard origin/master --quiet 2>nul
)
for /f %%i in ('git -C "%REPO_DIR%" rev-parse HEAD 2^>nul') do set NEW_COMMIT=%%i
if not "%OLD_COMMIT%"=="%NEW_COMMIT%" (
    echo.
    echo    --- Updated files ---
    git -C "%REPO_DIR%" diff --stat %OLD_COMMIT% %NEW_COMMIT% 2>nul
    echo    ---------------------
) else (
    echo    Already up to date.
)

:clone_done
echo    OK

REM --- Install dependencies ---
echo [4/5] Installing dependencies...

REM Bot venv
if not exist "%REPO_DIR%\bot\.venv" (
    echo    Creating bot venv...
    python -m venv "%REPO_DIR%\bot\.venv"
)
echo    Installing bot packages...
"%REPO_DIR%\bot\.venv\Scripts\pip.exe" install -r "%REPO_DIR%\bot\requirements.txt" %PIP_MIRROR% --retries 5 --timeout 120 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Bot dependencies failed!
) else (
    echo    Bot: OK
)

REM UI venv
if not exist "%REPO_DIR%\UI\.venv" (
    echo    Creating UI venv...
    python -m venv "%REPO_DIR%\UI\.venv"
)
echo    Installing UI packages...
"%REPO_DIR%\UI\.venv\Scripts\pip.exe" install -r "%REPO_DIR%\UI\requirements.txt" %PIP_MIRROR% --retries 5 --timeout 120 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] UI dependencies failed!
) else (
    echo    UI: OK
)

REM --- Configure .env ---
echo [5/5] Configuration...
if exist "%REPO_DIR%\bot\.env" (
    findstr /C:"API_SERVER" "%REPO_DIR%\bot\.env" >nul 2>&1
    if errorlevel 1 (
        echo    Adding API_SERVER...
        echo.>> "%REPO_DIR%\bot\.env"
        set /p API_SRV="    API server (http://ip:8080) or Enter to skip: "
        if "!API_SRV!"=="" (
            echo.>> "%REPO_DIR%\bot\.env"
        ) else (
            echo API_SERVER=!API_SRV!>> "%REPO_DIR%\bot\.env"
        )
    ) else (
        echo    bot.env OK
    )
    goto :done
)
echo.
set /p BOT_TOKEN="    Bot token from @BotFather (Enter to skip): "
set /p API_SRV="    API server (http://ip:8080) or Enter to skip: "
if "%BOT_TOKEN%"=="" (
    echo BOT_TOKEN=YOUR_TOKEN_HERE> "%REPO_DIR%\bot\.env"
    echo API_SERVER=%API_SRV%>> "%REPO_DIR%\bot\.env"
    echo    [WARN] Edit bot\.env before running bot
) else (
    echo BOT_TOKEN=%BOT_TOKEN%> "%REPO_DIR%\bot\.env"
    echo API_SERVER=%API_SRV%>> "%REPO_DIR%\bot\.env"
    echo    OK
)

:done
echo.
echo ========================================
echo      SETUP COMPLETE
echo ========================================
echo.
echo    Bot:   %REPO_DIR%\bot\bot.py
echo    UI:    %REPO_DIR%\UI\run.bat
echo    EXE:   %REPO_DIR%\UI\build_exe.bat
echo.
goto :end

:fail
echo.
echo Setup failed. See errors above.

:end
echo.
pause

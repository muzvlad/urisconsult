@echo off

set "SCRIPT_DIR=%~dp0"

REM Поддержка UNC-путей (сетевые папки)
pushd "%SCRIPT_DIR%" 2>nul
if errorlevel 1 (
    set "SCRIPT_DIR=%TEMP%\urisconsult_ui"
    if not exist "%SCRIPT_DIR%" mkdir "%SCRIPT_DIR%"
    xcopy /s /e /q "%~dp0src" "%SCRIPT_DIR%\src\" >nul
    xcopy /q "%~dp0db_viewer.py" "%SCRIPT_DIR%\" >nul
    cd /d "%SCRIPT_DIR%"
)

REM Активация venv если есть
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    start "" "%SCRIPT_DIR%.venv\Scripts\pythonw.exe" db_viewer.py
) else if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    start "" pythonw db_viewer.py
) else (
    start "" pythonw db_viewer.py
)
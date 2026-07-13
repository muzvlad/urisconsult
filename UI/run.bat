@echo off

REM Поддержка UNC-путей (сетевые папки)
pushd "%~dp0" 2>nul
if errorlevel 1 (
    set "TEMP_DIR=%TEMP%\urisconsult_ui"
    if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"
    xcopy /s /e /q "%~dp0src" "%TEMP_DIR%\src\" >nul
    xcopy /q "%~dp0db_viewer.py" "%TEMP_DIR%\" >nul
    cd /d "%TEMP_DIR%"
)

REM Активация venv если есть
if exist "%~dp0.venv\Scripts\python.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" db_viewer.py
) else (
    start "" pythonw db_viewer.py
)
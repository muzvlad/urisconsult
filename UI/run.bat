@echo off
cd /d "%~dp0"

REM API сервер (менять при необходимости)
set API_SERVER=http://144.76.70.246:56755

REM Если venv нет или пустой — создаём и ставим зависимости
if not exist ".venv\Scripts\python.exe" (
    echo Creating venv...
    python -m venv .venv
    echo Installing dependencies...
    ".venv\Scripts\pip.exe" install -r requirements.txt --retries 5 --timeout 120 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
)

REM Проверяем что Pillow установлен
".venv\Scripts\python.exe" -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    ".venv\Scripts\pip.exe" install -r requirements.txt --retries 5 --timeout 120 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
)

echo Starting application...
".venv\Scripts\python.exe" db_viewer.py

if errorlevel 1 (
    echo.
    echo ERROR! Code: %errorlevel%
    pause
)

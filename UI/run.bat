@echo off
chcp 65001 >nul
title DB Viewer
cls

echo ==================================================
echo              DB VIEWER
echo ==================================================
echo.

echo Активация виртуального окружения...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo ✅ Готов к запуску
) else (
    echo ⚠️  Используется системный Python
)

echo.
echo Запуск приложения...
echo ==================================================
echo.

python db_viewer.py

echo.
pause
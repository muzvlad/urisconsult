@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title URIS Consult — Setup

echo ========================================
echo     URIS CONSULT — УСТАНОВЩИК
echo ========================================
echo.

REM ─── 1. Проверка Git ───
echo [1/5] Проверка Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git не установлен!
    echo Скачайте: https://git-scm.com/download/win
    goto :end
)
for /f "tokens=*" %%i in ('git --version') do set GIT_VER=%%i
echo    OK: %GIT_VER%
echo.

REM ─── 2. Проверка Python ───
echo [2/5] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не установлен!
    echo Скачайте: https://www.python.org/downloads/
    echo ВАЖНО: поставьте галочку "Add Python to PATH" при установке!
    goto :end
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo    OK: %PY_VER%
echo.

REM ─── 3. Клонирование репозитория ───
echo [3/5] Клонирование репозитория...
set "REPO_DIR=%~dp0urisconsult"
if exist "!REPO_DIR!\bot\bot.py" (
    echo    Папка существует, обновляю...
    git -C "!REPO_DIR!" pull --quiet
    if errorlevel 1 (
        echo    [WARN] Не удалось обновить, использую текущую версию
    ) else (
        echo    OK: Репозиторий обновлён
    )
) else (
    echo    Клонирование с GitHub...
    git clone --quiet https://github.com/muzvlad/urisconsult.git "!REPO_DIR!"
    if errorlevel 1 (
        echo [ERROR] Ошибка клонирования. Проверьте подключение к интернету.
        goto :end
    )
    echo    OK: Репозиторий скачан
)
echo.

REM ─── 4. Установка зависимостей ───
echo [4/5] Установка зависимостей...

REM --- Бот ---
if not exist "!REPO_DIR!\bot\.venv" (
    echo    Создание venv для бота...
    python -m venv "!REPO_DIR!\bot\.venv"
)
echo    Установка пакетов (бот)...
"!REPO_DIR!\bot\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
"!REPO_DIR!\bot\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\bot\requirements.txt"
if errorlevel 1 (
    echo    [WARN] Ошибка установки зависимостей бота
) else (
    echo    OK: Зависимости бота установлены
)

REM --- UI ---
if not exist "!REPO_DIR!\UI\.venv" (
    echo    Создание venv для UI...
    python -m venv "!REPO_DIR!\UI\.venv"
)
echo    Установка пакетов (UI)...
"!REPO_DIR!\UI\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
"!REPO_DIR!\UI\.venv\Scripts\python.exe" -m pip install --quiet -r "!REPO_DIR!\UI\requirements.txt"
if errorlevel 1 (
    echo    [WARN] Ошибка установки зависимостей UI
) else (
    echo    OK: Зависимости UI установлены
)
echo.

REM ─── 5. Настройка .env ───
echo [5/5] Настройка конфигурации...
if not exist "!REPO_DIR!\bot\.env" (
    echo.
    echo    Для работы бота нужен токен от @BotFather
    echo.
    set /p BOT_TOKEN="    Введите токен (или Enter для пропуска): "
    if "!BOT_TOKEN!"=="" (
        echo BOT_TOKEN=YOUR_TOKEN_HERE> "!REPO_DIR!\bot\.env"
        echo    [WARN] Токен не введён. Отредактируйте bot\.env перед запуском.
    ) else (
        echo BOT_TOKEN=!BOT_TOKEN!> "!REPO_DIR!\bot\.env"
        echo    OK: bot\.env создан
    )
) else (
    echo    OK: bot\.env уже существует
)
echo.

echo ========================================
echo     УСТАНОВКА ЗАВЕРШЕНА!
echo ========================================
echo.
echo Запуск бота:   !REPO_DIR!\bot\bot.py
echo Запуск UI:     !REPO_DIR!\UI\db_viewer.py
echo.

:end
echo.
pause

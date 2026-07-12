@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion
chcp 65001 >nul
title Setup Bot
echo ========================================
echo        TELEGRAM BOT SETUP
echo ========================================
echo.

echo [1/2] Check git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git not installed!
    echo Install from https://git-scm.com/download/win
    goto :end
)
echo OK
echo.

echo [2/2] Cloning repository...
set "REPO_DIR=%~dp0urisconsult"
if exist "!REPO_DIR!" (
    echo Folder exists, pulling latest...
    git -C "!REPO_DIR!" pull
) else (
    set /p GITHUB_TOKEN="Enter GitHub token (or press Enter if public): "
    if "!GITHUB_TOKEN!"=="" (
        git clone https://github.com/muzvlad/urisconsult.git "!REPO_DIR!"
    ) else (
        git clone https://x-access-token:!GITHUB_TOKEN!@github.com/muzvlad/urisconsult.git "!REPO_DIR!"
    )
)
if errorlevel 1 (
    echo ERROR: Failed to clone repository
    goto :end
)
echo OK
echo.

echo ========================================
echo DONE. Files saved to: urisconsult
echo ========================================

:end
echo.
pause

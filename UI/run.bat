@echo off
chcp 65001 >nul
title DB Viewer

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

start "" pythonw db_viewer.py
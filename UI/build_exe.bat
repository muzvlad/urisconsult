@echo off
cd /d "%~dp0"

REM Создание venv если нет
if not exist ".venv\Scripts\python.exe" (
    echo Создание виртуального окружения...
    python -m venv .venv
    if errorlevel 1 (
        echo ОШИБКА: Не удалось создать venv
        pause
        exit /b 1
    )
    echo Установка зависимостей...
    ".venv\Scripts\pip.exe" install -r requirements.txt pyinstaller
    if errorlevel 1 (
        echo ОШИБКА: Не удалось установить зависимости
        pause
        exit /b 1
    )
)

echo Сборка EXE...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
del "[Search]Driver.spec" 2>nul

".venv\Scripts\python.exe" -m PyInstaller --onefile --windowed --name="[Search]Driver" --icon=NONE --noconfirm --clean --add-data "src;src" --collect-all Pillow --collect-all reportlab --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.ImageTk --hidden-import=PIL._tkinter_finder --hidden-import=reportlab --hidden-import=reportlab.pdfgen --hidden-import=reportlab.lib.pagesizes --hidden-import=reportlab.pdfbase --hidden-import=reportlab.pdfbase.ttfonts --hidden-import=reportlab.lib.utils --hidden-import=urllib.request --hidden-import=urllib.parse --hidden-import=json --hidden-import=sqlite3 --hidden-import=threading --hidden-import=concurrent.futures --hidden-import=src --hidden-import=src.config --hidden-import=src.database --hidden-import=src.models --hidden-import=src.services --hidden-import=src.widgets --hidden-import=src.dialogs --hidden-import=src.main --hidden-import=src.splash --hidden-import=src.logging_config db_viewer.py

if exist "dist\[Search]Driver.exe" (
    echo.
    echo =============================
    echo СБОРКА ЗАВЕРШЕНА!
    echo dist\[Search]Driver.exe
    echo =============================
) else (
    echo.
    echo ОШИБКА СБОРКИ!
)
pause

@echo off
cd /d "%~dp0"

echo Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Создание venv...
    python -m venv .venv
)

echo Установка зависимостей...
".venv\Scripts\pip.exe" install -r requirements.txt pyinstaller --timeout 60 --retries 3 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo Сборка EXE...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
del /q "[Search]Driver.spec" 2>nul

".venv\Scripts\python.exe" -m PyInstaller --onefile --windowed --name="[Search]Driver" --icon=NONE --noconfirm --clean --add-data "src;src" --collect-all Pillow --collect-all reportlab --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.ImageTk --hidden-import=PIL._tkinter_finder --hidden-import=reportlab --hidden-import=reportlab.pdfgen --hidden-import=reportlab.lib.pagesizes --hidden-import=reportlab.pdfbase --hidden-import=reportlab.pdfbase.ttfonts --hidden-import=reportlab.lib.utils --hidden-import=urllib.request --hidden-import=urllib.parse --hidden-import=json --hidden-import=sqlite3 --hidden-import=threading --hidden-import=concurrent.futures --hidden-import=src --hidden-import=src.config --hidden-import=src.database --hidden-import=src.models --hidden-import=src.services --hidden-import=src.widgets --hidden-import=src.dialogs --hidden-import=src.main --hidden-import=src.splash --hidden-import=src.logging_config db_viewer.py

if exist "dist\[Search]Driver.exe" (
    echo =============================
    echo ГОТОВО!
    echo =============================
) else (
    echo ОШИБКА СБОРКИ!
)
pause

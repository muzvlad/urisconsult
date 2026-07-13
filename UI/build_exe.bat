@echo off
cd /d "%~dp0"
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
del "[Search]Driver.spec" 2>nul

pyinstaller --onefile --windowed --name="[Search]Driver" --icon=NONE --noconfirm --clean --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.ImageTk --hidden-import=reportlab --hidden-import=reportlab.pdfgen --hidden-import=reportlab.lib.pagesizes --hidden-import=reportlab.pdfbase --hidden-import=reportlab.pdfbase.ttfonts --hidden-import=reportlab.lib.utils --hidden-import=urllib.request --hidden-import=urllib.parse --hidden-import=json --hidden-import=sqlite3 --hidden-import=threading --hidden-import=concurrent.futures --hidden-import=src.config --hidden-import=src.database --hidden-import=src.models --hidden-import=src.services --hidden-import=src.widgets --hidden-import=src.dialogs --hidden-import=src.main --hidden-import=src.splash --hidden-import=src.logging_config db_viewer.py

if exist "dist\[Search]Driver.exe" (
    echo.
    echo =============================
    echo BUILD SUCCESS!
    echo dist\[Search]Driver.exe created
    echo =============================
) else (
    echo.
    echo BUILD FAILED!
)
pause
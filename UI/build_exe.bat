@echo off
cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv...
    python -m venv .venv
)

echo Installing dependencies...
".venv\Scripts\pip.exe" install -r requirements.txt pyinstaller --retries 5 --timeout 120 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo Building EXE...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
del /q "*.spec" 2>nul

".venv\Scripts\python.exe" build_exe.py

if exist "dist\[Search]Driver.exe" (
    echo =============================
    echo DONE!
    echo =============================

    REM Создать ярлык с иконкой icon.ico
    if exist "icon.ico" (
        echo Creating shortcut with icon...
        powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%~dp0dist\[Search]Driver.lnk'); $Shortcut.TargetPath = '%~dp0dist\[Search]Driver.exe'; $Shortcut.IconLocation = '%~dp0icon.ico'; $Shortcut.Save()"
    )
) else (
    echo BUILD ERROR!
)
pause

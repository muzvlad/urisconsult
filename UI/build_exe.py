# -*- coding: utf-8 -*-
"""
Скрипт для создания исполняемого файла из Python приложения.
Поддерживает новую модульную структуру в src/.
"""

import subprocess
import sys
import os
import shutil


def install_pyinstaller() -> bool:
    """Установка PyInstaller если он не установлен."""
    try:
        import PyInstaller
        print("PyInstaller already installed")
        return True
    except ImportError:
        print("Installing PyInstaller...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print("PyInstaller successfully installed")
            return True
        else:
            print("Error installing PyInstaller:")
            print(result.stderr)
            return False


def clean_build_dirs() -> None:
    """Очистка папок сборки."""
    for dir_name in ['build', 'dist', '__pycache__']:
        path = os.path.join(os.path.dirname(__file__), dir_name)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            print(f"Cleaned: {dir_name}/")

    # Удаляем .spec файлы
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            os.remove(file)
            print(f"Cleaned: {file}")


def create_executable() -> bool:
    """Создание полностью автономного exe файла."""
    if not install_pyinstaller():
        return False

    try:
        # Определяем пути
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(base_dir)  # корень проекта (на уровень выше UI/)
        src_dir = os.path.join(base_dir, 'src')
        shared_dir = os.path.join(project_root, 'shared')
        db_viewer = os.path.join(base_dir, 'db_viewer.py')

        # Команда для создания exe
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--onefile',              # Один exe файл
            '--windowed',             # Без консоли (GUI приложение)
            '--name=[Search]Driver',  # Имя exe файла
            '--icon=NONE',            # Без иконки
            '--noconfirm',            # Не спрашивать подтверждение
            '--clean',                # Очистить перед сборкой
            # Добавляем src и shared как data
            f'--add-data={src_dir}{os.pathsep}src',
            f'--add-data={shared_dir}{os.pathsep}shared',
            # Скрытые импорты для надежности
            '--hidden-import=tkinter',
            '--hidden-import=PIL',
            '--hidden-import=PIL.Image',
            '--hidden-import=PIL.ImageTk',
            '--hidden-import=PIL._tkinter_finder',
            '--hidden-import=reportlab',
            '--hidden-import=reportlab.pdfgen',
            '--hidden-import=reportlab.lib.pagesizes',
            '--hidden-import=reportlab.pdfbase',
            '--hidden-import=reportlab.pdfbase.ttfonts',
            '--hidden-import=reportlab.lib.utils',
            '--hidden-import=urllib.request',
            '--hidden-import=urllib.parse',
            '--hidden-import=json',
            '--hidden-import=sqlite3',
            '--hidden-import=threading',
            '--hidden-import=concurrent.futures',
            '--hidden-import=src',
            '--hidden-import=src.config',
            '--hidden-import=src.api_client',
            '--hidden-import=src.models',
            '--hidden-import=src.services',
            '--hidden-import=src.widgets',
            '--hidden-import=src.dialogs',
            '--hidden-import=src.main',
            '--hidden-import=src.splash',
            '--hidden-import=src.logging_config',
            '--hidden-import=shared',
            db_viewer
        ]

        print("\n" + "=" * 50)
        print("Creating executable...")
        print("=" * 50)
        print("Command:", ' '.join(cmd))

        result = subprocess.run(cmd, cwd=base_dir, encoding='utf-8', errors='replace')

        if result.returncode == 0:
            exe_path = os.path.join(base_dir, 'dist', '[Search]Driver.exe')
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / 1024 / 1024
                print(f"\nExecutable created successfully!")
                print(f"Path: {exe_path}")
                print(f"Size: {size_mb:.1f} MB")
                print(f"\nFile can run on any Windows computer without Python!")
                return True
            else:
                print("Executable not found after build")
                return False
        else:
            print("Error creating exe file (see PyInstaller output above)")
            return False

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 50)
    print("Build URIS Consult DB Viewer to EXE")
    print("=" * 50)

    # Очистка перед сборкой
    clean_build_dirs()

    if create_executable():
        print("\nDone! Application built to exe file.")
        print("File is in 'dist' folder")
    else:
        print("\nError creating exe file.")
        print("Check messages above for diagnostics.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
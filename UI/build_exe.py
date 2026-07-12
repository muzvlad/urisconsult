# -*- coding: utf-8 -*-
"""
Скрипт для создания исполняемого файла из Python приложения
"""

import subprocess
import sys
import os

def install_pyinstaller():
    """Установка PyInstaller если он не установлен"""
    try:
        import PyInstaller
        print("PyInstaller уже установлен")
        return True
    except ImportError:
        print("Установка PyInstaller...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PyInstaller успешно установлен")
            return True
        else:
            print("❌ Ошибка установки PyInstaller:")
            print(result.stderr)
            return False

def create_executable():
    """Создание полностью автономного exe файла"""
    if not install_pyinstaller():
        return False
    
    try:
        # Команда для создания полностью автономного exe файла
        cmd = [
            'pyinstaller',
            '--onefile',              # Создать один exe файл
            '--windowed',             # Без консоли (GUI приложение)
            '--name=[Search]Driver',  # Имя exe файла
            '--icon=NONE',            # Без иконки
            '--noconfirm',            # Не спрашивать подтверждение
            '--clean',                # Очистить перед сборкой
            # Включаем все необходимые данные
            '--add-data=Users;Users',  # Добавить папку Users (legacy)
            # Скрытие консоли и оптимизация
            '--strip',                # Удалить символы отладки
            '--upx-dir=NONE',         # Без UPX сжатия (если нет UPX)
            # Автоопределение зависимостей
            '--hidden-import=tkinter',
            '--hidden-import=PIL',
            '--hidden-import=reportlab',
            '--hidden-import=json',
            '--hidden-import=os',
            '--hidden-import=pathlib',
            '--hidden-import=threading',
            'db_viewer.py'
        ]
        
        print("\nСоздание полностью автономного исполняемого файла...")
        print("Команда:", ' '.join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            exe_path = os.path.join('dist', '[Search]Driver.exe')
            if os.path.exists(exe_path):
                size_mb = os.path.getsize(exe_path) / 1024 / 1024
                print(f"\n✅ Полностью автономный exe файл успешно создан!")
                print(f"📁 Путь: {exe_path}")
                print(f"⚖️  Размер: {size_mb:.1f} МБ")
                print(f"\n🎉 Файл можно запускать на любом Windows компьютере без Python!")
                return True
            else:
                print("❌ Исполняемый файл не найден после сборки")
                return False
        else:
            print("❌ Ошибка при создании exe файла:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    print("=" * 50)
    print("Создание исполняемого файла DB Viewer")
    print("=" * 50)
    
    if create_executable():
        print("\n🎉 Готово! Приложение собрано в exe файл.")
        print("Файл находится в папке 'dist'")
    else:
        print("\n💥 Произошла ошибка при создании exe файла.")
        print("Проверьте сообщения выше для диагностики.")
    
    input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()
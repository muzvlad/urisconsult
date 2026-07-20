#!/usr/bin/env python3
"""
URIS Consult — Просмотр карточек сотрудников (Entry Point)

Старый файл db_viewer.py теперь является точкой входа, 
которая делегирует запуск новой модульной структуре в src/
"""
import sys
import os

# Добавляем папку src в путь для импортов
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_dir)


def main():
    """Запуск приложения через новый модульный код."""
    try:
        from src.main import main as new_main
        new_main()
    except Exception:
        pass


if __name__ == "__main__":
    main()
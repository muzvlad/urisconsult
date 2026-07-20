#!/usr/bin/env python3
"""
URIS Consult — Просмотр карточек сотрудников (Entry Point)
"""
import sys
import os
import traceback

# Добавляем папку src в путь для импортов
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_dir)

# Лог ошибок в файл (для EXE)
def _log_error(msg):
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui_error.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        pass


def main():
    """Запуск приложения через новый модульный код."""
    try:
        from src.main import main as new_main
        new_main()
    except Exception as e:
        _log_error(f"FATAL: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
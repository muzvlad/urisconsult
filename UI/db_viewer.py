#!/usr/bin/env python3
"""
URIS Consult — Просмотр карточек сотрудников (Entry Point)
"""
import sys
import os
import traceback

# Лог ошибок в файл — СРАЗУ, до любых импортов
def _log_error(msg):
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'ui_error.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except Exception:
        try:
            log_path = os.path.join(os.path.expanduser('~'), 'ui_error.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            pass

_log_error(f"=== START {sys.executable} ===")

# Добавляем папку src в путь для импортов
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_dir)
_log_error(f"src_dir={src_dir} exists={os.path.exists(src_dir)}")


def main():
    """Запуск приложения через новый модульный код."""
    try:
        _log_error("importing src.main...")
        from src.main import main as new_main
        _log_error("running main...")
        new_main()
        _log_error("main finished")
    except Exception as e:
        _log_error(f"FATAL: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
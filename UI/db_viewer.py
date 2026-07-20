#!/usr/bin/env python3
"""
URIS Consult — Просмотр карточек сотрудников (Entry Point)
"""
import sys
import os
import traceback


def _log(msg):
    """Лог в файл для диагностики EXE."""
    try:
        paths = [
            os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'ui_error.log'),
            os.path.join(os.path.expanduser('~'), 'ui_error.log'),
        ]
        for p in paths:
            try:
                with open(p, 'a', encoding='utf-8') as f:
                    f.write(msg + '\n')
            except Exception:
                continue
            break
    except Exception:
        pass


_log(f"=== ЗАПУСК {sys.executable} ===")

# Добавляем папку src в путь для импортов (только в dev режиме)
if not getattr(sys, "frozen", False):
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    sys.path.insert(0, src_dir)
    _log(f"Dev режим: src_dir={src_dir}")
else:
    _log("Режим EXE: src упакован в бандл")


def main():
    """Запуск приложения через новый модульный код."""
    try:
        _log("Импорт src.main...")
        from src.main import main as new_main
        _log("Импорт завершён, запуск main()...")
        new_main()
        _log("main() завершён")
    except Exception as e:
        _log(f"ОШИБКА: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
URIS Consult — Просмотр карточек сотрудников (Entry Point)

Splash screen → загрузка → retry при ошибке.
"""
import sys
import os
import time
import traceback

MAX_RETRIES = 2


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
                    f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
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


# ─── Splash screen (до загрузки main.py) ────────────────────────────

def _show_splash():
    """Показать splash screen и вернуть (root,关闭_функцию)."""
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)

    # Центрируем
    w, h = 400, 180
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Фон
    frame = tk.Frame(root, bg='#2c3e50', relief=tk.RAISED, borderwidth=2)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="URIS Consult",
             font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white'
             ).pack(pady=(25, 5))

    tk.Label(frame, text="Загрузка базы данных...",
             font=('Arial', 10), bg='#2c3e50', fg='#aaa'
             ).pack(pady=(0, 15))

    # Прогресс-бар
    from tkinter import ttk
    progress = ttk.Progressbar(frame, mode='indeterminate', length=300)
    progress.pack(pady=5)
    progress.start(15)

    status_label = tk.Label(frame, text="Подключение к серверу...",
                            font=('Arial', 9), bg='#2c3e50', fg='#888')
    status_label.pack(pady=(0, 15))

    root.update()

    def close():
        progress.stop()
        root.destroy()

    return root, close, status_label


def _try_run():
    """Попытка запустить приложение. Возвращает True при успехе."""
    _log("Импорт src.main...")
    from src.main import main as new_main
    _log("Импорт завершён, запуск main()...")
    new_main()
    _log("main() завершён")
    return True


def main():
    """Запуск приложения с splash screen и retry."""
    splash_root = None
    close_splash = None

    try:
        # Показываем splash ДО загрузки
        _log("Показ splash screen...")
        splash_root, close_splash, status_label = _show_splash()

        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):  # 1, 2, 3 попытки
            try:
                if attempt > 1:
                    _log(f"Попытка {attempt}/{MAX_RETRIES + 1}...")
                    if status_label:
                        status_label.config(text=f"Повторная попытка {attempt}...")
                        splash_root.update()

                # Закрываем splash ПЕРЕД запуском main (main создаст своё окно)
                _log("Закрытие splash, запуск main()...")
                if close_splash:
                    close_splash()
                    close_splash = None

                _try_run()
                return  # Успех — выходим

            except Exception as e:
                last_error = e
                _log(f"Попытка {attempt} не удалась: {e}")
                if attempt <= MAX_RETRIES:
                    _log(f"Повтор через 2 сек...")
                    # Пересоздаём splash для следующей попытки
                    if splash_root:
                        try:
                            splash_root.destroy()
                        except Exception:
                            pass
                    time.sleep(2)
                    splash_root, close_splash, status_label = _show_splash()

        # Все попытки исчерпаны
        _log(f"Все попытки исчерпаны. Последняя ошибка: {last_error}")
        if close_splash:
            close_splash()
        _show_error(f"Не удалось запустить приложение:\n{last_error}")

    except Exception as e:
        _log(f"Критическая ошибка: {e}\n{traceback.format_exc()}")
        if close_splash:
            close_splash()
        _show_error(f"Критическая ошибка:\n{e}")


def _show_error(msg):
    """Показать диалог ошибки."""
    import tkinter as tk
    from tkinter import messagebox
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Ошибка", msg)
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    main()

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

# Добавляем папку src и корень проекта в путь для импортов (только в dev режиме)
if not getattr(sys, "frozen", False):
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    sys.path.insert(0, src_dir)
    # Корень проекта для импорта shared/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    _log(f"Dev режим: src_dir={src_dir}, project_root={project_root}")
else:
    _log("Режим EXE: src упакован в бандл")


# ─── Splash screen ──────────────────────────────────────────────────

def _create_splash(root):
    """Создать splash screen поверх root. Возвращает (splash_window, status_label)."""
    import tkinter as tk
    from tkinter import ttk

    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.attributes('-topmost', True)

    w, h = 400, 180
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    splash.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(splash, bg='#2c3e50', relief=tk.RAISED, borderwidth=2)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="URIS Consult",
             font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white'
             ).pack(pady=(25, 5))

    tk.Label(frame, text="Загрузка базы данных...",
             font=('Arial', 10), bg='#2c3e50', fg='#aaa'
             ).pack(pady=(0, 15))

    progress = ttk.Progressbar(frame, mode='indeterminate', length=300)
    progress.pack(pady=5)
    progress.start(15)

    status_label = tk.Label(frame, text="Подключение к серверу...",
                            font=('Arial', 9), bg='#2c3e50', fg='#888')
    status_label.pack(pady=(0, 15))

    splash.update()
    return splash, status_label


def _destroy_splash(splash):
    """Безопасно уничтожить splash."""
    try:
        if splash and splash.winfo_exists():
            splash.destroy()
    except Exception:
        pass


def _try_run(root, splash=None):
    """Попытка запустить приложение."""
    _log("Импорт src.main...")
    # Обновляем splash пока идёт импорт (долго в EXE)
    if splash:
        try:
            splash.update()
        except Exception:
            pass
    from src.main import main as new_main
    _log("Импорт завершён, запуск main()...")
    if splash:
        try:
            splash.update()
        except Exception:
            pass
    new_main(root=root, splash=splash)
    _log("main() завершён")
    return True


def main():
    """Запуск приложения с splash screen и retry."""
    import tkinter as tk

    # Один корневой Tk() на всё приложение
    root = tk.Tk()
    root.withdraw()  # Скрываем пока не готово

    splash = None

    try:
        _log("Показ splash screen...")
        splash, status_label = _create_splash(root)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                if attempt > 1:
                    _log(f"Попытка {attempt}/{MAX_RETRIES + 1}...")
                    if status_label:
                        status_label.config(text=f"Повторная попытка {attempt}...")
                        splash.update()

                _try_run(root, splash)
                return

            except Exception as e:
                last_error = e
                _log(f"Попытка {attempt} не удалась: {e}")
                _destroy_splash(splash)
                splash = None
                if attempt <= MAX_RETRIES:
                    _log("Повтор через 2 сек...")
                    time.sleep(2)
                    splash, status_label = _create_splash(root)

        _log(f"Все попытки исчерпаны: {last_error}")
        _destroy_splash(splash)
        _show_error(f"Не удалось запустить приложение:\n{last_error}")
        root.destroy()

    except Exception as e:
        _log(f"Критическая ошибка: {e}\n{traceback.format_exc()}")
        _destroy_splash(splash)
        _show_error(f"Критическая ошибка:\n{e}")
        root.destroy()


def _show_error(msg):
    """Диалог ошибки."""
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

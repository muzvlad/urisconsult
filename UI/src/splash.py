"""
Splash screen для отображения во время загрузки приложения.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
import threading
import time

from src.config import get_config, center_window


class SplashScreen:
    """Экран загрузки (Splash screen)."""

    def __init__(
        self,
        root: tk.Tk,
        on_complete: Optional[Callable[[], None]] = None,
        min_duration: float = 1.5,
    ):
        self.root = root
        self.on_complete = on_complete
        self.min_duration = min_duration
        self.config = get_config()

        self._window: Optional[tk.Toplevel] = None
        self._progress: Optional[ttk.Progressbar] = None
        self._label: Optional[tk.Label] = None
        self._start_time = time.time()

        self._create_window()
        self._animate()

    def _create_window(self) -> None:
        """Создание окна загрузки."""
        self._window = tk.Toplevel(self.root)
        self._window.title("")
        self._window.overrideredirect(True)  # Без рамок
        self._window.attributes('-topmost', True)

        # Размеры
        width = 400
        height = 200
        center_window(self._window, width, height)

        # Фон
        main_frame = tk.Frame(self._window, bg=self.config.header_bg, relief=tk.RAISED, borderwidth=2)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Логотип/Название
        tk.Label(
            main_frame,
            text="URIS Consult",
            font=('Arial', 20, 'bold'),
            bg=self.config.header_bg,
            fg=self.config.header_fg,
        ).pack(pady=(30, 5))

        tk.Label(
            main_frame,
            text="Просмотр карточек сотрудников",
            font=('Arial', 11),
            bg=self.config.header_bg,
            fg='#bbb',
        ).pack(pady=(0, 20))

        # Прогресс-бар
        self._progress = ttk.Progressbar(
            main_frame,
            mode='indeterminate',
            length=300,
        )
        self._progress.pack(pady=10)
        self._progress.start(15)

        # Статус
        self._label = tk.Label(
            main_frame,
            text="Инициализация...",
            font=('Arial', 9),
            bg=self.config.header_bg,
            fg='#aaa',
        )
        self._label.pack(pady=(0, 20))

    def _animate(self) -> None:
        """Обновление анимации и проверка завершения."""
        if self._window is None or not self._window.winfo_exists():
            return

        elapsed = time.time() - self._start_time

        # Обновляем текст статуса
        if elapsed < 0.3:
            status = "Инициализация..."
        elif elapsed < 0.6:
            status = "Подключение к БД..."
        elif elapsed < 0.9:
            status = "Загрузка конфигурации..."
        elif elapsed < 1.2:
            status = "Подготовка интерфейса..."
        else:
            status = "Готово!"

        if self._label and self._label.winfo_exists():
            self._label.config(text=status)

        # Проверяем завершение
        if elapsed >= self.min_duration and self.on_complete:
            self._finish()
        else:
            self._window.after(50, self._animate)

    def _finish(self) -> None:
        """Завершение загрузки."""
        if self._progress:
            self._progress.stop()
        if self._window:
            self._window.destroy()
            self._window = None
        if self.on_complete:
            self.on_complete()

    def close(self) -> None:
        """Принудительное закрытие."""
        if self._window:
            self._window.destroy()
            self._window = None


def show_splash(root: tk.Tk, on_complete: Callable[[], None], min_duration: float = 1.5) -> SplashScreen:
    """Показать splash screen и вызвать on_complete после завершения."""
    # Скрываем главное окно до завершения загрузки
    root.withdraw()

    def on_splash_complete():
        on_complete()

    return SplashScreen(root, on_complete=on_splash_complete, min_duration=min_duration)
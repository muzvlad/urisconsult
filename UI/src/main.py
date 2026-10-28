"""
Главное приложение: точка входа, главное окно, координация компонентов.
"""
from __future__ import annotations
import sys
import logging
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, List, Dict, Any

from src.config import (get_config, get_paths, center_window, get_document_config,
                        normalize_citizenship, FONT_FAMILY, format_date, format_datetime,
                        period_range, HR_STATUS_KEYS, HR_STATUS_LABELS, hr_status_style,
                        _icon_path)
from src.api_client import get_db_service as get_api_client
from src.services import get_document_service, get_telegram_service, get_pdf_service
from src.models import Worker
from src.widgets import NotificationBell, WorkerListWidget, DocumentViewer, PhotoWidget
from src.dialogs import (NotificationsWindow, RejectDialog, MeetingDialog, NoteDialog,
                         LegalEntityDialog, ask_yes_no, show_info, show_error, show_warning)
from src.logging_config import setup_logging, get_logger, log_error, log_exception, log_info, diagnostic_log


class DBViewerApp:
    """Главное приложение просмотра карточек сотрудников."""

    def __init__(self, root: tk.Tk, splash: Optional[tk.Toplevel] = None):
        self.root = root
        self.splash = splash

        self._splash_update("Получение конфигурации...")
        self.config = get_config()
        self.paths = get_paths()
        diagnostic_log(f"БД: {self.paths.db_path}")
        diagnostic_log(f"Документы: {self.paths.docs_dir}")

        self._splash_update("Инициализация сервисов...")
        self.doc_service = get_document_service()
        self.telegram = get_telegram_service()
        self.pdf_service = get_pdf_service()

        self._splash_update("Подключение к API...")
        self.api = get_api_client()
        diagnostic_log("API клиент инициализирован")

        # Состояние
        self.search_results: List[Worker] = []
        self.current_worker: Optional[Worker] = None
        self.period_preset: str = "all"

        # UI компоненты
        self.list_widget: Optional[WorkerListWidget] = None
        self.scrollable_frame: Optional[tk.Frame] = None
        self.canvas: Optional[tk.Canvas] = None
        self.status_bar: Optional[tk.Label] = None
        self.bell: Optional[NotificationBell] = None

        self._splash_update("Настройка интерфейса...")
        self._setup_ui()

        self._splash_update("Обновление колокольчика...")
        self._refresh_pending_count()
        center_window(self.root, self.config.window_width, self.config.window_height)

    def _splash_update(self, text: str = "") -> None:
        """Обновить splash screen если он есть."""
        if self.splash:
            try:
                if self.splash.winfo_exists():
                    self.splash.update()
            except Exception:
                pass
        diagnostic_log("Приложение готово!")

    def _setup_ui(self) -> None:
        """Построение интерфейса."""
        self.root.title(f"{self.config.app_title} v{self.config.app_version}")
        # Иконка окна (titlebar) — icon.ico
        try:
            ico_path = _icon_path("icon.ico")
            self.root.iconbitmap(str(ico_path))
        except Exception as e:
            diagnostic_log(f"Не удалось установить иконку окна: {e}")
        self.root.geometry(f"{self.config.window_width}x{self.config.window_height}")
        self.root.configure(bg=self.config.bg_color)
        self.root.minsize(self.config.min_window_width, self.config.min_window_height)

        # Горячие клавиши
        self._setup_keybindings()

        # Верхняя панель
        self._create_top_bar()

        # Панель поиска
        self._create_search_bar()

        # Основная область (PanedWindow)
        self._create_main_area()

    def _setup_keybindings(self) -> None:
        """Настройка горячих клавиш."""
        self.root.bind('<Escape>', lambda e: self._on_escape())
        self.root.bind('<F5>', lambda e: self._refresh_all())
        self.root.bind('<Control-f>', lambda e: self._focus_search())
        self.root.bind('<Control-r>', lambda e: self._refresh_current_list())
        # Периодическое обновление колокольчика
        self._auto_refresh_bell()

    def _auto_refresh_bell(self) -> None:
        """Автоматическое обновление колокольчика каждые 15 секунд (в фоне)."""
        def _run():
            try:
                count = self.api.get_pending_count()
            except Exception as e:
                log_error(f"Bell refresh error: {e}")
                count = 0
            # Обновить UI в главном потоке
            self.root.after(0, lambda: self.bell.set_count(count) if self.bell else None)
            # Следующая итерация
            self.root.after(15000, self._auto_refresh_bell)

        threading.Thread(target=_run, daemon=True).start()

    def _refresh_all(self) -> None:
        """Обновить всё: колокольчик + текущий список."""
        self._refresh_pending_count()
        self._refresh_current_list()

    def _on_escape(self) -> None:
        """Обработка Escape."""
        # Если фокус в поиске - очистить
        if self.search_entry.focus_get() == self.search_entry:
            self.search_entry.delete(0, tk.END)
            self.search_entry.focus_set()
        else:
            # Иначе фокус на поиск
            self.search_entry.focus_set()

    def _focus_search(self) -> None:
        """Фокус на поле поиска."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def _refresh_current_list(self) -> None:
        """Обновить текущий список с текущими фильтрами."""
        self._execute_search()

    def _create_top_bar(self) -> None:
        """Создание верхней панели с иконкой в заголовке."""
        top_frame = tk.Frame(self.root, bg=self.config.header_bg, pady=8)
        top_frame.pack(fill=tk.X, padx=0, pady=0)

        # Логотип: иконка icon.png в заголовке окна
        self._create_header_logo(top_frame)

        # Кнопка "Все анкеты"
        tk.Button(top_frame, text="Все анкеты", command=self._show_all_workers,
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=14, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        # Кнопка "Экспорт в PDF"
        tk.Button(top_frame, text="PDF", command=self._export_to_pdf,
                  bg=self.config.accent_orange, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=14, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        # Кнопка "Экспорт списка в PDF"
        tk.Button(top_frame, text="Экспорт списка в PDF", command=self._export_list_to_pdf,
                  bg=self.config.accent_orange, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=14, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        # Архив
        tk.Label(top_frame, text="Показать:", bg=self.config.header_bg, fg='white',
                 font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(10, 4))
        self.show_labels = {"Активные": "0", "Архив": "1", "Все": "all"}
        self.show_var = tk.StringVar(value="Активные")
        show_combo = ttk.Combobox(top_frame, textvariable=self.show_var,
                                  values=list(self.show_labels), state="readonly",
                                  width=10, font=(FONT_FAMILY, 10))
        show_combo.pack(side=tk.LEFT)
        show_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_current_list())

        # Колокольчик уведомлений
        bell_frame = tk.Frame(top_frame, bg=self.config.header_bg)
        bell_frame.pack(side=tk.RIGHT, padx=15)

        self.bell = NotificationBell(bell_frame, on_click=self._open_notifications,
                                     bg=self.config.header_bg)
        self.bell.pack()

    def _create_header_logo(self, parent) -> None:
        """Иконка icon.png в заголовке окна."""
        from PIL import Image, ImageTk

        icon_frame = tk.Frame(parent, bg=self.config.header_bg)
        icon_frame.pack(side=tk.LEFT, padx=15)

        self._icon_label = tk.Label(icon_frame, bg=self.config.header_bg)
        self._icon_label.pack(side=tk.LEFT)

        # Базовый размер иконки — квадрат, пропорционален высоте окна
        base_size = max(16, int(self.config.window_height * 0.05))
        base_size = min(base_size, 64)
        self._load_header_icon(base_size)

        # Адаптивный размер при изменении окна
        self.root.bind("<Configure>", self._on_resize_header_icon)
        self._last_icon_size = base_size

    def _load_header_icon(self, size: int) -> None:
        """Загрузить иконку icon.png с заданным квадратным размером."""
        from PIL import Image, ImageTk
        try:
            path = _icon_path("icon.png")
            img = Image.open(path).convert("RGBA")
            # Квадрат: обрезаем по центру если нужно, пропорция не теряется
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._icon_label.configure(image=photo)
            self._icon_label.image = photo  # hold reference
        except Exception as e:
            diagnostic_log(f"Не удалось загрузить icon.png: {e}")
            self._icon_label.configure(text="")

    def _on_resize_header_icon(self, event) -> None:
        """Пересчитать размер иконки при изменении размера окна."""
        if event.widget != self.root:
            return
        new_size = max(16, int(self.root.winfo_height() * 0.05))
        new_size = min(new_size, 64)
        if abs(self._last_icon_size - new_size) < 4:
            return
        self._last_icon_size = new_size
        self._load_header_icon(new_size)

    def _create_search_bar(self) -> None:
        """Создание панели поиска."""
        search_frame = tk.Frame(self.root, bg=self.config.bg_color, pady=8)
        search_frame.pack(fill=tk.X, padx=10)

        tk.Label(search_frame, text="Поиск:", bg=self.config.bg_color,
                 font=(FONT_FAMILY, 11)).pack(side=tk.LEFT)

        self.search_entry = tk.Entry(search_frame, font=(FONT_FAMILY, 11), width=35)
        self.search_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', lambda e: self._search_workers())

        tk.Button(search_frame, text="Найти", command=self._search_workers,
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=14, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        tk.Label(search_frame, text="Период:", bg=self.config.bg_color,
                 font=(FONT_FAMILY, 10)).pack(side=tk.LEFT, padx=(15, 0))

        self.period_labels = {
            "Все время": "all",
            "Сегодня": "today",
            "За неделю": "week",
            "За месяц": "month",
            "Прошлый месяц": "prev_month",
            "За год": "year",
            "Произвольный": "custom",
        }
        self.period_var = tk.StringVar(value="Все время")
        period_combo = ttk.Combobox(search_frame, textvariable=self.period_var,
                                    values=list(self.period_labels), state="readonly",
                                    width=16, font=(FONT_FAMILY, 10))
        period_combo.pack(side=tk.LEFT, padx=5)
        period_combo.bind("<<ComboboxSelected>>", self._on_period_change)
        self.custom_range = (None, None)

        self.custom_frame = tk.Frame(search_frame, bg=self.config.bg_color)
        tk.Label(self.custom_frame, text="с", bg=self.config.bg_color,
                 font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)
        self.date_from_entry = tk.Entry(self.custom_frame, width=11, font=(FONT_FAMILY, 9))
        self.date_from_entry.pack(side=tk.LEFT, padx=3)
        tk.Label(self.custom_frame, text="по", bg=self.config.bg_color,
                 font=(FONT_FAMILY, 9)).pack(side=tk.LEFT)
        self.date_to_entry = tk.Entry(self.custom_frame, width=11, font=(FONT_FAMILY, 9))
        self.date_to_entry.pack(side=tk.LEFT, padx=3)
        tk.Button(self.custom_frame, text="Применить", command=self._apply_custom_period,
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=8, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT, padx=3)

        tk.Button(search_frame, text="Сброс", command=self._reset_period,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=10, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

    def _create_main_area(self) -> None:
        """Создание основной области с панелями."""
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Левая панель — список
        left_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1)
        main_paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Найденные записи:",
                 font=(FONT_FAMILY, 11, 'bold')).pack(pady=5, padx=5)

        self.list_widget = WorkerListWidget(
            left_frame,
            on_select=self._on_worker_select,
            on_double_click=self._on_worker_select
        )
        self.list_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Статус-бар внизу левой панели
        self.status_bar = tk.Label(left_frame, text="", bg='#ecf0f1',
                                   font=(FONT_FAMILY, 9), anchor='w', padx=5)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Правая панель — детали
        right_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1)
        main_paned.add(right_frame, weight=1)

        # Деление пополам по умолчанию (относительно окна, не в px).
        # Разделитель можно передвигать вручную — позиция запомнится.
        self.root.after_idle(lambda mp=main_paned: self._set_sash_center(mp))
        self.root.after(150, lambda mp=main_paned: self._set_sash_center(mp))

        self._create_scrollable_detail_area(right_frame)

    def _set_sash_center(self, paned: ttk.PanedWindow) -> None:
        """Установить разделитель PanedWindow в центр окна (50/50)."""
        try:
            self.root.update_idletasks()
            width = paned.winfo_width()
            if width > 10:
                paned.sashpos(0, width // 2)
            else:
                self.root.after(100, lambda: self._set_sash_center(paned))
        except tk.TclError:
            pass

    def _create_scrollable_detail_area(self, parent: tk.Widget) -> None:
        """Создание прокручиваемой области для деталей."""
        self.canvas = tk.Canvas(parent, bg='white')
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=self.canvas.xview)

        self.scrollable_frame = tk.Frame(self.canvas, bg='white')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="inner_frame")
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        def on_canvas_configure(event):
            self.canvas.itemconfig("inner_frame", width=event.width)
        self.canvas.bind("<Configure>", on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # Скролл мышью — глобальный bind при наведении на область
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_shift_mousewheel(event):
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_scroll(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

        def _unbind_scroll(event):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Shift-MouseWheel>")

        self.canvas.bind("<Enter>", _bind_scroll)
        self.canvas.bind("<Leave>", _unbind_scroll)
        self.scrollable_frame.bind("<Enter>", _bind_scroll)
        self.scrollable_frame.bind("<Leave>", _unbind_scroll)

    # ─── Обработчики событий ───

    def _refresh_pending_count(self) -> None:
        """Обновить счетчик на колокольчике."""
        try:
            count = self.api.get_pending_count()
            if self.bell:
                self.bell.set_count(count)
        except ConnectionError as e:
            log_error(f"Pending count error: server unavailable — {e}")
            if self.bell:
                self.bell.set_count(0)
        except Exception:
            if self.bell:
                self.bell.set_count(0)

    def _open_notifications(self) -> None:
        """Открыть окно уведомлений."""
        NotificationsWindow(
            self.root,
            on_refresh=self._refresh_notifications,
            on_accept=self._accept_worker,
            on_reject=self._reject_worker,
            on_view=self._view_worker_details
        )

    def _refresh_notifications(self) -> None:
        """Обновить уведомления после действия."""
        self._refresh_pending_count()
        self._open_notifications()  # Переоткрыть с обновленными данными

    def _on_period_change(self, _event=None) -> None:
        preset = self.period_labels.get(self.period_var.get(), "all")
        if preset == "custom":
            self.custom_frame.pack(side=tk.LEFT, padx=5)
            return
        self.custom_frame.pack_forget()
        self.period_preset = preset
        self._refresh_current_list()

    def _apply_custom_period(self) -> None:
        from src.config import parse_user_date
        date_from = parse_user_date(self.date_from_entry.get())
        date_to = parse_user_date(self.date_to_entry.get())
        if not date_from or not date_to:
            show_warning(self.root, "Внимание",
                         "Укажите обе даты в формате дд.мм.гггг")
            return
        if date_from > date_to:
            show_warning(self.root, "Внимание",
                         "Дата «с» не может быть позже даты «по»")
            return
        self.custom_range = (date_from, date_to)
        self.period_preset = "custom"
        self._refresh_current_list()

    def _reset_period(self) -> None:
        self.period_preset = "all"
        self.custom_range = (None, None)
        self.period_var.set("Все время")
        self.custom_frame.pack_forget()
        self._refresh_current_list()

    def _search_workers(self) -> None:
        """Поиск сотрудников по полям анкеты."""
        query = self.search_entry.get().strip()
        if (not query and self.period_preset == "all"
                and self.show_labels.get(self.show_var.get(), "0") == "0"):
            show_warning(self.root, "Предупреждение", "Введите слово для поиска!")
            return
        self._execute_search()

    def _show_all_workers(self) -> None:
        """Показать все анкеты (фильтры периода и архива сохраняются)."""
        self.search_entry.delete(0, tk.END)
        self._execute_search()

    def _execute_search(self) -> None:
        """Выполнить поиск через API (в фоновом потоке, чтобы GUI не зависал)."""
        if not self.list_widget:
            return

        self.list_widget.tree.delete(*self.list_widget.tree.get_children())
        self.search_results = []

        def _run():
            try:
                query = self.search_entry.get().strip() or None
                if self.period_preset == "custom":
                    date_from, date_to = self.custom_range
                elif self.period_preset != "all":
                    date_from, date_to = period_range(self.period_preset)
                else:
                    date_from, date_to = None, None
                archived = self.show_labels.get(self.show_var.get(), "0")
                results = self.api.get_workers(
                    search=query, date_from=date_from, date_to=date_to, archived=archived)

                def _update():
                    self.search_results = results
                    self.list_widget.set_workers(self.search_results)
                    self.status_bar.config(
                        text=f"Найдено: {len(self.search_results)}"
                             + (" (архив)" if archived == "1" else ""))
                    log_info(f"Search executed, found {len(self.search_results)} workers")
                    if not self.search_results:
                        show_info(self.root, "Результаты", "Записи не найдены")

                self.root.after(0, _update)
            except ConnectionError as e:
                def _error():
                    log_error(f"Search error: server unavailable — {e}")
                    show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
                self.root.after(0, _error)
            except Exception as e:
                def _error():
                    log_error(f"Search error: {e}", exc_info=True)
                    show_error(self.root, "Ошибка", f"Ошибка поиска: {e}")
                self.root.after(0, _error)

        threading.Thread(target=_run, daemon=True).start()

    def _on_worker_select(self, worker: Worker) -> None:
        """Обработка выбора сотрудника в списке."""
        self.current_worker = worker
        self._display_worker_details(worker)

    def _view_worker_details(self, worker: Worker) -> None:
        """Просмотр деталей сотрудника (из уведомлений)."""
        self.current_worker = worker
        self._display_worker_details(worker)
        # Подсветить в списке
        if self.list_widget:
            self.list_widget.select_by_id(worker.id)

    def _accept_worker(self, worker: Worker) -> None:
        """Принять анкету."""
        try:
            if self.api.accept_worker(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} принята!")
                self._refresh_pending_count()
                self._refresh_current_worker()
                log_info(f"Worker {worker.id} accepted")
            else:
                show_error(self.root, "Ошибка", "Не удалось обновить статус")
        except ConnectionError as e:
            log_error(f"Accept error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error accepting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _reject_worker(self, worker: Worker) -> None:
        """Отклонить анкету — открыть диалог выбора полей."""
        log_info(f"Opening reject dialog for worker {worker.id}")
        RejectDialog(self.root, worker, lambda w, reasons: self._handle_reject(w, reasons))

    def _handle_reject(self, worker: Worker, reasons: List[Dict[str, str]]) -> None:
        """Обработка отклонения — бот отправит уведомление через 60 сек."""
        try:
            if self.api.reject_worker(worker.id, reasons):
                show_info(self.root, "Готово",
                          f"Анкета #{worker.id} отклонена.\n"
                          f"Клиент получит уведомление в Telegram.")
                self._refresh_pending_count()
                self._refresh_current_worker()
                log_info(f"Worker {worker.id} rejected with reasons: {reasons}")
            else:
                show_error(self.root, "Ошибка", "Не удалось обновить статус")
        except ConnectionError as e:
            log_error(f"Reject error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error rejecting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _edit_worker(self, worker: Worker) -> None:
        """Открыть диалог редактирования сотрудника."""
        from src.dialogs import EditDialog

        def on_save(updated: Worker):
            try:
                if self.api.update_worker(updated):
                    show_info(self.root, "Готово", f"Анкета #{updated.id} обновлена!")
                    self._refresh_current_worker()
                    self._refresh_pending_count()
                    log_info(f"Worker {updated.id} updated")
                else:
                    show_error(self.root, "Ошибка", "Не удалось обновить запись")
            except ConnectionError as e:
                show_error(self.root, "Ошибка", f"Сервер недоступен ({self.api.base_url}).\n{e}")
            except Exception as e:
                log_error(f"Error updating worker {updated.id}: {e}", exc_info=True)
                show_error(self.root, "Ошибка", f"Ошибка: {e}")

        EditDialog(self.root, worker, on_save)

    def _archive_worker(self, worker: Worker) -> None:
        """Поместить анкету в архив."""
        if not ask_yes_no(self.root, "Архив",
                          f"Убрать анкету #{worker.id} — {worker.name} в архив?"):
            return
        try:
            if self.api.archive_worker(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} в архиве.")
                self.current_worker = None
                self._refresh_current_list()
                self._refresh_pending_count()
                self._clear_details()
            else:
                show_error(self.root, "Ошибка", "Не удалось архивировать запись")
        except ConnectionError as e:
            log_error(f"Archive error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error archiving worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _unarchive_worker(self, worker: Worker) -> None:
        """Вернуть анкету из архива."""
        try:
            if self.api.unarchive_worker(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} возвращена из архива.")
                self.current_worker = None
                self._refresh_current_list()
                self._refresh_pending_count()
                self._clear_details()
            else:
                show_error(self.root, "Ошибка", "Не удалось вернуть запись из архива")
        except ConnectionError as e:
            log_error(f"Unarchive error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error unarchiving worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _edit_legal_entity(self, worker: Worker) -> None:
        """Изменить юр. лицо отдельным запросом."""
        def on_save(value: str) -> None:
            try:
                if self.api.set_legal_entity(worker.id, value):
                    log_info(f"Worker {worker.id} legal entity updated")
                    self._refresh_current_worker()
                else:
                    show_error(self.root, "Ошибка", "Не удалось сохранить юр. лицо")
            except ConnectionError as e:
                log_error(f"Legal entity error: server unavailable — {e}")
                show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
            except Exception as e:
                log_error(f"Error setting legal entity {worker.id}: {e}", exc_info=True)
                show_error(self.root, "Ошибка", f"Ошибка: {e}")

        LegalEntityDialog(self.root, worker, on_save)

    def _open_note(self, worker: Worker, note: Optional[dict] = None) -> None:
        """Добавить или изменить комментарий."""
        def on_save(text: str) -> None:
            try:
                if note:
                    ok = self.api.update_note(worker.id, note['id'], text)
                else:
                    ok = self.api.add_note(worker.id, text)
                if ok:
                    self._refresh_current_worker()
                else:
                    show_error(self.root, "Ошибка", "Комментарий не сохранён")
            except ConnectionError as e:
                log_error(f"Save note error: server unavailable — {e}")
                show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
            except Exception as e:
                log_error(f"Error saving note {worker.id}: {e}", exc_info=True)
                show_error(self.root, "Ошибка", f"Ошибка: {e}")

        NoteDialog(self.root, worker, on_save, note=note)

    def _delete_note(self, worker: Worker, note: dict) -> None:
        """Удалить комментарий с подтверждением."""
        if not ask_yes_no(self.root, "Удаление", "Удалить комментарий?"):
            return
        try:
            if self.api.delete_note(worker.id, note['id']):
                self._refresh_current_worker()
            else:
                show_error(self.root, "Ошибка", "Не удалось удалить комментарий")
        except ConnectionError as e:
            log_error(f"Delete note error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error deleting note {note.get('id')}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _clear_details(self) -> None:
        """Очистить правую панель."""
        if self.scrollable_frame:
            for w in self.scrollable_frame.winfo_children():
                w.destroy()

    def _delete_worker(self, worker: Worker) -> None:
        """Удалить сотрудника из БД и файлов."""
        from src.dialogs import ask_yes_no

        if not ask_yes_no(self.root, "Удаление",
                          f"Удалить анкету #{worker.id} — {worker.name}?\n\n"
                          f"Все документы будут удалены с диска.\n"
                          f"Это действие необратимо!"):
            return

        try:
            if self.api.delete_worker(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} удалена!")
                self.current_worker = None
                self._refresh_current_list()
                self._refresh_pending_count()
                self._clear_details()
                log_info(f"Worker {worker.id} deleted")
            else:
                show_error(self.root, "Ошибка", "Не удалось удалить запись")
        except ConnectionError as e:
            log_error(f"Delete worker error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error deleting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _replace_document(self, worker: Worker, doc: DocumentInfo) -> None:
        """Перезалить документ анкеты из UI."""
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title=f"Выберите файл для замены: {doc.label}",
            filetypes=[("Изображения и PDF", "*.jpg *.jpeg *.png *.bmp *.gif *.pdf"),
                       ("Все файлы", "*.*")]
        )
        if not file_path:
            return

        path = Path(file_path)
        try:
            if self.doc_service.replace_document(worker, doc.doc_type, doc.filename, path):
                log_info(f"Document {doc.doc_type} replaced for worker {worker.id}")
                self._refresh_current_worker()
            else:
                show_error(self.root, "Ошибка", "Не удалось заменить документ")
        except ConnectionError as e:
            log_error(f"Replace document error: server unavailable — {e}")
            show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
        except Exception as e:
            log_error(f"Error replacing document {doc.doc_type}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _refresh_current_worker(self) -> None:
        """Обновить отображение текущего сотрудника."""
        if self.current_worker:
            fresh = self.api.get_worker(self.current_worker.id)
            if fresh:
                self.current_worker = fresh
                self._display_worker_details(fresh)
                if self.list_widget:
                    self._refresh_current_list()
                    self.list_widget.select_by_id(fresh.id)

    # ─── Отображение деталей ───

    def _build_hr_block(self, parent: tk.Widget, worker: Worker) -> None:
        """Блок HR-статуса: комбобокс, плашка, дата и сохранение."""
        from src.config import parse_user_date

        block = tk.Frame(parent, bg='white')
        block.pack(anchor=tk.W, pady=(10, 0))

        # Первая строка: надпись + поля
        fields_row = tk.Frame(block, bg='white')
        fields_row.pack(side=tk.TOP, anchor=tk.W)

        label = tk.Label(fields_row, text="HR-статус:", bg='white',
                         font=(FONT_FAMILY, 10, 'bold'))
        label.pack(side=tk.LEFT)

        current_label = HR_STATUS_LABELS.get(worker.hr_status, HR_STATUS_LABELS['not_processed'])
        status_var = tk.StringVar(value=current_label)
        combo = ttk.Combobox(fields_row, textvariable=status_var, width=18, state='readonly',
                             values=[HR_STATUS_LABELS[k] for k in HR_STATUS_KEYS],
                             font=(FONT_FAMILY, 10))
        combo.pack(side=tk.LEFT, padx=(6, 6))

        key_by_label = {HR_STATUS_LABELS[k]: k for k in HR_STATUS_KEYS}
        plaque = tk.Label(fields_row, text=current_label, font=(FONT_FAMILY, 9, 'bold'),
                          width=18, padx=0, pady=2)
        plaque.pack(side=tk.LEFT, padx=(10, 0))

        date_entry = tk.Entry(fields_row, width=12, font=(FONT_FAMILY, 10), justify='center')
        date_entry.pack(side=tk.LEFT, padx=(18, 6))
        if worker.hr_status_date:
            date_entry.insert(0, format_date(worker.hr_status_date))

        def current_key() -> str:
            return key_by_label.get(status_var.get(), 'not_processed')

        def refresh_style(*_args) -> None:
            style = hr_status_style(current_key())
            plaque.config(text=style['label'], bg=style['bg'], fg=style['fg'])
            required = current_key() in ('employed', 'fired')
            date_entry.config(state='normal' if required else 'disabled')

        def save() -> None:
            key = current_key()
            date_value = ''
            if key in ('employed', 'fired'):
                date_text = date_entry.get().strip()
                if not parse_user_date(date_text):
                    show_warning(self.root, "Внимание",
                                 "Укажите дату в формате дд.мм.гггг")
                    return
                date_value = date_text
            try:
                if self.api.set_hr_status(worker.id, key, date_value):
                    log_info(f"Worker {worker.id} HR status -> {key}")
                    self._refresh_current_worker()
                else:
                    show_error(self.root, "Ошибка", "Не удалось сохранить HR-статус")
            except ConnectionError as e:
                log_error(f"HR status error: server unavailable — {e}")
                show_error(self.root, "Ошибка", "Сервер недоступен. Проверьте подключение.")
            except Exception as e:
                log_error(f"Error setting HR status {worker.id}: {e}", exc_info=True)
                show_error(self.root, "Ошибка", f"Ошибка: {e}")

        combo.bind('<<ComboboxSelected>>', refresh_style)

        # Вторая строка: кнопка «Сохранить» под надписью «HR-статус:»
        save_row = tk.Frame(block, bg='white')
        save_row.pack(side=tk.TOP, anchor=tk.W, pady=(8, 0))
        SAVE_GREEN = '#1f7a4c'  # затемнённый accent_green (#27ae60)
        tk.Button(save_row, text="Сохранить", command=save,
                  bg=SAVE_GREEN, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=14, relief=tk.SOLID, borderwidth=1, cursor='hand2').pack(side=tk.LEFT)
        refresh_style()

    def _display_worker_details(self, worker: Worker) -> None:
        """Отобразить детальную информацию о сотруднике."""
        if not self.scrollable_frame:
            return

        # Очистка
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # ── Заголовок ──
        header = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
        header.pack(fill=tk.X, padx=5, pady=5)

        left_col = tk.Frame(header, bg='white')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_col = tk.Frame(header, bg='white')
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        # Статус
        status = worker.status
        status_config = {
            'pending': ('⏳ Ожидает', self.config.status_colors['pending']),
            'accepted': ('✅ Принята', self.config.status_colors['accepted']),
            'rejected': ('❌ Отклонена', self.config.status_colors['rejected']),
        }
        status_text, status_color = status_config.get(status, ('?', '#999'))
        status_text = f"Статус бота: {status_text}"

        tk.Label(left_col, text=f"ФИО: {worker.name}",
                 font=(FONT_FAMILY, 14, 'bold'), bg='white', anchor='w').pack(anchor=tk.W, fill=tk.X)

        tk.Label(left_col, text=status_text,
                 font=(FONT_FAMILY, 11, 'bold'), bg='white', fg=status_color).pack(anchor=tk.W, pady=(2, 0))

        # Кнопки управления
        btn_frame = tk.Frame(left_col, bg='white')
        btn_frame.pack(anchor=tk.W, pady=(8, 0))

        tk.Button(btn_frame, text="✏️ Редактировать",
                  command=lambda: self._edit_worker(worker),
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=12, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        if worker.is_archived:
            tk.Button(btn_frame, text="Вернуть из архива",
                      command=lambda: self._unarchive_worker(worker),
                      bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                      padx=12, relief=tk.FLAT, cursor='hand2'
                      ).pack(side=tk.LEFT, padx=(0, 5))
        else:
            tk.Button(btn_frame, text="В архив",
                      command=lambda: self._archive_worker(worker),
                      bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                      padx=12, relief=tk.FLAT, cursor='hand2'
                      ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🗑 Удалить",
                  command=lambda: self._delete_worker(worker),
                  bg=self.config.accent_red, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=12, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT)

        self._build_hr_block(left_col, worker)

        if worker.is_archived:
            tk.Label(left_col, text="Анкета в архиве", bg='#F3F4F6', fg='#6B7280',
                     font=(FONT_FAMILY, 10, 'bold'), padx=10, pady=4).pack(
                anchor=tk.W, pady=(8, 0))

        # Даты
        dates_frame = tk.Frame(left_col, bg='white')
        dates_frame.pack(anchor=tk.W, pady=(8, 0))
        for field, label in (('created_at', 'Дата заведения'), ('updated_at', 'Последнее редактирование')):
            raw = getattr(worker, field, '') or ''
            dt = format_datetime(raw) if raw else '—'
            tk.Label(dates_frame, text=f"{label}: {dt}",
                     font=(FONT_FAMILY, 9), bg='white', fg='#666').pack(anchor=tk.W)

        if worker.archived_at:
            tk.Label(dates_frame, text=f"В архиве с: {format_datetime(worker.archived_at)}",
                     font=(FONT_FAMILY, 9), bg='white', fg='#999').pack(anchor=tk.W)

        tk.Label(right_col, text=f"ИД: {worker.id}",
                 font=(FONT_FAMILY, 12), bg='white').pack(anchor=tk.NE)

        # Фото
        photo_frame = tk.Frame(right_col, bg='white', relief=tk.SOLID, borderwidth=2)
        photo_frame.pack(anchor=tk.NE, pady=(5, 0))
        PhotoWidget(photo_frame, worker.id, self.doc_service.open_file).pack()

        # ── Личная информация ──
        info_frame = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        info_inner = tk.Frame(info_frame, bg='white')
        info_inner.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('citizenship', 'Категория'),
            ('gender', 'Пол'),
            ('date', 'Дата рождения'),
            ('manager', 'Менеджер'),
            ('object', 'Объект'),
            ('customer', 'Заказчик'),
            ('legal_entity', 'Юр. лицо'),
            ('object_address', 'Адрес объекта'),
            ('position', 'Должность'),
            ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'),
            ('marital_status', 'Семейное положение'),
        ]

        for field_key, field_label in fields:
            if field_key == 'legal_entity':
                continue
            value = getattr(worker, field_key, '')
            if value:
                display = str(value)
                if len(display) > 60:
                    display = display[:57] + "..."
                tk.Label(info_inner, text=f"{field_label}: {display}",
                         font=(FONT_FAMILY, 11), bg='white', anchor='w',
                         wraplength=500, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=2)

        legal_row = tk.Frame(info_inner, bg='white')
        legal_row.pack(anchor=tk.W, fill=tk.X, pady=2)
        tk.Label(legal_row, text=f"Юр. лицо: {worker.legal_entity or '—'}",
                 font=(FONT_FAMILY, 11), bg='white', anchor='w',
                 wraplength=500, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(legal_row, text="Изменить",
                  command=lambda: self._edit_legal_entity(worker),
                  bg='white', fg=self.config.accent_blue, font=(FONT_FAMILY, 9),
                  relief=tk.FLAT, cursor='hand2').pack(side=tk.RIGHT)

        # Родственники
        relatives = getattr(worker, 'relatives', None) or []
        if relatives:
            rel_text = "Родственники:\n"
            for i, rel in enumerate(relatives, 1):
                if isinstance(rel, dict):
                    name = rel.get('name', '')
                    year = rel.get('birth_year', '')
                    phone = rel.get('phone', '')
                    rel_text += f"  {i}. {name}, {year}, {phone}\n"
            tk.Label(info_inner, text=rel_text.strip(),
                     font=(FONT_FAMILY, 10), bg='white', anchor='w',
                     wraplength=500, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=2)

        # ── Встречи ──
        meetings = self.api.get_meetings(worker.id)
        meetings_frame = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
        meetings_frame.pack(fill=tk.X, padx=5, pady=5)

        header_row = tk.Frame(meetings_frame, bg='white')
        header_row.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(header_row, text="Встречи:",
                 font=(FONT_FAMILY, 13, 'bold'), bg='white', anchor='w').pack(side=tk.LEFT)

        def _open_meeting_dialog():
            from src.dialogs import MeetingDialog
            MeetingDialog(self.root, worker, lambda: self._refresh_current_worker())
        tk.Button(header_row, text="+ Добавить встречу", command=_open_meeting_dialog,
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=12, pady=2, relief=tk.FLAT, cursor='hand2').pack(side=tk.RIGHT)

        if meetings:
            for m in meetings:
                date = format_datetime(m.get('date', ''))
                note = m.get('note', '')
                text = f"• {date} — {note}" if date else f"• {note}"
                tk.Label(meetings_frame, text=text, font=(FONT_FAMILY, 10),
                         bg='white', anchor='w', wraplength=700).pack(anchor=tk.W, padx=20, pady=1)
        else:
            tk.Label(meetings_frame, text="Нет встреч",
                     font=(FONT_FAMILY, 10), bg='white', fg='#999').pack(anchor=tk.W, padx=20, pady=5)

        # ── Комментарии ──
        notes_frame = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
        notes_frame.pack(fill=tk.X, padx=5, pady=5)
        notes_header = tk.Frame(notes_frame, bg='white')
        notes_header.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(notes_header, text="Комментарии:", font=(FONT_FAMILY, 13, 'bold'),
                 bg='white', anchor='w').pack(side=tk.LEFT)
        tk.Button(notes_header, text="+ Добавить комментарий",
                  command=lambda: self._open_note(worker),
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 9, 'bold'),
                  padx=12, pady=2, relief=tk.FLAT, cursor='hand2').pack(side=tk.RIGHT)
        try:
            notes = self.api.get_notes(worker.id)
        except Exception:
            notes = []
        if notes:
            for note in notes:
                row = tk.Frame(notes_frame, bg='white')
                row.pack(fill=tk.X, padx=20, pady=2)
                tk.Label(row, text=note.get('text', ''), font=(FONT_FAMILY, 10),
                         bg='white', anchor='w', justify=tk.LEFT,
                         wraplength=600).pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Button(row, text="Удалить",
                          command=lambda n=note: self._delete_note(worker, n),
                          bg='white', fg=self.config.accent_red,
                          font=(FONT_FAMILY, 9), relief=tk.FLAT,
                          cursor='hand2').pack(side=tk.RIGHT, padx=4)
                tk.Button(row, text="Изменить",
                          command=lambda n=note: self._open_note(worker, n),
                          bg='white', fg=self.config.accent_blue,
                          font=(FONT_FAMILY, 9), relief=tk.FLAT,
                          cursor='hand2').pack(side=tk.RIGHT, padx=4)
                tk.Label(row, text=format_datetime(note.get('created_at', '')),
                         font=(FONT_FAMILY, 8), bg='white', fg='#999'
                         ).pack(side=tk.RIGHT, padx=4)
        else:
            tk.Label(notes_frame, text="Нет комментариев", font=(FONT_FAMILY, 10),
                     bg='white', fg='#999').pack(anchor=tk.W, padx=20, pady=5)

        # ── Документы ──
        try:
            db_docs = self.api.get_documents(worker.id)
            citizenship = worker.citizenship

            from src.services import DocumentInfo
            from src.logging_config import diagnostic_log

            existing_docs = []
            missing_docs: list[tuple[str, str, str, str]] = []
            for doc_type, entries in db_docs.items():
                if isinstance(entries, str):
                    entries = [{'filename': entries, 'created_at': ''}]
                elif isinstance(entries, dict):
                    entries = [entries]
                if not entries or doc_type == 'photo':
                    continue
                label = self.doc_service.get_document_label(doc_type)
                for i, entry in enumerate(entries, 1):
                    filename = entry.get('filename', '') if isinstance(entry, dict) else str(entry)
                    uploaded_at = entry.get('created_at', '') if isinstance(entry, dict) else ''
                    full_path = self.api.download_file(worker.id, filename)
                    if full_path and full_path.exists() and full_path.stat().st_size > 0:
                        existing_docs.append(DocumentInfo(
                            doc_type=doc_type,
                            label=label + (f" ({i})" if len(entries) > 1 else ""),
                            prefix='', filename=filename,
                            exists=True, full_path=full_path,
                            uploaded_at=uploaded_at,
                        ))
                    else:
                        if not full_path:
                            reason = 'not_found_on_server'
                        elif not full_path.exists():
                            reason = 'cache_file_deleted'
                        else:
                            reason = 'empty_file_in_cache'
                        diagnostic_log(f"docs missing: worker={worker.id} type={doc_type} file={filename} reason={reason}")
                        missing_docs.append((doc_type, label, filename, reason))

            if existing_docs or missing_docs:
                # Порядок документов — из конфига бота (как в анкете), а не из БД
                flows, _, _ = get_document_config()
                normalized = normalize_citizenship(citizenship)
                flow_keys = [d.key for d in flows.get(normalized, flows.get('Патент', []))]
                order = {k: i for i, k in enumerate(flow_keys)}
                existing_docs.sort(key=lambda d: order.get(d.doc_type, 9999))
                missing_docs.sort(key=lambda m: order.get(m[0], 9999))

            if existing_docs:
                docs_header = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
                docs_header.pack(fill=tk.X, padx=5, pady=5)

                tk.Label(docs_header, text=f"Документы ({citizenship}):",
                         font=(FONT_FAMILY, 13, 'bold'), bg='white', anchor='w').pack(anchor=tk.W, padx=10, pady=(10, 5))

                for doc in existing_docs:
                    DocumentViewer(
                        self.scrollable_frame, doc,
                        self.doc_service.open_file,
                        on_replace=lambda d=doc: self._replace_document(worker, d),
                    ).pack(fill=tk.X, padx=5, pady=3)

            if missing_docs:
                miss_frame = tk.Frame(self.scrollable_frame, bg='#fff3cd', relief=tk.RAISED, borderwidth=1)
                miss_frame.pack(fill=tk.X, padx=5, pady=5)
                tk.Label(miss_frame, text=f"Не загружено ({len(missing_docs)}):",
                         font=(FONT_FAMILY, 11, 'bold'), bg='#fff3cd', anchor='w'
                         ).pack(anchor=tk.W, padx=10, pady=(8, 3))
                for doc_type, label, filename, reason in missing_docs:
                    tk.Label(miss_frame,
                             text=f"  • {label} — {reason} (файл: {filename})",
                             font=(FONT_FAMILY, 9), bg='#fff3cd', fg='#856404', anchor='w'
                             ).pack(anchor=tk.W, padx=20, pady=1)
        except Exception as e:
            import traceback
            print(f"DOCS ERROR: {e}")
            traceback.print_exc()
            tk.Label(self.scrollable_frame, text=f"Ошибка загрузки документов: {e}",
                     font=(FONT_FAMILY, 10), bg='white', fg='red').pack(anchor=tk.W, padx=10, pady=5)

        # ── Замечания (если отклонена) ──
        if worker.is_rejected and worker.reasons:
            rej_frame = tk.Frame(self.scrollable_frame, bg='#ffeaa7', relief=tk.RAISED, borderwidth=1)
            rej_frame.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(rej_frame, text="⚠ Замечания:",
                     font=(FONT_FAMILY, 12, 'bold'), bg='#ffeaa7', anchor='w').pack(anchor=tk.W, padx=10, pady=(8, 3))

            for r in worker.reasons:
                rkey = r.get('key', '') if isinstance(r, dict) else str(r)
                rcomment = r.get('comment', '') if isinstance(r, dict) else ''
                label = self.doc_service.get_document_label(rkey)
                if rkey == 'customer':
                    label = 'Заказчик'
                tk.Label(rej_frame, text=f"  • {label}",
                         font=(FONT_FAMILY, 10), bg='#ffeaa7', anchor='w').pack(anchor=tk.W, padx=20)
                if rcomment:
                    tk.Label(rej_frame, text=f"    📝 {rcomment}",
                             font=(FONT_FAMILY, 9), bg='#ffeaa7', fg='#7d6608', anchor='w'
                             ).pack(anchor=tk.W, padx=35)

        # Обновление scrollregion
        self._update_scroll_region()

    def _update_scroll_region(self) -> None:
        """Принудительное обновление области прокрутки."""
        try:
            if self.canvas:
                self.canvas.update_idletasks()
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    # ─── Экспорт в PDF ───

    def _export_to_pdf(self) -> None:
        """Экспорт выбранных карточек в PDF (каждая на отдельной странице).
        Если ничего не выделено — экспортирует текущую анкету."""
        workers = self.list_widget.get_selected_workers()
        if not workers:
            if self.current_worker:
                workers = [self.current_worker]
            else:
                show_warning(self.root, "Предупреждение", "Сначала выберите запись в списке!")
                return

        period_label = self._period_label()
        msg = (
            f"Будет произведена выгрузка за период «{period_label}».\n"
            f"Анкет для выгрузки: {len(workers)}.\n"
            f"Вы хотите сделать выгрузку?"
        )
        if not ask_yes_no(self.root, "Выгрузка в PDF", msg):
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Сохранить карточки в PDF"
            )
            if not filename:
                return

            log_info(f"Exporting {len(workers)} workers to PDF cards: {filename}")
            success, msg = self.pdf_service.export_cards(workers, filename, period_label=period_label)
            if success:
                show_info(self.root, "Успех", msg)
                log_info(f"PDF cards export successful: {filename}")
            else:
                show_error(self.root, "Ошибка", msg)
                log_error(f"PDF cards export failed: {msg}")
        except Exception as e:
            log_error(f"PDF cards export error: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка экспорта: {e}")

    # ─── Экспорт списка в PDF ───

    def _period_label(self) -> str:
        """Человекочитаемая метка текущего периода для диалога выгрузки."""
        preset = self.period_labels.get(self.period_var.get(), "all")
        if preset == "all":
            return "За все время"
        if preset == "custom" and self.custom_range and self.custom_range[0] and self.custom_range[1]:
            d_from, d_to = self.custom_range
            return f"За {d_from} — {d_to}"
        # Обратный перевод пресета в метку (по значению -> ключу)
        for label, value in self.period_labels.items():
            if value == preset:
                return label
        return "За все время"

    def _export_list_to_pdf(self) -> None:
        """Экспорт текущего отфильтрованного списка анкет в PDF."""
        if not self.search_results:
            show_warning(self.root, "Предупреждение", "Нет данных для выгрузки!")
            return

        period_label = self._period_label()
        msg = (
            f"Будет произведена выгрузка за период «{period_label}».\n"
            f"Найдено анкет: {len(self.search_results)}.\n"
            f"Вы хотите сделать выгрузку?"
        )
        if not ask_yes_no(self.root, "Выгрузка в PDF", msg):
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Сохранить список в PDF"
            )
            if not filename:
                return

            log_info(f"Exporting {len(self.search_results)} workers to PDF: {filename}")
            success, msg = self.pdf_service.export_list(
                self.search_results, filename, period_label=period_label
            )
            if success:
                show_info(self.root, "Успех", msg)
                log_info(f"PDF list export successful: {filename}")
            else:
                show_error(self.root, "Ошибка", msg)
                log_error(f"PDF list export failed: {msg}")
        except Exception as e:
            log_error(f"PDF list export error: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка экспорта: {e}")


def main(root=None, splash=None) -> None:
    """Точка входа приложения.

    Args:
        root: Корневое окно tk.Tk() (создаётся в db_viewer.py)
        splash: Splash window (Toplevel) для закрытия после загрузки
    """
    diagnostic_log("main() вызван")
    setup_logging(level=logging.INFO)
    diagnostic_log("Логирование настроено")

    own_root = root is None
    try:
        if own_root:
            diagnostic_log("Создание окна tk.Tk...")
            root = tk.Tk()
            diagnostic_log("Окно создано")

        # Обновляем splash если он есть
        if splash:
            try:
                splash.update()
            except Exception:
                pass

        diagnostic_log("Инициализация приложения...")
        app = DBViewerApp(root, splash=splash)
        diagnostic_log("Приложение инициализировано")

        # Закрываем splash — приложение готово
        if splash:
            try:
                splash.destroy()
            except Exception:
                pass

        root.deiconify()
        root.lift()
        root.focus_force()
        diagnostic_log("Окно поднято на передний план")

        diagnostic_log("Запуск mainloop...")
        root.mainloop()
        diagnostic_log("Mainloop завершён")

    except Exception as e:
        diagnostic_log(f"ОШИБКА: {e}")
        log_exception("Аварийное завершение приложения")
        # Закрываем splash при ошибке
        if splash:
            try:
                splash.destroy()
            except Exception:
                pass
        if own_root:
            try:
                root.destroy()
            except Exception:
                pass
        msg = f"Ошибка запуска:\n{e}"
        try:
            err_root = tk.Tk()
            err_root.withdraw()
            messagebox.showerror("Ошибка", msg)
            err_root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    import logging
    main()
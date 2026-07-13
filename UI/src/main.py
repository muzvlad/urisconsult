"""
Главное приложение: точка входа, главное окно, координация компонентов.
"""
from __future__ import annotations
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, List, Dict, Any

from src.config import get_config, get_paths, center_window
from src.database import get_db_service, DatabaseConnection, init_db
from src.services import get_document_service, get_telegram_service, get_pdf_service
from src.models import Worker
from src.widgets import NotificationBell, WorkerListWidget, DocumentViewer, PhotoWidget
from src.dialogs import NotificationsWindow, RejectDialog, ask_yes_no, show_info, show_error, show_warning
from src.logging_config import setup_logging, get_logger, log_error, log_exception, log_info


class DBViewerApp:
    """Главное приложение просмотра карточек сотрудников."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = get_config()
        self.paths = get_paths()
        self.doc_service = get_document_service()
        self.telegram = get_telegram_service()
        self.pdf_service = get_pdf_service()
        self.db = get_db_service()

        # Состояние
        self.search_results: List[Worker] = []
        self.current_worker: Optional[Worker] = None

        # UI компоненты
        self.list_widget: Optional[WorkerListWidget] = None
        self.scrollable_frame: Optional[tk.Frame] = None
        self.canvas: Optional[tk.Canvas] = None
        self.status_bar: Optional[tk.Label] = None
        self.bell: Optional[NotificationBell] = None

        self._init_db()
        self._setup_ui()
        self._refresh_pending_count()
        center_window(self.root, self.config.window_width, self.config.window_height)

    def _init_db(self) -> None:
        """Инициализация БД."""
        try:
            init_db(self.paths.db_path)
            get_logger().info("Database initialized successfully")
        except Exception as e:
            log_error(f"Failed to initialize database: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Не удалось инициализировать БД:\n{e}")
            raise

    def _setup_ui(self) -> None:
        """Построение интерфейса."""
        self.root.title(self.config.app_title)
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
        """Автоматическое обновление колокольчика каждые 15 секунд."""
        self._refresh_pending_count()
        self.root.after(15000, self._auto_refresh_bell)

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
        """Обновить текущий список (повторить последний поиск)."""
        if hasattr(self, '_last_search_params'):
            self._execute_search(*self._last_search_params)
        else:
            self._show_all_workers()

    def _create_top_bar(self) -> None:
        """Создание верхней панели."""
        top_frame = tk.Frame(self.root, bg=self.config.header_bg, pady=8)
        top_frame.pack(fill=tk.X, padx=0, pady=0)

        # Логотип
        tk.Label(top_frame, text="URIS Consult",
                 font=('Arial', 16, 'bold'), bg=self.config.header_bg, fg=self.config.header_fg
                 ).pack(side=tk.LEFT, padx=15)

        # Кнопка "Все анкеты"
        tk.Button(top_frame, text="Все анкеты", command=self._show_all_workers,
                  bg=self.config.accent_blue, fg='white', font=('Arial', 10),
                  padx=12, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        # Кнопка "Экспорт в PDF"
        tk.Button(top_frame, text="PDF", command=self._export_to_pdf,
                  bg=self.config.accent_orange, fg='white', font=('Arial', 10),
                  padx=12, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

        # Колокольчик уведомлений
        bell_frame = tk.Frame(top_frame, bg=self.config.header_bg)
        bell_frame.pack(side=tk.RIGHT, padx=15)

        self.bell = NotificationBell(bell_frame, on_click=self._open_notifications,
                                     bg=self.config.header_bg)
        self.bell.pack()

    def _create_search_bar(self) -> None:
        """Создание панели поиска."""
        search_frame = tk.Frame(self.root, bg=self.config.bg_color, pady=8)
        search_frame.pack(fill=tk.X, padx=10)

        tk.Label(search_frame, text="Поиск:", bg=self.config.bg_color,
                 font=('Arial', 11)).pack(side=tk.LEFT)

        self.search_entry = tk.Entry(search_frame, font=('Arial', 11), width=35)
        self.search_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', lambda e: self._search_workers())

        tk.Button(search_frame, text="Найти", command=self._search_workers,
                  bg=self.config.accent_blue, fg='white', font=('Arial', 10),
                  padx=10, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=5)

    def _create_main_area(self) -> None:
        """Создание основной области с панелями."""
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Левая панель — список
        left_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1, width=300)
        left_frame.pack_propagate(False)
        main_paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Найденные записи:",
                 font=('Arial', 11, 'bold')).pack(pady=5, padx=5)

        self.list_widget = WorkerListWidget(
            left_frame,
            on_select=self._on_worker_select,
            on_double_click=self._on_worker_select
        )
        self.list_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Статус-бар внизу левой панели
        self.status_bar = tk.Label(left_frame, text="", bg='#ecf0f1',
                                   font=('Arial', 9), anchor='w', padx=5)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Правая панель — детали
        right_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1)
        main_paned.add(right_frame, weight=10)

        self._create_scrollable_detail_area(right_frame)

    def _create_scrollable_detail_area(self, parent: tk.Widget) -> None:
        """Создание прокручиваемой области для деталей."""
        self.canvas = tk.Canvas(parent, bg='white')
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=self.canvas.xview)

        self.scrollable_frame = tk.Frame(self.canvas, bg='white', width=900)

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

        # Скролл мышью
        self.canvas.bind("<MouseWheel>",
                         lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind("<Shift-MouseWheel>",
                         lambda e: self.canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ─── Обработчики событий ───

    def _refresh_pending_count(self) -> None:
        """Обновить счетчик на колокольчике."""
        try:
            count = self.db.workers.count_pending()
            if self.bell:
                self.bell.set_count(count)
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

    def _search_workers(self) -> None:
        """Поиск сотрудников по ФИО."""
        query = self.search_entry.get().strip()
        if not query:
            show_warning(self.root, "Предупреждение", "Введите слово для поиска!")
            return

        self._last_search_params = ("name LIKE ?", (f"%{query}%",))
        self._execute_search("name LIKE ?", (f"%{query}%",))

    def _show_all_workers(self) -> None:
        """Показать все анкеты."""
        self._last_search_params = ("1=1", ())
        self._execute_search("1=1", ())

    def _execute_search(self, where_clause: str, params: tuple) -> None:
        """Выполнить поиск в БД."""
        if not self.list_widget:
            return

        self.list_widget.listbox.delete(0, tk.END)
        self.search_results = []

        try:
            sql = f"SELECT * FROM workers WHERE {where_clause} ORDER BY id"
            rows = self.db.db.fetchall(sql, params)

            for row in rows:
                worker = Worker.from_row(row)
                self.search_results.append(worker)

            self.list_widget.set_workers(self.search_results)
            self.status_bar.config(text=f"Найдено: {len(self.search_results)}")
            log_info(f"Search executed, found {len(self.search_results)} workers")

            if not self.search_results:
                show_info(self.root, "Результаты", "Записи не найдены")
        except Exception as e:
            log_error(f"Search error: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка поиска: {e}")

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
            if self.db.workers.accept(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} принята!")
                self._refresh_pending_count()
                self._refresh_current_worker()
                log_info(f"Worker {worker.id} accepted")
            else:
                show_error(self.root, "Ошибка", "Не удалось обновить статус")
        except Exception as e:
            log_error(f"Error accepting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _reject_worker(self, worker: Worker) -> None:
        """Отклонить анкету — открыть диалог выбора полей."""
        log_info(f"Opening reject dialog for worker {worker.id}")
        RejectDialog(self.root, worker, lambda w, reasons: self._handle_reject(w, reasons))

    def _handle_reject(self, worker: Worker, reasons: List[str]) -> None:
        """Обработка отклонения — бот отправит уведомление через 60 сек."""
        try:
            if self.db.workers.reject(worker.id, reasons):
                show_info(self.root, "Готово",
                          f"Анкета #{worker.id} отклонена.\n"
                          f"Клиент получит уведомление в Telegram.")
                self._refresh_pending_count()
                self._refresh_current_worker()
                log_info(f"Worker {worker.id} rejected with reasons: {reasons}")
            else:
                show_error(self.root, "Ошибка", "Не удалось обновить статус")
        except Exception as e:
            log_error(f"Error rejecting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _edit_worker(self, worker: Worker) -> None:
        """Открыть диалог редактирования сотрудника."""
        from src.dialogs import EditDialog

        def on_save(updated: Worker):
            try:
                if self.db.workers.update(updated):
                    show_info(self.root, "Готово", f"Анкета #{updated.id} обновлена!")
                    self._refresh_current_worker()
                    self._refresh_pending_count()
                    log_info(f"Worker {updated.id} updated")
                else:
                    show_error(self.root, "Ошибка", "Не удалось обновить запись")
            except Exception as e:
                log_error(f"Error updating worker {updated.id}: {e}", exc_info=True)
                show_error(self.root, "Ошибка", f"Ошибка: {e}")

        EditDialog(self.root, worker, on_save)

    def _delete_worker(self, worker: Worker) -> None:
        """Удалить сотрудника из БД и файлов."""
        from src.dialogs import ask_yes_no

        if not ask_yes_no(self.root, "Удаление",
                          f"Удалить анкету #{worker.id} — {worker.name}?\n\n"
                          f"Все документы будут удалены с диска.\n"
                          f"Это действие необратимо!"):
            return

        try:
            if self.db.workers.delete_worker(worker.id):
                show_info(self.root, "Готово", f"Анкета #{worker.id} удалена!")
                self.current_worker = None
                self._refresh_current_list()
                self._refresh_pending_count()
                # Очистить панель деталей
                if self.scrollable_frame:
                    for w in self.scrollable_frame.winfo_children():
                        w.destroy()
                log_info(f"Worker {worker.id} deleted")
            else:
                show_error(self.root, "Ошибка", "Не удалось удалить запись")
        except Exception as e:
            log_error(f"Error deleting worker {worker.id}: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка: {e}")

    def _refresh_current_worker(self) -> None:
        """Обновить отображение текущего сотрудника."""
        if self.current_worker:
            fresh = self.db.workers.get_by_id(self.current_worker.id)
            if fresh:
                self.current_worker = fresh
                self._display_worker_details(fresh)
                if self.list_widget:
                    self.list_widget.select_by_id(fresh.id)

    # ─── Отображение деталей ───

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

        tk.Label(left_col, text=f"ФИО: {worker.name}",
                 font=('Arial', 14, 'bold'), bg='white', anchor='w').pack(anchor=tk.W, fill=tk.X)

        tk.Label(left_col, text=status_text,
                 font=('Arial', 11, 'bold'), bg='white', fg=status_color).pack(anchor=tk.W, pady=(2, 0))

        # Кнопки управления
        btn_frame = tk.Frame(left_col, bg='white')
        btn_frame.pack(anchor=tk.W, pady=(8, 0))

        tk.Button(btn_frame, text="✏️ Редактировать",
                  command=lambda: self._edit_worker(worker),
                  bg=self.config.accent_blue, fg='white', font=('Arial', 9),
                  padx=10, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🗑 Удалить",
                  command=lambda: self._delete_worker(worker),
                  bg=self.config.accent_red, fg='white', font=('Arial', 9),
                  padx=10, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT)

        tk.Label(right_col, text=f"ИД: {worker.id}",
                 font=('Arial', 12), bg='white').pack(anchor=tk.NE)

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
            ('citizenship', 'Гражданство'),
            ('gender', 'Пол'),
            ('position', 'Должность'),
            ('object', 'Объект'),
            ('object_address', 'Адрес объекта'),
            ('manager', 'Менеджер'),
            ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'),
            ('email', 'Электронная почта'),
            ('date', 'Дата рождения'),
            ('registration', 'Регистрация'),
            ('marital_status', 'Семейное положение'),
        ]

        for field_key, field_label in fields:
            value = getattr(worker, field_key, '')
            if value:
                display = str(value)
                if len(display) > 60:
                    display = display[:57] + "..."
                tk.Label(info_inner, text=f"{field_label}: {display}",
                         font=('Arial', 11), bg='white', anchor='w',
                         wraplength=500, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=2)

        # Родственники
        try:
            relatives = getattr(worker, 'relatives_json', '[]')
            if isinstance(relatives, str):
                try:
                    import json
                    relatives = json.loads(relatives)
                except (json.JSONDecodeError, TypeError):
                    relatives = []
            if relatives:
                rel_text = "Родственники:\n"
                for i, rel in enumerate(relatives, 1):
                    if isinstance(rel, dict):
                        name = rel.get('name', '')
                        year = rel.get('birth_year', '')
                        phone = rel.get('phone', '')
                        rel_text += f"  {i}. {name}, {year}, {phone}\n"
                tk.Label(info_inner, text=rel_text.strip(),
                         font=('Arial', 10), bg='white', anchor='w',
                         wraplength=500, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=2)
            else:
                print(f"RELS DEBUG: worker={worker.id} relatives_json={worker.relatives_json!r} parsed={relatives!r}")
        except Exception as e:
            print(f"RELS ERROR: {e}")

        # ── Документы ──
        try:
            db_docs = self.db.documents.get_by_worker(worker.id)
            citizenship = worker.citizenship
            print(f"DOCS DEBUG: worker={worker.id} db_docs={db_docs}")

            # Показываем все документы из БД у которых есть файл
            from src.services import DocumentInfo
            existing_docs = []
            for doc_type, filename in db_docs.items():
                if not filename:
                    continue
                worker_dir = self.doc_service.paths.docs_dir / worker.id
                full_path = worker_dir / filename if worker_dir.exists() else None
                exists = full_path.exists() if full_path else False
                print(f"  {doc_type}: filename={filename} worker_dir={worker_dir} exists={exists}")
                if full_path and full_path.exists():
                    label = self.doc_service.get_document_label(doc_type)
                    existing_docs.append(DocumentInfo(
                        doc_type=doc_type, label=label,
                        prefix='', filename=filename,
                        exists=True, full_path=full_path,
                    ))

            print(f"DOCS DEBUG: existing_docs count={len(existing_docs)}")
            if existing_docs:
                docs_header = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
                docs_header.pack(fill=tk.X, padx=5, pady=5)

                tk.Label(docs_header, text=f"Документы ({citizenship}):",
                         font=('Arial', 13, 'bold'), bg='white', anchor='w').pack(anchor=tk.W, padx=10, pady=(10, 5))

                for doc in existing_docs:
                    DocumentViewer(self.scrollable_frame, doc, self.doc_service.open_file).pack(
                        fill=tk.X, padx=5, pady=3
                    )
        except Exception as e:
            import traceback
            print(f"DOCS ERROR: {e}")
            traceback.print_exc()
            tk.Label(self.scrollable_frame, text=f"Ошибка загрузки документов: {e}",
                     font=('Arial', 10), bg='white', fg='red').pack(anchor=tk.W, padx=10, pady=5)

        # ── Замечания (если отклонена) ──
        if worker.is_rejected and worker.reasons:
            rej_frame = tk.Frame(self.scrollable_frame, bg='#ffeaa7', relief=tk.RAISED, borderwidth=1)
            rej_frame.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(rej_frame, text="⚠ Замечания:",
                     font=('Arial', 12, 'bold'), bg='#ffeaa7', anchor='w').pack(anchor=tk.W, padx=10, pady=(8, 3))

            for r in worker.reasons:
                label = self.doc_service.get_document_label(r)
                tk.Label(rej_frame, text=f"  • {label}",
                         font=('Arial', 10), bg='#ffeaa7', anchor='w').pack(anchor=tk.W, padx=20)

        # ── Встречи ──
        meetings = self.db.meetings.get_by_worker(worker.id)
        if meetings:
            meetings_frame = tk.Frame(self.scrollable_frame, bg='white', relief=tk.RAISED, borderwidth=1)
            meetings_frame.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(meetings_frame, text="Встречи:",
                     font=('Arial', 13, 'bold'), bg='white', anchor='w').pack(anchor=tk.W, padx=10, pady=(10, 5))

            for m in meetings:
                date = m.get('date', '')
                note = m.get('note', '')
                text = f"• {date} — {note}" if date else f"• {note}"
                tk.Label(meetings_frame, text=text, font=('Arial', 10),
                         bg='white', anchor='w', wraplength=700).pack(anchor=tk.W, padx=20, pady=1)

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
        """Экспорт текущей карточки в PDF."""
        if not self.current_worker:
            show_warning(self.root, "Предупреждение", "Сначала выберите запись!")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Сохранить как PDF"
            )
            if filename:
                log_info(f"Exporting worker {self.current_worker.id} to PDF: {filename}")
                success, msg = self.pdf_service.export(self.current_worker, filename)
                if success:
                    show_info(self.root, "Успех", msg)
                    log_info(f"PDF export successful: {filename}")
                else:
                    show_error(self.root, "Ошибка", msg)
                    log_error(f"PDF export failed: {msg}")
        except Exception as e:
            log_error(f"PDF export error: {e}", exc_info=True)
            show_error(self.root, "Ошибка", f"Ошибка экспорта: {e}")


def main() -> None:
    """Точка входа приложения."""
    setup_logging(level=logging.INFO)
    logger = get_logger()

    try:
        root = tk.Tk()
        app = DBViewerApp(root)
        logger.info("Application started")
        root.mainloop()
        logger.info("Application closed normally")

    except Exception as e:
        log_exception("Application crashed")
        msg = f"Ошибка запуска:\n{e}"
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ошибка", msg)
            root.destroy()
        except Exception:
            pass
        if not sys.flags.interactive:
            input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    import logging
    main()
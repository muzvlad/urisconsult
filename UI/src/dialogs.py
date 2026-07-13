"""
Диалоговые окна: отклонение, уведомления, подтверждения.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, List, Dict, Any
from pathlib import Path

from src.config import get_config, get_paths, get_document_config
from src.models import Worker
from src.services import get_telegram_service
from src.database import get_db_service
from src.logging_config import get_logger, log_error, log_exception


# ─── Диалог отклонения анкеты ───

class RejectDialog:
    """Диалог выбора полей для отклонения."""

    def __init__(self, parent: tk.Widget, worker: Worker,
                 on_confirm: Callable[[Worker, List[str]], None]):
        self.worker = worker
        self.on_confirm = on_confirm
        self.config = get_config()
        self.doc_flows, self.doc_labels, self.doc_prefixes = get_document_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Отклонить анкету #{worker.id}")
        self.dialog.configure(bg='#f0f0f0')
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Центрирование
        self._center_window(520, 650)
        self._build_ui()

    def _center_window(self, w: int, h: int) -> None:
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        # Заголовок
        header = tk.Frame(self.dialog, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"❌ Отклонить анкету #{self.worker.id}",
                 font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white').pack(pady=5)
        tk.Label(header, text=f"{self.worker.name}",
                 font=('Arial', 11), bg='#2c3e50', fg='#bbb').pack()

        tk.Label(self.dialog, text="Выберите поля для исправления:",
                 font=('Arial', 12, 'bold'), bg='#f0f0f0').pack(pady=(12, 2))

        # Прокручиваемый список чекбоксов
        list_frame = tk.Frame(self.dialog, bg='#f0f0f0')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 0))

        canvas = tk.Canvas(list_frame, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner_frame = tk.Frame(canvas, bg='white')

        inner_frame.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner_frame, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_canvas_cfg(event):
            canvas.itemconfig("inner", width=event.width)
        canvas.bind("<Configure>", on_canvas_cfg)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Поля для выбора
        self.vars: Dict[str, tk.BooleanVar] = {}

        fields = [
            ('name', 'ФИО'), ('citizenship', 'Гражданство'), ('gender', 'Пол'),
            ('position', 'Должность'), ('object', 'Объект'), ('object_address', 'Адрес'),
            ('manager', 'Менеджер'), ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'), ('email', 'Email'),
            ('date', 'Дата рождения'), ('registration', 'Регистрация'),
        ]

        # Добавляем документы из конфига для данной категории
        citizenship = self.worker.citizenship
        docs_found = False
        if citizenship in self.doc_flows:
            for doc in self.doc_flows[citizenship]:
                fields.append((doc.key, f"[Док] {doc.label}"))
                docs_found = True

        # Если документы не найдены — добавляем ВСЕ из всех категорий
        if not docs_found:
            seen = set()
            for cat_docs in self.doc_flows.values():
                for doc in cat_docs:
                    if doc.key not in seen:
                        fields.append((doc.key, f"[Док] {doc.label}"))
                        seen.add(doc.key)

        for key, label in fields:
            var = tk.BooleanVar()
            self.vars[key] = var
            tk.Checkbutton(inner_frame, text=label, variable=var,
                           bg='white', font=('Arial', 10), anchor='w'
                           ).pack(fill=tk.X, padx=10, pady=1)

        # Кнопки внизу (всегда видны)
        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def do_reject():
            selected = [k for k, v in self.vars.items() if v.get()]
            if not selected:
                messagebox.showwarning("Внимание", "Выберите хотя бы одно поле!", parent=self.dialog)
                return
            self.dialog.destroy()
            self.on_confirm(self.worker, selected)

        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Отклонить и отправить",
                  command=do_reject,
                  bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.RIGHT, padx=(5, 15))


# ─── Окно уведомлений ───

class NotificationsWindow:
    """Окно со списком новых (pending) анкет."""

    def __init__(self, parent: tk.Widget,
                 on_refresh: Callable[[], None],
                 on_accept: Callable[[Worker], None],
                 on_reject: Callable[[Worker], None],
                 on_view: Callable[[Worker], None]):
        self.parent = parent
        self.on_refresh = on_refresh
        self.on_accept = on_accept
        self.on_reject = on_reject
        self.on_view = on_view
        self.config = get_config()
        self.db = get_db_service()

        self.window = tk.Toplevel(parent)
        self.window.title("Новые анкеты")
        self.window.configure(bg='#f0f0f0')
        self.window.transient(parent)
        self.window.grab_set()

        self._center_window(900, 600)
        self._build_ui()
        self._load_data()

    def _center_window(self, w: int, h: int) -> None:
        self.window.update_idletasks()
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        # Заголовок
        header = tk.Frame(self.window, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)

        self.title_label = tk.Label(header, text="🔔 Новые анкеты",
                                    font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white')
        self.title_label.pack(side=tk.LEFT, padx=15)

        tk.Button(header, text="Закрыть", command=self.window.destroy,
                  bg='#e74c3c', fg='white', font=('Arial', 10),
                  padx=10, relief=tk.FLAT).pack(side=tk.RIGHT, padx=15)

        # Область прокрутки
        canvas = tk.Canvas(self.window, bg='#f0f0f0')
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg='#f0f0f0')

        self.scroll_frame.bind("<Configure>",
                               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def _load_data(self) -> None:
        """Загрузить pending анкеты."""
        pending = self.db.workers.get_pending()
        self.title_label.config(text=f"🔔 Новые анкеты ({len(pending)})")

        if not pending:
            tk.Label(self.scroll_frame, text="Нет новых анкет",
                     font=('Arial', 12), bg='#f0f0f0', fg='#666').pack(expand=True)
            return

        for worker in pending:
            self._create_card(worker)

    def _create_card(self, worker: Worker) -> None:
        """Создать карточку анкеты."""
        from src.widgets import WorkerCardWidget

        def on_accept(w):
            self._handle_accept(w)

        def on_reject(w):
            RejectDialog(self.window, w, lambda wk, reasons: self._handle_reject(wk, reasons))

        def on_view(w):
            self.window.destroy()
            self.on_view(w)

        WorkerCardWidget(
            self.scroll_frame, worker,
            on_accept=on_accept,
            on_reject=on_reject,
            on_view=on_view
        ).pack(fill=tk.X, padx=10, pady=5)

    def _handle_accept(self, worker: Worker) -> None:
        """Обработка принятия анкеты."""
        try:
            if self.db.workers.accept(worker.id):
                messagebox.showinfo("Готово", f"Анкета #{worker.id} принята!", parent=self.window)
                self.window.destroy()
                self.on_refresh()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить статус", parent=self.window)
        except Exception as e:
            log_exception(f"Error accepting worker {worker.id}")
            messagebox.showerror("Ошибка", f"Ошибка: {e}", parent=self.window)

    def _handle_reject(self, worker: Worker, reasons: List[str]) -> None:
        """Обработка отклонения анкеты — бот отправит уведомление через 60 сек."""
        try:
            if self.db.workers.reject(worker.id, reasons):
                messagebox.showinfo("Готово",
                                    f"Анкета #{worker.id} отклонена.\n"
                                    f"Клиент получит уведомление в Telegram.",
                                    parent=self.window)
                self.window.destroy()
                self.on_refresh()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить статус", parent=self.window)
        except Exception as e:
            log_exception(f"Error rejecting worker {worker.id}")
            messagebox.showerror("Ошибка", f"Ошибка: {e}", parent=self.window)


# ─── Диалог подтверждения ───

def ask_yes_no(parent: tk.Widget, title: str, message: str) -> bool:
    """Диалог Да/Нет."""
    return messagebox.askyesno(title, message, parent=parent)


def show_info(parent: tk.Widget, title: str, message: str) -> None:
    """Информационное сообщение."""
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent: tk.Widget, title: str, message: str) -> None:
    """Предупреждение."""
    messagebox.showwarning(title, message, parent=parent)


def show_error(parent: tk.Widget, title: str, message: str) -> None:
    """Ошибка."""
    messagebox.showerror(title, message, parent=parent)


# ─── Диалог редактирования сотрудника ───

class EditDialog:
    """Диалог редактирования всех полей сотрудника."""

    def __init__(self, parent: tk.Widget, worker: Worker,
                 on_save: Callable[[Worker], None]):
        self.worker = worker
        self.on_save = on_save
        self.config = get_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Редактировать анкету #{worker.id}")
        self.dialog.configure(bg='#f0f0f0')
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._center_window(550, 650)
        self._build_ui()

    def _center_window(self, w: int, h: int) -> None:
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self) -> None:
        header = tk.Frame(self.dialog, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text=f"✏️ Редактировать анкету #{self.worker.id}",
                 font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white').pack(pady=5)
        tk.Label(header, text=self.worker.name,
                 font=('Arial', 11), bg='#2c3e50', fg='#bbb').pack()

        # Прокручиваемая область
        canvas_frame = tk.Frame(self.dialog, bg='#f0f0f0')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        canvas = tk.Canvas(canvas_frame, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg='white')

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_canvas_cfg(event):
            canvas.itemconfig("inner", width=event.width)
        canvas.bind("<Configure>", on_canvas_cfg)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Поля для редактирования
        fields = [
            ('name', 'ФИО'),
            ('citizenship', 'Гражданство'),
            ('gender', 'Пол'),
            ('position', 'Должность'),
            ('object', 'Объект'),
            ('object_address', 'Адрес объекта'),
            ('manager', 'Менеджер'),
            ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'),
            ('email', 'Email'),
            ('date', 'Дата рождения'),
            ('registration', 'Регистрация'),
        ]

        self.entries: Dict[str, tk.Entry] = {}
        for key, label in fields:
            row = tk.Frame(inner, bg='white')
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=f"{label}:", bg='white', font=('Arial', 10, 'bold'),
                     width=18, anchor='w').pack(side=tk.LEFT)
            entry = tk.Entry(row, font=('Arial', 10))
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entry.insert(0, getattr(self.worker, key, '') or '')
            self.entries[key] = entry

        # Кнопки
        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Сохранить",
                  command=self._save,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.RIGHT, padx=(5, 15))

    def _save(self) -> None:
        """Сохранить изменения."""
        for key, entry in self.entries.items():
            setattr(self.worker, key, entry.get().strip())

        self.dialog.destroy()
        self.on_save(self.worker)
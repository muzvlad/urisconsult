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
        self._center_window(520, 550)
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
            ('photo', 'Фото'), ('passport', 'Паспорт'),
        ]

        citizenship = self.worker.citizenship
        if citizenship in self.doc_flows:
            for doc in self.doc_flows[citizenship]:
                if doc.key not in [f[0] for f in fields]:
                    fields.append((doc.key, doc.label))

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
        """Обработка отклонения анкеты."""
        try:
            if self.db.workers.reject(worker.id, reasons):
                # Отправка в Telegram
                telegram = get_telegram_service()
                telegram.send_rejection(worker, reasons)

                messagebox.showinfo("Готово",
                                    f"Анкета #{worker.id} отклонена.\nЗамечания отправлены клиенту.",
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
"""
Диалоговые окна: отклонение, уведомления, подтверждения.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, List, Dict, Any
from pathlib import Path

from src.config import (get_config, get_document_config, normalize_citizenship,
                        FONT_FAMILY, format_date, parse_user_date,
                        HR_STATUS_KEYS, HR_STATUS_LABELS, hr_status_style)
from src.models import Worker
from src.services import get_telegram_service
from src.api_client import get_db_service as get_api_client
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

        # Откладываем центрирование чтобы окно не моргало
        self.dialog.after(10, lambda: self._center_window(520, 650))
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
                 font=(FONT_FAMILY, 14, 'bold'), bg='#2c3e50', fg='white').pack(pady=5)
        tk.Label(header, text=f"{self.worker.name}",
                 font=(FONT_FAMILY, 11), bg='#2c3e50', fg='#bbb').pack()

        tk.Label(self.dialog, text="Выберите поля для исправления:",
                 font=(FONT_FAMILY, 12, 'bold'), bg='#f0f0f0').pack(pady=(12, 2))

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
        self.comments: Dict[str, tk.Entry] = {}

        fields = [
            ('name', 'ФИО'), ('citizenship', 'Категория'), ('gender', 'Пол'),
            ('date', 'Дата рождения'), ('manager', 'Менеджер'), ('object', 'Объект'),
            ('customer', 'Заказчик'), ('object_address', 'Адрес'), ('position', 'Должность'),
            ('phone_main', 'Основной телефон'), ('phone_additional', 'Доп. телефон'),
        ]

        # Добавляем документы из конфига для данной категории
        citizenship = self.worker.citizenship
        normalized = normalize_citizenship(citizenship)

        # Документы из конфига для данной категории
        if normalized in self.doc_flows:
            for doc in self.doc_flows[normalized]:
                fields.append((doc.key, f"[Док] {doc.label}"))
        else:
            log_error(f" citizenship '{normalized}' not found in doc_flows")

        for key, label in fields:
            row = tk.Frame(inner_frame, bg='white')
            row.pack(fill=tk.X, padx=10, pady=1)

            var = tk.BooleanVar()
            self.vars[key] = var
            cb = tk.Checkbutton(row, text=label, variable=var,
                                bg='white', font=(FONT_FAMILY, 10), anchor='w')
            cb.pack(anchor=tk.W, fill=tk.X)

            entry = tk.Entry(row, bg='white', font=(FONT_FAMILY, 9), state='disabled',
                             disabledforeground='#aaa')
            entry.pack(fill=tk.X, padx=(25, 5), pady=(0, 2))
            self.comments[key] = entry

            var.trace_add('write', lambda *_, v=var, e=entry: _toggle_comment(v, e))

        def _toggle_comment(var, entry):
            if var.get():
                entry.config(state='normal')
            else:
                entry.config(state='disabled')

        # Кнопки внизу (всегда видны)
        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def do_reject():
            selected = []
            for key, var in self.vars.items():
                if var.get():
                    comment = self.comments[key].get().strip() if key in self.comments else ''
                    selected.append({'key': key, 'comment': comment})
            if not selected:
                messagebox.showwarning("Внимание", "Выберите хотя бы одно поле!", parent=self.dialog)
                return
            self.dialog.destroy()
            self.on_confirm(self.worker, selected)

        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=16, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Отклонить и отправить",
                  command=do_reject,
                  bg=self.config.accent_red, fg='white', font=(FONT_FAMILY, 10, 'bold'),
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
        self.api = get_api_client()

        self.window = tk.Toplevel(parent)
        self.window.title("Новые анкеты")
        self.window.configure(bg='#f0f0f0')
        self.window.transient(parent)
        self.window.grab_set()

        # Откладываем центрирование чтобы окно не моргало
        self.window.after(10, lambda: self._center_window(900, 600))
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
                                    font=(FONT_FAMILY, 14, 'bold'), bg='#2c3e50', fg='white')
        self.title_label.pack(side=tk.LEFT, padx=15)

        tk.Button(header, text="Закрыть", command=self.window.destroy,
                  bg=self.config.accent_red, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=12, relief=tk.FLAT).pack(side=tk.RIGHT, padx=15)

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
        try:
            pending = self.api.get_workers(status='pending')
        except ConnectionError:
            messagebox.showerror("Ошибка", "Сервер недоступен", parent=self.window)
            return
        self.title_label.config(text=f"🔔 Новые анкеты ({len(pending)})")

        if not pending:
            tk.Label(self.scroll_frame, text="Нет новых анкет",
                     font=(FONT_FAMILY, 12), bg='#f0f0f0', fg='#666').pack(expand=True)
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
            if self.api.accept_worker(worker.id):
                messagebox.showinfo("Готово", f"Анкета #{worker.id} принята!", parent=self.window)
                self.window.destroy()
                self.on_refresh()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить статус", parent=self.window)
        except ConnectionError:
            messagebox.showerror("Ошибка", "Сервер недоступен", parent=self.window)
        except Exception as e:
            log_exception(f"Error accepting worker {worker.id}")
            messagebox.showerror("Ошибка", f"Ошибка: {e}", parent=self.window)

    def _handle_reject(self, worker: Worker, reasons: List[str]) -> None:
        """Обработка отклонения анкеты — бот отправит уведомление через 60 сек."""
        try:
            if self.api.reject_worker(worker.id, reasons):
                messagebox.showinfo("Готово",
                                    f"Анкета #{worker.id} отклонена.\n"
                                    f"Клиент получит уведомление в Telegram.",
                                    parent=self.window)
                self.window.destroy()
                self.on_refresh()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить статус", parent=self.window)
        except ConnectionError:
            messagebox.showerror("Ошибка", "Сервер недоступен", parent=self.window)
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
                 font=(FONT_FAMILY, 14, 'bold'), bg='#2c3e50', fg='white').pack(pady=5)
        tk.Label(header, text=self.worker.name,
                 font=(FONT_FAMILY, 11), bg='#2c3e50', fg='#bbb').pack()

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
            ('citizenship', 'Категория'),
            ('gender', 'Пол'),
            ('date', 'Дата рождения'),
            ('manager', 'Менеджер'),
            ('object', 'Объект'),
            ('customer', 'Заказчик'),
            ('object_address', 'Адрес объекта'),
            ('position', 'Должность'),
            ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'),
        ]

        self.entries: Dict[str, tk.Entry] = {}
        for key, label in fields:
            row = tk.Frame(inner, bg='white')
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=f"{label}:", bg='white', font=(FONT_FAMILY, 10, 'bold'),
                     width=18, anchor='w').pack(side=tk.LEFT)
            entry = tk.Entry(row, font=(FONT_FAMILY, 10))
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entry.insert(0, getattr(self.worker, key, '') or '')
            self.entries[key] = entry

        # Кнопки
        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=16, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Сохранить",
                  command=self._save,
                  bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.RIGHT, padx=(5, 15))

    def _save(self) -> None:
        """Сохранить изменения."""
        for key, entry in self.entries.items():
            setattr(self.worker, key, entry.get().strip())

        self.dialog.destroy()
        self.on_save(self.worker)


# ─── Диалог добавления встречи ───

class MeetingDialog:
    """Диалог добавления встречи сотруднику."""

    def __init__(self, parent: tk.Widget, worker: Worker,
                 on_added: Callable[[], None]):
        self.worker = worker
        self.on_added = on_added
        self.api = get_api_client()
        self.config = get_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Новая встреча — {worker.name}")
        self.dialog.configure(bg='#f0f0f0')
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._center_window(520, 430)
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
        tk.Label(header, text=f"📅 Новая встреча",
                 font=(FONT_FAMILY, 13, 'bold'), bg='#2c3e50', fg='white').pack()
        tk.Label(header, text=self.worker.name,
                 font=(FONT_FAMILY, 10), bg='#2c3e50', fg='#bbb').pack()

        # Кнопки первыми (side=BOTTOM), чтобы заняли место
        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=16, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Добавить",
                  command=self._save,
                  bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.RIGHT, padx=(5, 15))

        # Форма заполняет оставшееся пространство
        form = tk.Frame(self.dialog, bg='#f0f0f0', padx=20, pady=15)
        form.pack(fill=tk.BOTH, expand=True)

        tk.Label(form, text="Дата и время (дд.мм.гггг чч:мм):",
                 font=(FONT_FAMILY, 10), bg='#f0f0f0').pack(anchor=tk.W)
        dt_row = tk.Frame(form, bg='#f0f0f0')
        dt_row.pack(fill=tk.X, pady=(0, 10))
        self.date_entry = tk.Entry(dt_row, font=(FONT_FAMILY, 11), width=15)
        self.date_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.date_entry.insert(0, __import__('datetime').date.today().strftime('%d.%m.%Y'))
        self.time_entry = tk.Entry(dt_row, font=(FONT_FAMILY, 11), width=8)
        self.time_entry.pack(side=tk.LEFT)
        self.time_entry.insert(0, __import__('datetime').datetime.now().strftime('%H:%M'))

        tk.Label(form, text="Примечание:", font=(FONT_FAMILY, 10), bg='#f0f0f0').pack(anchor=tk.W)
        self.note_text = tk.Text(form, font=(FONT_FAMILY, 11), width=50, height=6, wrap=tk.WORD)
        self.note_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

    def _save(self) -> None:
        date_text = self.date_entry.get().strip()
        time_str = self.time_entry.get().strip()
        iso_date = parse_user_date(date_text)
        if not iso_date:
            messagebox.showwarning("Внимание", "Дата должна быть в формате дд.мм.гггг",
                                   parent=self.dialog)
            return
        if len(time_str) != 5 or time_str[2] != ':':
            messagebox.showwarning("Ошибка", "Время должно быть в формате чч:мм",
                                   parent=self.dialog)
            return
        try:
            from datetime import datetime
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            messagebox.showwarning("Ошибка", "Время должно быть в формате чч:мм",
                                   parent=self.dialog)
            return
        date_value = f"{date_text} {time_str}"
        note = self.note_text.get("1.0", tk.END).strip()
        try:
            if not self.api.add_meeting(self.worker.id, date_value, note):
                messagebox.showerror("Ошибка", "Не удалось добавить встречу",
                                     parent=self.dialog)
                return
            self.dialog.destroy()
            self.on_added()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить встречу:\n{e}", parent=self.dialog)

# ─── Комментарий ───

class NoteDialog:
    """Диалог добавления/изменения комментария."""

    def __init__(self, parent: tk.Widget, worker: Worker,
                 on_save: Callable[[str], None],
                 note: Optional[dict] = None):
        self.worker = worker
        self.on_save = on_save
        self.note = note
        self.config = get_config()

        self.dialog = tk.Toplevel(parent)
        title = "Изменить комментарий" if note else "Новый комментарий"
        self.dialog.title(f"{title} — {worker.name}")
        self.dialog.configure(bg='#f0f0f0')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.after(10, lambda: self._center_window(520, 340))
        self._build_ui()

    def _center_window(self, w: int, h: int) -> None:
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        self.dialog.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build_ui(self) -> None:
        header = tk.Frame(self.dialog, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)
        text = "Изменить комментарий" if self.note else "Новый комментарий"
        tk.Label(header, text=text, font=(FONT_FAMILY, 13, 'bold'),
                 bg='#2c3e50', fg='white').pack()
        tk.Label(header, text=self.worker.name, font=(FONT_FAMILY, 10),
                 bg='#2c3e50', fg='#bbb').pack()

        form = tk.Frame(self.dialog, bg='#f0f0f0', padx=20, pady=15)
        form.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(form, height=6, width=50, wrap=tk.WORD, font=(FONT_FAMILY, 10))
        self.text.pack(fill=tk.BOTH, expand=True)
        if self.note:
            self.text.insert('1.0', self.note.get('text', ''))
        self.text.focus_set()

        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=16, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT, padx=(15, 5))
        tk.Button(btn_frame, text="Сохранить", command=self._save,
                  bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2').pack(side=tk.RIGHT, padx=(5, 15))

    def _save(self) -> None:
        text = self.text.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Внимание", "Комментарий не может быть пустым",
                                   parent=self.dialog)
            return
        self.dialog.destroy()
        self.on_save(text)


# ─── Юридическое лицо ───

class LegalEntityDialog:
    """Диалог изменения юридического лица."""

    def __init__(self, parent: tk.Widget, worker: Worker,
                 on_save: Callable[[str], None]):
        self.worker = worker
        self.on_save = on_save
        self.config = get_config()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Юр. лицо — {worker.name}")
        self.dialog.configure(bg='#f0f0f0')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.after(10, lambda: self._center_window(460, 230))
        self._build_ui()

    def _center_window(self, w: int, h: int) -> None:
        self.dialog.update_idletasks()
        sw = self.dialog.winfo_screenwidth()
        sh = self.dialog.winfo_screenheight()
        self.dialog.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build_ui(self) -> None:
        header = tk.Frame(self.dialog, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="Юридическое лицо", font=(FONT_FAMILY, 13, 'bold'),
                 bg='#2c3e50', fg='white').pack()
        tk.Label(header, text=self.worker.name, font=(FONT_FAMILY, 10),
                 bg='#2c3e50', fg='#bbb').pack()

        form = tk.Frame(self.dialog, bg='#f0f0f0', padx=20, pady=15)
        form.pack(fill=tk.BOTH, expand=True)
        self.entry = tk.Entry(form, font=(FONT_FAMILY, 11))
        self.entry.pack(fill=tk.X)
        self.entry.insert(0, self.worker.legal_entity or '')
        self.entry.focus_set()

        btn_frame = tk.Frame(self.dialog, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(btn_frame, text="Отмена", command=self.dialog.destroy,
                  bg=self.config.accent_gray, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=16, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT, padx=(15, 5))
        tk.Button(btn_frame, text="Сохранить", command=self._save,
                  bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2').pack(side=tk.RIGHT, padx=(5, 15))

    def _save(self) -> None:
        value = self.entry.get().strip()
        self.dialog.destroy()
        self.on_save(value)

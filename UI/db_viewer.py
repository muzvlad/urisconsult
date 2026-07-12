"""
Приложение для просмотра карточек сотрудников.

Включает:
- Поиск и просмотр анкет
- Колокольчик уведомлений о новых анкетах
- Обработка анкет (принятие/отклонение)
- Отправка замечаний клиенту через Telegram
"""
import sys
import os
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk

# Импорт общего конфига документов из бота
BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot')
sys.path.insert(0, BOT_DIR)

from config.documents import DOC_FLOWS, DOC_LABELS, DOC_PREFIXES

# Фиксированные пути
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(PROJECT_ROOT, "bot", "Users")
DB_PATH = os.path.join(DB_DIR, "users.db")
DOCS_DIR = os.path.join(PROJECT_ROOT, "users", "docs")


def init_db():
    """Создать БД и таблицу, если их ещё нет."""
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            citizenship TEXT,
            gender TEXT,
            position TEXT,
            object TEXT,
            object_address TEXT,
            manager TEXT,
            phone_main TEXT,
            phone_additional TEXT,
            email TEXT,
            date TEXT,
            registration TEXT,
            marital_status TEXT,
            relatives_json TEXT DEFAULT '[]',
            telegram_id INTEGER,
            telegram_username TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'pending',
            rejection_reasons TEXT DEFAULT '[]'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            date TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id)
        )
    """)

    # Миграция: добавляем колонки status/rejection_reasons если их нет
    for col, default in [("status", "'pending'"), ("rejection_reasons", "'[]'")]:
        try:
            conn.execute(f"ALTER TABLE workers ADD COLUMN {col} TEXT DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


class DBViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("URIS Consult — Просмотр Карточек")
        self.root.geometry("1300x850")
        self.root.configure(bg='#f0f0f0')

        self.search_results = []
        self.current_person_data = None
        self.pending_count = 0
        self.bell_label = None

        self.setup_ui()
        self.check_db_connection()
        self.refresh_pending_count()
        self._center_window(self.root, 1300, 850)

    def check_db_connection(self):
        try:
            init_db()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("SELECT count(*) FROM workers")
            conn.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось инициализировать БД:\n{e}")

    @staticmethod
    def _center_window(win, w, h):
        """Центрировать окно на экране."""
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ──────────────────────────────────────────────────────────────
    # Интерфейс
    # ──────────────────────────────────────────────────────────────

    def setup_ui(self):
        # Верхняя панель
        top_frame = tk.Frame(self.root, bg='#2c3e50', pady=8)
        top_frame.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(top_frame, text="URIS Consult",
                 font=('Arial', 16, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side=tk.LEFT, padx=15)

        # Кнопка "Показать всех"
        tk.Button(top_frame, text="Все анкеты", command=self.show_all_workers,
                  bg='#3498db', fg='white', font=('Arial', 10),
                  padx=12, relief=tk.FLAT
                  ).pack(side=tk.LEFT, padx=5)

        # Кнопка "Экспорт в PDF"
        tk.Button(top_frame, text="PDF", command=self.export_to_pdf,
                  bg='#e67e22', fg='white', font=('Arial', 10),
                  padx=12, relief=tk.FLAT
                  ).pack(side=tk.LEFT, padx=5)

        # Колокольчик
        self.bell_frame = tk.Frame(top_frame, bg='#2c3e50')
        self.bell_frame.pack(side=tk.RIGHT, padx=15)

        # Пробуем отрисовать эмодзи через Label с нужным шрифтом
        self.bell_label_icon = tk.Label(
            self.bell_frame, text="\U0001f514", bg='#2c3e50', fg='white',
            font=('Segoe UI Symbol', 16), cursor='hand2'
        )
        self.bell_label_icon.pack(side=tk.LEFT)
        self.bell_label_icon.bind('<Button-1>', lambda e: self.open_notifications())

        self.bell_badge = tk.Canvas(
            self.bell_frame, width=16, height=16,
            bg='#2c3e50', highlightthickness=0, bd=0
        )
        self.bell_badge.create_oval(0, 0, 16, 16, fill='#7f8c8d', outline='', tags='dot')
        self.bell_badge_text = self.bell_badge.create_text(8, 8, text='',
                                                          font=('Arial', 7, 'bold'),
                                                          fill='white', tags='num')

        # Панель поиска
        search_frame = tk.Frame(self.root, bg='#f0f0f0', pady=8)
        search_frame.pack(fill=tk.X, padx=10)

        tk.Label(search_frame, text="Поиск:", bg='#f0f0f0',
                 font=('Arial', 11)).pack(side=tk.LEFT)

        self.search_entry = tk.Entry(search_frame, font=('Arial', 11), width=35)
        self.search_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', lambda e: self.search_workers())

        tk.Button(search_frame, text="Найти", command=self.search_workers,
                  bg='#2196F3', fg='white', font=('Arial', 10),
                  padx=10, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # Основная область
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Левая панель — список
        left_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1, width=300)
        left_frame.pack_propagate(False)
        main_paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Найденные записи:",
                 font=('Arial', 11, 'bold')).pack(pady=5, padx=5)

        self.results_listbox = tk.Listbox(left_frame, font=('Arial', 10))
        self.results_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_listbox.bind('<<ListboxSelect>>', self.on_result_select)

        # Статус-бар внизу левой панели
        self.status_bar = tk.Label(left_frame, text="", bg='#ecf0f1',
                                   font=('Arial', 9), anchor='w', padx=5)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Правая панель — детали
        right_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1)
        main_paned.add(right_frame, weight=10)

        canvas = tk.Canvas(right_frame)
        v_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(right_frame, orient="horizontal", command=canvas.xview)

        self.scrollable_frame = tk.Frame(canvas, width=900)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw",
                             tags="inner_frame")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # При изменении размера canvas — растягиваем inner frame по ширине
        def on_canvas_configure(event):
            canvas.itemconfig("inner_frame", width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.bind("<Shift-MouseWheel>",
                    lambda e: canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ──────────────────────────────────────────────────────────────
    # Колокольчик
    # ──────────────────────────────────────────────────────────────

    def refresh_pending_count(self):
        """Обновить счётчик на колокольчике."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.execute("SELECT COUNT(*) FROM workers WHERE status = 'pending'")
            self.pending_count = cursor.fetchone()[0]
            conn.close()
        except Exception:
            self.pending_count = 0

        if self.pending_count > 0:
            self.bell_badge.pack(side=tk.LEFT, padx=(1, 0))
            self.bell_badge.itemconfig('num', text=str(self.pending_count))
        else:
            self.bell_badge.pack_forget()

    def open_notifications(self):
        """Открыть панель уведомлений — список новых анкет."""
        notif_window = tk.Toplevel(self.root)
        notif_window.title("Новые анкеты")
        notif_window.configure(bg='#f0f0f0')
        notif_window.transient(self.root)
        notif_window.grab_set()
        self._center_window(notif_window, 900, 600)

        # Заголовок
        header = tk.Frame(notif_window, bg='#2c3e50', pady=10)
        header.pack(fill=tk.X)

        tk.Label(header, text=f"🔔 Новые анкеты ({self.pending_count})",
                 font=('Arial', 14, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side=tk.LEFT, padx=15)

        tk.Button(header, text="Закрыть", command=notif_window.destroy,
                  bg='#e74c3c', fg='white', font=('Arial', 10),
                  padx=10, relief=tk.FLAT
                  ).pack(side=tk.RIGHT, padx=15)

        # Список pending анкет
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM workers WHERE status = 'pending' ORDER BY created_at DESC"
            )
            pending = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка загрузки: {e}")
            return

        if not pending:
            tk.Label(notif_window, text="Нет новых анкет",
                     font=('Arial', 12), bg='#f0f0f0', fg='#666'
                     ).pack(expand=True)
            return

        # Canvas для прокрутки
        canvas = tk.Canvas(notif_window, bg='#f0f0f0')
        scrollbar = ttk.Scrollbar(notif_window, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg='#f0f0f0')

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Карточки анкет
        for worker in pending:
            self._create_pending_card(scroll_frame, worker, notif_window)

    def _create_pending_card(self, parent, worker, notif_window):
        """Создать карточку.pending анкеты."""
        card = tk.Frame(parent, bg='white', relief=tk.RAISED, borderwidth=1,
                        padx=10, pady=8)
        card.pack(fill=tk.X, padx=10, pady=5)

        # Верхняя строка: ID + ФИО + Гражданство
        top = tk.Frame(card, bg='white')
        top.pack(fill=tk.X)

        tk.Label(top, text=f"#{worker['id']}",
                 font=('Arial', 10, 'bold'), bg='white', fg='#3498db'
                 ).pack(side=tk.LEFT)

        tk.Label(top, text=worker['name'],
                 font=('Arial', 12, 'bold'), bg='white'
                 ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(top, text=f"({worker['citizenship']})",
                 font=('Arial', 10), bg='white', fg='#666'
                 ).pack(side=tk.LEFT, padx=(5, 0))

        # Инфо
        info = tk.Frame(card, bg='white')
        info.pack(fill=tk.X, pady=(5, 0))

        info_items = [
            f"Должность: {worker.get('position', '')}",
            f"Объект: {worker.get('object', '')}",
            f"Тел: {worker.get('phone_main', '')}",
            f"Email: {worker.get('email', '')}",
        ]
        for item in info_items:
            tk.Label(info, text=item, font=('Arial', 9), bg='white', fg='#555'
                     ).pack(anchor=tk.W)

        # Кнопки
        btn_frame = tk.Frame(card, bg='white')
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Button(btn_frame, text="✅ Принять",
                  command=lambda w=worker: self._accept_from_notification(w, notif_window),
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="❌ Отклонить",
                  command=lambda w=worker: self._reject_from_notification(w, notif_window),
                  bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="👁 Просмотр",
                  command=lambda w=worker: self._view_from_notification(w, notif_window),
                  bg='#3498db', fg='white', font=('Arial', 10),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT)

    def _accept_from_notification(self, worker, notif_window):
        """Принять анкету."""
        worker_id = worker['id']
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE workers SET status = 'accepted', rejection_reasons = '[]' WHERE id = ?",
                (worker_id,)
            )
            conn.commit()
            conn.close()
            messagebox.showinfo("Готово", f"Анкета #{worker_id} принята!")
            notif_window.destroy()
            self.refresh_pending_count()
            self.open_notifications()  # Обновить список
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка: {e}")

    def _reject_from_notification(self, worker, notif_window):
        """Отклонить анкету — выбор полей для исправления."""
        reject_window = tk.Toplevel(notif_window)
        reject_window.title(f"Отклонить анкету #{worker['id']}")
        reject_window.configure(bg='#f0f0f0')
        reject_window.transient(notif_window)
        reject_window.grab_set()
        self._center_window(reject_window, 520, 550)

        # Заголовок
        tk.Label(reject_window, text="Выберите поля для исправления:",
                 font=('Arial', 12, 'bold'), bg='#f0f0f0'
                 ).pack(pady=(12, 2))

        tk.Label(reject_window, text=f"{worker['name']} (#{worker['id']})",
                 font=('Arial', 10), bg='#f0f0f0', fg='#666'
                 ).pack()

        # Прокручиваемый список чекбоксов
        list_frame = tk.Frame(reject_window, bg='#f0f0f0')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 0))

        canvas_check = tk.Canvas(list_frame, bg='white', highlightthickness=0)
        scrollbar_check = ttk.Scrollbar(list_frame, orient="vertical", command=canvas_check.yview)
        inner_frame = tk.Frame(canvas_check, bg='white')

        inner_frame.bind("<Configure>",
                         lambda e: canvas_check.configure(scrollregion=canvas_check.bbox("all")))
        canvas_check.create_window((0, 0), window=inner_frame, anchor="nw", tags="inner")
        canvas_check.configure(yscrollcommand=scrollbar_check.set)

        def on_canvas_cfg(event):
            canvas_check.itemconfig("inner", width=event.width)
        canvas_check.bind("<Configure>", on_canvas_cfg)

        canvas_check.pack(side="left", fill="both", expand=True)
        scrollbar_check.pack(side="right", fill="y")

        canvas_check.bind("<MouseWheel>",
                          lambda e: canvas_check.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Поля
        fields = [
            ('name', 'ФИО'), ('citizenship', 'Гражданство'), ('gender', 'Пол'),
            ('position', 'Должность'), ('object', 'Объект'), ('object_address', 'Адрес'),
            ('manager', 'Менеджер'), ('phone_main', 'Основной телефон'),
            ('phone_additional', 'Доп. телефон'), ('email', 'Email'),
            ('date', 'Дата рождения'), ('registration', 'Регистрация'),
            ('photo', 'Фото'), ('passport', 'Паспорт'),
        ]
        citizenship = worker.get('citizenship', '')
        if citizenship in DOC_FLOWS:
            for doc in DOC_FLOWS[citizenship]:
                if doc.key not in [f[0] for f in fields]:
                    fields.append((doc.key, doc.label))

        vars_dict = {}
        for key, label in fields:
            var = tk.BooleanVar()
            vars_dict[key] = var
            tk.Checkbutton(inner_frame, text=label, variable=var,
                           bg='white', font=('Arial', 10), anchor='w'
                           ).pack(fill=tk.X, padx=10, pady=1)

        # Кнопки внизу (всегда видны)
        btn_frame = tk.Frame(reject_window, bg='#f0f0f0', pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def do_reject():
            selected = [k for k, v in vars_dict.items() if v.get()]
            if not selected:
                messagebox.showwarning("Внимание", "Выберите хотя бы одно поле!",
                                       parent=reject_window)
                return
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "UPDATE workers SET status = 'rejected', rejection_reasons = ? WHERE id = ?",
                    (json.dumps(selected, ensure_ascii=False), worker['id'])
                )
                conn.commit()
                conn.close()
                self._send_rejection_to_telegram(worker, selected)
                messagebox.showinfo("Готово",
                    f"Анкета #{worker['id']} отклонена.\n"
                    f"Замечания отправлены клиенту.",
                    parent=reject_window)
                reject_window.destroy()
                notif_window.destroy()
                self.refresh_pending_count()
                self.open_notifications()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка: {e}", parent=reject_window)

        tk.Button(btn_frame, text="Отмена", command=reject_window.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(15, 5))

        tk.Button(btn_frame, text="Отклонить и отправить",
                  command=do_reject,
                  bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.RIGHT, padx=(5, 15))

    def _send_rejection_to_telegram(self, worker, reasons):
        """Отправить сообщение об отклонении клиенту через Telegram Bot API."""
        telegram_id = worker.get('telegram_id')
        if not telegram_id:
            return  # Нет telegram_id — не можем отправить

        # Читаем токен бота
        env_path = os.path.join(BOT_DIR, '.env')
        bot_token = None
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('BOT_TOKEN='):
                        bot_token = line.strip().split('=', 1)[1]
                        break

        if not bot_token:
            return

        # Формируем сообщение
        reasons_text = '\n'.join(f"  - {r}" for r in reasons)
        text = (
            f"❌ Ваша анкета #{worker['id']} отклонена.\n\n"
            f"Необходимо исправить:\n{reasons_text}\n\n"
            f"Отправьте исправленные данные через бота /start"
        )

        # Отправляем через Telegram Bot API (синхронно)
        import urllib.request
        import urllib.parse
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': telegram_id,
            'text': text,
        }).encode()
        try:
            urllib.request.urlopen(url, data=data, timeout=10)
        except Exception:
            pass  # Не критично если не удалось

    def _view_from_notification(self, worker, notif_window):
        """Просмотр анкеты из уведомлений."""
        notif_window.destroy()
        self.display_person_data(worker)
        # Подсветить в списке
        for i, item in enumerate(self.search_results):
            if item['id'] == worker['id']:
                self.results_listbox.selection_set(i)
                break

    # ──────────────────────────────────────────────────────────────
    # Поиск
    # ──────────────────────────────────────────────────────────────

    def search_workers(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Предупреждение", "Введите слово для поиска!")
            return
        self._execute_search(f"SELECT * FROM workers WHERE name LIKE ? ORDER BY id",
                             (f"%{query}%",))

    def show_all_workers(self):
        self._execute_search("SELECT * FROM workers ORDER BY id", ())

    def _execute_search(self, sql, params):
        self.results_listbox.delete(0, tk.END)
        self.search_results = []
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                self.search_results.append(dict(row))

            for item in self.search_results:
                status = item.get('status', 'pending')
                icon = {'pending': '⏳', 'accepted': '✅', 'rejected': '❌'}.get(status, '?')
                self.results_listbox.insert(tk.END,
                    f"{icon} {item['id']} — {item['name']}")

            self.status_bar.config(text=f"Найдено: {len(self.search_results)}")

            if not self.search_results:
                messagebox.showinfo("Результаты", "Записи не найдены")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка поиска: {e}")

    def on_result_select(self, event):
        selection = self.results_listbox.curselection()
        if selection:
            try:
                self.display_person_data(self.search_results[selection[0]])
            except Exception as e:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Ошибка", f"Ошибка отображения:\n{e}")

    # ──────────────────────────────────────────────────────────────
    # Отображение карточки
    # ──────────────────────────────────────────────────────────────

    def _get_worker_documents(self, worker_id):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT doc_type, filename FROM worker_documents WHERE worker_id = ?",
                (worker_id,)
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception:
            return {}

    def _get_worker_meetings(self, worker_id):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT date, note FROM worker_meetings WHERE worker_id = ? ORDER BY id",
                (worker_id,)
            )
            return [{'date': row[0], 'note': row[1]} for row in cursor.fetchall()]
        except Exception:
            return []

    def display_person_data(self, data):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.current_person_data = data
        worker_id = data.get('id', '')

        try:
            documents = self._get_worker_documents(worker_id)
        except Exception:
            documents = {}

        try:
            meetings = self._get_worker_meetings(worker_id)
        except Exception:
            meetings = []

        # ── Заголовок ──
        header_frame = tk.Frame(self.scrollable_frame, bg='white',
                                relief=tk.RAISED, borderwidth=1)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        left_col = tk.Frame(header_frame, bg='white')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_col = tk.Frame(header_frame, bg='white')
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        # Статус
        status = data.get('status', 'pending')
        status_config = {
            'pending': ('⏳ Ожидает', '#f39c12'),
            'accepted': ('✅ Принята', '#27ae60'),
            'rejected': ('❌ Отклонена', '#e74c3c'),
        }
        status_text, status_color = status_config.get(status, ('?', '#999'))

        tk.Label(left_col, text=f"ФИО: {data.get('name', 'Не указано')}",
                 font=('Arial', 14, 'bold'), bg='white', anchor='w'
                 ).pack(anchor=tk.W, fill=tk.X)

        status_label = tk.Label(left_col, text=status_text,
                                font=('Arial', 11, 'bold'), bg='white', fg=status_color)
        status_label.pack(anchor=tk.W, pady=(2, 0))

        tk.Label(right_col, text=f"ИД: {worker_id}",
                 font=('Arial', 12), bg='white').pack(anchor=tk.NE)

        # Фото
        photo_frame = tk.Frame(right_col, bg='white', relief=tk.SOLID, borderwidth=2)
        photo_frame.pack(anchor=tk.NE, pady=(5, 0))
        self._display_photo(photo_frame, worker_id, 'photo', 'photo')

        # ── Личная информация ──
        info_frame = tk.Frame(self.scrollable_frame, bg='white',
                              relief=tk.RAISED, borderwidth=1)
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
        ]

        for field_key, field_label in fields:
            value = data.get(field_key, '')
            if value:
                display = str(value)
                if len(display) > 60:
                    display = display[:57] + "..."
                tk.Label(info_inner, text=f"{field_label}: {display}",
                         font=('Arial', 11), bg='white', anchor='w',
                         wraplength=500, justify=tk.LEFT
                         ).pack(anchor=tk.W, fill=tk.X, pady=2)

        # ── Документы ──
        citizenship = data.get('citizenship', '')
        if citizenship in DOC_FLOWS:
            docs_header = tk.Frame(self.scrollable_frame, bg='white',
                                   relief=tk.RAISED, borderwidth=1)
            docs_header.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(docs_header, text=f"Документы ({citizenship}):",
                     font=('Arial', 13, 'bold'), bg='white', anchor='w'
                     ).pack(anchor=tk.W, padx=10, pady=(10, 5))

            for doc in DOC_FLOWS[citizenship]:
                filename = documents.get(doc.key, '')
                self._display_document_section(
                    self.scrollable_frame, doc.label, filename, doc.prefix
                )

        # ── Замечания (если отклонена) ──
        if status == 'rejected':
            rejection_raw = data.get('rejection_reasons', '[]')
            if isinstance(rejection_raw, str):
                try:
                    reasons = json.loads(rejection_raw)
                except (json.JSONDecodeError, TypeError):
                    reasons = []
            else:
                reasons = rejection_raw or []

            if reasons:
                rej_frame = tk.Frame(self.scrollable_frame, bg='#ffeaa7',
                                     relief=tk.RAISED, borderwidth=1)
                rej_frame.pack(fill=tk.X, padx=5, pady=5)

                tk.Label(rej_frame, text="⚠ Замечания:",
                         font=('Arial', 12, 'bold'), bg='#ffeaa7', anchor='w'
                         ).pack(anchor=tk.W, padx=10, pady=(8, 3))

                for r in reasons:
                    label = DOC_LABELS.get(r, r)
                    tk.Label(rej_frame, text=f"  • {label}",
                             font=('Arial', 10), bg='#ffeaa7', anchor='w'
                             ).pack(anchor=tk.W, padx=20)

        # ── Встречи ──
        if meetings:
            meetings_frame = tk.Frame(self.scrollable_frame, bg='white',
                                      relief=tk.RAISED, borderwidth=1)
            meetings_frame.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(meetings_frame, text="Встречи:",
                     font=('Arial', 13, 'bold'), bg='white', anchor='w'
                     ).pack(anchor=tk.W, padx=10, pady=(10, 5))

            for m in meetings:
                date = m.get('date', '')
                note = m.get('note', '')
                text = f"• {date} — {note}" if date else f"• {note}"
                tk.Label(meetings_frame, text=text, font=('Arial', 10),
                         bg='white', anchor='w', wraplength=700
                         ).pack(anchor=tk.W, padx=20, pady=1)

        # Принудительно обновляем scrollregion canvas
        try:
            canvas = self.scrollable_frame.master
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Документы / Фото
    # ──────────────────────────────────────────────────────────────

    def _display_document_section(self, parent, title, filename, prefix):
        section = tk.Frame(parent, bg='white', relief=tk.GROOVE, borderwidth=1)
        section.pack(fill=tk.X, padx=5, pady=3)

        header = tk.Frame(section, bg='white')
        header.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(header, text=f"{title}:", font=('Arial', 11, 'bold'),
                 bg='white').pack(side=tk.LEFT)

        if not filename:
            tk.Label(section, text="Не загружено",
                     font=('Arial', 9), bg='white', fg='#999').pack(pady=3)
            return

        client_id = self.current_person_data.get('id', '')
        if not client_id:
            return

        image_filename = f"{prefix}_{client_id}"
        full_path = None
        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            test_path = os.path.join(DOCS_DIR, image_filename + ext)
            if os.path.exists(test_path):
                full_path = test_path
                break

        if not full_path:
            tk.Label(section, text=f"Файл не найден ({image_filename})",
                     font=('Arial', 9), bg='white', fg='orange').pack(pady=3)
            return

        try:
            image = Image.open(full_path)
            display_image = image.copy()
            display_image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(display_image)

            img_frame = tk.Frame(section, bg='white')
            img_frame.pack(pady=5)

            img_label = tk.Label(img_frame, image=photo, bg='white', cursor='hand2')
            img_label.image = photo
            img_label.pack()
            img_label.bind('<Button-1>',
                           lambda e, p=full_path: self.open_image(p))

            tk.Label(section, text=os.path.basename(full_path),
                     font=('Arial', 9), bg='white', fg='#666').pack()
        except Exception as e:
            tk.Label(section, text=f"Ошибка загрузки: {e}",
                     font=('Arial', 9), bg='white', fg='red').pack(pady=3)

    def _display_photo(self, parent, worker_id, filename, prefix):
        if not worker_id:
            tk.Label(parent, text="Фото не найдено",
                     font=('Arial', 10), bg='white', fg='gray'
                     ).pack(expand=True, padx=10, pady=10)
            return

        image_filename = f"{prefix}_{worker_id}"
        photo_path = None
        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
            test_path = os.path.join(DOCS_DIR, image_filename + ext)
            if os.path.exists(test_path):
                photo_path = test_path
                break

        if not photo_path:
            tk.Label(parent, text="Фото не найдено",
                     font=('Arial', 10), bg='white', fg='gray'
                     ).pack(expand=True, padx=10, pady=10)
            return

        try:
            image = Image.open(photo_path)
            display_image = image.copy()
            display_image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(display_image)

            label = tk.Label(parent, image=photo, bg='white', cursor='hand2',
                             relief=tk.FLAT, bd=0)
            label.image = photo
            label.pack(padx=2, pady=2)
            label.bind('<Button-1>',
                       lambda e, p=photo_path: self.open_image(p))
        except Exception:
            tk.Label(parent, text="Ошибка загрузки фото",
                     font=('Arial', 9), bg='white', fg='red'
                     ).pack(expand=True, padx=10, pady=10)

    def open_image(self, path):
        try:
            import subprocess
            import platform
            system = platform.system()
            if system == "Windows":
                subprocess.run(["cmd", "/c", "start", "", path], shell=True)
            elif system == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}")

    # ──────────────────────────────────────────────────────────────
    # PDF экспорт
    # ──────────────────────────────────────────────────────────────

    def export_to_pdf(self):
        if not self.current_person_data:
            messagebox.showwarning("Предупреждение", "Сначала выберите запись!")
            return

        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Сохранить как PDF"
            )
            if filename:
                self._generate_pdf(filename)
                messagebox.showinfo("Успех", f"PDF сохранён:\n{filename}")
        except ImportError:
            messagebox.showerror("Ошибка",
                                 "Библиотека reportlab не установлена.\npip install reportlab")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}")

    def _generate_pdf(self, filename):
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.utils import ImageReader

        font_name = 'Helvetica'
        for fp in ["C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/arial.ttf",
                    "C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/verdana.ttf"]:
            if os.path.exists(fp):
                try:
                    safe = "Font_" + Path(fp).stem
                    pdfmetrics.registerFont(TTFont(safe, fp))
                    font_name = safe
                    break
                except Exception:
                    continue

        c = pdf_canvas.Canvas(filename, pagesize=A4)
        width, height = A4
        data = self.current_person_data
        worker_id = data.get('id', '')
        citizenship = data.get('citizenship', '')
        documents = self._get_worker_documents(worker_id)

        y = height - 50
        c.setFont(font_name, 16)
        c.drawString(50, y, "Карточка сотрудника")

        y -= 30
        c.setFont(font_name, 12)
        c.drawString(50, y, f"ФИО: {data.get('name', '')}")
        y -= 20
        c.drawString(50, y, f"ИД: {worker_id}")
        y -= 20
        c.drawString(50, y, f"Гражданство: {citizenship}")
        y -= 20

        profile = [
            ('gender', 'Пол'), ('position', 'Должность'),
            ('object', 'Объект'), ('object_address', 'Адрес'),
            ('manager', 'Менеджер'), ('phone_main', 'Телефон'),
            ('phone_additional', 'Доп. телефон'), ('email', 'Email'),
            ('date', 'Дата рождения'), ('registration', 'Регистрация'),
        ]
        for key, label in profile:
            val = data.get(key, '')
            if val:
                c.drawString(50, y, f"{label}: {val}")
                y -= 18

        # Фото
        if worker_id:
            photo_path = None
            for ext in ['.jpg', '.jpeg', '.png']:
                tp = os.path.join(DOCS_DIR, f"photo_{worker_id}{ext}")
                if os.path.exists(tp):
                    photo_path = tp
                    break
            if photo_path:
                try:
                    img = ImageReader(photo_path)
                    c.drawImage(img, 450, y - 10, width=80, height=80,
                                preserveAspectRatio=True, mask='auto')
                    y -= 100
                except Exception:
                    pass

        # Документы
        y -= 20
        if citizenship in DOC_FLOWS:
            c.setFont(font_name, 14)
            c.drawString(50, y, f"Документы ({citizenship}):")
            y -= 25
            c.setFont(font_name, 10)

            for doc in DOC_FLOWS[citizenship]:
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont(font_name, 10)

                filename_doc = documents.get(doc.key, '')
                if filename_doc and worker_id:
                    doc_path = None
                    for ext in ['.jpg', '.jpeg', '.png']:
                        tp = os.path.join(DOCS_DIR, f"{doc.prefix}_{worker_id}{ext}")
                        if os.path.exists(tp):
                            doc_path = tp
                            break

                    c.drawString(70, y, f"{doc.label}: {filename_doc}")
                    if doc_path:
                        try:
                            img = ImageReader(doc_path)
                            c.drawImage(img, 450, y - 5, width=60, height=60,
                                        preserveAspectRatio=True, mask='auto')
                        except Exception:
                            pass
                    y -= 70
                else:
                    c.drawString(70, y, f"{doc.label}: —")
                    y -= 18

        c.save()


def main():
    try:
        root = tk.Tk()
        app = DBViewerApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        msg = f"Ошибка запуска:\n{e}\n\n{traceback.format_exc()}"
        print(msg)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ошибка", msg)
            root.destroy()
        except Exception:
            print("Не удалось показать сообщение об ошибке")
        input("\nEnter для выхода...")


if __name__ == "__main__":
    main()

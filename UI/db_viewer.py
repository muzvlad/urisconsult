import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
from pathlib import Path
from PIL import Image, ImageTk
import io

# Фиксированные пути
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(PROJECT_ROOT, "bot", "Users")
DB_PATH = os.path.join(DB_DIR, "users.db")
DOCS_DIR = os.path.join(PROJECT_ROOT, "users", "docs")


def init_db():
    """Создать БД и таблицу, если их ещё нет"""
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
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
            photo TEXT,
            passport TEXT,
            patent_snils TEXT,
            patent_registration TEXT,
            patent_migration_card TEXT,
            patent_dms TEXT,
            patent_patent TEXT,
            patent_inn TEXT,
            patent_receipt TEXT,
            patent_language_cert TEXT,
            patent_bank_details TEXT,
            patent_fingerprint_card TEXT,
            student_snils TEXT,
            student_registration TEXT,
            student_migration_card TEXT,
            student_dms TEXT,
            student_inn TEXT,
            student_fingerprint_card TEXT,
            student_university_cert TEXT,
            student_bank_details TEXT,
            eaeas_registration TEXT,
            eaeas_migration_card TEXT,
            eaeas_dms TEXT,
            eaeas_inn TEXT,
            eaeas_snils TEXT,
            eaeas_fingerprint_card TEXT,
            eaeas_bank_details TEXT,
            rvp_migration_card TEXT,
            rvp_dms_oms TEXT,
            rvp_inn TEXT,
            rvp_snils TEXT,
            rvp_bank_details TEXT,
            vnzh_migration_card TEXT,
            vnzh_vnzh TEXT,
            vnzh_dms_oms TEXT,
            vnzh_inn TEXT,
            vnzh_snils TEXT,
            vnzh_work_book TEXT,
            vnzh_bank_details TEXT,
            russia_passport_propiska TEXT,
            russia_propiska TEXT,
            russia_inn TEXT,
            russia_snils TEXT,
            russia_education_doc TEXT,
            russia_work_book TEXT,
            russia_military_doc TEXT,
            russia_marital_status TEXT,
            russia_relatives TEXT DEFAULT '[]',
            registration TEXT,
            telegram_id INTEGER,
            telegram_username TEXT,
            created_at TEXT,
            meetings TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()

# Маппинг документов по категориям гражданства
CITIZENSHIP_DOCS = {
    'Патент': [
        ('passport', 'Паспорт', 'pas'),
        ('patent_snils', 'СНИЛС', 'snils'),
        ('patent_registration', 'Регистрация', 'reg'),
        ('patent_migration_card', 'Миграционная карта', 'mig'),
        ('patent_dms', 'ДМС', 'dms'),
        ('patent_patent', 'Патент', 'pat'),
        ('patent_inn', 'ИНН', 'inn'),
        ('patent_receipt', 'Чек по патенту', 'chek'),
        ('patent_language_cert', 'Сертификат о знании языка', 'lang'),
        ('patent_bank_details', 'Реквизиты банковской карты', 'bank'),
        ('patent_fingerprint_card', 'Дактилоскопическая карта', 'dactyl'),
    ],
    'Студент': [
        ('passport', 'Паспорт', 'pas'),
        ('student_snils', 'СНИЛС', 'snils'),
        ('student_registration', 'Регистрация', 'reg'),
        ('student_migration_card', 'Миграционная карта', 'mig'),
        ('student_dms', 'ДМС', 'dms'),
        ('student_inn', 'ИНН', 'inn'),
        ('student_fingerprint_card', 'Дактилоскопическая карта', 'dactyl'),
        ('student_university_cert', 'Справка из ВУЗа', 'spravka'),
        ('student_bank_details', 'Реквизиты банковской карты', 'bank'),
    ],
    'ЕАЭС': [
        ('passport', 'Паспорт', 'pas'),
        ('eaeas_registration', 'Регистрация', 'reg'),
        ('eaeas_migration_card', 'Миграционная карта', 'mig'),
        ('eaeas_dms', 'ДМС', 'dms'),
        ('eaeas_inn', 'ИНН', 'inn'),
        ('eaeas_snils', 'СНИЛС', 'snils'),
        ('eaeas_fingerprint_card', 'Дактилоскопическая карта', 'dactyl'),
        ('eaeas_bank_details', 'Реквизиты банковской карты', 'bank'),
    ],
    'РВП': [
        ('passport', 'Паспорт', 'pas'),
        ('rvp_migration_card', 'Миграционная карта', 'mig'),
        ('rvp_dms_oms', 'ДМС/ОМС', 'dms'),
        ('rvp_inn', 'ИНН', 'inn'),
        ('rvp_snils', 'СНИЛС', 'snils'),
        ('rvp_bank_details', 'Реквизиты банковской карты', 'bank'),
    ],
    'ВНЖ': [
        ('passport', 'Паспорт', 'pas'),
        ('vnzh_migration_card', 'Миграционная карта', 'mig'),
        ('vnzh_vnzh', 'ВНЖ', 'vnzh'),
        ('vnzh_dms_oms', 'ДМС/ОМС', 'dms'),
        ('vnzh_inn', 'ИНН', 'inn'),
        ('vnzh_snils', 'СНИЛС', 'snils'),
        ('vnzh_work_book', 'Трудовая книжка/ЭТК', 'trud'),
        ('vnzh_bank_details', 'Реквизиты банковской карты', 'bank'),
    ],
    'Россия': [
        ('passport', 'Паспорт', 'pas'),
        ('russia_passport_propiska', 'Паспорт прописка', 'propiska'),
        ('russia_propiska', 'Прописка', 'propiska'),
        ('russia_inn', 'ИНН', 'inn'),
        ('russia_snils', 'СНИЛС', 'snils'),
        ('russia_education_doc', 'Документ об образовании', 'edu'),
        ('russia_work_book', 'Трудовая книжка/ЭТК', 'trud'),
        ('russia_military_doc', 'Военный билет/Приписное', 'voen'),
    ],
}


class DBViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Просмотр Карточек — БД")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        self.search_results = []
        self.current_person_data = None

        self.setup_ui()
        self.check_db_connection()

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))

    def check_db_connection(self):
        try:
            init_db()
            conn = sqlite3.connect(DB_PATH)
            conn.execute("SELECT count(*) FROM workers")
            conn.close()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось инициализировать БД:\n{e}")

    def setup_ui(self):
        # Верхняя панель
        top_frame = tk.Frame(self.root, bg='#f0f0f0', pady=10)
        top_frame.pack(fill=tk.X, padx=10)

        tk.Label(top_frame, text="Просмотр Карточек",
                 font=('Arial', 16, 'bold'), bg='#f0f0f0').pack(pady=(0, 10))

        search_panel = tk.Frame(top_frame, bg='#f0f0f0')
        search_panel.pack(fill=tk.X)

        tk.Label(search_panel, text="Поиск:", bg='#f0f0f0',
                 font=('Arial', 12)).pack(side=tk.LEFT)

        self.search_entry = tk.Entry(search_panel, font=('Arial', 12), width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', lambda e: self.search_workers())

        tk.Button(search_panel, text="Найти", command=self.search_workers,
                  bg='#2196F3', fg='white', font=('Arial', 10),
                  padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(search_panel, text="Показать всех", command=self.show_all_workers,
                  bg='#607D8B', fg='white', font=('Arial', 10),
                  padx=10).pack(side=tk.LEFT, padx=5)

        tk.Button(search_panel, text="Экспорт в PDF", command=self.export_to_pdf,
                  bg='#FF9800', fg='white', font=('Arial', 10),
                  padx=10).pack(side=tk.LEFT, padx=5)

        # Основная область
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Левая панель — список
        left_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1, width=300)
        left_frame.pack_propagate(False)
        main_paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Найденные записи:",
                 font=('Arial', 12, 'bold')).pack(pady=5, padx=5)

        self.results_listbox = tk.Listbox(left_frame, font=('Arial', 10))
        self.results_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.results_listbox.bind('<<ListboxSelect>>', self.on_result_select)

        # Правая панель — детали
        right_frame = tk.Frame(main_paned, relief=tk.RAISED, borderwidth=1)
        main_paned.add(right_frame, weight=10)

        canvas = tk.Canvas(right_frame)
        v_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(right_frame, orient="horizontal", command=canvas.xview)

        self.scrollable_frame = tk.Frame(canvas, width=900)
        self.scrollable_frame.pack_propagate(False)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.bind("<Shift-MouseWheel>",
                    lambda e: canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ── Поиск ──────────────────────────────────────────────

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
                self.results_listbox.insert(tk.END, f"{item['id']} — {item['name']}")

            if not self.search_results:
                messagebox.showinfo("Результаты", "Записи не найдены")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка поиска: {e}")

    # ── Отображение карточки ───────────────────────────────

    def on_result_select(self, event):
        selection = self.results_listbox.curselection()
        if selection:
            self.display_person_data(self.search_results[selection[0]])

    def display_person_data(self, data):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.current_person_data = data

        # ── Заголовок: ФИО + ИД + фото ──
        header_frame = tk.Frame(self.scrollable_frame, bg='white',
                                relief=tk.RAISED, borderwidth=1)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        left_col = tk.Frame(header_frame, bg='white')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_col = tk.Frame(header_frame, bg='white')
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        # ФИО
        tk.Label(left_col, text=f"ФИО: {data.get('name', 'Не указано')}",
                 font=('Arial', 14, 'bold'), bg='white', anchor='w'
                 ).pack(anchor=tk.W, fill=tk.X)

        # ИД
        tk.Label(right_col, text=f"ИД: {data.get('id', '')}",
                 font=('Arial', 12), bg='white').pack(anchor=tk.NE)

        # Фото
        photo_frame = tk.Frame(right_col, bg='white', relief=tk.SOLID, borderwidth=2)
        photo_frame.pack(anchor=tk.NE, pady=(5, 0))
        self._display_photo(photo_frame, data.get('id', ''), 'photo', 'photo')

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

        # ── Документы по категории ──
        citizenship = data.get('citizenship', '')
        docs_list = CITIZENSHIP_DOCS.get(citizenship, [])

        if docs_list:
            docs_header = tk.Frame(self.scrollable_frame, bg='white',
                                   relief=tk.RAISED, borderwidth=1)
            docs_header.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(docs_header, text=f"Документы ({citizenship}):",
                     font=('Arial', 13, 'bold'), bg='white', anchor='w'
                     ).pack(anchor=tk.W, padx=10, pady=(10, 5))

            for field_key, display_name, prefix in docs_list:
                value = data.get(field_key, '')
                self._display_document_section(
                    self.scrollable_frame, display_name, value, prefix
                )

        # ── Встречи ──
        meetings_raw = data.get('meetings', '[]')
        if isinstance(meetings_raw, str):
            try:
                import json
                meetings = json.loads(meetings_raw)
            except Exception:
                meetings = []
        else:
            meetings = meetings_raw or []

        if meetings:
            meetings_frame = tk.Frame(self.scrollable_frame, bg='white',
                                      relief=tk.RAISED, borderwidth=1)
            meetings_frame.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(meetings_frame, text="Встречи:",
                     font=('Arial', 13, 'bold'), bg='white', anchor='w'
                     ).pack(anchor=tk.W, padx=10, pady=(10, 5))

            for m in meetings:
                if isinstance(m, dict):
                    date = m.get('date', '')
                    note = m.get('note', m.get('description', ''))
                    text = f"• {date} — {note}" if date else f"• {note}"
                else:
                    text = f"• {m}"
                tk.Label(meetings_frame, text=text, font=('Arial', 10),
                         bg='white', anchor='w', wraplength=700
                         ).pack(anchor=tk.W, padx=20, pady=1)

    # ── Документы ──────────────────────────────────────────

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
            tk.Label(section, text="Не указан ID клиента",
                     font=('Arial', 9), bg='white', fg='red').pack(pady=3)
            return

        # Ищем файл документа
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

    # ── Открытие / скачивание ──────────────────────────────

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

    # ── PDF экспорт ────────────────────────────────────────

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
                                 "Библиотека reportlab не установлена.\n"
                                 "pip install reportlab")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}")

    def _generate_pdf(self, filename):
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.utils import ImageReader

        # Шрифт
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

        y = height - 50
        c.setFont(font_name, 16)
        c.drawString(50, y, "Карточка сотрудника")

        y -= 30
        c.setFont(font_name, 12)
        c.drawString(50, y, f"ФИО: {data.get('name', '')}")
        y -= 20
        c.drawString(50, y, f"ИД: {data.get('id', '')}")
        y -= 20
        c.drawString(50, y, f"Гражданство: {data.get('citizenship', '')}")
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
        worker_id = data.get('id', '')
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
        citizenship = data.get('citizenship', '')
        docs_list = CITIZENSHIP_DOCS.get(citizenship, [])

        if docs_list:
            c.setFont(font_name, 14)
            c.drawString(50, y, f"Документы ({citizenship}):")
            y -= 25
            c.setFont(font_name, 10)

            for field_key, display_name, prefix in docs_list:
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont(font_name, 10)

                val = data.get(field_key, '')
                if val and worker_id:
                    doc_path = None
                    for ext in ['.jpg', '.jpeg', '.png']:
                        tp = os.path.join(DOCS_DIR, f"{prefix}_{worker_id}{ext}")
                        if os.path.exists(tp):
                            doc_path = tp
                            break

                    c.drawString(70, y, f"{display_name}: {val}")
                    if doc_path:
                        try:
                            img = ImageReader(doc_path)
                            c.drawImage(img, 450, y - 5, width=60, height=60,
                                        preserveAspectRatio=True, mask='auto')
                        except Exception:
                            pass
                    y -= 70
                else:
                    c.drawString(70, y, f"{display_name}: —")
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

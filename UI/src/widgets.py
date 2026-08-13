"""
Виджеты UI: карточка сотрудника, просмотр документов, фото, колокольчик.
"""
from __future__ import annotations
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, List
from pathlib import Path

from PIL import Image, ImageTk

from src.config import get_config, FONT_FAMILY
from src.models import Worker
from src.services import get_document_service, DocumentInfo


# ─── Колокольчик уведомлений ───

class NotificationBell(tk.Frame):
    """Колокольчик с бейджем количества."""

    def __init__(self, parent: tk.Widget,
                 on_click: Optional[Callable[[], None]] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.on_click = on_click
        self.count = 0

        # Иконка колокольчика
        self.bell_label = tk.Label(
            self, text="\U0001f514",  # 🔔
            bg=kwargs.get('bg', '#2c3e50'), fg='white',
            font=('Segoe UI Symbol', 16), cursor='hand2'
        )
        self.bell_label.pack(side=tk.LEFT)
        self.bell_label.bind('<Button-1>', lambda e: self._on_click())

        # Бейдж (Canvas с кружком и числом)
        self.badge_canvas = tk.Canvas(
            self, width=16, height=16,
            bg=kwargs.get('bg', '#2c3e50'), highlightthickness=0, bd=0
        )
        self.badge_canvas.create_oval(0, 0, 16, 16, fill='#7f8c8d', outline='', tags='dot')
        self.badge_text = self.badge_canvas.create_text(8, 8, text='',
                                                         font=(FONT_FAMILY, 7, 'bold'),
                                                         fill='white', tags='num')

        self.set_count(0)

    def _on_click(self) -> None:
        if self.on_click:
            self.on_click()

    def set_count(self, count: int) -> None:
        """Установить количество уведомлений."""
        self.count = count
        if count > 0:
            self.badge_canvas.pack(side=tk.LEFT, padx=(1, 0))
            self.badge_canvas.itemconfig('num', text=str(count) if count < 100 else '99+')
        else:
            self.badge_canvas.pack_forget()


# ─── Виджет списка сотрудников ───

class WorkerListWidget(tk.Frame):
    """Виджет списка сотрудников с Listbox и сортировкой."""

    def __init__(self, parent: tk.Widget,
                 on_select: Optional[Callable[[Worker], None]] = None,
                 on_double_click: Optional[Callable[[Worker], None]] = None):
        super().__init__(parent)
        self.on_select = on_select
        self.on_double_click = on_double_click
        self.config = get_config()
        self.workers: List[Worker] = []
        self._sort_column: str = "id"  # id, name, status, created_at
        self._sort_reverse: bool = False

        # Заголовок с кнопками сортировки
        header_frame = tk.Frame(self, bg='#ecf0f1', height=28)
        header_frame.pack(fill=tk.X, padx=2, pady=(2, 0))
        header_frame.pack_propagate(False)

        # Кликабельные заголовки колонок
        status_header = tk.Label(header_frame, text="Статус", bg='#ecf0f1', font=(FONT_FAMILY, 8, 'bold'), width=6, cursor='hand2')
        status_header.pack(side=tk.LEFT, padx=2)
        status_header.bind('<Button-1>', lambda e: self._sort_by("status"))

        id_header = tk.Label(header_frame, text="ID", bg='#ecf0f1', font=(FONT_FAMILY, 8, 'bold'), width=8, cursor='hand2')
        id_header.pack(side=tk.LEFT, padx=2)
        id_header.bind('<Button-1>', lambda e: self._sort_by("id"))

        name_header = tk.Label(header_frame, text="ФИО", bg='#ecf0f1', font=(FONT_FAMILY, 8, 'bold'), cursor='hand2')
        name_header.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        name_header.bind('<Button-1>', lambda e: self._sort_by("name"))

        # Список
        self.listbox = tk.Listbox(self, font=(FONT_FAMILY, 10), selectmode=tk.SINGLE, activestyle='none')
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.listbox.bind('<<ListboxSelect>>', self._on_select)
        self.listbox.bind('<Double-Button-1>', self._on_double_click)

        # Сохраняем ссылки на заголовки для обновления стрелочек
        self._headers = {"status": status_header, "id": id_header, "name": name_header}

    def _sort_by(self, column: str) -> None:
        """Сортировка по колонке."""
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        self._update_header_arrows()
        self._apply_sort()

    def _update_header_arrows(self) -> None:
        """Обновление стрелочек в заголовках."""
        arrows = {"status": "", "id": "", "name": ""}
        arrow = " ▲" if not self._sort_reverse else " ▼"
        arrows[self._sort_column] = arrow

        for col, header in self._headers.items():
            base_text = {"status": "Статус", "id": "ID", "name": "ФИО"}[col]
            header.config(text=base_text + arrows[col])

    def _apply_sort(self) -> None:
        """Применить сортировку к списку."""
        key_funcs = {
            "id": lambda w: w.id,
            "name": lambda w: w.name.lower(),
            "status": lambda w: w.status,
            "created_at": lambda w: w.created_at or "",
        }
        key_func = key_funcs.get(self._sort_column, lambda w: w.id)
        self.workers.sort(key=key_func, reverse=self._sort_reverse)
        self._refresh_listbox()

    def _refresh_listbox(self) -> None:
        """Обновить отображение Listbox."""
        self.listbox.delete(0, tk.END)
        for worker in self.workers:
            icon = self.config.status_icons.get(worker.status, '?')
            self.listbox.insert(tk.END, f"{icon} {worker.id} — {worker.name}")

    def set_workers(self, workers: List[Worker]) -> None:
        """Установить список сотрудников."""
        self.workers = workers
        self._apply_sort()

    def _on_select(self, event) -> None:
        selection = self.listbox.curselection()
        if selection and self.on_select:
            self.on_select(self.workers[selection[0]])

    def _on_double_click(self, event) -> None:
        selection = self.listbox.curselection()
        if selection and self.on_double_click:
            self.on_double_click(self.workers[selection[0]])

    def select_by_id(self, worker_id: str) -> None:
        """Выбрать сотрудника по ID."""
        for i, worker in enumerate(self.workers):
            if worker.id == worker_id:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(i)
                self.listbox.see(i)
                if self.on_select:
                    self.on_select(worker)
                break


# ─── Карточка сотрудника для уведомлений ───

class WorkerCardWidget(tk.Frame):
    """Карточка сотрудника в окне уведомлений."""

    def __init__(self, parent: tk.Widget,
                 worker: Worker,
                 on_accept: Callable[[Worker], None],
                 on_reject: Callable[[Worker], None],
                 on_view: Callable[[Worker], None]):
        super().__init__(parent, bg='white', relief=tk.RAISED, borderwidth=1, padx=10, pady=8)
        self.worker = worker
        self.on_accept = on_accept
        self.on_reject = on_reject
        self.on_view = on_view
        self.config = get_config()

        self._build_ui()

    def _build_ui(self) -> None:
        # Верхняя строка: ID + ФИО + Гражданство
        top = tk.Frame(self, bg='white')
        top.pack(fill=tk.X)

        tk.Label(top, text=f"#{self.worker.id}",
                 font=(FONT_FAMILY, 10, 'bold'), bg='white', fg=self.config.accent_blue).pack(side=tk.LEFT)

        tk.Label(top, text=self.worker.name,
                 font=(FONT_FAMILY, 12, 'bold'), bg='white').pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(top, text=f"({self.worker.citizenship})",
                 font=(FONT_FAMILY, 10), bg='white', fg='#666').pack(side=tk.LEFT, padx=(5, 0))

        # Инфо
        info = tk.Frame(self, bg='white')
        info.pack(fill=tk.X, pady=(5, 0))

        info_items = [
            f"Должность: {self.worker.position}",
            f"Объект: {self.worker.object}",
            f"Тел: {self.worker.phone_main}",
        ]
        for item in info_items:
            if item.split(': ')[1]:
                tk.Label(info, text=item, font=(FONT_FAMILY, 9), bg='white', fg='#555'
                         ).pack(anchor=tk.W)

        # Кнопки
        btn_frame = tk.Frame(self, bg='white')
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Button(btn_frame, text="✅ Принять",
                  command=lambda: self.on_accept(self.worker),
                  bg=self.config.accent_green, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="❌ Отклонить",
                  command=lambda: self.on_reject(self.worker),
                  bg=self.config.accent_red, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="👁 Просмотр",
                  command=lambda: self.on_view(self.worker),
                  bg=self.config.accent_blue, fg='white', font=(FONT_FAMILY, 10, 'bold'),
                  padx=15, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT)


# ─── Виджет фото ───

class PhotoWidget(tk.Frame):
    """Виджет для отображения фото с возможностью открытия."""

    def __init__(self, parent: tk.Widget,
                 worker_id: str,
                 on_click: Optional[Callable[[Path], None]] = None):
        super().__init__(parent, bg='white')
        self.worker_id = worker_id
        self.on_click = on_click
        self.doc_service = get_document_service()
        self.config = get_config()

        self._load_photo()

    def _load_photo(self) -> None:
        """Загрузить и отобразить фото."""
        photo_path = self.doc_service.find_photo(self.worker_id)

        if not photo_path:
            tk.Label(self, text="Фото не найдено",
                     font=(FONT_FAMILY, 10), bg='white', fg='gray').pack(expand=True, padx=10, pady=10)
            return

        try:
            image = Image.open(photo_path)
            display_image = image.copy()
            display_image.thumbnail(self.config.thumbnail_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(display_image)

            label = tk.Label(self, image=photo, bg='white', cursor='hand2',
                             relief=tk.FLAT, bd=0)
            label.image = photo  # Сохранить ссылку
            label.pack(padx=2, pady=2)
            label.bind('<Button-1>', lambda e: self._on_click(photo_path))
        except Exception:
            tk.Label(self, text="Ошибка загрузки фото",
                     font=(FONT_FAMILY, 9), bg='white', fg='red').pack(expand=True, padx=10, pady=10)

    def _on_click(self, path: Path) -> None:
        if self.on_click:
            self.on_click(path)


# ─── Виджет просмотра документа ───

class DocumentViewer(tk.Frame):
    """Виджет для отображения документа с миниатюрой."""

    def __init__(self, parent: tk.Widget,
                 doc_info: DocumentInfo,
                 on_open: Optional[Callable[[Path], None]] = None,
                 on_replace: Optional[Callable[[], None]] = None):
        super().__init__(parent, bg='white', relief=tk.GROOVE, borderwidth=1)
        self.doc_info = doc_info
        self.on_open = on_open
        self.on_replace = on_replace
        self.doc_service = get_document_service()
        self.config = get_config()

        self._build_ui()

    @staticmethod
    def _format_date(value: str) -> str:
        """Отформатировать дату из ISO в ДД.ММ.ГГГГ ЧЧ:ММ."""
        if not value:
            return ''
        try:
            from datetime import datetime
            dt = value[:16].replace('T', ' ')
            return datetime.strptime(dt, '%Y-%m-%d %H:%M').strftime('%d.%m.%Y %H:%M')
        except Exception:
            return value[:16]

    def _build_ui(self) -> None:
        main = tk.Frame(self, bg='white')
        main.pack(fill=tk.X, padx=8, pady=5)

        # Левая колонка: название, дата, кнопки (под названием, не под фоткой)
        left_col = tk.Frame(main, bg='white')
        left_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Название документа
        tk.Label(left_col, text=self.doc_info.label,
                 font=(FONT_FAMILY, 10, 'bold'), bg='white', anchor='w').pack(anchor=tk.W)

        # Дата заливки документа под названием
        if self.doc_info.uploaded_at:
            fmt = self._format_date(self.doc_info.uploaded_at)
            if fmt:
                tk.Label(left_col, text=f"Залит: {fmt}",
                         font=(FONT_FAMILY, 8), bg='white', fg='#888', anchor='w'
                         ).pack(anchor=tk.W, pady=(0, 2))

        # Кнопки «Скачать» и «Заменить» под названием документа
        if self.doc_info.exists and self.doc_info.full_path:
            btn_frame = tk.Frame(left_col, bg='white')
            btn_frame.pack(anchor=tk.W, pady=(2, 0))
            if self.on_replace:
                tk.Button(btn_frame, text="📤 Заменить",
                          command=self._replace,
                          bg=self.config.accent_blue, fg='white',
                          font=(FONT_FAMILY, 9, 'bold'), padx=12, relief=tk.FLAT,
                          cursor='hand2').pack(side=tk.LEFT, padx=(0, 5))
            tk.Button(btn_frame, text="⬇ Скачать",
                      command=self._download,
                      bg=self.config.accent_blue, fg='white',
                      font=(FONT_FAMILY, 9, 'bold'), padx=12, relief=tk.FLAT,
                      cursor='hand2').pack(side=tk.LEFT)

        # Миниатюра справа (кликабельная)
        if self.doc_info.exists and self.doc_info.full_path:
            suffix = self.doc_info.full_path.suffix.lower()
            if suffix in self.config.image_extensions:
                try:
                    image = Image.open(self.doc_info.full_path)
                    display_image = image.copy()
                    thumb_size = self.config.small_thumbnail_size
                    display_image.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(display_image)

                    img_label = tk.Label(main, image=photo, bg='white', cursor='hand2',
                                         relief=tk.SOLID, bd=1)
                    img_label.image = photo
                    img_label.pack(side=tk.RIGHT, padx=(10, 0))
                    img_label.bind('<Button-1>', lambda e: self._on_click())
                except Exception:
                    self._build_thumbnail(main)
            elif suffix == '.pdf':
                self._build_thumbnail(main)
            else:
                self._build_placeholder(main)

    def _build_thumbnail(self, parent: tk.Widget) -> None:
        """Миниатюра PDF (первая страница) — кликабельная, как у изображений."""
        thumb = self.doc_service.load_pdf_thumbnail(
            self.doc_info.full_path, self.config.small_thumbnail_size
        )
        if thumb is None:
            self._build_placeholder(parent)
            return
        img_label = tk.Label(parent, image=thumb, bg='white', cursor='hand2',
                             relief=tk.SOLID, bd=1)
        img_label.image = thumb
        img_label.pack(side=tk.RIGHT, padx=(10, 0))
        img_label.bind('<Button-1>', lambda e: self._on_click())

    def _build_placeholder(self, parent: tk.Widget) -> None:
        """Плейсхолдер для не-изображений (PDF и др.) — кликабельный."""
        btn = tk.Button(parent, text="открыть", font=(FONT_FAMILY, 9, 'bold'), bg='#f0f0f0',
                        cursor='hand2', command=self._on_click)
        btn.pack(side=tk.RIGHT, padx=(10, 0))

    def _on_click(self) -> None:
        if self.on_open and self.doc_info.full_path:
            self.on_open(self.doc_info.full_path)

    def _replace(self) -> None:
        """Вызвать колбэк перезаливки документа."""
        if self.on_replace:
            self.on_replace()

    def _download(self) -> None:
        """Сохранить документ в выбранную пользователем директорию."""
        if not self.doc_info.full_path:
            return
        source = self.doc_info.full_path
        initial = self.doc_info.filename or os.path.basename(str(source))
        target = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Сохранить документ",
            initialfile=initial,
            defaultextension=os.path.splitext(initial)[1],
            filetypes=[("Все файлы", "*.*")],
        )
        if not target:
            return
        try:
            shutil.copy2(source, target)
            messagebox.showinfo(
                "Готово", f"Файл сохранён:\n{target}",
                parent=self.winfo_toplevel()
            )
        except Exception as e:
            messagebox.showerror(
                "Ошибка", f"Не удалось сохранить файл:\n{e}",
                parent=self.winfo_toplevel()
            )
"""
Виджеты UI: карточка сотрудника, просмотр документов, фото, колокольчик.
"""
from __future__ import annotations
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, List, Dict
from pathlib import Path

from PIL import Image, ImageTk

from src.config import (get_config, FONT_FAMILY, format_date, format_datetime,
                        HR_STATUS_KEYS, hr_status_style)
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
    """Виджет списка сотрудников с Treeview и фильтрацией."""

    COLUMNS = ("select", "status", "id", "name", "created_at", "citizenship",
               "manager", "customer", "object", "hr_status", "hr_status_date",
               "documents_signed")
    HEADERS = {
        "select": "✓",
        "status": "Статус бота",
        "id": "ID",
        "name": "ФИО",
        "created_at": "Дата",
        "citizenship": "Категория",
        "manager": "Менеджер",
        "customer": "Заказчик",
        "object": "Объект",
        "hr_status": "HR-статус",
        "hr_status_date": "Дата",
        "documents_signed": "Док. подписаны",
    }
    COLUMN_WIDTHS = {
        "select": 34,
        "status": 95,
        "id": 70,
        "name": 200,
        "created_at": 100,
        "citizenship": 90,
        "manager": 120,
        "customer": 110,
        "object": 150,
        "hr_status": 110,
        "hr_status_date": 95,
        "documents_signed": 70,
    }

    def __init__(self, parent: tk.Widget,
                 on_select: Optional[Callable[[Worker], None]] = None,
                 on_double_click: Optional[Callable[[Worker], None]] = None):
        super().__init__(parent)
        self.on_select = on_select
        self.on_double_click = on_double_click
        self.config = get_config()
        self.workers: List[Worker] = []
        self._selected_ids: set = set()
        self._sort_column: str = "id"
        self._sort_reverse: bool = False
        self._filter_text: str = ""

        # Фильтр
        filter_frame = tk.Frame(self, bg='#ecf0f1', height=28)
        filter_frame.pack(fill=tk.X, padx=2, pady=(2, 0))
        filter_frame.pack_propagate(False)

        tk.Label(filter_frame, text="Фильтр:", bg='#ecf0f1',
                 font=(FONT_FAMILY, 8)).pack(side=tk.LEFT, padx=4)
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", self._on_filter_change)
        filter_entry = tk.Entry(filter_frame, textvariable=self._filter_var,
                                font=(FONT_FAMILY, 9), width=20)
        filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Treeview
        style = ttk.Style()
        style.configure("Custom.Treeview", font=(FONT_FAMILY, 9), rowheight=24)
        style.configure("Custom.Treeview.Heading", font=(FONT_FAMILY, 8, 'bold'))

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.COLUMNS, show="headings",
            selectmode="browse", style="Custom.Treeview"
        )

        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col],
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=self.COLUMN_WIDTHS[col], minwidth=40)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for key in HR_STATUS_KEYS:
            self.tree.tag_configure(f"hr_{key}", background=hr_status_style(key)['bg'])
        self.tree.tag_configure("archived", foreground='#9CA3AF')

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-Button-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")

    def _on_tree_click(self, event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":  # колонка чекбоксов
                iid = self.tree.identify_row(event.y)
                if iid:
                    self._toggle_select(iid)

    def _sort_by(self, column: str) -> None:
        if column == "select":
            self._toggle_all()
            return
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        self._update_headers()
        self._apply_sort()

    def _on_filter_change(self, *_args) -> None:
        self._filter_text = self._filter_var.get().strip().lower()
        self._refresh_tree()

    def _update_headers(self) -> None:
        arrow = " ▲" if not self._sort_reverse else " ▼"
        for col in self.COLUMNS:
            base = self.HEADERS[col]
            text = base + (arrow if col == self._sort_column else "")
            self.tree.heading(col, text=text)

    def _get_sort_key(self, worker: Worker):
        val = getattr(worker, self._sort_column, "")
        if self._sort_column == "created_at":
            return val or ""
        if self._sort_column == "id":
            return val
        return (val or "").lower()

    def _apply_sort(self) -> None:
        self.workers.sort(key=self._get_sort_key, reverse=self._sort_reverse)
        self._refresh_tree()

    def _toggle_select(self, iid: str) -> None:
        if iid in self._selected_ids:
            self._selected_ids.discard(iid)
        else:
            self._selected_ids.add(iid)
        checked = "☑" if iid in self._selected_ids else "☐"
        self.tree.set(iid, "select", checked)

    def _toggle_all(self) -> None:
        visible_ids = list(self.tree.get_children())
        if not visible_ids:
            return
        all_selected = all(iid in self._selected_ids for iid in visible_ids)
        if all_selected:
            self._selected_ids.clear()
        else:
            self._selected_ids = set(visible_ids)
        for iid in visible_ids:
            checked = "☑" if iid in self._selected_ids else "☐"
            self.tree.set(iid, "select", checked)

    def get_selected_workers(self) -> List[Worker]:
        """Вернуть отмеченные анкеты (или все видимые, если ничего не выбрано)."""
        if self._selected_ids:
            return [w for w in self.workers if w.id in self._selected_ids]
        return list(self.workers)

    def _matches_filter(self, worker: Worker) -> bool:
        if not self._filter_text:
            return True
        f = self._filter_text
        fields = [
            worker.status, worker.id, worker.name,
            worker.created_at or "", worker.citizenship,
            worker.manager, worker.customer, worker.object,
            worker.legal_entity, worker.hr_status,
        ]
        return any(f in (v or "").lower() for v in fields)

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        icon_map = self.config.status_icons
        for worker in self.workers:
            if not self._matches_filter(worker):
                continue
            icon = icon_map.get(worker.status, "?")
            hr_style = hr_status_style(worker.hr_status)
            status_key = worker.hr_status if worker.hr_status in HR_STATUS_KEYS else 'not_processed'
            tags = (f"hr_{status_key}",)
            if worker.is_archived:
                tags = tags + ("archived",)
            checked = "☑" if worker.id in self._selected_ids else "☐"
            self.tree.insert("", tk.END, iid=worker.id,
                             tags=tags, values=(
                checked, icon, worker.id, worker.name, format_date(worker.created_at),
                worker.citizenship, worker.manager, worker.customer, worker.object,
                hr_style['label'],
                format_date(worker.hr_status_date),
                "☑" if worker.documents_signed == "1" else "☐",
            ))

    def set_workers(self, workers: List[Worker]) -> None:
        self.workers = workers
        # Выделение сохраняем для анкет, которые остались в списке
        ids = {w.id for w in workers}
        self._selected_ids &= ids
        self._apply_sort()

    def _on_select(self, event) -> None:
        if not self.on_select:
            return
        sel = self.tree.selection()
        if sel:
            wid = sel[0]
            for w in self.workers:
                if w.id == wid:
                    self.on_select(w)
                    break

    def _on_double_click(self, event) -> None:
        if not self.on_double_click:
            return
        sel = self.tree.selection()
        if sel:
            wid = sel[0]
            for w in self.workers:
                if w.id == wid:
                    self.on_double_click(w)
                    break

    def select_by_id(self, worker_id: str) -> None:
        if self.tree.exists(worker_id):
            self.tree.selection_set(worker_id)
            self.tree.see(worker_id)


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

        hr_style = hr_status_style(self.worker.hr_status)
        tk.Label(top, text=hr_style['label'], font=(FONT_FAMILY, 9, 'bold'),
                 bg=hr_style['bg'], fg=hr_style['fg'], padx=8, pady=2
                 ).pack(side=tk.RIGHT)

        # Инфо
        info = tk.Frame(self, bg='white')
        info.pack(fill=tk.X, pady=(5, 0))

        info_items = [
            f"Должность: {self.worker.position}",
            f"Объект: {self.worker.object}",
            f"Заказчик: {self.worker.customer}",
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
            fmt = format_datetime(self.doc_info.uploaded_at)
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
"""
Сервисы: работа с документами, Telegram-уведомлениями, PDF-экспортом.
"""
from __future__ import annotations
import json
import threading
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

from src.config import (get_paths, get_config, get_bot_token, get_document_config,
                        normalize_citizenship, format_date, format_datetime,
                        HR_STATUS_LABELS)
from src.models import Worker

# Статус анкеты (поле workers.status) -> человекочитаемый перевод
STATUS_LABELS = {
    'pending': 'В ожидании',
    'accepted': 'Принят',
    'rejected': 'Отклонён',
}


# ─── Сервис документов ───

@dataclass
class DocumentInfo:
    """Информация о документе для отображения."""
    doc_type: str
    label: str
    prefix: str
    filename: str = ""
    exists: bool = False
    full_path: Optional[Path] = None
    uploaded_at: str = ""


class DocumentService:
    """Работа с файлами документов и фото."""

    def __init__(self):
        self.paths = get_paths()
        self.config = get_config()
        self._doc_flows, self._doc_labels, self._doc_prefixes = get_document_config()
        self._image_cache: Dict[str, Tuple[float, ImageTk.PhotoImage]] = {}
        self._cache_max_size = 50
        self._cache_ttl = 300.0  # 5 минут

    def get_worker_documents(self, worker: Worker) -> List[DocumentInfo]:
        """Получить список документов сотрудника с информацией о файлах."""
        from src.api_client import get_db_service
        db_docs = get_db_service().get_documents(worker.id)
        citizenship = worker.citizenship
        normalized = normalize_citizenship(citizenship)
        flow = self._doc_flows.get(normalized, self._doc_flows.get("Патент", []))

        result = []
        for doc in flow:
            entries = db_docs.get(doc.key, [])
            if isinstance(entries, dict):
                entries = [entries]
            if not entries:
                result.append(DocumentInfo(
                    doc_type=doc.key, label=doc.label, prefix=doc.prefix,
                ))
                continue
            for i, entry in enumerate(entries, 1):
                filename = entry.get('filename', '') if isinstance(entry, dict) else str(entry)
                uploaded_at = entry.get('created_at', '') if isinstance(entry, dict) else ''
                label = doc.label + (f" ({i})" if len(entries) > 1 else "")
                info = DocumentInfo(
                    doc_type=doc.key,
                    label=label,
                    prefix=doc.prefix,
                    filename=filename,
                    uploaded_at=uploaded_at,
                )
                info.full_path = self._find_document_file(worker.id, doc.prefix, filename)
                info.exists = info.full_path is not None
                result.append(info)
        return result

    def _find_document_file(self, worker_id: str, prefix: str,
                            filename: str | None = None) -> Optional[Path]:
        """Найти файл документа по префиксу и ID (или по точному имени)."""
        from src.api_client import get_db_service
        api = get_db_service()
        if filename:
            path = api.download_file(worker_id, filename)
            if path:
                return path
        for ext in self.config.image_extensions + ['.pdf']:
            path = api.download_file(worker_id, f"{prefix}{ext}")
            if path:
                return path
        return None

    def find_photo(self, worker_id: str) -> Optional[Path]:
        """Найти фото сотрудника."""
        return self._find_document_file(worker_id, "photo")

    def replace_document(self, worker: Worker, doc_type: str,
                         old_filename: str, new_file_path: Path) -> bool:
        """Перезалить документ анкеты из UI."""
        from src.api_client import get_db_service
        api = get_db_service()
        return api.replace_document(worker.id, doc_type, old_filename, new_file_path)

    def _cache_get(self, cache_key: str) -> Optional[ImageTk.PhotoImage]:
        """Запись из кэша, если она не старше TTL."""
        entry = self._image_cache.get(cache_key)
        if not entry:
            return None
        stamp, photo = entry
        if time.monotonic() - stamp > self._cache_ttl:
            del self._image_cache[cache_key]
            return None
        return photo

    def _cache_put(self, cache_key: str, photo: ImageTk.PhotoImage) -> None:
        """Положить миниатюру в кэш: вытесняем старые и по TTL, и по количеству."""
        now = time.monotonic()
        expired = [k for k, (stamp, _) in self._image_cache.items()
                   if now - stamp > self._cache_ttl]
        for key in expired:
            del self._image_cache[key]
        if len(self._image_cache) >= self._cache_max_size:
            first_key = next(iter(self._image_cache))
            del self._image_cache[first_key]
        self._image_cache[cache_key] = (now, photo)

    def load_thumbnail(self, path: Path, size: Optional[Tuple[int, int]] = None) -> Optional[ImageTk.PhotoImage]:
        """Загрузить и закэшировать миниатюру."""
        size = size or self.config.thumbnail_size
        cache_key = f"{path}:{size[0]}x{size[1]}"

        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            with Image.open(path) as image:
                image.thumbnail(size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)

            self._cache_put(cache_key, photo)
            return photo
        except Exception:
            return None

    def load_pdf_thumbnail(self, path: Path, size: Tuple[int, int] = (120, 120)) -> Optional[ImageTk.PhotoImage]:
        """Миниатюра первой страницы PDF (теми через PyMuPDF)."""
        cache_key = f"pdf:{path}:{size[0]}x{size[1]}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            import fitz
            doc = fitz.open(str(path))
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=60)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            image.thumbnail(size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            self._cache_put(cache_key, photo)
            return photo
        except Exception:
            return None

    def open_file(self, path: Path) -> bool:
        """Открыть файл в системе."""
        import subprocess
        import platform

        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(["cmd", "/c", "start", "", str(path)], shell=True, check=False)
            elif system == "Darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
            return True
        except Exception:
            return False

    def get_document_label(self, doc_key: str) -> str:
        """Получить человекочитаемое название документа."""
        return self._doc_labels.get(doc_key, doc_key)

    def clear_cache(self) -> None:
        """Очистить кэш изображений."""
        self._image_cache.clear()


# ─── Сервис Telegram уведомлений ───

class TelegramService:
    """Асинхронная отправка уведомлений в Telegram."""

    def __init__(self):
        self.config = get_config()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="telegram")
        self._bot_token: Optional[str] = None

    def _get_token(self) -> Optional[str]:
        if self._bot_token is None:
            self._bot_token = get_bot_token()
        return self._bot_token

    def send_rejection(self, worker: Worker, reasons: List[str], callback: Optional[Callable[[bool, str], None]] = None) -> None:
        """Отправить уведомление об отклонении асинхронно."""
        self._executor.submit(self._send_rejection_sync, worker, reasons, callback)

    def _send_rejection_sync(self, worker: Worker, reasons: List[str], callback: Optional[Callable[[bool, str], None]]) -> None:
        from src.logging_config import log_info, log_error

        token = self._get_token()
        if not token:
            log_error("Telegram token not found")
            if callback:
                callback(False, "Токен бота не найден")
            return

        telegram_id = worker.telegram_id
        if not telegram_id:
            log_error(f"Worker {worker.id} has no telegram_id")
            if callback:
                callback(False, "У сотрудника нет telegram_id")
            return

        # Русские названия полей
        field_labels = {
            'name': 'ФИО', 'citizenship': 'Категория', 'gender': 'Пол',
            'position': 'Должность', 'object': 'Объект', 'customer': 'Заказчик',
            'object_address': 'Адрес',
            'manager': 'Менеджер', 'phone_main': 'Основной телефон',
            'phone_additional': 'Доп. телефон',
            'date': 'Дата рождения',
        }
        doc_labels = get_document_config()[1]
        field_labels.update(doc_labels)

        def _fmt(r):
            rkey = r.get('key', '') if isinstance(r, dict) else str(r)
            rcomment = r.get('comment', '') if isinstance(r, dict) else ''
            line = f"  - {field_labels.get(rkey, rkey)}"
            if rcomment:
                line += f"\n    📝 {rcomment}"
            return line

        reasons_text = "\n".join(_fmt(r) for r in reasons)
        # Уведомления об отказе отправляются фоновой задачей бота
        # (check_rejected_workers в bot/bot.py). UI не дублирует отправку,
        # чтобы пользователь не получал одно и то же уведомление дважды.
        log_info(f"Rejection for worker {worker.id} (chat_id={telegram_id}) "
                 f"will be sent by bot background task; reasons: {reasons_text}")
        if callback:
            callback(True, "Уведомление будет отправлено ботом")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


# ─── Сервис PDF экспорта ───

class PDFExportService:
    """Генерация PDF карточки сотрудника."""

    def __init__(self):
        self.config = get_config()
        self.paths = get_paths()
        self.doc_service = DocumentService()
        self._font_name = "Helvetica"
        self._font_registered = False

    def _draw_worker_card(self, c, worker, y, width, height):
        """Нарисовать карточку одного сотрудника на холсте c, начиная с y."""
        c.setFont(self._font_name, 16)
        c.drawString(50, y, "Карточка сотрудника")
        y -= 30

        c.setFont(self._font_name, 12)
        c.drawString(50, y, f"ФИО: {worker.name}")
        y -= 20
        c.drawString(50, y, f"ИД: {worker.id}")
        y -= 20
        c.drawString(50, y, f"Категория: {worker.citizenship}")
        y -= 20

        profile = [
            ('gender', 'Пол'), ('date', 'Дата рождения'),
            ('manager', 'Менеджер'), ('object', 'Объект'),
            ('customer', 'Заказчик'), ('legal_entity', 'Юр. лицо'),
            ('object_address', 'Адрес'), ('position', 'Должность'),
            ('phone_main', 'Телефон'), ('phone_additional', 'Доп. телефон'),
        ]
        for key, label in profile:
            val = getattr(worker, key, '')
            if val:
                if key == 'date':
                    val = format_date(val)
                c.drawString(50, y, f"{label}: {val}")
                y -= 18

        # Фото — в правом верхнем углу (поверх всего)
        if worker.id:
            photo_path = self.doc_service.find_photo(worker.id)
            if photo_path:
                try:
                    from reportlab.lib.utils import ImageReader
                    img = ImageReader(str(photo_path))
                    photo_x = width - 50 - 80
                    photo_y = height - 50 - 80
                    c.drawImage(img, photo_x, photo_y, width=80, height=80,
                                preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass

        # Документы (только текст, без миниатюр)
        y -= 20
        citizenship = worker.citizenship
        normalized = normalize_citizenship(citizenship)
        if normalized in self.doc_service._doc_flows:
            c.setFont(self._font_name, 14)
            c.drawString(50, y, f"Документы ({citizenship}):")
            y -= 25
            c.setFont(self._font_name, 10)

            from src.api_client import get_db_service
            db_docs = get_db_service().get_documents(worker.id)

            for doc in self.doc_service._doc_flows[normalized]:
                entries = db_docs.get(doc.key, [])
                if isinstance(entries, str):
                    entries = [{'filename': entries, 'created_at': ''}]
                elif isinstance(entries, dict):
                    entries = [entries]
                if entries and worker.id:
                    filename_doc = (entries[0].get('filename', '')
                                    if isinstance(entries[0], dict) else str(entries[0]))

                    c.drawString(70, y, f"{doc.label}: {filename_doc}")
                    if len(entries) > 1:
                        c.drawString(70, y - 12, f"  + ещё {len(entries) - 1} файл(а)")
                    y -= 70
                else:
                    c.drawString(70, y, f"{doc.label}: —")
                    y -= 18

        # Замечания
        if worker.is_rejected and worker.reasons:
            y -= 10
            c.setFont(self._font_name, 12)
            c.drawString(50, y, "⚠ Замечания:")
            y -= 20
            c.setFont(self._font_name, 10)
            for r in worker.reasons:
                rkey = r.get('key', '') if isinstance(r, dict) else str(r)
                rcomment = r.get('comment', '') if isinstance(r, dict) else ''
                label = self.doc_service.get_document_label(rkey)
                c.drawString(70, y, f"• {label}")
                y -= 16
                if rcomment:
                    c.drawString(85, y, f"📝 {rcomment}")
                    y -= 16

        # Встречи
        from src.api_client import get_db_service
        meetings = get_db_service().get_meetings(worker.id)
        if meetings:
            y -= 10
            c.setFont(self._font_name, 12)
            c.drawString(50, y, "Встречи:")
            y -= 20
            c.setFont(self._font_name, 10)
            for m in meetings:
                meeting_date = format_datetime(m.get('date', ''))
                text = f"• {meeting_date} — {m['note']}" if meeting_date else f"• {m['note']}"
                c.drawString(70, y, text)
                y -= 16

        return y

    def export(self, worker: Worker, output_path: Path,
               progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str]:
        """Экспортировать одну карточку в PDF (одна анкета на странице)."""
        try:
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            return False, "Библиотека reportlab не установлена"

        self._register_font()

        c = pdf_canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4

        self._draw_worker_card(c, worker, height - 50, width, height)

        c.save()
        return True, f"PDF сохранён: {output_path}"

    def export_cards(self, workers: List[Worker], output_path: Path,
                     period_label: str = "",
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str]:
        """Экспортировать несколько карточек в один PDF (каждая на своей странице)."""
        try:
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            return False, "Библиотека reportlab не установлена"

        self._register_font()

        c = pdf_canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4

        total = len(workers)
        for idx, worker in enumerate(workers):
            if idx > 0:
                c.showPage()
            self._draw_worker_card(c, worker, height - 50, width, height)

        c.save()
        return True, f"PDF сохранён: {output_path}"

    def _register_font(self) -> None:
        """Зарегистрировать TTF шрифт для поддержки кириллицы."""
        if self._font_registered:
            return

        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Пробуем найти системные шрифты с поддержкой кириллицы
        import platform
        _system = platform.system()
        if _system == "Windows":
            font_paths = [
                "C:/Windows/Fonts/calibri.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/times.ttf",
                "C:/Windows/Fonts/verdana.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
            ]
        elif _system == "Darwin":
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
        else:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

        for fp in font_paths:
            if Path(fp).exists():
                try:
                    safe_name = "Font_" + Path(fp).stem
                    pdfmetrics.registerFont(TTFont(safe_name, fp))
                    self._font_name = safe_name
                    break
                except Exception:
                    continue

        self._font_registered = True


# ─── Сервис Excel экспорта ───

class ExcelExportService:
    """Экспорт списка анкет в Excel (.xlsx)."""

    def __init__(self):
        self.config = get_config()

    def export_list(self, workers: List[Worker], output_path: Path,
                    period_label: str = "",
                    progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str]:
        """Экспортировать список анкет в Excel — таблица со столбцами списка."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        except ImportError:
            return False, "Библиотека openpyxl не установлена"

        wb = Workbook()
        ws = wb.active
        ws.title = "Список сотрудников"

        # Заголовок документа
        ws["A1"] = "Список сотрудников"
        ws["A1"].font = Font(bold=True, size=14)
        row = 2
        if period_label:
            ws.cell(row=row, column=1, value=f"Период: {period_label}").font = Font(size=11, italic=True)
            row += 1
        row += 1  # пустая строка

        header_row = row
        columns = [
            ("ID", "id"),
            ("ФИО", "name"),
            ("Категория", "citizenship"),
            ("Менеджер", "manager"),
            ("Заказчик", "customer"),
            ("Объект", "object"),
            ("HR-статус", "hr_status"),
            ("Дата HR", "hr_status_date"),
            ("Док. подписаны", "documents_signed"),
            ("Статус анкеты", "status"),
            ("Телефон", "phone_main"),
            ("Дата рожд.", "date"),
        ]

        # Стили заголовка
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="2C3E50")
        thin = Side(style="thin", color="B0B0B0")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col_idx, (label, _) in enumerate(columns, start=1):
            cell = ws.cell(row=header_row, column=col_idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border

        # Данные
        for idx, worker in enumerate(workers, start=header_row + 1):
            hr_label = HR_STATUS_LABELS.get(worker.hr_status, worker.hr_status)
            status_label = STATUS_LABELS.get(worker.status, worker.status)
            signed = "Да" if worker.documents_signed == "1" else "Нет"
            values = [
                worker.id or "",
                worker.name or "",
                worker.citizenship or "",
                worker.manager or "",
                worker.customer or "",
                worker.object or "",
                hr_label,
                format_date(worker.hr_status_date) if worker.hr_status_date else "",
                signed,
                status_label,
                worker.phone_main or "",
                format_date(worker.date) if worker.date else "",
            ]
            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=idx, column=col_idx, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                if idx % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor="F2F2F2")

        # Ширина колонок
        widths = [8, 26, 14, 16, 16, 20, 16, 12, 14, 16, 16, 14]
        for col_idx, width in enumerate(widths, start=1):
            ws.column_dimensions[chr(64 + col_idx)].width = width

        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

        wb.save(str(output_path))
        return True, f"Excel сохранён: {output_path}"


# Глобальные экземпляры сервисов (ленивые)
_doc_service: Optional[DocumentService] = None
_telegram_service: Optional[TelegramService] = None
_pdf_service: Optional[PDFExportService] = None
_excel_service: Optional[ExcelExportService] = None


def get_document_service() -> DocumentService:
    global _doc_service
    if _doc_service is None:
        _doc_service = DocumentService()
    return _doc_service


def get_telegram_service() -> TelegramService:
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service


def get_pdf_service() -> PDFExportService:
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFExportService()
    return _pdf_service


def get_excel_service() -> ExcelExportService:
    global _excel_service
    if _excel_service is None:
        _excel_service = ExcelExportService()
    return _excel_service
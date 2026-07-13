"""
Сервисы: работа с документами, Telegram-уведомлениями, PDF-экспортом.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
import threading
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

from src.config import get_paths, get_config, get_bot_token, get_document_config
from src.database import get_db_service
from src.models import Worker


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


class DocumentService:
    """Работа с файлами документов и фото."""

    def __init__(self):
        self.paths = get_paths()
        self.config = get_config()
        self._doc_flows, self._doc_labels, self._doc_prefixes = get_document_config()
        self._image_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._cache_max_size = 50

    def get_worker_documents(self, worker: Worker) -> List[DocumentInfo]:
        """Получить список документов сотрудника с информацией о файлах."""
        db_docs = get_db_service().documents.get_by_worker(worker.id)
        citizenship = worker.citizenship
        # Нормализация citizenship для совпадения с ключами DOC_FLOWS
        citizenship_map = {
            'Российская Федерация': 'Россия',
            'РФ': 'Россия',
        }
        normalized = citizenship_map.get(citizenship, citizenship)
        flow = self._doc_flows.get(normalized, self._doc_flows.get("Патент", []))

        result = []
        for doc in flow:
            filename = db_docs.get(doc.key, "")
            info = DocumentInfo(
                doc_type=doc.key,
                label=doc.label,
                prefix=doc.prefix,
                filename=filename,
            )
            if filename:
                info.full_path = self._find_document_file(worker.id, doc.prefix)
                info.exists = info.full_path is not None
            result.append(info)
        return result

    def _find_document_file(self, worker_id: str, prefix: str) -> Optional[Path]:
        """Найти файл документа по префиксу и ID."""
        worker_dir = self.paths.docs_dir / worker_id
        if not worker_dir.exists():
            return None
        for ext in self.config.image_extensions:
            path = worker_dir / f"{prefix}{ext}"
            if path.exists():
                return path
        return None

    def find_photo(self, worker_id: str) -> Optional[Path]:
        """Найти фото сотрудника."""
        return self._find_document_file(worker_id, "photo")

    def load_thumbnail(self, path: Path, size: Optional[Tuple[int, int]] = None) -> Optional[ImageTk.PhotoImage]:
        """Загрузить и закэшировать миниатюру."""
        size = size or self.config.thumbnail_size
        cache_key = f"{path}:{size[0]}x{size[1]}"

        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        try:
            image = Image.open(path)
            image.thumbnail(size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            # Ограничение размера кэша
            if len(self._image_cache) >= self._cache_max_size:
                first_key = next(iter(self._image_cache))
                del self._image_cache[first_key]

            self._image_cache[cache_key] = photo
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
            'name': 'ФИО', 'citizenship': 'Гражданство', 'gender': 'Пол',
            'position': 'Должность', 'object': 'Объект', 'object_address': 'Адрес',
            'manager': 'Менеджер', 'phone_main': 'Основной телефон',
            'phone_additional': 'Доп. телефон', 'email': 'Email',
            'date': 'Дата рождения', 'registration': 'Регистрация',
        }
        doc_labels = get_document_config()[1]
        field_labels.update(doc_labels)
        reasons_text = "\n".join(f"  - {field_labels.get(r, r)}" for r in reasons)
        text = (
            f"❌ Ваша анкета #{worker.id} отклонена.\n\n"
            f"Необходимо исправить:\n{reasons_text}"
        )

        import json as _json
        keyboard = _json.dumps({
            "inline_keyboard": [[
                {"text": "✏️ Исправить анкету", "callback_data": f"fix_rejected:{worker.id}"},
                {"text": "📝 Новая анкета", "callback_data": f"new_rejected:{worker.id}"},
            ]]
        })

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": telegram_id,
            "text": text,
            "reply_markup": keyboard,
        }).encode()

        try:
            log_info(f"Sending rejection to chat_id={telegram_id}, worker={worker.id}")
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=self.config.telegram_timeout) as resp:
                result = resp.read().decode()
                log_info(f"Telegram API response: {resp.status} - {result}")
                if callback:
                    callback(True, "Уведомление отправлено")
        except Exception as e:
            log_error(f"Telegram send error: {e}")
            if callback:
                callback(False, f"Ошибка отправки: {e}")

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

    def export(self, worker: Worker, output_path: Path,
               progress_callback: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str]:
        """
        Экспортировать карточку в PDF.

        Args:
            worker: Сотрудник
            output_path: Путь для сохранения
            progress_callback: Функция обратного вызова (current, total)
        """
        try:
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.utils import ImageReader
        except ImportError:
            return False, "Библиотека reportlab не установлена"

        self._register_font()

        c = pdf_canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        y = height - 50

        # Подсчет общего количества элементов для прогресса
        total_items = self._count_pdf_items(worker)
        current_item = 0

        def update_progress():
            nonlocal current_item
            current_item += 1
            if progress_callback:
                progress_callback(current_item, total_items)

        c.setFont(self._font_name, 16)
        c.drawString(50, y, "Карточка сотрудника")
        update_progress()

        y -= 30
        c.setFont(self._font_name, 12)
        c.drawString(50, y, f"ФИО: {worker.name}")
        update_progress()
        y -= 20
        c.drawString(50, y, f"ИД: {worker.id}")
        update_progress()
        y -= 20
        c.drawString(50, y, f"Гражданство: {worker.citizenship}")
        update_progress()
        y -= 20

        # Основные поля
        profile = [
            ('gender', 'Пол'), ('position', 'Должность'),
            ('object', 'Объект'), ('object_address', 'Адрес'),
            ('manager', 'Менеджер'), ('phone_main', 'Телефон'),
            ('phone_additional', 'Доп. телефон'), ('email', 'Email'),
            ('date', 'Дата рождения'), ('registration', 'Регистрация'),
        ]
        for key, label in profile:
            val = getattr(worker, key, '')
            if val:
                c.drawString(50, y, f"{label}: {val}")
                update_progress()
                y -= 18

        # Фото
        if worker.id:
            photo_path = self.doc_service.find_photo(worker.id)
            if photo_path:
                try:
                    img = ImageReader(str(photo_path))
                    c.drawImage(img, 450, y - 10, width=80, height=80,
                                preserveAspectRatio=True, mask='auto')
                    update_progress()
                    y -= 100
                except Exception:
                    pass

        # Документы
        update_progress()
        y -= 20
        citizenship = worker.citizenship
        citizenship_map = {'Российская Федерация': 'Россия', 'РФ': 'Россия'}
        normalized = citizenship_map.get(citizenship, citizenship)
        if normalized in self.doc_service._doc_flows:
            c.setFont(self._font_name, 14)
            c.drawString(50, y, f"Документы ({citizenship}):")
            update_progress()
            y -= 25
            c.setFont(self._font_name, 10)

            db_docs = get_db_service().documents.get_by_worker(worker.id)

            for doc in self.doc_service._doc_flows[citizenship]:
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont(self._font_name, 10)
                    update_progress()

                filename_doc = db_docs.get(doc.key, '')
                if filename_doc and worker.id:
                    doc_path = None
                    worker_dir = self.paths.docs_dir / worker.id
                    if worker_dir.exists():
                        for ext in self.config.image_extensions:
                            tp = worker_dir / f"{doc.prefix}{ext}"
                            if tp.exists():
                                doc_path = tp
                                break

                    c.drawString(70, y, f"{doc.label}: {filename_doc}")
                    update_progress()
                    if doc_path:
                        try:
                            img = ImageReader(str(doc_path))
                            c.drawImage(img, 450, y - 5, width=60, height=60,
                                        preserveAspectRatio=True, mask='auto')
                        except Exception:
                            pass
                    y -= 70
                else:
                    c.drawString(70, y, f"{doc.label}: —")
                    update_progress()
                    y -= 18

        # Замечания
        if worker.is_rejected and worker.reasons:
            update_progress()
            y -= 10
            c.setFont(self._font_name, 12)
            c.drawString(50, y, "⚠ Замечания:")
            update_progress()
            y -= 20
            c.setFont(self._font_name, 10)
            for r in worker.reasons:
                label = self.doc_service.get_document_label(r)
                c.drawString(70, y, f"• {label}")
                update_progress()
                y -= 16

        # Встречи
        meetings = get_db_service().meetings.get_by_worker(worker.id)
        if meetings:
            update_progress()
            y -= 10
            c.setFont(self._font_name, 12)
            c.drawString(50, y, "Встречи:")
            update_progress()
            y -= 20
            c.setFont(self._font_name, 10)
            for m in meetings:
                text = f"• {m['date']} — {m['note']}" if m['date'] else f"• {m['note']}"
                c.drawString(70, y, text)
                update_progress()
                y -= 16

        c.save()
        return True, f"PDF сохранён: {output_path}"

    def _count_pdf_items(self, worker: Worker) -> int:
        """Подсчет общего количества элементов для прогресса."""
        count = 10  # базовые поля
        if self.doc_service.find_photo(worker.id):
            count += 1
        citizenship = worker.citizenship
        citizenship_map = {'Российская Федерация': 'Россия', 'РФ': 'Россия'}
        normalized = citizenship_map.get(citizenship, citizenship)
        if normalized in self.doc_service._doc_flows:
            db_docs = get_db_service().documents.get_by_worker(worker.id)
            for doc in self.doc_service._doc_flows[normalized]:
                count += 1
        if worker.is_rejected and worker.reasons:
            count += len(worker.reasons) + 1
        meetings = get_db_service().meetings.get_by_worker(worker.id)
        if meetings:
            count += len(meetings) + 1
        return count

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


# Глобальные экземпляры сервисов (ленивые)
_doc_service: Optional[DocumentService] = None
_telegram_service: Optional[TelegramService] = None
_pdf_service: Optional[PDFExportService] = None


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
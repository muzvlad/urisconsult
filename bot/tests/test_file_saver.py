"""
Тесты для bot/services/file_saver.py — FileSaver (сохранение файлов документов).
"""
import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import file_saver  # noqa: E402
import services.file_saver as file_saver_module  # noqa: E402


@pytest.fixture
def temp_dirs(tmp_path, monkeypatch):
    """Временные папки для DOCS_DIR и temp-файлов."""
    docs_dir = tmp_path / "Users" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # file_saver импортирует DOCS_DIR на уровне модуля — патчим напрямую
    monkeypatch.setattr(file_saver_module, "DOCS_DIR", str(docs_dir))

    yield str(docs_dir), str(temp_dir)


@pytest.mark.asyncio
async def test_validate_file_too_large(temp_dirs):
    """Слишком большой файл → False + сообщение."""
    docs_dir, temp_dir = temp_dirs
    _, _ = docs_dir, temp_dir

    is_valid, msg = file_saver_module.FileSaver.validate_file(
        "dummy.jpg", file_size=file_saver_module.MAX_FILE_SIZE + 1
    )
    assert is_valid is False
    assert "слишком большой" in msg.lower()


@pytest.mark.asyncio
async def test_validate_file_bad_extension(temp_dirs):
    """Недопустимое расширение → False + сообщение."""
    is_valid, msg = file_saver_module.FileSaver.validate_file("dummy.xyz", file_size=100)
    assert is_valid is False
    assert "недопустимый" in msg.lower()


@pytest.mark.asyncio
async def test_validate_file_ok(temp_dirs):
    """Корректный файл → True + пустая строка."""
    is_valid, msg = file_saver_module.FileSaver.validate_file("photo.jpg", file_size=100)
    assert is_valid is True
    assert msg == ""


@pytest.mark.asyncio
async def test_save_document_single(temp_dirs):
    """Сохранение одного файла: prefix + ext."""
    docs_dir, temp_dir = temp_dirs

    # Создаём временный файл
    temp_path = os.path.join(temp_dir, "temp_upload.jpg")
    with open(temp_path, "wb") as f:
        f.write(b"fake image data")

    filename = await asyncio.to_thread(
        file_saver_module.FileSaver.save_document,
        temp_path, "00001", "passport", index=1
    )
    assert filename == "pas.jpg"

    saved_path = os.path.join(docs_dir, "00001", "pas.jpg")
    assert os.path.exists(saved_path)
    assert not os.path.exists(temp_path)  # исходный temp файл перемещён


@pytest.mark.asyncio
async def test_save_document_multi_file(temp_dirs):
    """multi_file (index > 1) → prefix_{index}.ext."""
    docs_dir, temp_dir = temp_dirs

    temp_path = os.path.join(temp_dir, "temp_upload.jpg")
    with open(temp_path, "wb") as f:
        f.write(b"fake image data")

    filename = await asyncio.to_thread(
        file_saver_module.FileSaver.save_document,
        temp_path, "00001", "russia_work_book", index=3
    )
    assert filename == "trud_3.jpg"


@pytest.mark.asyncio
async def test_save_document_temp_not_found(temp_dirs):
    """Временный файл не найден → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await asyncio.to_thread(
            file_saver_module.FileSaver.save_document,
            "/nonexistent/temp.jpg", "00001", "passport", index=1
        )


@pytest.mark.asyncio
async def test_save_document_invalid_file(temp_dirs):
    """Невалидный файл (плохое расширение) → ValueError."""
    docs_dir, temp_dir = temp_dirs

    temp_path = os.path.join(temp_dir, "temp_upload.xyz")
    with open(temp_path, "wb") as f:
        f.write(b"data")

    with pytest.raises(ValueError):
        await asyncio.to_thread(
            file_saver_module.FileSaver.save_document,
            temp_path, "00001", "passport", index=1
        )


@pytest.mark.asyncio
async def test_cleanup_temp_files(temp_dirs):
    """Удаляет существующие temp-файлы, не падает на отсутствующие."""
    docs_dir, temp_dir = temp_dirs

    f1 = os.path.join(temp_dir, "a.tmp")
    f2 = os.path.join(temp_dir, "b.tmp")
    with open(f1, "w") as f:
        f.write("a")
    with open(f2, "w") as f:
        f.write("b")

    await asyncio.to_thread(
        file_saver_module.FileSaver.cleanup_temp_files,
        [f1, f2, os.path.join(temp_dir, "nonexistent.tmp")],
    )

    assert not os.path.exists(f1)
    assert not os.path.exists(f2)

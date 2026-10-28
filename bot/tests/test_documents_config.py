"""
Тесты для bot/config/documents.py — DOC_FLOWS, get_next_doc, get_doc_by_key,
DOC_PREFIXES, DOC_LABELS, get_doc_flow.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.documents import (  # noqa: E402
    DOC_FLOWS,
    DOC_PREFIXES,
    DOC_LABELS,
    get_doc_flow,
    get_next_doc,
    get_doc_by_key,
)


# ─── DOC_FLOWS ────────────────────────────────────────────────────────

def test_doc_flows_has_all_categories():
    """Все 6 категорий присутствуют."""
    expected = {"Патент", "Студент", "ЕАЭС", "РВП", "ВНЖ", "Россия"}
    assert set(DOC_FLOWS.keys()) == expected


def test_doc_flows_each_category_has_docs():
    """Каждая категория имеет хотя бы один документ."""
    for cat, docs in DOC_FLOWS.items():
        assert len(docs) > 0, f"Категория {cat} без документов"


def test_doc_flows_unique_keys():
    """Ключи документов уникальны внутри каждой категории."""
    for cat, docs in DOC_FLOWS.items():
        keys = [d.key for d in docs]
        assert len(keys) == len(set(keys)), f"Дубли ключей в категории {cat}: {keys}"


# ─── get_next_doc ─────────────────────────────────────────────────────

def test_get_next_doc_returns_next():
    """Возвращает следующий документ в цепочке."""
    flow = DOC_FLOWS["Патент"]
    first = flow[0]
    second = flow[1]
    result = get_next_doc(first.key, "Патент")
    assert result is not None
    assert result.key == second.key


def test_get_next_doc_last_returns_none():
    """Последний документ → None."""
    flow = DOC_FLOWS["Патент"]
    last = flow[-1]
    result = get_next_doc(last.key, "Патент")
    assert result is None


def test_get_next_doc_unknown_key():
    """Неизвестный ключ → None."""
    result = get_next_doc("nonexistent_key", "Патент")
    assert result is None


# ─── get_doc_by_key ───────────────────────────────────────────────────

def test_get_doc_by_key_found():
    """Находит документ по ключу."""
    result = get_doc_by_key("passport")
    assert result is not None
    assert result.key == "passport"
    assert result.label == "Паспорт"


def test_get_doc_by_key_not_found():
    """Неизвестный ключ → None."""
    result = get_doc_by_key("nonexistent_key")
    assert result is None


# ─── DOC_PREFIXES ─────────────────────────────────────────────────────

def test_doc_prefixes_all_keys():
    """Каждый ключ документа имеет префикс."""
    all_keys = set()
    for docs in DOC_FLOWS.values():
        for doc in docs:
            all_keys.add(doc.key)
    assert all_keys.issubset(set(DOC_PREFIXES.keys()))


def test_doc_prefixes_non_empty():
    """Все префиксы не пустые."""
    for prefix in DOC_PREFIXES.values():
        assert prefix != ""


# ─── DOC_LABELS ───────────────────────────────────────────────────────

def test_doc_labels_all_keys():
    """Каждый ключ документа имеет метку."""
    all_keys = set()
    for docs in DOC_FLOWS.values():
        for doc in docs:
            all_keys.add(doc.key)
    assert all_keys.issubset(set(DOC_LABELS.keys()))


# ─── get_doc_flow ─────────────────────────────────────────────────────

def test_get_doc_flow_known_category():
    """Возвращает документы для известной категории."""
    result = get_doc_flow("Патент")
    assert result == DOC_FLOWS["Патент"]


def test_get_doc_flow_unknown_category_fallback():
    """Неизвестная категория → PATENT (fallback)."""
    result = get_doc_flow("Неизвестная")
    assert result == DOC_FLOWS["Патент"]

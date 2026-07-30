"""
Тесты для bot/config/documents.py — конфигурация документов.
"""
import sys
import os
import pytest

BOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bot')
sys.path.insert(0, BOT_DIR)

from config.documents import (
    DocumentType, DOC_FLOWS, DOC_PREFIXES, DOC_LABELS, DOC_PROMPTS,
    CITIZENSHIP_DOC_KEYS, get_doc_flow, get_next_doc, get_doc_by_key,
)


class TestDocumentType:
    def test_create_document_type(self):
        doc = DocumentType(key='photo', label='Фото', prefix='photo')
        assert doc.key == 'photo'
        assert doc.label == 'Фото'
        assert doc.prefix == 'photo'
        assert doc.required is False
        assert doc.can_skip is True

    def test_document_type_required(self):
        doc = DocumentType(key='passport', label='Паспорт', prefix='pas', required=True)
        assert doc.required is True

    def test_document_type_frozen(self):
        doc = DocumentType(key='photo', label='Фото', prefix='photo')
        with pytest.raises(AttributeError):
            doc.key = 'new_key'


class TestDocFlows:
    ALL_CATEGORIES = ['Патент', 'Студент', 'ЕАЭС', 'РВП', 'ВНЖ', 'Россия']

    def test_all_categories_present(self):
        for cat in self.ALL_CATEGORIES:
            assert cat in DOC_FLOWS, f"Категория '{cat}' отсутствует"

    def test_flows_are_lists(self):
        for cat, docs in DOC_FLOWS.items():
            assert isinstance(docs, list)
            assert len(docs) > 0

    def test_photo_is_first_in_all_flows(self):
        for cat, docs in DOC_FLOWS.items():
            assert docs[0].key == 'photo'

    def test_passport_is_second_in_all_flows(self):
        for cat, docs in DOC_FLOWS.items():
            assert docs[1].key == 'passport'

    def test_unique_keys_per_category(self):
        for cat, docs in DOC_FLOWS.items():
            keys = [d.key for d in docs]
            assert len(keys) == len(set(keys))

    def test_patent_has_17_docs(self):
        assert len(DOC_FLOWS['Патент']) == 17

    def test_student_has_10_docs(self):
        assert len(DOC_FLOWS['Студент']) == 10

    def test_eaeas_has_9_docs(self):
        assert len(DOC_FLOWS['ЕАЭС']) == 9

    def test_rvp_has_7_docs(self):
        assert len(DOC_FLOWS['РВП']) == 7

    def test_vnzh_has_9_docs(self):
        assert len(DOC_FLOWS['ВНЖ']) == 9

    def test_russia_has_8_docs(self):
        assert len(DOC_FLOWS['Россия']) == 8


class TestDocPrefixes:
    def test_prefixes_exist(self):
        assert len(DOC_PREFIXES) > 0

    def test_photo_prefix(self):
        assert DOC_PREFIXES.get('photo') == 'photo'

    def test_passport_prefix(self):
        assert DOC_PREFIXES.get('passport') == 'pas'

    def test_all_flow_keys_have_prefixes(self):
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert doc.key in DOC_PREFIXES


class TestDocLabels:
    def test_labels_exist(self):
        assert len(DOC_LABELS) > 0

    def test_all_flow_keys_have_labels(self):
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert doc.key in DOC_LABELS


class TestDocPrompts:
    def test_prompts_exist(self):
        assert len(DOC_PROMPTS) > 0

    def test_all_flow_keys_have_prompts(self):
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert doc.key in DOC_PROMPTS

    def test_prompts_are_strings(self):
        for key, prompt in DOC_PROMPTS.items():
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestCitizenshipDocKeys:
    def test_keys_exist(self):
        for cat in DOC_FLOWS:
            assert cat in CITIZENSHIP_DOC_KEYS

    def test_keys_match_flows(self):
        for cat in DOC_FLOWS:
            flow_keys = [d.key for d in DOC_FLOWS[cat]]
            assert CITIZENSHIP_DOC_KEYS[cat] == flow_keys


class TestHelperFunctions:
    def test_get_doc_flow_valid(self):
        flow = get_doc_flow('Патент')
        assert isinstance(flow, list)
        assert len(flow) == 17

    def test_get_doc_flow_invalid_returns_patent(self):
        flow = get_doc_flow('Несуществующая категория')
        assert flow == DOC_FLOWS['Патент']

    def test_get_next_doc_middle(self):
        next_doc = get_next_doc('patent_snils', 'Патент')
        assert next_doc is not None
        assert next_doc.key == 'patent_registration'

    def test_get_next_doc_last(self):
        last_doc = DOC_FLOWS['Патент'][-1]
        next_doc = get_next_doc(last_doc.key, 'Патент')
        assert next_doc is None

    def test_get_next_doc_first(self):
        next_doc = get_next_doc('photo', 'Патент')
        assert next_doc is not None
        assert next_doc.key == 'passport'

    def test_get_next_doc_invalid(self):
        next_doc = get_next_doc('nonexistent', 'Патент')
        assert next_doc is None

    def test_get_doc_by_key_valid(self):
        doc = get_doc_by_key('patent_snils')
        assert doc is not None
        assert doc.key == 'patent_snils'
        assert doc.label == 'СНИЛС'

    def test_get_doc_by_key_invalid(self):
        doc = get_doc_by_key('nonexistent')
        assert doc is None

    def test_document_type_has_category_set(self):
        """Каждый DocumentType имеет непустую category."""
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert doc.category, \
                    f"DocumentType '{doc.key}' не имеет category"

    def test_category_matches_key(self):
        """category DocumentType совпадает с ключом DOC_FLOWS."""
        valid_categories = set(DOC_FLOWS.keys())
        for cat, docs in DOC_FLOWS.items():
            for doc in docs:
                assert doc.category in valid_categories, \
                    f"DocumentType '{doc.key}': category='{doc.category}' не в {valid_categories}"
                # Проверяем что category соответствует этой ветке
                assert doc in DOC_FLOWS[doc.category], \
                    f"DocumentType '{doc.key}' не найден в DOC_FLOWS['{doc.category}']"

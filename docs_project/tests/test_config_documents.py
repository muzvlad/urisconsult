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
            # ЕАЭС использует свой тип паспорта (паспорт или ID-карта)
            expected = 'eaeas_passport' if cat == 'ЕАЭС' else 'passport'
            assert docs[1].key == expected, f"Второй документ '{cat}' ≠ {expected}"

    def test_unique_keys_per_category(self):
        for cat, docs in DOC_FLOWS.items():
            keys = [d.key for d in docs]
            assert len(keys) == len(set(keys))

    def test_patent_has_26_docs(self):
        assert len(DOC_FLOWS['Патент']) == 26

    def test_student_has_14_docs(self):
        assert len(DOC_FLOWS['Студент']) == 14

    def test_student_flow_order(self):
        """Порядок потока «Студент» соответствует ТЗ."""
        keys = [d.key for d in DOC_FLOWS['Студент']]
        expected = [
            'photo', 'passport',
            'student_passport_translation', 'student_visa', 'student_migration_card',
            'student_registration', 'student_registration_back',
            'student_fingerprint_card', 'student_fingerprint_back',
            'student_dms', 'student_snils', 'student_inn',
            'student_university_cert', 'student_bank_details',
        ]
        assert keys == expected

    def test_student_new_doc_prefixes(self):
        """Новые документы студента имеют корректные префиксы."""
        assert get_doc_by_key('student_passport_translation').prefix == 'pas_trans'
        assert get_doc_by_key('student_visa').prefix == 'visa'
        assert get_doc_by_key('student_registration_back').prefix == 'reg_back'
        assert get_doc_by_key('student_fingerprint_back').prefix == 'dactyl_back'
        assert get_doc_by_key('student_registration_back').can_skip is True

    def test_eaeas_has_13_docs(self):
        assert len(DOC_FLOWS['ЕАЭС']) == 13

    def test_rvp_has_9_docs(self):
        assert len(DOC_FLOWS['РВП']) == 9

    def test_rvp_passport_spread_docs_after_passport(self):
        """Разворот с РВП и пропиской идут сразу после паспорта."""
        keys = [d.key for d in DOC_FLOWS['РВП']]
        assert keys[2] == 'rvp_passport_rvp'
        assert keys[3] == 'rvp_passport_propiska'

    def test_vnzh_has_10_docs(self):
        assert len(DOC_FLOWS['ВНЖ']) == 10

    def test_vnzh_registration_after_vnzh(self):
        """Регистрация в ВНЖ идёт сразу после документа ВНЖ."""
        keys = [d.key for d in DOC_FLOWS['ВНЖ']]
        assert keys[3] == 'vnzh_vnzh'
        assert keys[4] == 'vnzh_registration'

    def test_work_book_multi_file(self):
        """Трудовая книжка ВНЖ и России допускает несколько файлов."""
        assert get_doc_by_key('vnzh_work_book').multi_file is True
        assert get_doc_by_key('russia_work_book').multi_file is True

    def test_vnzh_registration_prefix(self):
        assert get_doc_by_key('vnzh_registration').prefix == 'reg'

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
        assert len(flow) == 26

    def test_get_doc_flow_invalid_returns_patent(self):
        flow = get_doc_flow('Несуществующая категория')
        assert flow == DOC_FLOWS['Патент']

    def test_get_next_doc_middle(self):
        next_doc = get_next_doc('patent_snils', 'Патент')
        assert next_doc is not None
        assert next_doc.key == 'patent_bank_details'

    def test_patent_flow_order(self):
        """Порядок патентного потока соответствует ТЗ."""
        keys = [d.key for d in DOC_FLOWS['Патент']]
        expected = [
            'photo', 'passport',
            'patent_passport_translation', 'patent_migration_card',
            'patent_registration', 'patent_registration_back',
            'patent_fingerprint_front', 'patent_fingerprint_back',
            'patent_dms', 'patent_patent_front', 'patent_patent_back',
            *[f'patent_receipt_{i}' for i in range(1, 12)],
            'patent_language_cert', 'patent_inn', 'patent_snils',
            'patent_bank_details',
        ]
        assert keys == expected

    def test_patent_receipts_all_skippable(self):
        """Все чеки патента можно пропустить."""
        for i in range(1, 12):
            doc = get_doc_by_key(f'patent_receipt_{i}')
            assert doc is not None, f"Чек {i} отсутствует"
            assert doc.can_skip, f"Чек {i} должен быть пропускаемым"

    def test_patent_registration_back_skippable(self):
        """Оборотная сторона регистрации пропускается (скрин Амина — одно фото)."""
        doc = get_doc_by_key('patent_registration_back')
        assert doc is not None
        assert doc.can_skip is True

    def test_eaeas_flow_order(self):
        """Порядок ЕАЭС-потока соответствует ТЗ."""
        keys = [d.key for d in DOC_FLOWS['ЕАЭС']]
        expected = [
            'photo',
            'eaeas_passport', 'eaeas_passport_back',
            'eaeas_passport_translation',
            'eaeas_migration_card',
            'eaeas_registration', 'eaeas_registration_back',
            'eaeas_fingerprint_card', 'eaeas_fingerprint_back',
            'eaeas_dms',
            'eaeas_inn', 'eaeas_snils', 'eaeas_bank_details',
        ]
        assert keys == expected

    def test_eaeas_passport_back_skippable(self):
        """Разворот ID-карты пропускается (паспорт — одно фото)."""
        doc = get_doc_by_key('eaeas_passport_back')
        assert doc is not None
        assert doc.can_skip is True

    def test_eaeas_registration_back_skippable(self):
        """Оборотная сторона регистрации пропускается (скрин Амина — одно фото)."""
        doc = get_doc_by_key('eaeas_registration_back')
        assert doc is not None
        assert doc.can_skip is True

    def test_eaeas_labels(self):
        """Метки ЕАЭС-документов соответствуют ТЗ."""
        assert get_doc_by_key('eaeas_passport').label == 'Паспорт или идентификационная карта (лицевая)'
        assert get_doc_by_key('eaeas_passport_back').label == 'Идентификационная карта (разворот)'
        assert get_doc_by_key('eaeas_passport_translation').label == 'Перевод паспорта'
        assert get_doc_by_key('eaeas_registration').label == 'Регистрация (лицевая) / скрин Амина'
        assert get_doc_by_key('eaeas_registration_back').label == 'Регистрация (оборотная)'
        assert get_doc_by_key('eaeas_dms').label == 'Полис ДМС или ОМС'
        assert get_doc_by_key('eaeas_fingerprint_card').label == 'Дактилоскопия (лицевая)'
        assert get_doc_by_key('eaeas_fingerprint_back').label == 'Дактилоскопия (разворот)'
        assert get_doc_by_key('eaeas_passport').prefix == 'pas'
        assert get_doc_by_key('eaeas_passport_back').prefix == 'pas_back'
        assert get_doc_by_key('eaeas_fingerprint_back').prefix == 'dactyl_back'

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

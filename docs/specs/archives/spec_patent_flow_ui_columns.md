# Спека: Оптимизация патентного потока + колонки в UI

## Задача

1. **Патентный поток**: оставить только первый и последний чек, убрать селфи
2. **UI список**: заменить Listbox на Treeview с колонками для фильтрации

## Детали

### 1. Патентный поток (bot/config/documents.py)

**Было**: 26 документов (включая селфи и 11 чеков)
**Стало**: 16 документов (без селфи, чеки только 1 и 11)

Убрать:
- `_PHOTO` из потока
- `_PATENT_RECEIPT_2` — `_PATENT_RECEIPT_10`

Итоговый порядок:
1. passport
2. patent_passport_translation
3. patent_migration_card
4. patent_registration
5. patent_registration_back
6. patent_fingerprint_front
7. patent_fingerprint_back
8. patent_dms
9. patent_patent_front
10. patent_patent_back
11. patent_receipt_1
12. patent_receipt_11
13. patent_language_cert
14. patent_inn
15. patent_snils
16. patent_bank_details

### 2. UI список (UI/src/widgets.py)

**Было**: Listbox с форматом `{icon} {id} — {name}`
**Стало**: ttk.Treeview с колонками:
- Статус (иконка)
- ID
- ФИО
- Дата поступления (created_at)
- Категория (citizenship)
- Менеджер (manager)
- Объект (object)

Фильтрация: строка фильтра под заголовками (поиск по всем колонкам).

## Тесты

Обновить тесты в `test_config_documents.py`:
- `test_patent_has_26_docs` → `test_patent_has_16_docs`
- `test_patent_flow_order` — обновить ожидаемый порядок
- `test_get_doc_flow_valid` — обновить длину
- `test_photo_is_first_in_all_flows` — патент больше не начинается с photo

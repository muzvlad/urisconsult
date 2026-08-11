# Спека 007 — Порядок документов «Студент» в боте и UI

## Проблема

Текущий порядок `DOC_FLOWS['Студент']` не соответствует бизнес-требованию:

```python
_PHOTO, _PASSPORT,
_STUDENT_SNILS, _STUDENT_REGISTRATION, _STUDENT_MIGRATION_CARD,
_STUDENT_DMS, _STUDENT_INN, _STUDENT_FINGERPRINT_CARD,
_STUDENT_UNIVERSITY_CERT, _STUDENT_BANK_DETAILS,
```

Отсутствуют документы: **Перевод паспорта**, **Виза**, **Регистрация (оборотная)**, **Дактилоскопия (оборотная)**.

Требуемый порядок после паспорта:

1. Перевод паспорта
2. Виза
3. Миграционная карта
4. Регистрация — лицевая и оборотная
5. Дактилоскопия — лицевая и оборотная
6. ДМС
7. СНИЛС
8. ИНН
9. Справка из ВУЗа
10. Реквизиты

Порядок должен совпадать в боте и в UI. UI читает конфиг документов из `bot/config/documents.py`
(через `get_document_config`), поэтому правка только в конфиге бота синхронно обновляет оба.

## Решение

### 1. Новые типы документов (`bot/config/documents.py`)

По образцу ЕАЭС/Патента (лицевая + оборотная):

| key | label | prefix | can_skip |
|---|---|---|---|
| `student_passport_translation` | Перевод паспорта | `pas_trans` | — |
| `student_visa` | Виза | `visa` | — |
| `student_registration_back` | Регистрация (оборотная) | `reg_back` | True |
| `student_fingerprint_back` | Дактилоскопия (разворот) | `dactyl_back` | — |

Уточнить labels существующих лицевых сторон:
- `student_registration` → «Регистрация (лицевая)»
- `student_fingerprint_card` → «Дактилоскопия (лицевая)»

### 2. Новый порядок `DOC_FLOWS['Студент']`

```python
'Студент': [
    _PHOTO, _PASSPORT,
    _STUDENT_PASSPORT_TRANSLATION, _STUDENT_VISA, _STUDENT_MIGRATION_CARD,
    _STUDENT_REGISTRATION, _STUDENT_REGISTRATION_BACK,
    _STUDENT_FINGERPRINT_CARD, _STUDENT_FINGERPRINT_BACK,
    _STUDENT_DMS, _STUDENT_SNILS, _STUDENT_INN,
    _STUDENT_UNIVERSITY_CERT, _STUDENT_BANK_DETAILS,
],
```

Слотов: 10 → 14.

### 3. Промпты (`DOC_PROMPTS`)

- `student_passport_translation`: «📄 Отправьте перевод паспорта:»
- `student_visa`: «🛂 Отправьте визу:»
- `student_registration`: «📋 Приложите скан или фото регистрации (лицевая сторона):»
- `student_registration_back`: «📋 Приложите скан или фото регистрации (оборотная сторона) (или пропустите):»
- `student_fingerprint_card`: «🖐 Отправьте дактилоскопию (лицевая сторона):»
- `student_fingerprint_back`: «🖐 Отправьте дактилоскопию (разворот):»
- `student_snils`: «📄 Отправьте СНИЛС:»

### 4. UI

UI не хранит порядок отдельно — читает `DOC_FLOWS` из `bot/config/documents.py`. Правок в
`UI/src/*` не требуется. При сборке EXE нужно пересобрать (bundled копия конфига).

### 5. Тесты

- `docs_project/tests/test_config_documents.py`: `test_student_has_10_docs` → `test_student_has_14_docs`;
  добавить тест порядка `DOC_FLOWS['Студент']` по требуемому списку.

## Критерии приёмки

1. Порядок «Студент» в боте совпадает с требованием (после паспорта: перевод, виза, мигрантка,
   регистрация лицевая+оборотная, дактилоскопия лицевая+оборотная, ДМС, СНИЛС, ИНН, справка, реквизиты).
2. UI (dev-режим) отображает тот же порядок — читается из того же конфига.
3. Новый/обновлённый тест зелёный; весь прогон `pytest docs_project/tests/ UI/tests/` зелёный.

## Файлы

- `bot/config/documents.py` — новые типы, порядок, промпты.
- `docs_project/tests/test_config_documents.py` — тесты.
- `docs_project/CHANGELOG.md` — запись.

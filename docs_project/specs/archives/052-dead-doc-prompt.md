# Спецификация 009 — мёртвый ключ в DOC_PROMPTS

## Проблема
`bot/config/documents.py:279` ключ `'russia_propiska'`, но фактический ключ документа — `'russia_passport_propiska'` (строка 104). Подсказка никогда не покажется.

## Что изменить
Переименовать ключ в `DOC_PROMPTS` на `'russia_passport_propiska'`.

## Критерий приемки
`DOC_PROMPTS.get('russia_passport_propiska')` возвращает текст, а не `None`.

## ponytail
Одна строка в словаре.

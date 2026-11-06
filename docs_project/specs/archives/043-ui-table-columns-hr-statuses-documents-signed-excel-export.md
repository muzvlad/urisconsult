# Спека 043. Таблица: колонки Заказчик и Дата, новые HR-статусы, чекбокс «Документы подписаны», список в Excel

## Цель

В десктопном UI (Tkinter):

1. В таблице списка — колонка **«Заказчик»** после «Менеджер» и колонка **«Дата»** (дата смены HR-статуса) после «HR-статус».
2. В карточке — новые HR-статусы **«Уведомить»** и **«На проверке МВД»**; поле даты HR-статуса активно для **всех** статусов, а не только «Трудоустроен»/«Уволен».
3. Отдельная галочка **«Документы подписаны»** в карточке, отражающаяся в таблице.
4. Выгрузка **списка (таблицы)** — в Excel (.xlsx); единичные анкеты (карточки) остаются в PDF, как сейчас.

## Почему

Пользователь хочет видеть заказчика и дату HR-статуса прямо в списке, расширить кадровые статусы и фиксировать факт подписания документов. Excel выбран для списка из-за удобства дальнейшей обработки таблицы; PDF оставлен только для печатных карточек.

## Изменения в данных (БД + API bot/)

### 1. Новая колонка `workers.documents_signed`

`shared/__init__.py`:
- Добавить в `WORKER_SCHEMA` колонку `documents_signed TEXT DEFAULT '0'` (хранит '0'/'1').
- Добавить в `MIGRATIONS`: `("documents_signed", "TEXT DEFAULT '0'")`.

`bot/services/db.py`:
- Бump `CURRENT_SCHEMA_VERSION` с 6 на 7.
- Добавить `_migrate_v6_to_v7`: `ALTER TABLE workers ADD COLUMN documents_signed TEXT DEFAULT '0'`.
- Функция `set_documents_signed(worker_id, value: str) -> bool`: `UPDATE workers SET documents_signed = ?, updated_at = ? WHERE id = ?`, вернуть `cursor.rowcount > 0`.
- `save_worker` (generic PUT) уже пишет все поля из `data`, достаточно добавить ключ в `personal_keys`, если понадобится массовое редактирование — не требуется для этой спеки.

### 2. Новые HR-статусы

`bot/services/db.py`:
- `HR_STATUSES = ('not_processed', 'docs_pending', 'employed', 'rejected', 'fired', 'notify', 'mvd_check')`.
- `set_hr_status(worker_id, status, date_value)`:
  - Проверка `status in HR_STATUSES` оставить.
  - Дата разрешается для **любого** статуса (убрать ограничение только employed/fired).
  - Если дата передана — проверить формат дд.мм.гггг (`_valid_hr_date`), иначе 400.
  - Если дата не передана — сохранить NULL/''. Не очищать дату автоматически при смене статуса.

`bot/api_server.py`:
- Маршрут `PUT /api/workers/<worker_id>/hr-status`: оставить проверку статуса через `db.HR_STATUSES`; валидацию даты оставить только когда она передана.
- Новый маршрут `PUT /api/workers/<worker_id>/documents-signed`, тело `{"documents_signed": "1"|"0"}`, вызов `db.set_documents_signed`.

### 3. UI config (UI/src/config.py)

`HR_STATUS_LABELS` добавить:
- `'notify': 'Уведомить'`
- `'mvd_check': 'На проверке МВД'`

`HR_STATUS_STYLES` добавить цвета (подобрать отличные от существующих):
- `'notify': {'bg': '#E0E7FF', 'fg': '#3730A3'}`
- `'mvd_check': {'bg': '#FFFBEB', 'fg': '#92400E'}`

`HR_STATUS_KEYS = list(HR_STATUS_LABELS)` — обновится автоматически.

## Изменения в UI (UI/src/)

### 4. Модель (UI/src/models.py)

`Worker`:
- Поле `documents_signed: str = "0"`.
- `to_dict()` включить `documents_signed`.
- `_dict_to_worker` в `api_client.py` прочитать `d.get("documents_signed", "0")`.

### 5. Таблица списка (UI/src/widgets.py)

`WorkerListWidget.COLUMNS`:
- Добавить `'customer'` после `'manager'` (Заказчик после Менеджера).
- Добавить `'hr_status_date'` после `'hr_status'` (Дата после HR-статуса).
- Добавить `'documents_signed'` в конец (галочка в таблице).

`HEADERS`:
- `'customer': 'Заказчик'`
- `'hr_status_date': 'Дата'`
- `'documents_signed': 'Док. подписаны'`

`COLUMN_WIDTHS`: customer 110, hr_status_date 100, documents_signed 70.

`_refresh_tree` values (в порядке COLUMNS):
`checked, icon, id, name, format_date(created_at), citizenship, manager, customer, object, hr_style['label'], format_date(hr_status_date), "☑" if documents_signed == "1" else "☐"`

`_matches_filter` fields: добавить `worker.customer`, `worker.hr_status_date`, `worker.documents_signed`.

### 6. Карточка (UI/src/main.py)

`_build_hr_block`:
- `date_entry` всегда `state='normal'` (убрать условие `required = current_key() in ('employed', 'fired')`).
- При сохранении: если дата введена — валидировать `parse_user_date`, иначе warning; отправить `date_value` (может быть '') для любого статуса.

Новый блок «Документы подписаны» (рядом с HR-статусом или в情報 блоке):
- `ttk.Checkbutton` / `tk.Checkbutton` с текстом «Документы подписаны», переменная привязана к `worker.documents_signed == '1'`.
- Кнопка «Сохранить» под блоком (или общая с HR) вызывает `self.api.set_documents_signed(worker.id, '1'/'0')`, затем `self._refresh_current_worker()`.
- В таблице отражается колонкой «Док. подписаны» (см. п. 5).

### 7. Экспорт (UI/src/main.py, UI/src/services.py)

- Кнопка верхней панели «Экспорт списка в PDF» переименовать в **«Экспорт списка в Excel»**, диалог подтверждения с периодом оставить, `asksaveasfilename` с `.xlsx`.
- Новый сервис `ExcelExportService` в `UI/src/services.py` (зависимость `openpyxl`):
  - `export_list(workers, output_path, period_label)` — лист «Список сотрудников», заголовок с периодом, затем таблица колонками: ID, ФИО, Категория, Менеджер, Заказчик, Объект, HR-статус, Дата HR, Dok. подписаны, Статус анкеты, Телефон, Дата рождения.
- «PDF» (единичная карточка / выбранные карточки) — без изменений, остаётся PDF.

`UI/src/requirements.txt`: добавить `openpyxl>=3.1.0`.

## Файлы

| Файл | Изменение |
|------|-----------|
| `shared/__init__.py` | колонка `documents_signed` в схема + миграция |
| `bot/services/db.py` | v7, `HR_STATUSES` + `notify`/`mvd_check`, `set_documents_signed`, `set_hr_status` без ограничения даты |
| `bot/api_server.py` | валидация hr-status для любого статуса, новый эндпоинт `/documents-signed` |
| `UI/src/config.py` | `HR_STATUS_LABELS`/`HR_STATUS_STYLES` с новыми статусами |
| `UI/src/models.py` | `Worker.documents_signed`, `to_dict` |
| `UI/src/api_client.py` | `_dict_to_worker` читает `documents_signed`; `set_documents_signed` |
| `UI/src/widgets.py` | COLUMNS/HEADERS/COLUMN_WIDTHS + customer, hr_status_date, documents_signed |
| `UI/src/main.py` | `_build_hr_block` дата всегда активна; блок чекбокса документов; кнопка Excel вместо PDF-списка |
| `UI/src/services.py` | новый `ExcelExportService.export_list` |
| `UI/src/requirements.txt` | `openpyxl` |
| `UI/tests/` | тест модели `documents_signed`, тест чекбокса/экрана |
| `docs_project/tests/test_db.py` | `set_documents_signed`, `set_hr_status` с новыми статусами и датой |
| `docs_project/tests/test_api.py` | эндпоинты hr-status и documents-signed |

## Критерии приёмки

- [ ] В таблице после «Менеджер» колонка «Заказчик», после «HR-статус» — «Дата».
- [ ] В карточке HR-статусы «Уведомить» и «На проверке МВД» в списке; дата активна для всех статусов.
- [ ] Чекбокс «Документы подписаны» в карточке сохраняется и показывается в таблице (☑/☐).
- [ ] Кнопка «Экспорт списка в Excel» создаёт .xlsx с текущим отфильтрованным списком и периодом.
- [ ] Кнопка «PDF» по-прежнему экспортирует карточку(ы) в PDF без изменений.
- [ ] Тесты `UI/tests` и `docs_project/tests` проходят.

## Риски

- Существующие записи получат `documents_signed = '0'` миграцией — корректно (не подписаны).
- Дата HR-статуса теперь сохраняется для любого статуса; старые логики, ожидающие дату только у employed/fired, не ломаются (date просто игнорируется).
- `openpyxl` — новая зависимость для UI; добавить в `requirements.txt` и в сборку EXE (`build_exe.py` hidden-import при необходимости).

Серийный номер: **043**.

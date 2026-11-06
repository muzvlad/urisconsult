# Спецификация 005 — заменить asyncio.run() на общий event loop в Flask API

## Проблема
`bot/api_server.py:29` `run_async` вызывает `asyncio.run(coro)` на каждый HTTP-запрос. Работает только пока у потока Flask нет запущенного event loop. При переходе на ASGI/gunicorn/другой сервер упадет с `RuntimeError: asyncio.run() cannot be called from a running event loop`.

## Что изменить
Создать один event loop в фоновом потоке при старте API и выполнять корутины через `asyncio.run_coroutine_threadsafe`, либо перевести API на `aiohttp.web`/`quart`.

## Критерий приемки
API обрабатывает запросы под сервером с уже запущенным event loop без `RuntimeError`.

## ponytail
Минимум изменений: один поток с `asyncio.new_event_loop()` + `run_coroutine_threadsafe`, не переписывать API на другой фреймворк.

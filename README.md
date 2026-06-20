# SSHelper

MVP Telegram-бот для уведомлений о новых объявлениях SS.lv (авто и недвижимость).

## Возможности MVP

- Добавление поиска по ссылке SS.lv
- Список активных поисков
- Пауза/возобновление поиска
- Удаление поиска
- Уведомления о новых объявлениях

## Технологии

- Python 3.11+
- aiogram 3
- SQLAlchemy 2
- APScheduler
- SQLite (по умолчанию)

## Быстрый старт

1. Создайте бота в @BotFather и получите токен.
2. Скопируйте `.env.example` в `.env` и заполните значения.
3. Установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

4. Запустите бота:

```bash
python -m app.main
```

## Команды

- `/start`
- `/add <ss.lv search url>`
- `/list`
- `/pause <id>`
- `/resume <id>`
- `/delete <id>`

## Переменные окружения

Смотрите `.env.example`.

## Важно

SS.lv может менять HTML-структуру страниц. В этом случае нужно обновить парсер в `app/services/ss_parser.py`.

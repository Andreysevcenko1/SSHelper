# SSHelper

MVP-скелет Telegram-бота для мониторинга новых объявлений на SS.lv.

## Стек

- Python 3.11+
- aiogram 3
- SQLAlchemy 2
- APScheduler
- aiohttp
- beautifulsoup4
- python-dotenv

## Подготовка

1. Создайте Telegram-бота через @BotFather и получите токен.
2. Скопируйте `.env.example` в `.env` и заполните переменные.
3. Установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
```

## Запуск

```bash
python -m app.main
```

## Команды

- `/start` — приветствие и подсказка.
- `/add <ss.lv search url>` — сохранить ссылку поиска для мониторинга.

## Переменные окружения

- `TELEGRAM_BOT_TOKEN` — токен бота (обязательно).
- `DATABASE_URL` — SQLAlchemy URL БД (по умолчанию `sqlite:///./sshelper.db`).
- `POLL_INTERVAL_SECONDS` — интервал опроса поисков в секундах (минимум 30).

## Что уже реализовано в MVP

- Инициализация бота и БД.
- Команды `/start` и `/add`.
- Базовый парсер страницы поиска SS.lv.
- Периодический watcher, который проверяет активные поиски и отправляет уведомление о новом верхнем объявлении.

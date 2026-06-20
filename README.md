# SSHelper

Telegram-бот для мониторинга новых объявлений на SS.lv.

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
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Запуск

```bash
python -m app.main
```

## Команды

| Команда | Описание |
|---|---|
| `/start` | Приветствие и список команд |
| `/add <url>` | Добавить поиск по ссылке с SS.lv |
| `/list` | Показать все ваши поиски с ID и статусом |
| `/pause <ID>` | Приостановить поиск |
| `/resume <ID>` | Возобновить приостановленный поиск |
| `/delete <ID>` | Удалить поиск |

### Примеры использования

```
/add https://www.ss.lv/lv/transport/cars/
/add https://www.ss.lv/lv/real-estate/flats/riga/

/list

/pause 3
/resume 3
/delete 3
```

### Формат уведомления

Когда появляется новое объявление, бот отправляет:

```
🔔 Новое объявление (поиск #1):
Название: Toyota Corolla 2019
Цена: 12 500 €
Город: Рига
🔗 https://www.ss.lv/msg/lv/...
```

## Переменные окружения

| Переменная | Обязательна | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен бота от @BotFather |
| `DATABASE_URL` | ❌ | SQLAlchemy URL БД (по умолчанию `sqlite:///./sshelper.db`) |
| `POLL_INTERVAL_SECONDS` | ❌ | Интервал опроса в секундах (минимум 30, по умолчанию 120) |

## Что реализовано

- Инициализация бота и БД.
- Команды `/start`, `/add`, `/list`, `/pause`, `/resume`, `/delete`.
- Парсер страниц поиска SS.lv (title, price, city, url).
- Периодический watcher с дедупликацией (не отправляет одно объявление дважды).
- Определение категории по URL (транспорт, недвижимость и др.).
- Логирование основных событий watcher.

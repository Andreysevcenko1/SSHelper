"""Internationalisation helpers.

Priority for resolving a user's language:
  1. Explicitly chosen language saved in the DB (user_settings.selected_language).
  2. Telegram from_user.language_code (if supported).
  3. Default: "lv" (Latvian).
"""

from __future__ import annotations

SUPPORTED_LANGS = ("lv", "ru", "en")
DEFAULT_LANG = "lv"

# ---------------------------------------------------------------------------
# Translation table
# ---------------------------------------------------------------------------

_T: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ #
    # Welcome / /start                                                     #
    # ------------------------------------------------------------------ #
    "welcome": {
        "lv": (
            "👋 Sveiki! Es esmu <b>SSHelper</b> — bots SS.lv sludinājumu "
            "uzraudzībai.\n\n"
            "<b>Pieejamās komandas:</b>\n"
            "/add &lt;saite&gt; — pievienot meklējumu\n"
            "/list — jūsu meklējumu saraksts\n"
            "/pause &lt;ID&gt; — apturēt meklējumu\n"
            "/resume &lt;ID&gt; — atsākt meklējumu\n"
            "/delete &lt;ID&gt; — dzēst meklējumu\n"
            "/filters &lt;ID&gt; — meklējuma filtri\n"
            "/lang — mainīt valodu\n\n"
            "Vai izmantojiet pogas zemāk:"
        ),
        "ru": (
            "👋 Привет! Я <b>SSHelper</b> — бот для мониторинга объявлений на SS.lv.\n\n"
            "<b>Доступные команды:</b>\n"
            "/add &lt;ссылка&gt; — добавить поиск\n"
            "/list — список ваших поисков\n"
            "/pause &lt;ID&gt; — приостановить поиск\n"
            "/resume &lt;ID&gt; — возобновить поиск\n"
            "/delete &lt;ID&gt; — удалить поиск\n"
            "/filters &lt;ID&gt; — фильтры поиска\n"
            "/lang — сменить язык\n\n"
            "Или используйте кнопки меню ниже:"
        ),
        "en": (
            "👋 Hello! I am <b>SSHelper</b> — a bot for monitoring listings on SS.lv.\n\n"
            "<b>Available commands:</b>\n"
            "/add &lt;url&gt; — add a search\n"
            "/list — your searches\n"
            "/pause &lt;ID&gt; — pause a search\n"
            "/resume &lt;ID&gt; — resume a search\n"
            "/delete &lt;ID&gt; — delete a search\n"
            "/filters &lt;ID&gt; — search filters\n"
            "/lang — change language\n\n"
            "Or use the menu buttons below:"
        ),
    },
    # ------------------------------------------------------------------ #
    # Main menu                                                            #
    # ------------------------------------------------------------------ #
    "menu_welcome": {
        "lv": "👋 <b>SSHelper</b> — SS.lv sludinājumu uzraudzība\n\nIzvēlieties darbību:",
        "ru": "👋 <b>SSHelper</b> — мониторинг объявлений SS.lv\n\nВыберите действие:",
        "en": "👋 <b>SSHelper</b> — SS.lv listing monitor\n\nChoose an action:",
    },
    # ------------------------------------------------------------------ #
    # Buttons                                                              #
    # ------------------------------------------------------------------ #
    "btn_my_searches": {
        "lv": "📋 Mani meklējumi",
        "ru": "📋 Мои поиски",
        "en": "📋 My searches",
    },
    "btn_add_search": {
        "lv": "➕ Pievienot meklējumu",
        "ru": "➕ Добавить поиск",
        "en": "➕ Add search",
    },
    "btn_language": {
        "lv": "🌐 Valoda / Language",
        "ru": "🌐 Valoda / Language",
        "en": "🌐 Valoda / Language",
    },
    "btn_back_to_menu": {
        "lv": "🏠 Uz izvēlni",
        "ru": "🏠 В меню",
        "en": "🏠 Main menu",
    },
    "btn_my_searches_short": {
        "lv": "📋 Mani meklējumi",
        "ru": "📋 Мои поиски",
        "en": "📋 My searches",
    },
    "btn_add_more": {
        "lv": "➕ Pievienot vēl",
        "ru": "➕ Добавить ещё",
        "en": "➕ Add another",
    },
    "btn_open_filters": {
        "lv": "🔍 Atvērt filtrus",
        "ru": "🔍 Открыть фильтры",
        "en": "🔍 Open filters",
    },
    "btn_back_to_search": {
        "lv": "◀️ Atpakaļ uz meklējumu",
        "ru": "◀️ Назад к поиску",
        "en": "◀️ Back to search",
    },
    "btn_pause": {
        "lv": "⏸ Pauze",
        "ru": "⏸ Пауза",
        "en": "⏸ Pause",
    },
    "btn_resume": {
        "lv": "▶️ Atsākt",
        "ru": "▶️ Возобновить",
        "en": "▶️ Resume",
    },
    "btn_delete": {
        "lv": "🗑 Dzēst",
        "ru": "🗑 Удалить",
        "en": "🗑 Delete",
    },
    "btn_filters": {
        "lv": "🔍 Filtri",
        "ru": "🔍 Фильтры",
        "en": "🔍 Filters",
    },
    "btn_show_filters": {
        "lv": "📋 Rādīt filtrus",
        "ru": "📋 Показать фильтры",
        "en": "📋 Show filters",
    },
    "btn_edit_filter": {
        "lv": "✏️ Mainīt / pievienot filtru",
        "ru": "✏️ Изменить / добавить фильтр",
        "en": "✏️ Edit / add filter",
    },
    "btn_clear_filters": {
        "lv": "🗑 Notīrīt visus filtrus",
        "ru": "🗑 Очистить все фильтры",
        "en": "🗑 Clear all filters",
    },
    "btn_cancel": {
        "lv": "❌ Atcelt",
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
    },
    "btn_next_page": {
        "lv": "Nāk. ▶️",
        "ru": "След. ▶️",
        "en": "Next ▶️",
    },
    "btn_prev_page": {
        "lv": "◀️ Iepr.",
        "ru": "◀️ Пред.",
        "en": "◀️ Prev",
    },
    "btn_edit_more": {
        "lv": "✏️ Mainīt vēl",
        "ru": "✏️ Изменить ещё",
        "en": "✏️ Edit more",
    },
    # ------------------------------------------------------------------ #
    # Language selection                                                   #
    # ------------------------------------------------------------------ #
    "lang_select_prompt": {
        "lv": "🌐 <b>Valodas izvēle</b>\n\nIzvēlieties valodu:",
        "ru": "🌐 <b>Выбор языка</b>\n\nВыберите язык:",
        "en": "🌐 <b>Language selection</b>\n\nChoose your language:",
    },
    "lang_changed": {
        "lv": "✅ Valoda mainīta uz <b>Latviešu</b>.",
        "ru": "✅ Язык изменён на <b>Русский</b>.",
        "en": "✅ Language changed to <b>English</b>.",
    },
    # ------------------------------------------------------------------ #
    # Search list                                                          #
    # ------------------------------------------------------------------ #
    "no_searches": {
        "lv": "📋 Jums nav meklējumu.\n\nPievienojiet pirmo meklējumu, nospiežot pogu zemāk.",
        "ru": "📋 У вас нет поисков.\n\nДобавьте первый поиск, нажав кнопку ниже.",
        "en": "📋 You have no searches.\n\nAdd your first search by pressing the button below.",
    },
    "searches_list_header": {
        "lv": "📋 <b>Jūsu meklējumi</b> ({count}):\n\nIzvēlieties meklējumu, lai apskatītu vai pārvaldītu:",
        "ru": "📋 <b>Ваши поиски</b> ({count}):\n\nВыберите поиск для просмотра или управления:",
        "en": "📋 <b>Your searches</b> ({count}):\n\nSelect a search to view or manage:",
    },
    # ------------------------------------------------------------------ #
    # Search status                                                        #
    # ------------------------------------------------------------------ #
    "status_active": {
        "lv": "▶️ aktīvs",
        "ru": "▶️ активен",
        "en": "▶️ active",
    },
    "status_paused": {
        "lv": "⏸ pauzēts",
        "ru": "⏸ на паузе",
        "en": "⏸ paused",
    },
    # ------------------------------------------------------------------ #
    # Search detail                                                        #
    # ------------------------------------------------------------------ #
    "search_detail_header": {
        "lv": "🔎 <b>Meklējums #{sid}</b>",
        "ru": "🔎 <b>Поиск #{sid}</b>",
        "en": "🔎 <b>Search #{sid}</b>",
    },
    "search_detail_category": {
        "lv": "Kategorija: {cat}",
        "ru": "Категория: {cat}",
        "en": "Category: {cat}",
    },
    "search_detail_status": {
        "lv": "Statuss: {status}",
        "ru": "Статус: {status}",
        "en": "Status: {status}",
    },
    "search_detail_active_filters": {
        "lv": "\n🔍 <b>Aktīvie filtri:</b>",
        "ru": "\n🔍 <b>Активные фильтры:</b>",
        "en": "\n🔍 <b>Active filters:</b>",
    },
    "search_detail_no_filters": {
        "lv": "\n(bez papildu filtriem)",
        "ru": "\n(без дополнительных фильтров)",
        "en": "\n(no additional filters)",
    },
    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #
    "search_paused": {
        "lv": "⏸ Meklējums #{sid} apturēts.",
        "ru": "⏸ Поиск #{sid} поставлен на паузу.",
        "en": "⏸ Search #{sid} paused.",
    },
    "search_resumed": {
        "lv": "▶️ Meklējums #{sid} atsākts.",
        "ru": "▶️ Поиск #{sid} возобновлён.",
        "en": "▶️ Search #{sid} resumed.",
    },
    "search_deleted": {
        "lv": "🗑 Meklējums #{sid} dzēsts.",
        "ru": "🗑 Поиск #{sid} удалён.",
        "en": "🗑 Search #{sid} deleted.",
    },
    # ------------------------------------------------------------------ #
    # Add search FSM                                                       #
    # ------------------------------------------------------------------ #
    "add_search_prompt": {
        "lv": (
            "➕ <b>Pievienot meklējumu</b>\n\n"
            "Nosūtiet SS.lv meklēšanas lapas saiti.\n\n"
            "<i>Piemērs:</i>\n"
            "<code>https://www.ss.lv/lv/transport/cars/</code>"
        ),
        "ru": (
            "➕ <b>Добавить поиск</b>\n\n"
            "Отправьте ссылку на страницу поиска SS.lv.\n\n"
            "<i>Пример:</i>\n"
            "<code>https://www.ss.lv/lv/transport/cars/</code>"
        ),
        "en": (
            "➕ <b>Add search</b>\n\n"
            "Send a link to an SS.lv search page.\n\n"
            "<i>Example:</i>\n"
            "<code>https://www.ss.lv/lv/transport/cars/</code>"
        ),
    },
    # ------------------------------------------------------------------ #
    # Filters                                                              #
    # ------------------------------------------------------------------ #
    "filters_header": {
        "lv": "🔍 <b>Meklējuma #{sid} filtri</b>\n\n{content}",
        "ru": "🔍 <b>Фильтры поиска #{sid}</b>\n\n{content}",
        "en": "🔍 <b>Filters for search #{sid}</b>\n\n{content}",
    },
    "filters_none": {
        "lv": "(filtri nav iestatīti)",
        "ru": "(фильтры не установлены)",
        "en": "(no filters set)",
    },
    "filter_set_ok": {
        "lv": "✅ Filtrs iestatīts.",
        "ru": "✅ Фильтр установлен.",
        "en": "✅ Filter set.",
    },
    "filter_deleted_ok": {
        "lv": "✅ Filtrs dzēsts.",
        "ru": "✅ Фильтр удалён.",
        "en": "✅ Filter deleted.",
    },
    "filter_cleared_ok": {
        "lv": "✅ Visi filtri notīrīti.",
        "ru": "✅ Все фильтры очищены.",
        "en": "✅ All filters cleared.",
    },
    "filter_enter_value": {
        "lv": "✏️ Ievadiet vērtību filtra laukam <b>{field}</b>:",
        "ru": "✏️ Введите значение для поля <b>{field}</b>:",
        "en": "✏️ Enter a value for filter field <b>{field}</b>:",
    },
    # ------------------------------------------------------------------ #
    # Errors                                                               #
    # ------------------------------------------------------------------ #
    "err_no_user": {
        "lv": "Nevarēja noteikt lietotāju.",
        "ru": "Не удалось определить пользователя.",
        "en": "Could not identify the user.",
    },
    "err_search_not_found": {
        "lv": "❌ Meklējums nav atrasts vai nepieder jums.",
        "ru": "❌ Поиск не найден или не принадлежит вам.",
        "en": "❌ Search not found or does not belong to you.",
    },
    "err_search_not_found_short": {
        "lv": "❌ Meklējums nav atrasts.",
        "ru": "❌ Поиск не найден.",
        "en": "❌ Search not found.",
    },
    "err_already_paused": {
        "lv": "⏸ Meklējums jau ir pauzēts.",
        "ru": "⏸ Поиск уже на паузе.",
        "en": "⏸ Search is already paused.",
    },
    "err_already_active": {
        "lv": "▶️ Meklējums jau ir aktīvs.",
        "ru": "▶️ Поиск уже активен.",
        "en": "▶️ Search is already active.",
    },
    "err_invalid_url": {
        "lv": "❌ URL jābūt no ss.lv domēna",
        "ru": "❌ URL должен быть с домена ss.lv",
        "en": "❌ URL must be from the ss.lv domain",
    },
    "err_duplicate_url": {
        "lv": "⚠️ Meklējums ar šo URL jau eksistē (#{sid})",
        "ru": "⚠️ Поиск с этим URL уже существует (#{sid})",
        "en": "⚠️ A search with this URL already exists (#{sid})",
    },
    "err_usage_pause": {
        "lv": "Lietošana: /pause <ID>",
        "ru": "Использование: /pause <ID поиска>",
        "en": "Usage: /pause <search ID>",
    },
    "err_usage_resume": {
        "lv": "Lietošana: /resume <ID>",
        "ru": "Использование: /resume <ID поиска>",
        "en": "Usage: /resume <search ID>",
    },
    "err_usage_delete": {
        "lv": "Lietošana: /delete <ID>",
        "ru": "Использование: /delete <ID поиска>",
        "en": "Usage: /delete <search ID>",
    },
    "err_usage_filters": {
        "lv": "Lietošana: /filters <ID>",
        "ru": "Использование: /filters <ID>",
        "en": "Usage: /filters <search ID>",
    },
    "err_usage_setfilter": {
        "lv": "Lietošana: /setfilter <ID> <lauks> <vērtība>",
        "ru": "Использование: /setfilter <ID> <поле> <значение>",
        "en": "Usage: /setfilter <ID> <field> <value>",
    },
    "err_usage_delfilter": {
        "lv": "Lietošana: /delfilter <ID> <lauks>",
        "ru": "Использование: /delfilter <ID> <поле>",
        "en": "Usage: /delfilter <ID> <field>",
    },
    "err_usage_clearfilters": {
        "lv": "Lietošana: /clearfilters <ID>",
        "ru": "Использование: /clearfilters <ID>",
        "en": "Usage: /clearfilters <search ID>",
    },
    "err_filter_not_found": {
        "lv": "⚠️ Filtrs `{field}` nav atrasts",
        "ru": "⚠️ Фильтр `{field}` не найден",
        "en": "⚠️ Filter `{field}` not found",
    },
    "err_filter_schema": {
        "lv": "⚠️ Nevarēja iegūt lauku sarakstu",
        "ru": "⚠️ Не удалось получить список полей",
        "en": "⚠️ Could not retrieve the list of fields",
    },
    "err_search_already_exists_pause": {
        "lv": "Meklējums #{sid} jau ir pauzēts.",
        "ru": "Поиск #{sid} уже на паузе.",
        "en": "Search #{sid} is already paused.",
    },
    "err_search_already_active_resume": {
        "lv": "Meklējums #{sid} jau ir aktīvs.",
        "ru": "Поиск #{sid} уже активен.",
        "en": "Search #{sid} is already active.",
    },
    # ------------------------------------------------------------------ #
    # Add search: results                                                  #
    # ------------------------------------------------------------------ #
    "add_search_ok": {
        "lv": "✅ Meklējums pievienots! #{sid}, {cat}",
        "ru": "✅ Поиск добавлен! #{sid}, {cat}",
        "en": "✅ Search added! #{sid}, {cat}",
    },
    "add_search_ok_with_filters": {
        "lv": "✅ Meklējums pievienots! #{sid}, {cat}, filtri: {filters}",
        "ru": "✅ Поиск добавлен! #{sid}, {cat}, фильтры: {filters}",
        "en": "✅ Search added! #{sid}, {cat}, filters: {filters}",
    },
    # ------------------------------------------------------------------ #
    # List (slash command)                                                 #
    # ------------------------------------------------------------------ #
    "list_header": {
        "lv": "📋 <b>Jūsu meklējumi</b> ({count}):\n",
        "ru": "📋 <b>Ваши поиски</b> ({count}):\n",
        "en": "📋 <b>Your searches</b> ({count}):\n",
    },
    # ------------------------------------------------------------------ #
    # Watcher notifications                                                #
    # ------------------------------------------------------------------ #
    "new_listing": {
        "lv": "🔔 Jauns sludinājums (meklējums #{sid}):",
        "ru": "🔔 Новое объявление (поиск #{sid}):",
        "en": "🔔 New listing (search #{sid}):",
    },
    "listing_title": {
        "lv": "Nosaukums: {title}",
        "ru": "Название: {title}",
        "en": "Title: {title}",
    },
    "listing_price": {
        "lv": "Cena: {price}",
        "ru": "Цена: {price}",
        "en": "Price: {price}",
    },
    "listing_city": {
        "lv": "Pilsēta: {city}",
        "ru": "Город: {city}",
        "en": "City: {city}",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_text(key: str, lang: str, **kwargs: object) -> str:
    """Return a translated string for *key* in *lang*.

    Falls back to DEFAULT_LANG if the key is missing for the requested
    language, then to the raw key as a last resort.
    """
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    entry = _T.get(key, {})
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def resolve_lang(tg_lang_code: str | None, db_lang: str | None) -> str:
    """Resolve the effective language for a user.

    Priority:
      1. DB-stored selection (*db_lang*)
      2. Telegram *tg_lang_code* (if supported)
      3. DEFAULT_LANG ("lv")
    """
    if db_lang and db_lang in SUPPORTED_LANGS:
        return db_lang
    if tg_lang_code and tg_lang_code in SUPPORTED_LANGS:
        return tg_lang_code
    return DEFAULT_LANG

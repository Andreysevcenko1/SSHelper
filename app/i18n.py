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
            "👋 Sveiki! Es esmu <b>SSHelper</b> — bots SS.lv sludinājumu uzraudzībai.\n\n"
            "📢 Visi jaunākie SS.lv sludinājumi mūsu grupā: https://t.me/sslvhelper\n\n"
            "Atsūtiet man SS.lv meklēšanas saiti vai izmantojiet pogas zemāk:"
        ),
        "ru": (
            "👋 Привет! Я <b>SSHelper</b> — бот для мониторинга объявлений на SS.lv.\n\n"
            "📢 Все новые объявления SS.lv в нашей группе: https://t.me/sslvhelper\n\n"
            "Отправьте мне ссылку на поиск SS.lv или используйте кнопки ниже:"
        ),
        "en": (
            "👋 Hello! I am <b>SSHelper</b> — a bot for monitoring listings on SS.lv.\n\n"
            "📢 All new SS.lv listings in our group: https://t.me/sslvhelper\n\n"
            "Send me an SS.lv search link or use the buttons below:"
        ),
    },
    "dm_fallback_prompt": {
        "lv": (
            "👋 <b>Es esmu gatavs pieņemt SS.lv saites!</b>\n\n"
            "Nosūtiet man SS.lv meklēšanas lapas vai kategorijas saiti (piemēram, dzīvokļi vai auto).\n\n"
            "Vai izmantojiet izvēlni zemāk:"
        ),
        "ru": (
            "👋 <b>Я готов принимать ссылки на SS.lv!</b>\n\n"
            "Просто отправьте мне ссылку на категорию или поиск SS.lv (например, квартиры или авто).\n\n"
            "Или используйте меню ниже:"
        ),
        "en": (
            "👋 <b>I am ready to accept SS.lv links!</b>\n\n"
            "Simply send me a link to an SS.lv category or search page (e.g. flats or cars).\n\n"
            "Or use the menu below:"
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
        "lv": "🌐 Valoda / Язык",
        "ru": "🌐 Язык / Valoda",
        "en": "🌐 Language / Valoda",
    },
    "btn_group": {
        "lv": "📢 Visi sludinājumi grupā",
        "ru": "📢 Все объявления в группе",
        "en": "📢 All listings in the group",
    },
    "btn_help": {
        "lv": "ℹ️ Palīdzība",
        "ru": "ℹ️ Помощь",
        "en": "ℹ️ Help",
    },
    # ------------------------------------------------------------------ #
    # Subscription / paid plans                                            #
    # ------------------------------------------------------------------ #
    "btn_subscription": {
        "lv": "⭐ Abonements",
        "ru": "⭐ Подписка",
        "en": "⭐ Subscription",
    },
    "sub_screen_title": {
        "lv": "⭐ <b>Abonements</b>",
        "ru": "⭐ <b>Подписка</b>",
        "en": "⭐ <b>Subscription</b>",
    },
    "sub_status_free": {
        "lv": "Jums ir bezmaksas plāns: 1 aktīvs meklējums.",
        "ru": "У вас бесплатный план: 1 активный поиск.",
        "en": "You are on the free plan: 1 active search.",
    },
    "sub_status_trial": {
        "lv": "🎁 Bezmaksas izmēģinājums: 1 aktīvs meklējums.\nAtlikušas dienas: {days}",
        "ru": "🎁 Бесплатный пробный период: 1 активный поиск.\nОсталось дней: {days}",
        "en": "🎁 Free trial: 1 active search.\nDays left: {days}",
    },
    "sub_status_expired": {
        "lv": "⌛ Bezmaksas periods beidzies. Lai turpinātu, izvēlieties tarifu vai uzaiciniet draugu.",
        "ru": "⌛ Бесплатный период закончился. Чтобы продолжить, выберите тариф или пригласите друга.",
        "en": "⌛ Your free trial has ended. Choose a plan or invite a friend to continue.",
    },
    "trial_expired_paused": {
        "lv": "⌛ Bezmaksas periods beidzies — {count} meklējums(-i) apturēts(-i).\nIzvēlieties tarifu vai uzaiciniet draugu (+1 vieta uz 30 dienām), lai atsāktu.",
        "ru": "⌛ Бесплатный период закончился — приостановлено поисков: {count}.\nВыберите тариф или пригласите друга (+1 слот на 30 дней), чтобы возобновить.",
        "en": "⌛ Your free trial has ended — {count} search(es) paused.\nChoose a plan or invite a friend (+1 slot for 30 days) to resume.",
    },
    "sub_status_active": {
        "lv": "Aktīvais plāns: {plan}\nAtlikušas dienas: {days}",
        "ru": "Активный тариф: {plan}\nОсталось дней: {days}",
        "en": "Active plan: {plan}\nDays left: {days}",
    },
    "sub_status_admin": {
        "lv": "Administrators: neierobežots meklējumu skaits",
        "ru": "Администратор: неограниченное количество поисков",
        "en": "Administrator: unlimited searches",
    },
    "sub_usage": {
        "lv": "Izmantoti meklējumi: {active} no {limit}",
        "ru": "Используется поисков: {active} из {limit}",
        "en": "Searches in use: {active} of {limit}",
    },
    "sub_usage_unlimited": {
        "lv": "Aktīvie meklējumi: {active} (bez ierobežojuma)",
        "ru": "Активных поисков: {active} (без ограничений)",
        "en": "Active searches: {active} (unlimited)",
    },
    "sub_pick_plan": {
        "lv": "Izvēlieties tarifu (uz 30 dienām, jauns tarifs aizstāj esošo):",
        "ru": "Выберите тариф (на 30 дней, новый тариф заменяет текущий):",
        "en": "Choose a plan (30 days; a new plan replaces the current one):",
    },
    "sub_plan_plus1": {
        "lv": "1 meklējums — {eur} (⭐{stars})",
        "ru": "1 поиск — {eur} (⭐{stars})",
        "en": "1 search — {eur} (⭐{stars})",
    },
    "sub_plan_plus4": {
        "lv": "5 meklējumi — {eur} (⭐{stars})",
        "ru": "5 поисков — {eur} (⭐{stars})",
        "en": "5 searches — {eur} (⭐{stars})",
    },
    "sub_plan_plus9": {
        "lv": "10 meklējumi — {eur} (⭐{stars})",
        "ru": "10 поисков — {eur} (⭐{stars})",
        "en": "10 searches — {eur} (⭐{stars})",
    },
    "sub_invoice_title": {
        "lv": "Abonements: {total} aktīvi meklējumi",
        "ru": "Подписка: {total} активных поисков",
        "en": "Subscription: {total} active searches",
    },
    "sub_invoice_desc": {
        "lv": "{total} aktīvi meklējumi uz {days} dienām. Cena: {eur}.",
        "ru": "{total} активных поисков на {days} дней. Цена: {eur}.",
        "en": "{total} active searches for {days} days. Price: {eur}.",
    },
    "btn_invite_friend": {
        "lv": "🎁 Uzaicini draugu (+1 meklējums uz 30 dienām)",
        "ru": "🎁 Пригласить друга (+1 поиск на 30 дней)",
        "en": "🎁 Invite a friend (+1 search for 30 days)",
    },
    "ref_screen": {
        "lv": (
            "🎁 <b>Uzaicini draugu — saņem +1 meklējumu uz 30 dienām!</b>\n\n"
            "Par katru draugu, kurš pirmo reizi palaiž botu caur tavu saiti, "
            "tu saņem +1 meklēšanas vietu uz 30 dienām (līdz +{max}).\n\n"
            "Tava saite:\n{link}\n\n"
            "Aktīvie draugu bonusi: {count} no {max}"
        ),
        "ru": (
            "🎁 <b>Пригласи друга — получи +1 поиск на 30 дней!</b>\n\n"
            "За каждого друга, который впервые запустит бота по твоей ссылке, "
            "ты получаешь +1 слот поиска на 30 дней (до +{max}).\n\n"
            "Твоя ссылка:\n{link}\n\n"
            "Активные бонусы за друзей: {count} из {max}"
        ),
        "en": (
            "🎁 <b>Invite a friend — get +1 search for 30 days!</b>\n\n"
            "For every friend who starts the bot for the first time via your link, "
            "you get +1 search slot for 30 days (up to +{max}).\n\n"
            "Your link:\n{link}\n\n"
            "Active friend bonuses: {count} of {max}"
        ),
    },
    "ref_credited": {
        "lv": "🎁 Tavs draugs pievienojās! Tev ir +1 meklēšanas vieta uz 30 dienām.",
        "ru": "🎁 Твой друг присоединился! У тебя +1 слот поиска на 30 дней.",
        "en": "🎁 Your friend joined! You have +1 search slot for 30 days.",
    },
    "sub_paid_ok": {
        "lv": "✅ Apmaksa saņemta! Tagad jums pieejami {total} aktīvi meklējumi uz {days} dienām.",
        "ru": "✅ Оплата получена! Теперь вам доступно {total} активных поисков на {days} дней.",
        "en": "✅ Payment received! You now have {total} active searches for {days} days.",
    },
    "err_search_limit": {
        "lv": "🚫 Sasniegts aktīvo meklējumu limits: {limit}.\nIegādājieties tarifu, lai pievienotu vairāk, vai apturiet kādu no esošajiem meklējumiem.",
        "ru": "🚫 Достигнут лимит активных поисков: {limit}.\nКупите тариф, чтобы добавить больше, или приостановите один из текущих поисков.",
        "en": "🚫 Active search limit reached: {limit}.\nBuy a plan to add more, or pause one of your current searches.",
    },
    "btn_buy_more_searches": {
        "lv": "⭐ Palielināt limitu",
        "ru": "⭐ Увеличить лимит",
        "en": "⭐ Increase limit",
    },
    "brand_from_url_applied": {
        "lv": "ℹ️ Marka no saites automātiski pievienota filtriem: <b>{brand}</b>",
        "ru": "ℹ️ Марка из ссылки автоматически добавлена в фильтры: <b>{brand}</b>",
        "en": "ℹ️ Brand from the link was added to filters automatically: <b>{brand}</b>",
    },
    "brand_conflict_question": {
        "lv": "Saitē norādīta marka <b>{url_brand}</b>, bet filtros izvēlēta <b>{filter_brand}</b>.\nAizstāt ar marku no saites? (Modelis tiks atiestatīts.)",
        "ru": "В ссылке указана марка <b>{url_brand}</b>, а в фильтрах выбрана <b>{filter_brand}</b>.\nЗаменить на марку из ссылки? (Модель будет сброшена.)",
        "en": "The link specifies brand <b>{url_brand}</b>, but filters have <b>{filter_brand}</b>.\nReplace with the brand from the link? (Model will be reset.)",
    },
    "btn_replace_brand": {
        "lv": "✅ Jā, aizstāt",
        "ru": "✅ Да, заменить",
        "en": "✅ Yes, replace",
    },
    "btn_keep_brand": {
        "lv": "❌ Nē, atstāt",
        "ru": "❌ Нет, оставить",
        "en": "❌ No, keep",
    },
    "btn_back_to_menu": {
        "lv": "🏠 Uz izvēlni",
        "ru": "🏠 В меню",
        "en": "🏠 Main menu",
    },
    "btn_back": {
        "lv": "🔙 Atpakaļ",
        "ru": "🔙 Назад",
        "en": "🔙 Back",
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
        "lv": "⚙️ Filtri",
        "ru": "⚙️ Фильтры",
        "en": "⚙️ Filters",
    },
    "btn_back_to_search": {
        "lv": "🔙 Atpakaļ uz meklējumu",
        "ru": "🔙 Назад к поиску",
        "en": "🔙 Back to search",
    },
    "btn_back_to_list": {
        "lv": "🔙 Uz sarakstu",
        "ru": "🔙 К списку",
        "en": "🔙 Back to list",
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
        "lv": "⚙️ Filtri",
        "ru": "⚙️ Фильтры",
        "en": "⚙️ Filters",
    },
    "btn_show_filters": {
        "lv": "👁 Rādīt filtrus",
        "ru": "👁 Показать фильтры",
        "en": "👁 Show filters",
    },
    "btn_edit_filter": {
        "lv": "✏️ Mainīt filtru",
        "ru": "✏️ Изменить фильтр",
        "en": "✏️ Edit filter",
    },
    "btn_del_filter": {
        "lv": "➖ Dzēst filtru",
        "ru": "➖ Удалить фильтр",
        "en": "➖ Delete filter",
    },
    "btn_clear_filters": {
        "lv": "♻️ Notīrīt visus filtrus",
        "ru": "♻️ Очистить фильтры",
        "en": "♻️ Clear filters",
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
    # Help screen                                                          #
    # ------------------------------------------------------------------ #
    "help_text": {
        "lv": (
            "ℹ️ <b>Palīdzība</b>\n\n"
            "SSHelper uzrauga SS.lv meklēšanas lapas un paziņo par jauniem "
            "sludinājumiem.\n\n"
            "<b>Kā sākt:</b>\n"
            "1. Nospiediet <b>➕ Pievienot meklējumu</b>\n"
            "2. Nosūtiet SS.lv meklēšanas lapas saiti\n"
            "3. Saņemiet paziņojumus par jauniem sludinājumiem\n\n"
            "<b>Meklējumu pārvaldība:</b>\n"
            "Atveriet <b>📋 Mani meklējumi</b>, atlasiet meklējumu un "
            "izmantojiet kontekstuālās pogas.\n\n"
            "<b>Filtri:</b>\n"
            "Katram meklējumam varat iestatīt filtrus (cena, pilsēta u.c.), "
            "izmantojot pogu <b>⚙️ Filtri</b> meklējuma kartītē."
        ),
        "ru": (
            "ℹ️ <b>Помощь</b>\n\n"
            "SSHelper отслеживает страницы поиска SS.lv и уведомляет о новых "
            "объявлениях.\n\n"
            "<b>Как начать:</b>\n"
            "1. Нажмите <b>➕ Добавить поиск</b>\n"
            "2. Отправьте ссылку на страницу поиска SS.lv\n"
            "3. Получайте уведомления о новых объявлениях\n\n"
            "<b>Управление поисками:</b>\n"
            "Откройте <b>📋 Мои поиски</b>, выберите поиск и используйте "
            "контекстные кнопки.\n\n"
            "<b>Фильтры:</b>\n"
            "Для каждого поиска можно настроить фильтры (цена, город и т.д.) "
            "через кнопку <b>⚙️ Фильтры</b> в карточке поиска."
        ),
        "en": (
            "ℹ️ <b>Help</b>\n\n"
            "SSHelper monitors SS.lv search pages and notifies you about new "
            "listings.\n\n"
            "<b>Getting started:</b>\n"
            "1. Press <b>➕ Add search</b>\n"
            "2. Send a link to an SS.lv search page\n"
            "3. Receive notifications about new listings\n\n"
            "<b>Managing searches:</b>\n"
            "Open <b>📋 My searches</b>, select a search and use the context "
            "buttons.\n\n"
            "<b>Filters:</b>\n"
            "You can configure filters (price, city, etc.) for each search "
            "using the <b>⚙️ Filters</b> button in the search card."
        ),
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
    "search_detail_url": {
        "lv": "🔗 {url}",
        "ru": "🔗 {url}",
        "en": "🔗 {url}",
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
    "filter_edit_prompt": {
        "lv": (
            "✏️ <b>Filtra maiņa:</b> {field}\n"
            "Pašreizējā vērtība: {current}\n"
            "Ievadiet jaunu vērtību. {hint}"
        ),
        "ru": (
            "✏️ <b>Изменение фильтра:</b> {field}\n"
            "Текущее значение: {current}\n"
            "Введите новое значение. {hint}"
        ),
        "en": (
            "✏️ <b>Editing filter:</b> {field}\n"
            "Current value: {current}\n"
            "Enter a new value. {hint}"
        ),
    },
    "filter_current_value_missing": {
        "lv": "nav norādīta",
        "ru": "не задано",
        "en": "not set",
    },
    "filter_hint_numeric": {
        "lv": "Piemērs: 5000",
        "ru": "Пример: 5000",
        "en": "Example: 5000",
    },
    "filter_hint_price": {
        "lv": "Piemērs: 5000",
        "ru": "Пример: 5000",
        "en": "Example: 5000",
    },
    "filter_hint_year": {
        "lv": "Piemērs: 2018",
        "ru": "Пример: 2018",
        "en": "Example: 2018",
    },
    "filter_hint_volume": {
        "lv": "Piemērs: 2.0",
        "ru": "Пример: 2.0",
        "en": "Example: 2.0",
    },
    "filter_hint_select": {
        "lv": "Izvēlieties vērtību no saraksta zemāk.",
        "ru": "Выберите значение из списка ниже.",
        "en": "Choose a value from the list below.",
    },
    "filter_input_mode_error": {
        "lv": "Filtra ievades kļūda. Lūdzu, mēģiniet vēlreiz.",
        "ru": "Ошибка режима ввода фильтра. Пожалуйста, попробуйте ещё раз.",
        "en": "Filter input mode error. Please try again.",
    },
    "filter_hint_text": {
        "lv": "Piemērs: BMW",
        "ru": "Пример: BMW",
        "en": "Example: BMW",
    },
    "filter_hint_rooms": {
        "lv": "Piemērs: 2",
        "ru": "Пример: 2",
        "en": "Example: 2",
    },
    "filter_hint_area": {
        "lv": "Piemērs: 45 (m²)",
        "ru": "Пример: 45 (м²)",
        "en": "Example: 45 (m²)",
    },
    "filter_hint_floor": {
        "lv": "Piemērs: 3",
        "ru": "Пример: 3",
        "en": "Example: 3",
    },
    "filter_hint_street": {
        "lv": "Piemērs: Brīvības iela",
        "ru": "Пример: Бривибас (улица)",
        "en": "Example: Brivibas street",
    },
    "filter_select_brand_first": {
        "lv": "Vispirms izvēlieties automašīnas marku.",
        "ru": "Сначала выберите марку автомобиля.",
        "en": "Select a car brand first.",
    },
    "filter_options_unavailable": {
        "lv": "Šim filtram opcijas šobrīd nav pieejamas.",
        "ru": "Опции для этого фильтра сейчас недоступны.",
        "en": "Options for this filter are currently unavailable.",
    },
    "filter_model_reset_after_brand_change": {
        "lv": "Marka nomainīta. Lūdzu, izvēlieties modeli atkārtoti.",
        "ru": "Марка изменена. Пожалуйста, выберите модель заново.",
        "en": "Brand changed. Please select the model again.",
    },
    "filter_option_unavailable": {
        "lv": "Opcija nav pieejama",
        "ru": "Опция недоступна",
        "en": "Option unavailable",
    },
    # Label fallbacks used by filter_display_label when no schema label exists
    "filter_lbl_price_from": {
        "lv": "Cena no",
        "ru": "Цена от",
        "en": "Price from",
    },
    "filter_lbl_price_to": {
        "lv": "Cena līdz",
        "ru": "Цена до",
        "en": "Price to",
    },
    "filter_lbl_city_district": {
        "lv": "Pilsēta/rajons",
        "ru": "Город/район",
        "en": "City/district",
    },
    "filter_lbl_brand": {
        "lv": "Marka",
        "ru": "Марка",
        "en": "Brand",
    },
    "filter_lbl_model": {
        "lv": "Modelis",
        "ru": "Модель",
        "en": "Model",
    },
    "filter_lbl_body_type": {
        "lv": "Virsbūves tips",
        "ru": "Тип кузова",
        "en": "Body type",
    },
    "filter_lbl_fuel_type": {
        "lv": "Degvielas tips",
        "ru": "Тип топлива",
        "en": "Fuel type",
    },
    "filter_lbl_engine_type": {
        "lv": "Dzinējs",
        "ru": "Двигатель",
        "en": "Engine type",
    },
    "filter_lbl_gearbox": {
        "lv": "Pārnesumkārba",
        "ru": "Коробка передач",
        "en": "Gearbox",
    },
    "filter_lbl_color": {
        "lv": "Krāsa",
        "ru": "Цвет",
        "en": "Color",
    },
    "filter_lbl_volume_from": {
        "lv": "Tilpums no",
        "ru": "Объём от",
        "en": "Volume from",
    },
    "filter_lbl_volume_to": {
        "lv": "Tilpums līdz",
        "ru": "Объём до",
        "en": "Volume to",
    },
    "filter_lbl_year_from": {
        "lv": "Gads no",
        "ru": "Год от",
        "en": "Year from",
    },
    "filter_lbl_year_to": {
        "lv": "Gads līdz",
        "ru": "Год до",
        "en": "Year to",
    },
    "filter_lbl_parameter": {
        "lv": "Parametrs",
        "ru": "Параметр",
        "en": "Parameter",
    },
    "filter_lbl_opt": {
        "lv": "Filtrs",
        "ru": "Фильтр",
        "en": "Filter",
    },
    "filter_lbl_district": {
        "lv": "Rajons",
        "ru": "Район",
        "en": "District",
    },
    # Range (min/max) labels for topt[<id>][min|max] keys
    "filter_lbl_topt_price_min": {
        "lv": "Cena: no",
        "ru": "Цена: от",
        "en": "Price: from",
    },
    "filter_lbl_topt_price_max": {
        "lv": "Cena: līdz",
        "ru": "Цена: до",
        "en": "Price: to",
    },
    "filter_lbl_area_from": {
        "lv": "Platība no",
        "ru": "Площадь от",
        "en": "Area from",
    },
    "filter_lbl_area_to": {
        "lv": "Platība līdz",
        "ru": "Площадь до",
        "en": "Area to",
    },
    "filter_lbl_rooms_from": {
        "lv": "Istabas no",
        "ru": "Комнаты от",
        "en": "Rooms from",
    },
    "filter_lbl_rooms_to": {
        "lv": "Istabas līdz",
        "ru": "Комнаты до",
        "en": "Rooms to",
    },
    "filter_lbl_range_min": {
        "lv": "no",
        "ru": "от",
        "en": "from",
    },
    "filter_lbl_range_max": {
        "lv": "līdz",
        "ru": "до",
        "en": "to",
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
    "err_search_not_found_id": {
        "lv": "❌ Meklējums ar ID {sid} nav atrasts.\n\nPārbaudiet sarakstu un mēģiniet vēlreiz.",
        "ru": "❌ Поиск с ID {sid} не найден.\n\nПроверьте список и попробуйте снова.",
        "en": "❌ Search with ID {sid} not found.\n\nCheck the list and try again.",
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
        "lv": "❌ URL jābūt no ss.lv vai ss.com domēna",
        "ru": "❌ URL должен быть с домена ss.lv или ss.com",
        "en": "❌ URL must be from the ss.lv or ss.com domain",
    },
    "err_listing_url": {
        "lv": "❌ Šī ir saite uz konkrētu sludinājumu. Lūdzu, ievietojiet saiti uz sadaļu vai meklēšanas rezultātiem, piemēram: https://www.ss.lv/lv/transport/cars/",
        "ru": "❌ Это ссылка на конкретное объявление — так поиск не сработает. Вставьте ссылку на раздел или результаты поиска, например: https://www.ss.lv/lv/transport/cars/",
        "en": "❌ This is a link to a single listing — it won't work as a search. Please paste a section or search-results link, e.g. https://www.ss.lv/lv/transport/cars/",
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
    "err_filter_key_not_found": {
        "lv": (
            "❌ Filtrs <code>{key}</code> neeksistē šim meklējumam.\n\n"
            "Izmantojiet 👁 Rādīt filtrus, lai redzētu esošos filtrus."
        ),
        "ru": (
            "❌ Фильтр <code>{key}</code> не существует для этого поиска.\n\n"
            "Используйте 👁 Показать фильтры, чтобы увидеть текущие фильтры."
        ),
        "en": (
            "❌ Filter <code>{key}</code> does not exist for this search.\n\n"
            "Use 👁 Show filters to see the current filters."
        ),
    },
    "err_filter_schema": {
        "lv": (
            "⚠️ Nevarēja iegūt filtru sarakstu.\n\n"
            "Iespējams, SS.lv nav pieejams. Mēģiniet vēlreiz vēlāk."
        ),
        "ru": (
            "⚠️ Не удалось получить список фильтров.\n\n"
            "Возможно, SS.lv недоступен. Попробуйте снова позже."
        ),
        "en": (
            "⚠️ Could not retrieve the filter list.\n\n"
            "SS.lv may be unavailable. Please try again later."
        ),
    },
    "err_no_filters_set": {
        "lv": (
            "ℹ️ Šim meklējumam nav saglabātu filtru.\n\n"
            "Vispirms pievienojiet filtru, izmantojot ✏️ Mainīt filtru."
        ),
        "ru": (
            "ℹ️ У этого поиска нет сохранённых фильтров.\n\n"
            "Сначала добавьте фильтр с помощью ✏️ Изменить фильтр."
        ),
        "en": (
            "ℹ️ This search has no saved filters.\n\n"
            "First add a filter using ✏️ Edit filter."
        ),
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
    "err_network": {
        "lv": (
            "⚠️ Nevarēja sazināties ar SS.lv.\n\n"
            "Tas ir īslaicīgs tīkla kļūda. Mēģiniet vēlreiz pēc brīža."
        ),
        "ru": (
            "⚠️ Не удалось связаться с SS.lv.\n\n"
            "Это временная сетевая ошибка. Попробуйте снова через некоторое время."
        ),
        "en": (
            "⚠️ Could not reach SS.lv.\n\n"
            "This is a temporary network error. Please try again shortly."
        ),
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
        "lv": "🔔 <b>Jauns sludinājums!</b>",
        "ru": "🔔 <b>Новое объявление!</b>",
        "en": "🔔 <b>New listing!</b>",
    },
    "notification_search_label": {
        "lv": "📋 Meklējums #{sid}",
        "ru": "📋 Поиск #{sid}",
        "en": "📋 Search #{sid}",
    },
    "listing_title": {
        "lv": "<b>{title}</b>",
        "ru": "<b>{title}</b>",
        "en": "<b>{title}</b>",
    },
    "listing_price": {
        "lv": "💰 {price}",
        "ru": "💰 {price}",
        "en": "💰 {price}",
    },
    "listing_city": {
        "lv": "📍 {city}",
        "ru": "📍 {city}",
        "en": "📍 {city}",
    },
    "listing_link": {
        "lv": "🔗 Atvērt sludinājumu",
        "ru": "🔗 Открыть объявление",
        "en": "🔗 Open listing",
    },
}


# ---------------------------------------------------------------------------
# Category translations
# ---------------------------------------------------------------------------

# Canonical key → emoji icon
_CATEGORY_ICONS: dict[str, str] = {
    "transport": "🚗",
    "real-estate": "🏠",
    "animals": "🐾",
    "electronics": "💻",
    "services": "🔧",
    "other": "📦",
    "clothing": "👗",
    "garden": "🌱",
    "food": "🍎",
    "sport": "⚽",
    "business": "💼",
    "collect": "🏺",
    "household": "🏡",
    "ss.lv": "📋",
}

# Canonical key → {lang: localized name}
_CATEGORY_NAMES: dict[str, dict[str, str]] = {
    "transport":    {"lv": "Transports",           "ru": "Транспорт",           "en": "Transport"},
    "real-estate":  {"lv": "Nekustamais īpašums",  "ru": "Недвижимость",        "en": "Real estate"},
    "animals":      {"lv": "Dzīvnieki",            "ru": "Животные",            "en": "Animals"},
    "electronics":  {"lv": "Elektronika",           "ru": "Электроника",         "en": "Electronics"},
    "services":     {"lv": "Pakalpojumi",           "ru": "Услуги",              "en": "Services"},
    "other":        {"lv": "Cits",                  "ru": "Прочее",              "en": "Other"},
    "clothing":     {"lv": "Apģērbs",              "ru": "Одежда",              "en": "Clothing"},
    "garden":       {"lv": "Dārzs",                "ru": "Сад и огород",        "en": "Garden"},
    "food":         {"lv": "Pārtika",              "ru": "Еда",                 "en": "Food"},
    "sport":        {"lv": "Sports",               "ru": "Спорт",               "en": "Sports"},
    "business":     {"lv": "Bizness",              "ru": "Бизнес",              "en": "Business"},
    "collect":      {"lv": "Kolekcionēšana",       "ru": "Коллекционирование",  "en": "Collectibles"},
    "household":    {"lv": "Māja un sadzīve",      "ru": "Дом и быт",           "en": "Household"},
    "ss.lv":        {"lv": "SS.lv",                "ru": "SS.lv",               "en": "SS.lv"},
}

# Reverse mapping: old Russian names (legacy DB values) → canonical key
_LEGACY_CATEGORY_MAP: dict[str, str] = {
    names["ru"]: key
    for key, names in _CATEGORY_NAMES.items()
    if "ru" in names
}


def translate_category(category_key: str, lang: str) -> str:
    """Return a localised category label with emoji for the given *lang*.

    *category_key* is the canonical key stored in ``Search.title`` (e.g.
    ``"transport"``) **or** a legacy Russian name from older DB records
    (e.g. ``"Транспорт"``).

    Examples::

        translate_category("transport", "ru")  → "🚗 Транспорт"
        translate_category("transport", "lv")  → "🚗 Transports"
        translate_category("transport", "en")  → "🚗 Transport"
        translate_category("unknown_key", "en") → "📋 unknown_key"
    """
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG

    # Resolve legacy Russian names to canonical keys
    resolved_key = _LEGACY_CATEGORY_MAP.get(category_key, category_key)

    icon = _CATEGORY_ICONS.get(resolved_key, "📋")
    names = _CATEGORY_NAMES.get(resolved_key)
    if names:
        name = names.get(lang) or names.get(DEFAULT_LANG) or resolved_key
    else:
        # Unknown category: show as-is without mixing languages
        name = category_key
    return f"{icon} {name}"


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

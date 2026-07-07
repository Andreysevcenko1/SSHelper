"""
Filter-related handlers:
- Slash commands: /filters, /setfilter, /delfilter, /clearfilters
- Callback handlers: FilterCB, FilterDelCB, FilterEditCB, FilterOptCB, PageCB
- FSM: EditFilterFSM.waiting_value for free-text filter input
"""
import logging
import re
from urllib.parse import urlparse, urlunparse

import aiohttp
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.bot.callbacks import FilterCB, FilterDelCB, FilterEditCB, FilterOptCB, PageCB
from app.bot.handlers.common import get_user_lang
from app.bot.keyboards.filters import (
    after_filter_kb,
    cancel_kb,
    filter_fields_kb,
    filter_items_kb,
    filter_options_kb,
    filters_menu_kb,
    no_filters_kb,
)
from app.bot.keyboards.searches import after_action_kb, error_kb
from app.bot.states import EditFilterFSM
from app.bot.utils import try_delete_message
from app.db.repo import SearchRepository
from app.i18n import get_text
from app.services.filters import (
    base_url_without_query,
    build_effective_url,
    canonical_filter_key_for_profile,
    filter_display_label,
    filter_value_label,
    filters_from_json,
    sanitize_personal_ui_text,
)
from app.services.filter_registry import cars_registry_by_canonical_key
from app.services.ss_parser import SSParser
from app.filters.renderer import render_canonical_filters

logger = logging.getLogger(__name__)
router = Router()

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

_NUMERIC_KEYWORDS = ("min", "max", "price", "pr_", "year", "run", "area", "floor", "room", "volume")
_CARS_SPECS_BY_CANONICAL = cars_registry_by_canonical_key()
_RE_BRAND_LINK = re.compile(r"/(?P<lang>lv|ru|en)/transport/cars/(?P<slug>[a-z0-9][a-z0-9-]*)/", re.IGNORECASE)
_RE_NON_SLUG = re.compile(r"[^a-z0-9-]+")

# Path segments under /transport/cars/ that are sections, not car brands.
_NON_BRAND_SLUGS: frozenset[str] = frozenset({
    "rare-cars", "exchange", "other", "all", "new", "today", "search",
    "filter", "rss", "spare-parts", "sell", "buy", "change", "hand-over",
})

# Maintained fallback used when the live brand fetch fails (task B).
_FALLBACK_BRAND_SLUGS: tuple[str, ...] = (
    "alfa-romeo", "audi", "bmw", "chevrolet", "chrysler", "citroen", "dacia",
    "dodge", "fiat", "ford", "honda", "hyundai", "jaguar", "jeep", "kia",
    "land-rover", "lexus", "mazda", "mercedes", "mini", "mitsubishi",
    "nissan", "opel", "peugeot", "porsche", "renault", "saab", "seat",
    "skoda", "smart", "subaru", "suzuki", "tesla", "toyota", "volkswagen",
    "volvo",
)


def _cars_lang_from_url(url: str) -> str:
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] in {"lv", "ru", "en"}:
        return parts[0]
    return "lv"


def _normalize_brand_slug(value: str) -> str:
    slug = value.strip().lower().replace("_", "-").replace(" ", "-")
    slug = _RE_NON_SLUG.sub("", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


def _brand_display_name(slug: str) -> str:
    overrides = {
        "mercedes-benz": "Mercedes-Benz",
        "land-rover": "Land Rover",
        "alfa-romeo": "Alfa Romeo",
    }
    if slug in overrides:
        return overrides[slug]
    return " ".join(part.capitalize() for part in slug.split("-"))


def _extract_brand_slug_options_from_html(html: str, lang: str) -> list[dict]:
    seen: set[str] = set()
    options: list[dict] = []
    for match in _RE_BRAND_LINK.finditer(html):
        if match.group("lang").lower() != lang:
            continue
        slug = _normalize_brand_slug(match.group("slug"))
        if not slug or slug in seen or slug in _NON_BRAND_SLUGS:
            continue
        seen.add(slug)
        options.append({"value": slug, "text": _brand_display_name(slug)})
    return sorted(options, key=lambda o: o["text"])


def _fallback_brand_slug_options() -> list[dict]:
    """Maintained brand slug list used when the live fetch fails."""
    return [
        {"value": slug, "text": _brand_display_name(slug)}
        for slug in sorted(_FALLBACK_BRAND_SLUGS, key=_brand_display_name)
    ]


async def _fetch_brand_slug_options(search_url: str, lang: str) -> list[dict]:
    parsed = urlparse(search_url)
    cars_root = f"{parsed.scheme or 'https'}://{parsed.netloc}/" \
        f"{lang}/transport/cars/"
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(cars_root, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html = await response.text()
    except Exception as exc:
        logger.warning("filter_cmds: failed to fetch brand slugs from %s: %s", cars_root, exc)
        return _fallback_brand_slug_options()
    options = _extract_brand_slug_options_from_html(html, lang)
    if not options:
        logger.warning("filter_cmds: no brand slugs parsed from %s, using fallback list", cars_root)
        return _fallback_brand_slug_options()
    return options


def _rewrite_cars_brand_slug_in_url(url: str, brand_slug: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 3:
        return url
    if parts[1:3] != ["transport", "cars"]:
        return url
    if len(parts) >= 4:
        parts[3] = brand_slug
    else:
        parts.append(brand_slug)
    new_path = "/" + "/".join(parts) + "/"
    return urlunparse(parsed._replace(path=new_path))


def _is_numeric_field(name: str, field_type: str) -> bool:
    name_lower = name.lower()
    return field_type in {"number"} or any(kw in name_lower for kw in _NUMERIC_KEYWORDS)


def _spec_for_canonical(canonical_key: str):
    """Return the cars registry spec for a canonical key, or None."""
    return _CARS_SPECS_BY_CANONICAL.get(canonical_key)


def _resolve_field_by_canonical(schema: dict, canonical_key: str) -> tuple[str, dict] | tuple[None, None]:
    """Strict routing: resolve schema field from an explicit canonical key.

    Falls back to a synthetic select field for path-based keys (brand) whose
    options do not come from the schema at all.
    """
    spec = _spec_for_canonical(canonical_key)
    if spec is None:
        return None, None
    for raw_key in spec.raw_keys:
        if raw_key in schema:
            return raw_key, schema[raw_key]
    if spec.ss_param_mode == "path" or spec.canonical_key == "brand":
        return spec.raw_keys[0], {"label": "", "type": "select", "options": []}
    return None, None


def _input_mode_for(field_name: str, field_info: dict, profile: str | None) -> str:
    """Resolve input mode. For cars, the registry is the only authority."""
    if profile == "cars":
        canonical = canonical_filter_key_for_profile(field_name, profile)
        spec = _spec_for_canonical(canonical) if canonical else None
        if spec is not None:
            return spec.input_mode
    if _is_numeric_field(field_name, str(field_info.get("type", ""))):
        return "numeric"
    return "select" if field_info.get("options") else "numeric"


def _prompt_hint_key(field_name: str, field_info: dict, profile: str | None) -> str:
    """Per-canonical-key localized prompt hint (task I)."""
    if profile == "cars":
        canonical = canonical_filter_key_for_profile(field_name, profile)
        spec = _spec_for_canonical(canonical) if canonical else None
        if spec is not None:
            return spec.prompt_hint_i18n_key
    if _is_numeric_field(field_name, str(field_info.get("type", ""))):
        return "filter_hint_numeric"
    return "filter_hint_text"


async def _get_schema(url: str) -> dict:
    try:
        parser = SSParser()
        return await parser.discover_available_filters(url)
    except Exception as exc:
        logger.warning("filter_cmds: could not fetch schema for %s — %s", url, exc)
        return {}


def _sorted_fields(schema: dict, lang: str = "lv", profile: str | None = None) -> list[tuple[int, str, str, str]]:
    """Return (index, name, label, canonical_key) tuples in stable order.

    For cars, fields come exclusively from the canonical registry (strict,
    deduplicated, ordered) and each item carries its canonical key so the
    keyboard can embed it in callback payloads.
    """
    if profile == "cars":
        items: list[tuple[int, str, str, str]] = []
        idx = 0
        for spec in sorted(_CARS_SPECS_BY_CANONICAL.values(), key=lambda s: s.order):
            field_name = next((rk for rk in spec.raw_keys if rk in schema), None)
            if field_name is None:
                if spec.ss_param_mode == "path":
                    field_name = spec.raw_keys[0]
                else:
                    continue
            else:
                field_info = schema[field_name]
                if str(field_info.get("type", "")).lower() == "hidden":
                    continue
            label = filter_display_label(field_name, schema, lang, profile=profile)
            items.append((idx, field_name, label, spec.canonical_key))
            idx += 1
        return items

    seen_canonical: set[str] = set()
    raw_items: list[tuple[str, dict, str, str]] = []
    for name, info in sorted(schema.items()):
        if str(info.get("type", "")).lower() == "hidden":
            continue
        canonical = canonical_filter_key_for_profile(name, profile) or name.lower()
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)
        label = filter_display_label(name, schema, lang, profile=profile)
        raw_items.append((name, info, label, canonical))

    items = []
    for i, (name, _info, label, canonical) in enumerate(raw_items):
        ck = canonical if canonical in _CARS_SPECS_BY_CANONICAL else ""
        items.append((i, name, label, ck))
    return items


def _field_by_idx(
    schema: dict,
    field_order: list[str],
    fidx: int,
) -> tuple[str, dict] | tuple[None, None]:
    if 0 <= fidx < len(field_order):
        key = field_order[fidx]
        if key in schema:
            return key, schema[key]
    return None, None


def _find_selected_brand(
    current_filters: dict[str, str | list[str]],
    profile: str | None,
) -> tuple[str, str] | None:
    for raw_key, raw_value in current_filters.items():
        canonical = canonical_filter_key_for_profile(raw_key, profile)
        if canonical == "brand":
            if isinstance(raw_value, list):
                if raw_value:
                    return raw_key, str(raw_value[0])
            else:
                return raw_key, str(raw_value)
    return None


def _is_mismatched_option_source(canonical_key: str, options: list[dict], locale: str) -> bool:
    known_fuel = {
        "Бензин", "Дизель", "Газ", "Гибрид", "Электро",
        "Benzīns", "Dīzelis", "Gāze", "Hibrīds", "Elektriskais",
        "Petrol", "Diesel", "Gas", "Hybrid", "Electric",
    }
    known_body = {
        "Седан", "Универсал", "Хэтчбек", "Купе", "Кабриолет", "Минивэн", "Внедорожник", "Пикап",
        "Sedans", "Universāls", "Hečbeks", "Kupe", "Kabriolets", "Minivens", "SUV/Džips", "Pikaps",
        "Sedan", "Estate", "Hatchback", "Coupe", "Convertible", "Minivan", "SUV", "Pickup",
    }
    texts = {str(opt.get("display_text") or opt.get("text") or "").strip() for opt in options}
    texts.discard("")
    if not texts:
        return False

    if canonical_key == "model":
        return len(texts & known_fuel) > 0 or len(texts & known_body) > 0
    if canonical_key == "brand":
        return len(texts & known_fuel) > 0
    if canonical_key == "engine_type":
        return not bool(texts & known_fuel)
    if canonical_key == "body_type":
        return not bool(texts & known_body)
    if canonical_key == "gearbox":
        known_gearbox = {
            "Механика", "Автомат", "Робот", "Вариатор",
            "Manuāla", "Automāts", "Robota", "Variators",
            "Manual", "Automatic", "Robot", "CVT",
        }
        return not bool(texts & known_gearbox)
    return False


def _prepare_options_for_ui(
    *,
    field_name: str,
    options: list[dict],
    profile: str | None,
    lang: str,
    schema: dict | None = None,
) -> list[dict]:
    canonical = canonical_filter_key_for_profile(field_name, profile) or field_name
    prepared: list[dict] = []
    strict_value_domains = {"engine_type", "gearbox", "body_type", "color"}
    for opt in options:
        value = str(opt.get("value", "")).strip()
        if not value:
            continue
        display_text = filter_value_label(field_name, value, locale=lang, profile=profile, schema=schema)
        if display_text == value and canonical in strict_value_domains:
            display_text = get_text("filter_option_unavailable", lang)
        elif display_text == value and not str(opt.get("text", "")).strip() and canonical in {
            "brand", "model", "engine_type", "body_type", "gearbox", "color", "city_district",
        }:
            display_text = get_text("filter_option_unavailable", lang)
        if display_text == value and str(opt.get("text", "")).strip():
            display_text = str(opt.get("text", "")).strip()
        prepared.append({**opt, "display_text": sanitize_personal_ui_text(display_text, locale=lang, profile=profile)})

    logger.debug(
        "filter_options: canonical_key=%s locale=%s option_source=%s option_count=%d",
        canonical,
        lang,
        "schema",
        len(prepared),
    )
    return prepared


def _filters_lines(
    filters: dict,
    schema: dict | None = None,
    lang: str = "lv",
    profile: str | None = None,
) -> list[str]:
    """Format filters as bullet lines.

    Uses the profile-aware renderer when *profile* is given; falls back to
    the legacy ``filter_display_label``-based formatter otherwise.
    """
    if profile:
        return render_canonical_filters(filters, profile, locale=lang)
    return [
        f"  • {filter_display_label(k, schema, lang, profile=profile)} = "
        f"{filter_value_label(k, v, locale=lang, profile=profile, schema=schema)}"
        for k, v in filters.items()
    ]


def _autodetect_profile(search) -> str | None:
    """Auto-detect profile from a Search/GroupSearch URL for backward compatibility.

    For existing records that were saved before the ``category_profile`` column
    was introduced, we derive the profile on-the-fly from the stored URL.
    """
    from app.filters.profiles import detect_profile
    url = search.url or ""
    return detect_profile(url)


def _format_edit_prompt(
    *,
    lang: str,
    field_name: str,
    field_info: dict,
    current_value: str | None,
    profile: str | None,
) -> str:
    label = filter_display_label(field_name, schema={field_name: field_info}, locale=lang, profile=profile)
    current = (
        filter_value_label(
            field_name,
            current_value,
            locale=lang,
            profile=profile,
            schema={field_name: field_info},
        )
        if current_value
        else get_text("filter_current_value_missing", lang)
    )
    hint_key = _prompt_hint_key(field_name, field_info, profile)
    hint = get_text(hint_key, lang)
    prompt = get_text("filter_edit_prompt", lang, field=label, current=current, hint=hint)
    return sanitize_personal_ui_text(prompt, locale=lang, profile=profile)


async def _resolve_field_options(
    *,
    field_name: str,
    field_info: dict,
    search_url: str,
    current_filters: dict[str, str | list[str]],
    profile: str | None,
    lang: str,
    schema: dict,
) -> tuple[list[dict], str | None, str]:
    """Resolve options for a field with model-by-brand cascade and source guards."""
    canonical = canonical_filter_key_for_profile(field_name, profile) or field_name
    spec = _CARS_SPECS_BY_CANONICAL.get(canonical) if profile == "cars" else None
    source = "schema"
    if profile == "cars" and spec is None:
        return [], get_text("filter_options_unavailable", lang), "unknown_canonical"
    options = [o for o in field_info.get("options", []) if str(o.get("value", "")).strip()]

    if canonical == "brand" and profile == "cars":
        options = await _fetch_brand_slug_options(search_url, _cars_lang_from_url(search_url))
        source = "brand_path_slug"
        if not options:
            return [], get_text("filter_options_unavailable", lang), "brand_source_unavailable"

    if canonical == "model":
        selected_brand = _find_selected_brand(current_filters, profile)
        if selected_brand is None:
            return [], get_text("filter_select_brand_first", lang), "missing_brand"
        brand_key, brand_value = selected_brand
        scoped_filters = dict(current_filters)
        brand_slug = _normalize_brand_slug(brand_value)
        scoped_filters[brand_key] = brand_slug
        base_url = _rewrite_cars_brand_slug_in_url(base_url_without_query(search_url), brand_slug)
        scoped_url = build_effective_url(base_url, scoped_filters)
        scoped_schema = await _get_schema(scoped_url)
        scoped_field = scoped_schema.get(field_name)
        if scoped_field is not None:
            options = [
                o for o in scoped_field.get("options", [])
                if str(o.get("value", "")).strip()
            ]
            source = "model_scoped_by_brand"
        else:
            return [], get_text("filter_options_unavailable", lang), "model_scoped_missing"

    prepared = _prepare_options_for_ui(
        field_name=field_name,
        options=options,
        profile=profile,
        lang=lang,
        schema=schema,
    )

    if spec and spec.option_provider_id in {"brand", "model", "engine_type", "gearbox", "body_type"}:
        if _is_mismatched_option_source(canonical, prepared, lang):
            logger.error(
                "filter_option_source_guard: canonical_key=%s locale=%s option_source=%s option_count=%d",
                canonical,
                lang,
                source,
                len(prepared),
            )
            return [], get_text("filter_options_unavailable", lang), f"guard_mismatch:{canonical}"
    elif _is_mismatched_option_source(canonical, prepared, lang):
        logger.error(
            "filter_option_source_guard: canonical_key=%s locale=%s option_source=%s option_count=%d",
            canonical,
            lang,
            source,
            len(prepared),
        )
        return [], get_text("filter_options_unavailable", lang), f"guard_mismatch:{canonical}"

    logger.debug(
        "filter_options_resolved: canonical_key=%s locale=%s option_source=%s option_count=%d",
        canonical,
        lang,
        spec.option_provider_id if spec else source,
        len(prepared),
    )
    return prepared, None, (spec.option_provider_id if spec else source)


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("_safe_edit failed: %s", exc)


# ------------------------------------------------------------------ #
# /filters <search_id>                                                 #
# ------------------------------------------------------------------ #


@router.message(Command("filters"))
async def cmd_filters(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            get_text("err_usage_filters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(
            get_text("err_usage_filters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    content = (
        "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        if filters
        else get_text("filters_none", lang)
    )
    text = get_text("filters_header", lang, sid=sid, content=content)
    await message.answer(text, reply_markup=filters_menu_kb(sid, bool(filters), lang=lang))


# ------------------------------------------------------------------ #
# /setfilter <search_id> <field> <value>                              #
# ------------------------------------------------------------------ #


@router.message(Command("setfilter"))
async def cmd_setfilter(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            get_text("err_usage_setfilter", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_setfilter", lang), reply_markup=error_kb(lang=lang))
        return

    field = parts[2].strip()
    value = parts[3].strip()

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        repo.set_filter(search, field, value)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    safe_label = filter_display_label(field, locale=lang, profile=profile)
    safe_value = filter_value_label(field, value, locale=lang, profile=profile)
    await message.answer(
        sanitize_personal_ui_text(
            f"✅ <b>{safe_label}</b> = <b>{safe_value}</b> → #{sid}",
            locale=lang,
            profile=profile,
        ),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# /delfilter <search_id> <field>                                       #
# ------------------------------------------------------------------ #


@router.message(Command("delfilter"))
async def cmd_delfilter(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            get_text("err_usage_delfilter", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_delfilter", lang), reply_markup=error_kb(lang=lang))
        return

    field = parts[2].strip()

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        deleted = repo.delete_filter(search, field)
        sid = search.id
    finally:
        session.close()

    if not deleted:
        safe_label = filter_display_label(field, locale=lang)
        await message.answer(
            get_text("err_filter_key_not_found", lang, key=safe_label),
            reply_markup=error_kb(back_search_id=sid, lang=lang),
        )
        return

    await message.answer(
        get_text("filter_deleted_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# /clearfilters <search_id>                                            #
# ------------------------------------------------------------------ #


@router.message(Command("clearfilters"))
async def cmd_clearfilters(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None:
        return

    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory)

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            get_text("err_usage_clearfilters", lang),
            reply_markup=error_kb(lang=lang),
        )
        return

    try:
        search_id = int(parts[1].strip())
    except ValueError:
        await message.answer(get_text("err_usage_clearfilters", lang), reply_markup=error_kb(lang=lang))
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(search_id)
        if search is None or search.user_id != user_id:
            await message.answer(
                get_text("err_search_not_found_id", lang, sid=search_id),
                reply_markup=error_kb(lang=lang),
            )
            return
        existing_filters = filters_from_json(search.filters_json)
        sid = search.id
        if not existing_filters:
            await message.answer(
                get_text("err_no_filters_set", lang),
                reply_markup=no_filters_kb(sid, lang=lang),
            )
            return
        repo.clear_filters(search)
    finally:
        session.close()

    await message.answer(
        get_text("filter_cleared_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )


# ------------------------------------------------------------------ #
# FilterCB: show / del_start / edit_start / clear                      #
# ------------------------------------------------------------------ #


@router.callback_query(FilterCB.filter(F.action == "show"))
async def cb_filter_show(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not filters:
        await _safe_edit(
            callback,
            get_text("err_no_filters_set", lang),
            reply_markup=no_filters_kb(sid, lang=lang),
        )
    else:
        lines = [get_text("filters_header", lang, sid=sid, content="")]
        lines += _filters_lines(filters, lang=lang, profile=profile)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text("\n".join(lines), locale=lang, profile=profile),
            reply_markup=filters_menu_kb(sid, bool(filters), lang=lang),
        )

    await callback.answer()


@router.callback_query(FilterCB.filter(F.action == "del_start"))
async def cb_filter_del_start(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    """Show filters with individual delete buttons."""
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not filters:
        await _safe_edit(
            callback,
            get_text("err_no_filters_set", lang),
            reply_markup=no_filters_kb(sid, lang=lang),
        )
    else:
        content = "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        text = get_text("filters_header", lang, sid=sid, content=content)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text(text, locale=lang),
            reply_markup=filter_items_kb(sid, filters, lang=lang, profile=profile),
        )

    await callback.answer()


@router.callback_query(FilterCB.filter(F.action == "edit_start"))
async def cb_filter_edit_start(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        search_url = search.effective_url or search.url
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
        current_filters = filters_from_json(search.filters_json)
    finally:
        session.close()

    await callback.answer("⏳")

    schema = await _get_schema(search_url)
    if not schema:
        await _safe_edit(
            callback,
            get_text("err_filter_schema", lang),
            reply_markup=error_kb(back_search_id=sid, lang=lang),
        )
        return

    fields = _sorted_fields(schema, lang, profile=profile)
    field_order = [f[1] for f in fields]
    await state.update_data(
        schema=schema,
        sid=sid,
        profile=profile,
        current_filters=current_filters,
        search_url=search_url,
        field_order=field_order,
    )

    await _safe_edit(
        callback,
        get_text("filters_header", lang, sid=sid, content=""),
        reply_markup=filter_fields_kb(sid, fields, page=0, lang=lang),
    )


@router.callback_query(FilterCB.filter(F.action == "clear"))
async def cb_filter_clear(
    callback: CallbackQuery,
    callback_data: FilterCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        existing_filters = filters_from_json(search.filters_json)
        sid = search.id
        if not existing_filters:
            await _safe_edit(
                callback,
                get_text("err_no_filters_set", lang),
                reply_markup=no_filters_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        repo.clear_filters(search)
    finally:
        session.close()

    await _safe_edit(
        callback,
        get_text("filter_cleared_ok", lang),
        reply_markup=after_filter_kb(sid, lang=lang),
    )
    await callback.answer()


# ------------------------------------------------------------------ #
# FilterDelCB: delete a single filter                                  #
# ------------------------------------------------------------------ #


@router.callback_query(FilterDelCB.filter())
async def cb_filter_delete_key(
    callback: CallbackQuery,
    callback_data: FilterDelCB,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(callback_data.sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        deleted = repo.delete_filter(search, callback_data.key)
        filters = filters_from_json(search.filters_json)
        sid = search.id
        profile = search.category_profile or _autodetect_profile(search)
    finally:
        session.close()

    if not deleted:
        safe_label = filter_display_label(callback_data.key, locale=lang, profile=profile)
        await callback.answer(
            get_text("err_filter_key_not_found", lang, key=safe_label),
            show_alert=True,
        )
        return

    if filters:
        content = "\n".join(_filters_lines(filters, lang=lang, profile=profile))
        text = get_text("filters_header", lang, sid=sid, content=content)
        await _safe_edit(
            callback,
            sanitize_personal_ui_text(text, locale=lang, profile=profile),
            reply_markup=filter_items_kb(sid, filters, lang=lang, profile=profile),
        )
    else:
        await _safe_edit(
            callback,
            get_text("filter_deleted_ok", lang),
            reply_markup=after_filter_kb(sid, lang=lang),
        )
    await callback.answer()


# ------------------------------------------------------------------ #
# FilterEditCB: field selected → show options or ask for text         #
# ------------------------------------------------------------------ #


@router.callback_query(FilterEditCB.filter())
async def cb_filter_edit_field(
    callback: CallbackQuery,
    callback_data: FilterEditCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    data = await state.get_data()
    schema: dict = data.get("schema", {})
    sid: int = data.get("sid", callback_data.sid)
    profile: str | None = data.get("profile")
    current_filters: dict = data.get("current_filters", {})
    search_url: str = data.get("search_url", "")
    field_order: list[str] = data.get("field_order", [])

    # Re-fetch schema if not in state (e.g. after restart)
    if not schema:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(callback_data.sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            sid = search.id
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [f[1] for f in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            current_filters=current_filters,
            search_url=search_url,
            field_order=field_order,
        )
    elif not search_url:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search:
                search_url = search.effective_url or search.url
                await state.update_data(search_url=search_url)
        finally:
            session.close()

    # ---- Strict routing: canonical key from callback payload (cars) ----
    canonical_key = (callback_data.ck or "").strip()
    if profile == "cars":
        spec = None
        if canonical_key:
            spec = _spec_for_canonical(canonical_key)
            if spec is None:
                logger.error(
                    "filter_routing_guard: invalid canonical key=%r sid=%s profile=%s",
                    canonical_key, sid, profile,
                )
                await callback.answer(get_text("filter_input_mode_error", lang), show_alert=True)
                return
            field_name, field_info = _resolve_field_by_canonical(schema, canonical_key)
        else:
            # Legacy payload (pre-refactor button): derive canonical from schema field.
            field_name, field_info = _field_by_idx(schema, field_order, callback_data.fidx)
            if field_name is not None:
                canonical_key = canonical_filter_key_for_profile(field_name, profile) or ""
                spec = _spec_for_canonical(canonical_key)
        if field_name is None or spec is None:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return

        if spec.input_mode == "numeric":
            # Hard guard: numeric keys only ever open a numeric input prompt.
            await state.set_state(EditFilterFSM.waiting_value)
            await state.update_data(
                field_name=field_name,
                field_label=filter_display_label(field_name, schema=schema, locale=lang, profile=profile),
                field_info=field_info,
                profile=profile,
                sid=sid,
                prompt_msg_id=callback.message.message_id,
            )
            await _safe_edit(
                callback,
                _format_edit_prompt(
                    lang=lang,
                    field_name=field_name,
                    field_info=field_info,
                    current_value=current_filters.get(field_name),
                    profile=profile,
                ),
                reply_markup=cancel_kb(sid, lang=lang),
            )
            await callback.answer()
            return

        # Hard guard: select keys only ever open an options list.
        options, unavailable_message, option_source = await _resolve_field_options(
            field_name=field_name,
            field_info=field_info,
            search_url=search_url,
            current_filters=current_filters,
            profile=profile,
            lang=lang,
            schema=schema,
        )
        if not options:
            logger.error(
                "filter_input_mode_guard: canonical_key=%s input_mode=%s option_source=%s sid=%s",
                canonical_key, spec.input_mode, option_source, sid,
            )
            await _safe_edit(
                callback,
                sanitize_personal_ui_text(
                    unavailable_message or get_text("filter_options_unavailable", lang),
                    locale=lang,
                    profile=profile,
                ),
                reply_markup=after_filter_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=current_filters.get(field_name),
                profile=profile,
            ),
            reply_markup=filter_options_kb(
                sid, callback_data.fidx, options, page=0, lang=lang, ck=canonical_key,
            ),
        )
        await state.update_data(
            options=options,
            option_source=option_source,
            option_field_name=field_name,
            option_fidx=callback_data.fidx,
            option_ck=canonical_key,
        )
        await callback.answer()
        return

    # ---- Legacy flow for non-cars profiles (unchanged behavior) ----
    field_name, field_info = _field_by_idx(schema, field_order, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    options, unavailable_message, option_source = await _resolve_field_options(
        field_name=field_name,
        field_info=field_info,
        search_url=search_url,
        current_filters=current_filters,
        profile=profile,
        lang=lang,
        schema=schema,
    )

    if options:
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=current_filters.get(field_name),
                profile=profile,
            ),
            reply_markup=filter_options_kb(sid, callback_data.fidx, options, page=0, lang=lang),
        )
        await state.update_data(
            options=options,
            option_source=option_source,
            option_field_name=field_name,
            option_fidx=callback_data.fidx,
            option_ck="",
        )
    else:
        if unavailable_message:
            await _safe_edit(
                callback,
                sanitize_personal_ui_text(unavailable_message, locale=lang, profile=profile),
                reply_markup=after_filter_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        # Free-text input
        await state.set_state(EditFilterFSM.waiting_value)
        await state.update_data(
            field_name=field_name,
            field_label=filter_display_label(field_name, schema=schema, locale=lang, profile=profile),
            field_info=field_info,
            profile=profile,
            sid=sid,
            prompt_msg_id=callback.message.message_id,
        )
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=current_filters.get(field_name),
                profile=profile,
            ),
            reply_markup=cancel_kb(sid, lang=lang),
        )

    await callback.answer()


# ------------------------------------------------------------------ #
# FilterOptCB: option selected → save                                  #
# ------------------------------------------------------------------ #


@router.callback_query(FilterOptCB.filter())
async def cb_filter_opt(
    callback: CallbackQuery,
    callback_data: FilterOptCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    data = await state.get_data()
    schema: dict = data.get("schema", {})
    options: list = data.get("options", [])
    sid = callback_data.sid
    profile: str | None = data.get("profile")
    field_order: list[str] = data.get("field_order", [])
    option_field_name: str | None = data.get("option_field_name")
    search_url: str = data.get("search_url", "")
    current_filters: dict = data.get("current_filters", {})

    if not schema:
        # Recover schema
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [f[1] for f in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            field_order=field_order,
            current_filters=current_filters,
            search_url=search_url,
        )

    # ---- Strict routing: canonical key from callback payload (cars) ----
    ck = (callback_data.ck or "").strip() or str(data.get("option_ck") or "")
    if profile == "cars" and ck:
        spec = _spec_for_canonical(ck)
        if spec is None or spec.input_mode != "select":
            logger.error(
                "filter_routing_guard: invalid option canonical key=%r sid=%s input_mode=%s",
                ck, sid, spec.input_mode if spec else None,
            )
            await callback.answer(get_text("filter_input_mode_error", lang), show_alert=True)
            return
        field_name, field_info = _resolve_field_by_canonical(schema, ck)
    elif option_field_name and option_field_name in schema:
        field_name = option_field_name
        field_info = schema[field_name]
    else:
        field_name, field_info = _field_by_idx(schema, field_order, callback_data.fidx)
    if field_name is None:
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    # Re-build options if not cached, honoring strict cars option sources.
    if not options:
        if profile == "cars" and ck:
            options, unavailable_message, _src = await _resolve_field_options(
                field_name=field_name,
                field_info=field_info,
                search_url=search_url,
                current_filters=current_filters,
                profile=profile,
                lang=lang,
                schema=schema,
            )
            if not options:
                await _safe_edit(
                    callback,
                    sanitize_personal_ui_text(
                        unavailable_message or get_text("filter_options_unavailable", lang),
                        locale=lang,
                        profile=profile,
                    ),
                    reply_markup=after_filter_kb(sid, lang=lang),
                )
                await callback.answer()
                return
        else:
            options = _prepare_options_for_ui(
                field_name=field_name,
                options=field_info.get("options", []),
                profile=profile,
                lang=lang,
                schema=schema,
            )

    if callback_data.vidx < 0 or callback_data.vidx >= len(options):
        await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
        return

    chosen = options[callback_data.vidx]
    value = str(chosen.get("value", ""))
    canonical = canonical_filter_key_for_profile(field_name, profile)
    model_reset = False
    final_search_url = ""
    selected_brand_slug = ""
    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(sid)
        if search is None or search.user_id != user_id:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        existing_filters = filters_from_json(search.filters_json)
        previous_brand = None
        if canonical == "brand":
            for raw_key, raw_value in existing_filters.items():
                if canonical_filter_key_for_profile(raw_key, profile) == "brand":
                    previous_brand = str(raw_value)
                    break
            selected_brand_slug = _normalize_brand_slug(value)
            value = selected_brand_slug
        repo.set_filter(search, field_name, value)
        if canonical == "brand":
            merged_filters = filters_from_json(search.filters_json)
            rewritten_base = _rewrite_cars_brand_slug_in_url(search.base_url or search.url or "", selected_brand_slug)
            search.base_url = rewritten_base
            search.effective_url = build_effective_url(rewritten_base, merged_filters)
            final_search_url = search.effective_url or ""
            if f"/transport/cars/{selected_brand_slug}/" not in final_search_url:
                logger.warning(
                    "filter_cmds: brand slug validation failed slug=%s final_url=%s",
                    selected_brand_slug,
                    final_search_url,
                )
            logger.debug(
                "filter_cmds: selected_brand_slug=%s final_search_url=%s",
                selected_brand_slug,
                final_search_url,
            )
            session.add(search)
            session.commit()
        if canonical == "brand" and previous_brand is not None and previous_brand != value:
            # Brand changed; clear model to force fresh compatible selection.
            model_raw_keys = [
                key for key in filters_from_json(search.filters_json).keys()
                if canonical_filter_key_for_profile(key, profile) == "model"
            ]
            for model_key in model_raw_keys:
                repo.delete_filter(search, model_key)
                model_reset = True
    finally:
        session.close()

    await state.clear()
    await _safe_edit(
        callback,
        (
            f"{get_text('filter_set_ok', lang)}\n\n{get_text('filter_model_reset_after_brand_change', lang)}"
            if model_reset else get_text("filter_set_ok", lang)
        ),
        reply_markup=after_filter_kb(sid, lang=lang),
    )
    await callback.answer()


# ------------------------------------------------------------------ #
# PageCB: pagination                                                   #
# ------------------------------------------------------------------ #


@router.callback_query(PageCB.filter())
async def cb_page(
    callback: CallbackQuery,
    callback_data: PageCB,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    tg_lang = callback.from_user.language_code if callback.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    sid = callback_data.sid
    pg = callback_data.pg
    data = await state.get_data()
    schema: dict = data.get("schema", {})
    profile: str | None = data.get("profile")
    field_order: list[str] = data.get("field_order", [])
    current_filters: dict = data.get("current_filters", {})
    search_url: str = data.get("search_url", "")

    if not schema:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search is None or search.user_id != user_id:
                await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
                return
            search_url = search.effective_url or search.url
            profile = search.category_profile or _autodetect_profile(search)
            current_filters = filters_from_json(search.filters_json)
        finally:
            session.close()
        schema = await _get_schema(search_url)
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [f[1] for f in fields]
        await state.update_data(
            schema=schema,
            sid=sid,
            profile=profile,
            current_filters=current_filters,
            search_url=search_url,
            field_order=field_order,
        )
    elif not search_url:
        session = session_factory()
        try:
            repo = SearchRepository(session)
            search = repo.get_by_id(sid)
            if search:
                search_url = search.effective_url or search.url
                await state.update_data(search_url=search_url)
        finally:
            session.close()

    if callback_data.ctx == "fields":
        fields = _sorted_fields(schema, lang, profile=profile)
        field_order = [f[1] for f in fields]
        await state.update_data(field_order=field_order)
        await _safe_edit(
            callback,
            get_text("filters_header", lang, sid=sid, content=""),
            reply_markup=filter_fields_kb(sid, fields, page=pg, lang=lang),
        )
    elif callback_data.ctx == "opts":
        fidx = callback_data.fidx
        ck = (callback_data.ck or "").strip()
        if profile == "cars" and ck:
            spec = _spec_for_canonical(ck)
            if spec is None or spec.input_mode != "select":
                logger.error(
                    "filter_routing_guard: invalid page canonical key=%r sid=%s", ck, sid,
                )
                await callback.answer(get_text("filter_input_mode_error", lang), show_alert=True)
                return
            field_name, field_info = _resolve_field_by_canonical(schema, ck)
        else:
            field_name, field_info = _field_by_idx(schema, field_order, fidx)
        if field_name is None:
            await callback.answer(get_text("err_search_not_found_short", lang), show_alert=True)
            return
        options, unavailable_message, option_source = await _resolve_field_options(
            field_name=field_name,
            field_info=field_info,
            search_url=search_url,
            current_filters=current_filters,
            profile=profile,
            lang=lang,
            schema=schema,
        )
        if unavailable_message:
            await _safe_edit(
                callback,
                sanitize_personal_ui_text(unavailable_message, locale=lang, profile=profile),
                reply_markup=after_filter_kb(sid, lang=lang),
            )
            await callback.answer()
            return
        await state.update_data(
            options=options,
            option_source=option_source,
            option_field_name=field_name,
            option_fidx=fidx,
            option_ck=ck,
        )
        await _safe_edit(
            callback,
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=(data.get("current_filters") or {}).get(field_name),
                profile=profile,
            ),
            reply_markup=filter_options_kb(sid, fidx, options, page=pg, lang=lang, ck=ck),
        )

    await callback.answer()


# ------------------------------------------------------------------ #
# EditFilterFSM.waiting_value: receive free-text value                 #
# ------------------------------------------------------------------ #


@router.message(EditFilterFSM.waiting_value, F.text)
async def fsm_filter_value(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await try_delete_message(message)

    data = await state.get_data()
    field_name: str = data.get("field_name", "")
    field_label: str = data.get("field_label", field_name)
    field_info: dict = data.get("field_info", {"name": field_name, "type": "text"})
    profile: str | None = data.get("profile")
    sid: int = data.get("sid", 0)
    prompt_msg_id: int | None = data.get("prompt_msg_id")
    value = (message.text or "").strip()

    user_id = message.from_user.id if message.from_user else None
    tg_lang = message.from_user.language_code if message.from_user else None
    lang = get_user_lang(user_id, tg_lang, session_factory) if user_id else "lv"

    if not value:
        # Re-prompt
        if prompt_msg_id and message.bot:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_msg_id,
                    text=_format_edit_prompt(
                        lang=lang,
                        field_name=field_name,
                        field_info=field_info,
                        current_value=None,
                        profile=profile,
                    ),
                    reply_markup=cancel_kb(sid, lang=lang),
                )
                return
            except TelegramBadRequest:
                pass
        await message.answer(
            _format_edit_prompt(
                lang=lang,
                field_name=field_name,
                field_info=field_info,
                current_value=None,
                profile=profile,
            ),
            reply_markup=cancel_kb(sid, lang=lang),
        )
        return

    session = session_factory()
    try:
        repo = SearchRepository(session)
        search = repo.get_by_id(sid)
        if search is None or search.user_id != user_id:
            await state.clear()
            await message.answer(
                get_text("err_search_not_found_short", lang),
                reply_markup=error_kb(lang=lang),
            )
            return
        repo.set_filter(search, field_name, value)
    finally:
        session.close()

    await state.clear()

    text = get_text("filter_set_ok", lang)
    kb = after_filter_kb(sid, lang=lang)

    if prompt_msg_id and message.bot:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=prompt_msg_id,
                text=text,
                reply_markup=kb,
            )
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)

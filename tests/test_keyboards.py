"""Tests for keyboard builder functions."""
import pytest
from aiogram.types import InlineKeyboardMarkup

from app.bot.keyboards.main import main_menu_kb, lang_selection_kb
from app.bot.keyboards.searches import (
    after_action_kb,
    after_add_kb,
    error_kb,
    search_actions_kb,
    searches_list_kb,
)
from app.bot.keyboards.filters import (
    after_filter_kb,
    cancel_kb,
    filter_fields_kb,
    filter_items_kb,
    filter_options_kb,
    filters_menu_kb,
)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

class _FakeSearch:
    def __init__(self, id_: int, title: str = "Транспорт", is_active: bool = True):
        self.id = id_
        self.title = title
        self.is_active = is_active


# ------------------------------------------------------------------ #
# main keyboards                                                       #
# ------------------------------------------------------------------ #


def test_main_menu_kb_returns_markup():
    kb = main_menu_kb()
    assert isinstance(kb, InlineKeyboardMarkup)
    # Should have at least 3 buttons (searches, add, language)
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) >= 3


def test_main_menu_kb_has_correct_texts():
    kb = main_menu_kb(lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "📋 Мои поиски" in texts
    assert "➕ Добавить поиск" in texts
    assert "🌐 Язык / Valoda" in texts


def test_lang_selection_kb():
    kb = lang_selection_kb()
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "🇱🇻 Latviešu" in texts
    assert "🇷🇺 Русский" in texts
    assert "🇬🇧 English" in texts


# ------------------------------------------------------------------ #
# search keyboards                                                     #
# ------------------------------------------------------------------ #


def test_searches_list_kb_empty():
    kb = searches_list_kb([])
    assert isinstance(kb, InlineKeyboardMarkup)
    texts = {b.text for row in kb.inline_keyboard for b in row}
    # At least one button (add search in some language)
    assert len(texts) >= 1


def test_searches_list_kb_with_items():
    searches = [_FakeSearch(1), _FakeSearch(2, is_active=False)]
    kb = searches_list_kb(searches)
    buttons = [b for row in kb.inline_keyboard for b in row]
    # At least one button per search + add + menu
    assert len(buttons) >= 4


def test_search_actions_kb_active():
    kb = search_actions_kb(5, is_active=True, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "⏸ Пауза" in texts
    assert "▶️ Возобновить" not in texts


def test_search_actions_kb_paused():
    kb = search_actions_kb(5, is_active=False, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "▶️ Возобновить" in texts
    assert "⏸ Пауза" not in texts


def test_after_add_kb():
    kb = after_add_kb(3, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "⚙️ Фильтры" in texts
    assert "📋 Мои поиски" in texts


def test_after_action_kb():
    kb = after_action_kb(lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "📋 Мои поиски" in texts
    assert "🏠 В меню" in texts


def test_error_kb_without_search_id():
    kb = error_kb(lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "📋 Мои поиски" in texts
    assert "🏠 В меню" in texts


def test_error_kb_with_search_id():
    kb = error_kb(back_search_id=7, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "🔙 Назад к поиску" in texts


# ------------------------------------------------------------------ #
# filter keyboards                                                     #
# ------------------------------------------------------------------ #


def test_filters_menu_kb_no_filters():
    kb = filters_menu_kb(1, has_filters=False, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "♻️ Очистить фильтры" not in texts
    assert "👁 Показать фильтры" in texts


def test_filters_menu_kb_with_filters():
    kb = filters_menu_kb(1, has_filters=True, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "♻️ Очистить фильтры" in texts


def test_filter_items_kb():
    filters = {"pr_min": "5000", "pr_max": "15000"}
    kb = filter_items_kb(2, filters)
    buttons = [b for row in kb.inline_keyboard for b in row]
    # Each filter should have a delete button
    delete_texts = [b.text for b in buttons if b.text.startswith("🗑")]
    assert len(delete_texts) >= 2


def test_filter_fields_kb_pagination():
    fields = [(i, f"field_{i}", f"Field {i}") for i in range(20)]
    kb = filter_fields_kb(1, fields, page=0, lang="ru")
    assert isinstance(kb, InlineKeyboardMarkup)
    buttons = [b for row in kb.inline_keyboard for b in row]
    # Should have pagination "next" button since there are 20 fields
    nav_texts = [b.text for b in buttons]
    assert "След. ▶️" in nav_texts


def test_filter_fields_kb_no_prev_on_first_page():
    fields = [(i, f"field_{i}", f"Field {i}") for i in range(20)]
    kb = filter_fields_kb(1, fields, page=0, lang="ru")
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert "◀️ Пред." not in texts


def test_filter_options_kb():
    options = [{"value": str(i), "text": f"Option {i}"} for i in range(12)]
    kb = filter_options_kb(1, fidx=0, options=options, page=0, lang="ru")
    assert isinstance(kb, InlineKeyboardMarkup)
    buttons = [b for row in kb.inline_keyboard for b in row]
    nav_texts = [b.text for b in buttons]
    assert "След. ▶️" in nav_texts


def test_after_filter_kb():
    kb = after_filter_kb(4, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "👁 Показать фильтры" in texts
    assert "🔙 Назад к поиску" in texts


def test_cancel_kb():
    kb = cancel_kb(lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "❌ Отмена" in texts


def test_cancel_kb_with_search_id():
    kb = cancel_kb(search_id=3, lang="ru")
    texts = {b.text for row in kb.inline_keyboard for b in row}
    assert "🔙 Назад к поиску" in texts

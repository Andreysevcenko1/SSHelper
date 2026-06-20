"""Tests for CallbackData factories — pack/unpack round-trips."""
import pytest

from app.bot.callbacks import (
    FilterCB,
    FilterDelCB,
    FilterEditCB,
    FilterOptCB,
    LangCB,
    MenuCB,
    PageCB,
    SearchCB,
)


def _packed_len(cb) -> int:
    return len(cb.pack())


# ------------------------------------------------------------------ #
# MenuCB                                                              #
# ------------------------------------------------------------------ #


def test_menu_cb_pack_unpack():
    cb = MenuCB(action="main")
    packed = cb.pack()
    restored = MenuCB.unpack(packed)
    assert restored.action == "main"


def test_menu_cb_all_actions():
    for action in ("main", "searches", "add_start", "lang"):
        cb = MenuCB(action=action)
        assert MenuCB.unpack(cb.pack()).action == action


# ------------------------------------------------------------------ #
# LangCB                                                               #
# ------------------------------------------------------------------ #


def test_lang_cb_pack_unpack():
    for lang in ("lv", "ru", "en"):
        cb = LangCB(lang=lang)
        restored = LangCB.unpack(cb.pack())
        assert restored.lang == lang
        assert _packed_len(cb) < 64


# ------------------------------------------------------------------ #
# SearchCB                                                             #
# ------------------------------------------------------------------ #


def test_search_cb_pack_unpack():
    cb = SearchCB(action="pause", sid=42)
    restored = SearchCB.unpack(cb.pack())
    assert restored.action == "pause"
    assert restored.sid == 42


def test_search_cb_large_id():
    cb = SearchCB(action="view", sid=9_999_999_999)
    restored = SearchCB.unpack(cb.pack())
    assert restored.sid == 9_999_999_999
    assert _packed_len(cb) < 64


# ------------------------------------------------------------------ #
# FilterCB                                                             #
# ------------------------------------------------------------------ #


def test_filter_cb_pack_unpack():
    for action in ("show", "edit_start", "clear"):
        cb = FilterCB(action=action, sid=1)
        restored = FilterCB.unpack(cb.pack())
        assert restored.action == action


# ------------------------------------------------------------------ #
# FilterDelCB                                                          #
# ------------------------------------------------------------------ #


def test_filter_del_cb_short_key():
    cb = FilterDelCB(sid=1, key="pr_min")
    restored = FilterDelCB.unpack(cb.pack())
    assert restored.key == "pr_min"
    assert _packed_len(cb) < 64


def test_filter_del_cb_long_key_truncated():
    key = "a" * 40  # Max allowed truncation
    cb = FilterDelCB(sid=1, key=key)
    restored = FilterDelCB.unpack(cb.pack())
    assert restored.key == key
    assert _packed_len(cb) < 64


# ------------------------------------------------------------------ #
# FilterEditCB                                                         #
# ------------------------------------------------------------------ #


def test_filter_edit_cb():
    cb = FilterEditCB(sid=5, fidx=12, pg=2)
    restored = FilterEditCB.unpack(cb.pack())
    assert restored.fidx == 12
    assert restored.pg == 2
    assert _packed_len(cb) < 64


# ------------------------------------------------------------------ #
# FilterOptCB                                                          #
# ------------------------------------------------------------------ #


def test_filter_opt_cb():
    cb = FilterOptCB(sid=7, fidx=3, vidx=99, pg=1)
    restored = FilterOptCB.unpack(cb.pack())
    assert restored.fidx == 3
    assert restored.vidx == 99
    assert _packed_len(cb) < 64


# ------------------------------------------------------------------ #
# PageCB                                                               #
# ------------------------------------------------------------------ #


def test_page_cb_fields():
    cb = PageCB(ctx="fields", sid=1, fidx=-1, pg=3)
    restored = PageCB.unpack(cb.pack())
    assert restored.ctx == "fields"
    assert restored.pg == 3
    assert _packed_len(cb) < 64


def test_page_cb_opts():
    cb = PageCB(ctx="opts", sid=1, fidx=5, pg=2)
    restored = PageCB.unpack(cb.pack())
    assert restored.ctx == "opts"
    assert restored.fidx == 5
    assert _packed_len(cb) < 64

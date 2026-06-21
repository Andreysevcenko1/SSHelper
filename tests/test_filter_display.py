"""Tests ensuring raw SS.lv keys are never surfaced in user-facing UI strings."""
import re

import pytest

from app.services.filters import filter_display_label
from app.bot.keyboards.filters import filter_items_kb

# Pattern that must NOT appear in any user-visible string
_RAW_KEY_PATTERN = re.compile(r"opt\[|topt\[|mid\[")


# ------------------------------------------------------------------ #
# filter_display_label: pattern-based fallbacks                        #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "key,expected",
    [
        ("opt[123]", "Фильтр 123"),
        ("opt[]", "Фильтр"),
        ("topt[456]", "Фильтр 456"),
        ("topt[]", "Фильтр"),
        ("mid[78]", "Район 78"),
        ("mid[]", "Район"),
        ("pr_min", "Цена от"),
        ("pr_max", "Цена до"),
        ("PR_MIN", "Цена от"),
        ("PR_MAX", "Цена до"),
    ],
)
def test_display_label_pattern_fallbacks(key, expected):
    assert filter_display_label(key) == expected


def test_display_label_schema_takes_priority():
    schema = {"opt[123]": {"label": "Марка автомобиля"}}
    assert filter_display_label("opt[123]", schema) == "Марка автомобиля"


def test_display_label_schema_empty_label_falls_back():
    schema = {"opt[123]": {"label": ""}}
    assert filter_display_label("opt[123]", schema) == "Фильтр 123"


def test_display_label_generic_cleanup():
    # Keys without special patterns should still be cleaned up
    label = filter_display_label("deal_type")
    assert "[" not in label and "]" not in label


def test_display_label_never_returns_bracket_key_without_schema():
    for key in ("opt[1]", "topt[2]", "mid[3]"):
        label = filter_display_label(key)
        assert not _RAW_KEY_PATTERN.search(label), (
            f"Raw key pattern leaked into label for key={key!r}: {label!r}"
        )


# ------------------------------------------------------------------ #
# filter_items_kb: buttons must not contain raw key patterns           #
# ------------------------------------------------------------------ #


def test_filter_items_kb_no_raw_keys_in_buttons():
    """Button texts in filter_items_kb must never contain raw SS.lv key patterns."""
    filters = {
        "opt[123]": "456",
        "topt[789]": "10",
        "mid[11]": "12",
        "pr_min": "5000",
        "pr_max": "15000",
    }
    kb = filter_items_kb(search_id=1, filters=filters, lang="ru")
    for row in kb.inline_keyboard:
        for button in row:
            text = button.text or ""
            assert not _RAW_KEY_PATTERN.search(text), (
                f"Raw SS.lv key pattern found in button text: {text!r}"
            )


def test_filter_items_kb_with_schema_uses_schema_labels():
    """When schema is provided, filter_items_kb uses schema labels in buttons."""
    filters = {"opt[123]": "456"}
    schema = {"opt[123]": {"label": "Марка"}}
    kb = filter_items_kb(search_id=1, filters=filters, lang="ru", schema=schema)
    button_texts = [b.text for row in kb.inline_keyboard for b in row]
    delete_texts = [t for t in button_texts if t and t.startswith("🗑")]
    assert any("Марка" in t for t in delete_texts)

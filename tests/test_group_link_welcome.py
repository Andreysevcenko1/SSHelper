from app.bot.keyboards.main import GROUP_URL, main_menu_kb
from app.i18n import get_text


def test_welcome_contains_group_link_in_all_languages():
    for lang in ("lv", "ru", "en"):
        assert "https://t.me/ss_lvcom" in get_text("welcome", lang)


def test_main_menu_has_group_url_button():
    for lang in ("lv", "ru", "en"):
        buttons = [btn for row in main_menu_kb(lang).inline_keyboard for btn in row]
        assert any(btn.url == GROUP_URL for btn in buttons)

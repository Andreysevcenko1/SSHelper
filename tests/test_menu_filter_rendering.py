from types import SimpleNamespace

from app.bot.handlers.menu import _format_search_details


def _search(url: str, profile: str | None = None):
    return SimpleNamespace(
        id=1,
        title="flats",
        is_active=True,
        url=url,
        effective_url=url,
        category_profile=profile,
    )


def test_flats_filters_render_human_labels_no_raw_keys():
    search = _search("https://www.ss.lv/lv/real-estate/flats/riga/sell/")
    text = _format_search_details(
        search,
        {"topt[18][min]": "2", "opt[6]": "1", "pr_max": "150000"},
        "ru",
    )
    assert "Комнат" in text
    assert "Тип дома" in text
    assert "Цена" in text
    assert "opt[" not in text and "topt[" not in text


def test_cars_filters_render_human_labels_no_raw_keys():
    search = _search("https://www.ss.lv/lv/transport/cars/bmw/")
    text = _format_search_details(
        search,
        {"topt[8][min]": "2018", "opt[4]": "2", "opt[5]": "2"},
        "ru",
    )
    assert "Год" in text
    assert "Дизель" in text
    assert "Автомат" in text
    assert "opt[" not in text and "topt[" not in text


def test_unknown_profile_uses_safe_generic_labels():
    search = _search("https://www.ss.lv/lv/services/")
    text = _format_search_details(
        search,
        {"opt[999]": "1", "topt[888][min]": "5"},
        "ru",
    )
    assert "opt[" not in text and "topt[" not in text

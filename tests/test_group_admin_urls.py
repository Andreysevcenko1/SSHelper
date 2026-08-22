from app.bot.handlers.group_admin import _canonical_group_url


def test_canonical_group_url_rent_riga_root_to_all():
    url = "https://www.ss.lv/lv/real-estate/flats/riga/hand_over/"
    assert _canonical_group_url(url, "ire_riga") == (
        "https://www.ss.lv/lv/real-estate/flats/riga/all/hand_over/"
    )


def test_canonical_group_url_sell_riga_root_to_all():
    url = "https://www.ss.lv/lv/real-estate/flats/riga/sell/"
    assert _canonical_group_url(url, "sell_riga") == (
        "https://www.ss.lv/lv/real-estate/flats/riga/all/sell/"
    )


def test_canonical_group_url_keeps_non_matching_urls():
    url = "https://www.ss.lv/lv/real-estate/flats/riga/centre/hand_over/"
    assert _canonical_group_url(url, "ire_riga") == url

"""Paid subscription plan definitions (Telegram Stars pricing).

The free tier always allows 1 active search. Plans add extra slots for
30 days; buying a new plan replaces the current one immediately.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    plan_id: str
    extra_searches: int
    total_searches: int
    price_eur: str      # display only
    price_stars: int    # Telegram Stars (XTR) invoice amount
    label_i18n_key: str


PLANS: dict[str, Plan] = {
    "plus1": Plan("plus1", 1, 2, "1,99 €", 150, "sub_plan_plus1"),
    "plus4": Plan("plus4", 4, 5, "4,99 €", 380, "sub_plan_plus4"),
    "plus9": Plan("plus9", 9, 10, "8,99 €", 680, "sub_plan_plus9"),
}

PLAN_DURATION_DAYS = 30

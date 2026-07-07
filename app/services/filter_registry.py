"""Centralized SS.lv filter key registry for DM filter UI labels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterKeySpec:
    canonical_key: str
    label_i18n_key: str
    raw_keys: tuple[str, ...]


# Single source of truth: SS.lv raw query keys -> canonical semantic keys.
SS_FILTER_KEY_REGISTRY: tuple[FilterKeySpec, ...] = (
    FilterKeySpec(
        canonical_key="city_district",
        label_i18n_key="filter_lbl_city_district",
        raw_keys=("opt[17]",),
    ),
    FilterKeySpec(
        canonical_key="brand",
        label_i18n_key="filter_lbl_brand",
        raw_keys=("opt[32]",),
    ),
    FilterKeySpec(
        canonical_key="model",
        label_i18n_key="filter_lbl_model",
        raw_keys=("opt[34]",),
    ),
    FilterKeySpec(
        canonical_key="body_type",
        label_i18n_key="filter_lbl_body_type",
        raw_keys=("opt[35]",),
    ),
    FilterKeySpec(
        canonical_key="price_from",
        label_i18n_key="filter_lbl_price_from",
        raw_keys=("topt[15][min]", "pr_min", "price_min", "price_from"),
    ),
    FilterKeySpec(
        canonical_key="price_to",
        label_i18n_key="filter_lbl_price_to",
        raw_keys=("topt[15][max]", "pr_max", "price_max", "price_to"),
    ),
    FilterKeySpec(
        canonical_key="year_from",
        label_i18n_key="filter_lbl_year_from",
        raw_keys=("topt[18][min]",),
    ),
    FilterKeySpec(
        canonical_key="year_to",
        label_i18n_key="filter_lbl_year_to",
        raw_keys=("topt[18][max]",),
    ),
)


def registry_reverse_map() -> dict[str, FilterKeySpec]:
    """Return lowercased raw_key -> FilterKeySpec map."""
    reverse: dict[str, FilterKeySpec] = {}
    for spec in SS_FILTER_KEY_REGISTRY:
        for raw_key in spec.raw_keys:
            reverse[raw_key.lower()] = spec
    return reverse

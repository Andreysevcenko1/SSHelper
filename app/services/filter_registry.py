"""Centralized SS.lv filter key registry for DM filter UI labels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterKeySpec:
    canonical_key: str
    label_i18n_key: str
    raw_keys: tuple[str, ...]


@dataclass(frozen=True)
class CarFilterSpec:
    canonical_key: str
    label_i18n_key: str
    raw_keys: tuple[str, ...]
    option_provider_id: str
    input_mode: str
    order: int


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
        raw_keys=("opt[14]", "opt[32]"),
    ),
    FilterKeySpec(
        canonical_key="model",
        label_i18n_key="filter_lbl_model",
        raw_keys=("opt[15]", "opt[34]"),
    ),
    FilterKeySpec(
        canonical_key="body_type",
        label_i18n_key="filter_lbl_body_type",
        raw_keys=("opt[3]", "opt[35]"),
    ),
    FilterKeySpec(
        canonical_key="fuel_type",
        label_i18n_key="filter_lbl_fuel_type",
        raw_keys=("opt[4]",),
    ),
    FilterKeySpec(
        canonical_key="price_min",
        label_i18n_key="filter_lbl_price_from",
        raw_keys=("topt[15][min]", "topt[17][min]", "pr_min", "price_min", "price_from"),
    ),
    FilterKeySpec(
        canonical_key="price_max",
        label_i18n_key="filter_lbl_price_to",
        raw_keys=("topt[15][max]", "topt[17][max]", "pr_max", "price_max", "price_to"),
    ),
    FilterKeySpec(
        canonical_key="year_min",
        label_i18n_key="filter_lbl_year_from",
        raw_keys=("topt[18][min]",),
    ),
    FilterKeySpec(
        canonical_key="year_max",
        label_i18n_key="filter_lbl_year_to",
        raw_keys=("topt[18][max]",),
    ),
)


# Personal DM cars filters: strict semantic order/mapping/source contract.
CARS_DM_FILTER_REGISTRY: tuple[CarFilterSpec, ...] = (
    CarFilterSpec(
        canonical_key="price_min",
        label_i18n_key="filter_lbl_price_from",
        raw_keys=("topt[17][min]", "pr_min", "price_min", "opt[17]"),
        option_provider_id="price",
        input_mode="range",
        order=10,
    ),
    CarFilterSpec(
        canonical_key="price_max",
        label_i18n_key="filter_lbl_price_to",
        raw_keys=("topt[17][max]", "pr_max", "price_max", "opt[32]"),
        option_provider_id="price",
        input_mode="range",
        order=20,
    ),
    CarFilterSpec(
        canonical_key="year_min",
        label_i18n_key="filter_lbl_year_from",
        raw_keys=("topt[8][min]", "topt[18][min]"),
        option_provider_id="year",
        input_mode="range",
        order=30,
    ),
    CarFilterSpec(
        canonical_key="year_max",
        label_i18n_key="filter_lbl_year_to",
        raw_keys=("topt[8][max]", "topt[18][max]"),
        option_provider_id="year",
        input_mode="range",
        order=40,
    ),
    CarFilterSpec(
        canonical_key="volume_min",
        label_i18n_key="filter_lbl_volume_from",
        raw_keys=("topt[11][min]",),
        option_provider_id="volume",
        input_mode="range",
        order=50,
    ),
    CarFilterSpec(
        canonical_key="volume_max",
        label_i18n_key="filter_lbl_volume_to",
        raw_keys=("topt[11][max]",),
        option_provider_id="volume",
        input_mode="range",
        order=60,
    ),
    CarFilterSpec(
        canonical_key="engine_type",
        label_i18n_key="filter_lbl_engine_type",
        raw_keys=("opt[4]",),
        option_provider_id="engine_type",
        input_mode="select",
        order=70,
    ),
    CarFilterSpec(
        canonical_key="gearbox",
        label_i18n_key="filter_lbl_gearbox",
        raw_keys=("opt[5]",),
        option_provider_id="gearbox",
        input_mode="select",
        order=80,
    ),
    CarFilterSpec(
        canonical_key="body_type",
        label_i18n_key="filter_lbl_body_type",
        raw_keys=("opt[3]", "opt[35]"),
        option_provider_id="body_type",
        input_mode="select",
        order=90,
    ),
    CarFilterSpec(
        canonical_key="color",
        label_i18n_key="filter_lbl_color",
        raw_keys=("opt[6]",),
        option_provider_id="color",
        input_mode="select",
        order=100,
    ),
    CarFilterSpec(
        canonical_key="brand",
        label_i18n_key="filter_lbl_brand",
        raw_keys=("opt[14]",),
        option_provider_id="brand",
        input_mode="select",
        order=110,
    ),
    CarFilterSpec(
        canonical_key="model",
        label_i18n_key="filter_lbl_model",
        raw_keys=("opt[15]", "opt[34]"),
        option_provider_id="model",
        input_mode="select",
        order=120,
    ),
)


def registry_reverse_map() -> dict[str, FilterKeySpec]:
    """Return lowercased raw_key -> FilterKeySpec map."""
    reverse: dict[str, FilterKeySpec] = {}
    for spec in SS_FILTER_KEY_REGISTRY:
        for raw_key in spec.raw_keys:
            reverse[raw_key.lower()] = spec
    return reverse


def cars_registry_by_raw_key() -> dict[str, CarFilterSpec]:
    reverse: dict[str, CarFilterSpec] = {}
    for spec in CARS_DM_FILTER_REGISTRY:
        for raw_key in spec.raw_keys:
            reverse[raw_key.lower()] = spec
    return reverse


def cars_registry_by_canonical_key() -> dict[str, CarFilterSpec]:
    return {spec.canonical_key: spec for spec in CARS_DM_FILTER_REGISTRY}

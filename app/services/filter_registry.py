"""Centralized SS.lv filter key registry for DM filter UI labels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterKeySpec:
    canonical_key: str
    label_i18n_key: str
    raw_keys: tuple[str, ...]


INPUT_MODE_NUMERIC = "numeric"
INPUT_MODE_SELECT = "select"

SS_PARAM_MODE_QUERY = "query"
SS_PARAM_MODE_PATH = "path"


@dataclass(frozen=True)
class CarFilterSpec:
    canonical_key: str
    label_i18n_key: str
    raw_keys: tuple[str, ...]
    option_provider_id: str
    input_mode: str
    order: int
    prompt_hint_i18n_key: str = "filter_hint_select"
    ss_param_mode: str = SS_PARAM_MODE_QUERY


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
        input_mode=INPUT_MODE_NUMERIC,
        order=10,
        prompt_hint_i18n_key="filter_hint_price",
    ),
    CarFilterSpec(
        canonical_key="price_max",
        label_i18n_key="filter_lbl_price_to",
        raw_keys=("topt[17][max]", "pr_max", "price_max", "opt[32]"),
        option_provider_id="price",
        input_mode=INPUT_MODE_NUMERIC,
        order=20,
        prompt_hint_i18n_key="filter_hint_price",
    ),
    CarFilterSpec(
        canonical_key="year_min",
        label_i18n_key="filter_lbl_year_from",
        raw_keys=("topt[8][min]", "topt[18][min]"),
        option_provider_id="year",
        input_mode=INPUT_MODE_NUMERIC,
        order=30,
        prompt_hint_i18n_key="filter_hint_year",
    ),
    CarFilterSpec(
        canonical_key="year_max",
        label_i18n_key="filter_lbl_year_to",
        raw_keys=("topt[8][max]", "topt[18][max]"),
        option_provider_id="year",
        input_mode=INPUT_MODE_NUMERIC,
        order=40,
        prompt_hint_i18n_key="filter_hint_year",
    ),
    CarFilterSpec(
        canonical_key="volume_min",
        label_i18n_key="filter_lbl_volume_from",
        raw_keys=("topt[11][min]",),
        option_provider_id="volume",
        input_mode=INPUT_MODE_NUMERIC,
        order=50,
        prompt_hint_i18n_key="filter_hint_volume",
    ),
    CarFilterSpec(
        canonical_key="volume_max",
        label_i18n_key="filter_lbl_volume_to",
        raw_keys=("topt[11][max]",),
        option_provider_id="volume",
        input_mode=INPUT_MODE_NUMERIC,
        order=60,
        prompt_hint_i18n_key="filter_hint_volume",
    ),
    CarFilterSpec(
        canonical_key="engine_type",
        label_i18n_key="filter_lbl_engine_type",
        raw_keys=("opt[4]",),
        option_provider_id="engine_type",
        input_mode=INPUT_MODE_SELECT,
        order=70,
    ),
    CarFilterSpec(
        canonical_key="gearbox",
        label_i18n_key="filter_lbl_gearbox",
        raw_keys=("opt[5]",),
        option_provider_id="gearbox",
        input_mode=INPUT_MODE_SELECT,
        order=80,
    ),
    CarFilterSpec(
        canonical_key="body_type",
        label_i18n_key="filter_lbl_body_type",
        raw_keys=("opt[3]", "opt[35]"),
        option_provider_id="body_type",
        input_mode=INPUT_MODE_SELECT,
        order=90,
    ),
    CarFilterSpec(
        canonical_key="color",
        label_i18n_key="filter_lbl_color",
        raw_keys=("opt[6]",),
        option_provider_id="color",
        input_mode=INPUT_MODE_SELECT,
        order=100,
    ),
    CarFilterSpec(
        canonical_key="brand",
        label_i18n_key="filter_lbl_brand",
        raw_keys=("opt[14]",),
        option_provider_id="brand",
        input_mode=INPUT_MODE_SELECT,
        order=110,
        ss_param_mode=SS_PARAM_MODE_PATH,
    ),
    CarFilterSpec(
        canonical_key="model",
        label_i18n_key="filter_lbl_model",
        raw_keys=("opt[15]", "opt[34]"),
        option_provider_id="model",
        input_mode=INPUT_MODE_SELECT,
        order=120,
    ),
)

CARS_CANONICAL_KEYS: frozenset[str] = frozenset(
    spec.canonical_key for spec in CARS_DM_FILTER_REGISTRY
)

# Expected option provider per select key: guards against cross-source wiring.
_EXPECTED_SELECT_PROVIDERS: dict[str, str] = {
    "engine_type": "engine_type",
    "gearbox": "gearbox",
    "body_type": "body_type",
    "color": "color",
    "brand": "brand",
    "model": "model",
}


def _validate_cars_registry() -> None:
    seen_keys: set[str] = set()
    seen_orders: set[int] = set()
    for spec in CARS_DM_FILTER_REGISTRY:
        if spec.input_mode not in {INPUT_MODE_NUMERIC, INPUT_MODE_SELECT}:
            raise ValueError(f"invalid input_mode for {spec.canonical_key}: {spec.input_mode}")
        if spec.ss_param_mode not in {SS_PARAM_MODE_QUERY, SS_PARAM_MODE_PATH}:
            raise ValueError(f"invalid ss_param_mode for {spec.canonical_key}: {spec.ss_param_mode}")
        if spec.canonical_key in seen_keys:
            raise ValueError(f"duplicate canonical key: {spec.canonical_key}")
        if spec.order in seen_orders:
            raise ValueError(f"duplicate order for {spec.canonical_key}: {spec.order}")
        expected = _EXPECTED_SELECT_PROVIDERS.get(spec.canonical_key)
        if expected is not None and spec.option_provider_id != expected:
            raise ValueError(
                f"cross-wired option source for {spec.canonical_key}: "
                f"{spec.option_provider_id} != {expected}"
            )
        if not spec.raw_keys:
            raise ValueError(f"no raw keys for {spec.canonical_key}")
        seen_keys.add(spec.canonical_key)
        seen_orders.add(spec.order)


_validate_cars_registry()


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

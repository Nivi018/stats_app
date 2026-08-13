"""Funciones puras del mercado: probabilidad implícita, de-vig y CLV.

Independientes de FastAPI y ORM; compartidas por API y worker.
"""

import math

MARKET_OVER_UNDER = "over_under_2_5"
LINE_2_5 = 2.5
VALID_SELECTIONS = frozenset({"over", "under"})
OVERS_UNDERS = frozenset({MARKET_OVER_UNDER})

# Rango de overround aceptado para consenso automático (sin alerta).
OVERROUND_MIN = 1.00
OVERROUND_MAX = 1.30

# Antigüedad máxima por defecto de un snapshot para ser elegible en una predicción.
MAX_SNAPSHOT_AGE = 30 * 60  # segundos

# Máxima separación temporal entre over y under para considerarlos un par comparable.
MAX_PAIR_GAP = 60  # segundos


class InvalidOddsError(ValueError):
    """Cuota fuera de contrato (<=1, NaN, infinito)."""


class InvalidMarketError(ValueError):
    """Mercado, línea o selección fuera de contrato."""


def validate_odds(decimal_odds: float) -> float:
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        raise InvalidOddsError(f"Cuota inválida: {decimal_odds!r} (debe ser finita y > 1.0)")
    return decimal_odds


def implied_probability(decimal_odds: float) -> float:
    return 1.0 / validate_odds(decimal_odds)


def overround(over_odds: float, under_odds: float) -> float:
    return implied_probability(over_odds) + implied_probability(under_odds)


def remove_margin(over_odds: float, under_odds: float) -> tuple[float, float]:
    """Probabilidades sin margen (de-vig) para over y under."""
    p_over_raw = implied_probability(over_odds)
    p_under_raw = implied_probability(under_odds)
    total = p_over_raw + p_under_raw
    return p_over_raw / total, p_under_raw / total


def de_vig_fair_odds(over_odds: float, under_odds: float) -> tuple[float, float]:
    p_over, p_under = remove_margin(over_odds, under_odds)
    return 1.0 / p_over, 1.0 / p_under


def overround_is_anomalous(over_odds: float, under_odds: float) -> bool:
    value = overround(over_odds, under_odds)
    return not (OVERROUND_MIN <= value <= OVERROUND_MAX)


def clv_probability_pp(entry_no_vig_prob: float, closing_no_vig_prob: float) -> float:
    """CLV en puntos porcentuales: positivo si el cierre movió a favor de la entrada."""
    return (closing_no_vig_prob - entry_no_vig_prob) * 100.0


def clv_price_ratio(entry_decimal_odds: float, closing_decimal_odds: float) -> float:
    """Ratio de precio entrada/cierre - 1: positivo si el precio de entrada fue mejor."""
    validate_odds(entry_decimal_odds)
    validate_odds(closing_decimal_odds)
    return entry_decimal_odds / closing_decimal_odds - 1.0

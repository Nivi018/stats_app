"""Funciones puras del mercado: de-vig y CLV.

Independientes de FastAPI y ORM; compartidas por API y worker.
Las fórmulas base (cuota justa, implícita, edge, EV) viven en `app.domain.odds`.
"""

import math
from dataclasses import dataclass

from app.domain.odds import InvalidOddsError, implied_probability, validate_odds

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


class InvalidMarketError(ValueError):
    """Mercado, línea o selección fuera de contrato."""


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


@dataclass(frozen=True)
class DeVigResult:
    """Resultado de eliminar el margen de un mercado Over/Under 2.5.

    Conserva las cuotas originales y expone estado explícito cuando falta
    uno de los lados (no lanza error por faltante; solo por cuota inválida).
    """

    complete: bool
    over_odds: float | None = None
    under_odds: float | None = None
    over_probability: float | None = None
    under_probability: float | None = None
    fair_over_odds: float | None = None
    fair_under_odds: float | None = None
    missing: str | None = None  # "over" | "under" | "both"

    @property
    def normalized_overround(self) -> float | None:
        if not self.complete:
            return None
        return self.over_probability + self.under_probability


def de_vig(over_odds: float | None, under_odds: float | None) -> DeVigResult:
    """Elimina el margen normalizando las probabilidades a sumar ~1.0.

    Cuotas inválidas lanzan `InvalidOddsError`; un lado ausente produce un
    estado `complete=False` con `missing` explícito.
    """
    if over_odds is None and under_odds is None:
        return DeVigResult(complete=False, missing="both")
    if over_odds is None:
        validate_odds(under_odds)
        return DeVigResult(complete=False, under_odds=under_odds, missing="over")
    if under_odds is None:
        validate_odds(over_odds)
        return DeVigResult(complete=False, over_odds=over_odds, missing="under")

    p_over, p_under = remove_margin(over_odds, under_odds)
    fair_over, fair_under = de_vig_fair_odds(over_odds, under_odds)
    return DeVigResult(
        complete=True,
        over_odds=over_odds,
        under_odds=under_odds,
        over_probability=p_over,
        under_probability=p_under,
        fair_over_odds=fair_over,
        fair_under_odds=fair_under,
    )


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

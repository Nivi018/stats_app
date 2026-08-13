"""Fórmulas base del dominio estadístico.

Espejo de `apps/web/src/lib/domain/odds.ts`. Funciones puras, sin dependencia
de FastAPI ni ORM, compartidas por API y worker.

La precisión (cálculo crudo) y el redondeo (presentación) son decisiones
separadas: las funciones devuelven valores exactos y `round_to` solo se usa
en la capa de presentación.
"""

import math


class InvalidOddsError(ValueError):
    """Cuota fuera de contrato (<=1, NaN, infinito)."""


class InvalidProbabilityError(ValueError):
    """Probabilidad fuera del intervalo (0, 1]."""


def validate_odds(decimal_odds: float) -> float:
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        raise InvalidOddsError(f"Cuota inválida: {decimal_odds!r} (debe ser finita y > 1.0)")
    return decimal_odds


def _validate_probability(probability: float) -> float:
    if not math.isfinite(probability) or probability <= 0 or probability > 1:
        raise InvalidProbabilityError(f"Probabilidad inválida: {probability!r} (debe estar en (0, 1])")
    return probability


def implied_probability(decimal_odds: float) -> float:
    """Probabilidad implícita de una cuota decimal: 1 / cuota."""
    return 1.0 / validate_odds(decimal_odds)


def fair_odds(probability: float) -> float:
    """Cuota justa de una probabilidad de modelo: 1 / p."""
    return 1.0 / _validate_probability(probability)


def edge_pp(model_probability: float, market_probability: float) -> float:
    """Edge en puntos porcentuales: (p_modelo - p_mercado) * 100."""
    _validate_probability(model_probability)
    _validate_probability(market_probability)
    return (model_probability - market_probability) * 100.0


def expected_value(probability: float, decimal_odds: float) -> float:
    """Valor esperado por unidad apostada: p * cuota - 1."""
    _validate_probability(probability)
    validate_odds(decimal_odds)
    return probability * decimal_odds - 1.0


def round_to(value: float, digits: int = 4) -> float:
    """Redondeo explícito para presentación; no altera la precisión interna."""
    return round(value, digits)

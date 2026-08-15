"""Resolución de resultados de predicciones demo (US4).

Una predicción es inmutable: resolverla NUNCA la modifica. La resolución
produce un `PredictionOutcome` aparte con `result` en {win, loss, void}:

- **win/loss**: según el mercado y la selección contra el marcador final.
- **void**: mercado desconocido, marcador ausente o empate contra la línea
  (push). No cuenta como acierto ni como fallo.
"""

from app.model.baseline import MARKET

# Línea derivada del mercado canónico del MVP.
MARKET_LINE: dict[str, float] = {MARKET: 2.5}

WIN = "win"
LOSS = "loss"
VOID = "void"


def resolve_outcome(
    market: str,
    selection: str,
    home_score: int | None,
    away_score: int | None,
    *,
    line: float | None = None,
) -> str:
    """Determina el resultado de una selección contra el marcador final."""
    if line is None:
        line = MARKET_LINE.get(market)
    if line is None:
        return VOID
    if home_score is None or away_score is None:
        return VOID
    total = home_score + away_score
    if total == line:
        return VOID  # push

    if selection == "over":
        return WIN if total > line else LOSS
    if selection == "under":
        return WIN if total < line else LOSS
    return VOID

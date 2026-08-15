"""Baselines del backtest (US7): mercado, frecuencia de liga y Poisson.

Todos predicen la probabilidad de Over/Under 2.5; la cuota apostable es la del
mercado observado antes del kickoff. `None` indica que el baseline no pudo
producir probabilidad (cobertura).
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.walk_forward import MatchRecord
from app.domain.market import remove_margin
from app.features.feature_set import FeatureSet
from app.model.baseline import PoissonBaseline

OVER_UNDER_LINE = 2.5


def league_over_rate(train: list[MatchRecord]) -> float | None:
    """Frecuencia de Over en la liga dentro del bloque de entrenamiento."""
    scored = [r for r in train if r.has_score]
    if not scored:
        return None
    over = sum(1 for r in scored if (r.total_goals or 0) > OVER_UNDER_LINE)
    return over / len(scored)


def league_probability(train: list[MatchRecord], selection: str) -> float | None:
    rate = league_over_rate(train)
    if rate is None:
        return None
    return rate if selection == "over" else 1.0 - rate


def market_probability(record: MatchRecord, selection: str) -> float | None:
    if record.over_odds is None or record.under_odds is None:
        return None
    p_over, p_under = remove_margin(record.over_odds, record.under_odds)
    return p_over if selection == "over" else p_under


def market_odds(record: MatchRecord, selection: str) -> float | None:
    return record.over_odds if selection == "over" else record.under_odds


async def poisson_probabilities(
    session: AsyncSession,
    match_external_id: str,
    prediction_timestamp: datetime,
) -> tuple[float, float] | None:
    """Probabilidades Poisson sin lookahead: solo datos anteriores a `at`."""
    features = await FeatureSet().compute(session, match_external_id, prediction_timestamp)
    if features is None:
        return None
    over, under = PoissonBaseline().predict(features.lambda_home, features.lambda_away)
    return over.probability, under.probability

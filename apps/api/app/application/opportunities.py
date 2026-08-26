"""Servicio de oportunidades: combina predicciones persistidas con el mercado.

Para cada partido próximo empareja la última predicción del modelo con un par
de cuotas elegible (de-vig), calcula edge y EV, y aplica la política de
señales. No recalcula el modelo en cada request.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.domain.confidence import assess_confidence
from app.domain.odds import edge_pp, expected_value
from app.domain.stake import suggest_stake
from app.model.signal import evaluate_signal
from app.models import Match, OddsSnapshot, Prediction, Team
from app.odds.snapshots import Snapshot, de_vig_pair, is_eligible_at


@dataclass(frozen=True)
class Opportunity:
    match_id: str
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    market: str
    selection: str
    model_probability: float
    market_no_vig_probability: float
    observed_odds: float
    fair_odds: float
    edge_pp: float
    ev: float
    data_quality: str
    risk_level: str
    is_signal: bool
    signal_exclusions: list[str]
    snapshot_age_minutes: int
    confidence_level: str
    confidence_score: float
    confidence_factors: list[str]
    stake_pct: float | None
    stake_units: float | None


class OpportunityService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get_opportunities(
        self,
        at: datetime | None = None,
        *,
        min_edge: float = 0.0,
        risk: str | None = None,
        matchday: int | None = None,
        sort: str = "edge",
    ) -> list[Opportunity]:
        at = at or datetime.now(UTC)
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)

        async with self._session_factory() as session:
            home = aliased(Team)
            away = aliased(Team)
            matches = (
                await session.execute(
                    select(Match, home, away)
                    .join(home, Match.home_team_id == home.id)
                    .join(away, Match.away_team_id == away.id)
                    .where(Match.status == "scheduled")
                    .order_by(Match.kickoff_at)
                )
            ).all()

            match_ids = [m.id for m, _, _ in matches]

            # Cargas por lote: predicciones y snapshots en 2 consultas (sin N+1).
            preds = (
                await session.execute(
                    select(Prediction)
                    .where(
                        Prediction.match_id.in_(match_ids),
                        Prediction.market == "over_under_2_5",
                    )
                    .order_by(Prediction.prediction_timestamp.desc())
                )
            ).scalars().all()
            preds_by_match: dict = defaultdict(list)
            for pred in preds:
                preds_by_match[pred.match_id].append(pred)

            snap_rows = (
                await session.execute(
                    select(OddsSnapshot).where(OddsSnapshot.match_id.in_(match_ids))
                )
            ).scalars().all()
            snaps_by_match: dict = defaultdict(list)
            for row in snap_rows:
                snaps_by_match[row.match_id].append(Snapshot.from_model(row))

            opportunities: list[Opportunity] = []
            for match, home_team, away_team in matches:
                if matchday is not None and match.matchday != matchday:
                    continue

                match_preds = preds_by_match.get(match.id, [])
                if not match_preds:
                    continue

                odds = snaps_by_match.get(match.id, [])
                pair = de_vig_pair(odds, at)
                if pair is None:
                    continue
                market_no_vig = dict(zip(("over", "under"), pair.no_vig_probabilities))

                latest_by_selection: dict[str, Prediction] = {}
                for pred in match_preds:
                    latest_by_selection.setdefault(pred.selection, pred)

                for selection, pred in latest_by_selection.items():
                    snapshot = next(
                        (s for s in odds if s.selection == selection and is_eligible_at(s, at)),
                        None,
                    )
                    if snapshot is None:
                        continue
                    edge = edge_pp(pred.probability, market_no_vig[selection])
                    ev = expected_value(pred.probability, snapshot.odds)
                    age_seconds = max(0, (at - snapshot.observed_at).total_seconds())
                    decision = evaluate_signal(
                        selection=selection,
                        edge_pp=edge,
                        ev=ev,
                        data_quality=pred.data_quality,
                        snapshot_age_seconds=age_seconds,
                    )
                    confidence = assess_confidence(
                        probability=pred.probability,
                        data_quality=pred.data_quality,
                        freshness_seconds=age_seconds,
                    )
                    stake = suggest_stake(
                        probability=pred.probability,
                        decimal_odds=snapshot.odds,
                    )
                    opportunity = Opportunity(
                        match_id=match.external_id,
                        home_team_short=home_team.short_name or home_team.name,
                        away_team_short=away_team.short_name or away_team.name,
                        kickoff_at=match.kickoff_at,
                        market=pred.market,
                        selection=selection,
                        model_probability=pred.probability,
                        market_no_vig_probability=market_no_vig[selection],
                        observed_odds=snapshot.odds,
                        fair_odds=pred.fair_odds,
                        edge_pp=round(edge, 2),
                        ev=round(ev, 4),
                        data_quality=pred.data_quality,
                        risk_level=pred.risk_level,
                        is_signal=decision.is_signal,
                        signal_exclusions=decision.exclusions,
                        snapshot_age_minutes=int(age_seconds / 60),
                        confidence_level=confidence.level,
                        confidence_score=confidence.score,
                        confidence_factors=confidence.factors,
                        stake_pct=stake.stake_pct,
                        stake_units=stake.stake_units,
                    )
                    if opportunity.edge_pp < min_edge:
                        continue
                    if risk is not None and opportunity.risk_level != risk:
                        continue
                    opportunities.append(opportunity)

            return self._sort(opportunities, sort)

    @staticmethod
    def _sort(opportunities: list[Opportunity], sort: str) -> list[Opportunity]:
        """Orden determinista: señales primero; desempate por match_id."""
        if sort == "ev":
            key = lambda o: (not o.is_signal, -o.ev, o.match_id)
        elif sort == "probability":
            key = lambda o: (not o.is_signal, -o.model_probability, o.match_id)
        else:  # edge (default)
            key = lambda o: (not o.is_signal, -o.edge_pp, o.match_id)
        return sorted(opportunities, key=key)

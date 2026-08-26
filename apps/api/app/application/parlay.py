"""Caso de uso: estimación agregada de un parlay.

Resuelve cada selección canónica (`match_id`, `market`, `selection`) contra la
predicción y cuota vigentes, calcula cuota combinada, probabilidad estimada y
riesgo agregado, y reporta correlaciones. No persiste nada: es una consulta.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.confidence import assess_confidence
from app.domain.odds import edge_pp
from app.domain.parlay import (
    PARLAY_MAX,
    SelectionEstimate,
    SelectionRef,
    estimate_parlay,
)
from app.domain.stake import suggest_stake
from app.models import Match, OddsSnapshot, Prediction, Team


class SelectionUnresolvable(ValueError):
    """Una selección no puede resolverse (sin predicción, sin cuota o inexistente)."""


@dataclass(frozen=True)
class ResolvedSelection:
    key: str
    match_id: str
    market: str
    selection: str
    home_team_id: str
    away_team_id: str
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    probability: float
    odds: float
    fair_odds: float
    edge_pp: float
    data_quality: str
    risk_level: str
    confidence_level: str
    confidence_score: float
    confidence_factors: list[str]
    stake_pct: float | None
    stake_units: float | None


@dataclass(frozen=True)
class ParlayEstimateResult:
    selections: list[ResolvedSelection]
    combined_odds: float
    naive_probability: float
    estimated_probability: float
    fair_combined_odds: float | None
    risk_level: str
    risk_factors: list[str]
    correlation_warnings: list[str]
    assumes_independence: bool
    selection_count: int
    stake_pct: float | None
    stake_units: float | None


class ParlayService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def estimate(self, refs: list[dict]) -> ParlayEstimateResult:
        if not refs:
            raise SelectionUnresolvable("El parlay necesita al menos una selección")
        if len(refs) > PARLAY_MAX:
            raise SelectionUnresolvable(f"El parlay admite hasta {PARLAY_MAX} selecciones")

        async with self._session_factory() as session:
            resolved: list[ResolvedSelection] = []
            estimates: list[SelectionEstimate] = []
            risks: list[str] = []

            for ref in refs:
                selection = await self._resolve(session, ref)
                resolved.append(selection)
                estimates.append(
                    SelectionEstimate(
                        ref=SelectionRef(
                            match_id=selection.match_id,
                            market=selection.market,
                            selection=selection.selection,
                            teams=frozenset({selection.home_team_id, selection.away_team_id}),
                        ),
                        probability=selection.probability,
                        odds=selection.odds,
                    )
                )
                risks.append(selection.risk_level)

        estimate, _ = estimate_parlay(estimates, risks)
        aggregate = suggest_stake(
            probability=estimate.estimated_probability,
            decimal_odds=estimate.combined_odds,
        )
        return ParlayEstimateResult(
            selections=resolved,
            combined_odds=estimate.combined_odds,
            naive_probability=estimate.naive_probability,
            estimated_probability=estimate.estimated_probability,
            fair_combined_odds=estimate.fair_combined_odds,
            risk_level=estimate.risk_level,
            risk_factors=estimate.risk_factors,
            correlation_warnings=estimate.correlation_warnings,
            assumes_independence=estimate.assumes_independence,
            selection_count=estimate.selection_count,
            stake_pct=aggregate.stake_pct,
            stake_units=aggregate.stake_units,
        )

    async def _resolve(self, session: AsyncSession, ref: dict) -> ResolvedSelection:
        match_id = ref.get("match_id")
        market = ref.get("market")
        selection = ref.get("selection")
        if not match_id or not market or not selection:
            raise SelectionUnresolvable(f"Selección incompleta: {ref}")

        home = aliased(Team)
        away = aliased(Team)
        row = (
            await session.execute(
                select(Match, home, away)
                .join(home, Match.home_team_id == home.id)
                .join(away, Match.away_team_id == away.id)
                .where(Match.external_id == match_id)
            )
        ).one_or_none()
        if row is None:
            raise SelectionUnresolvable(f"Partido no encontrado: {match_id}")
        match, home_team, away_team = row

        prediction = (
            await session.execute(
                select(Prediction)
                .where(
                    Prediction.match_id == match.id,
                    Prediction.market == market,
                    Prediction.selection == selection,
                )
                .order_by(Prediction.prediction_timestamp.desc())
            )
        ).scalars().first()
        if prediction is None:
            raise SelectionUnresolvable(
                f"Sin predicción para {match_id}::{market}::{selection}"
            )

        snapshot = (
            await session.execute(
                select(OddsSnapshot)
                .where(
                    OddsSnapshot.match_id == match.id,
                    OddsSnapshot.market == market,
                    OddsSnapshot.selection == selection,
                )
                .order_by(OddsSnapshot.observed_at.desc())
            )
        ).scalars().first()
        if snapshot is None:
            raise SelectionUnresolvable(
                f"Sin cuota para {match_id}::{market}::{selection}"
            )

        home_short = home_team.short_name or home_team.name
        away_short = away_team.short_name or away_team.name
        observed = snapshot.observed_at
        now = datetime.now(timezone.utc)
        freshness = max(0, (now - observed).total_seconds())
        confidence = assess_confidence(
            probability=prediction.probability,
            data_quality=prediction.data_quality,
            freshness_seconds=freshness,
        )
        stake = suggest_stake(
            probability=prediction.probability,
            decimal_odds=snapshot.odds,
        )
        return ResolvedSelection(
            key=f"{match_id}::{market}::{selection}",
            match_id=match_id,
            market=market,
            selection=selection,
            home_team_id=str(home_team.id),
            away_team_id=str(away_team.id),
            home_team_short=home_short,
            away_team_short=away_short,
            kickoff_at=match.kickoff_at,
            probability=prediction.probability,
            odds=snapshot.odds,
            fair_odds=prediction.fair_odds,
            edge_pp=round(edge_pp(prediction.probability, 1 / snapshot.odds), 2),
            data_quality=prediction.data_quality,
            risk_level=prediction.risk_level,
            confidence_level=confidence.level,
            confidence_score=confidence.score,
            confidence_factors=confidence.factors,
            stake_pct=stake.stake_pct,
            stake_units=stake.stake_units,
        )

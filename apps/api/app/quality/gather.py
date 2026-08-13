"""Recolecta inputs de calidad/riesgo para un partido desde PostgreSQL."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market import overround
from app.models import Match, OddsSnapshot, TeamMatchStats
from app.odds.snapshots import Snapshot, de_vig_pair, is_eligible_at
from app.quality.assessment import QualityInputs

# Campos obligatorios de estadística por fila (para completitud).
REQUIRED_STATS_FIELDS = ("shots", "shots_on_target", "possession", "corners")

EXPECTED_STATS_ROWS = 2
EXPECTED_ODDS_SIDES = 2


async def gather_match_quality_inputs(
    session: AsyncSession,
    match_external_id: str,
    at: datetime,
) -> QualityInputs | None:
    match = (
        await session.execute(select(Match).where(Match.external_id == match_external_id))
    ).scalar_one_or_none()
    if match is None:
        return None

    stats_rows = (
        await session.execute(select(TeamMatchStats).where(TeamMatchStats.match_id == match.id))
    ).scalars().all()
    odds_rows = (
        await session.execute(select(OddsSnapshot).where(OddsSnapshot.match_id == match.id))
    ).scalars().all()

    has_both_stats = len(stats_rows) >= EXPECTED_STATS_ROWS

    present = 0
    total_fields = 0
    for row in stats_rows:
        for field in REQUIRED_STATS_FIELDS:
            total_fields += 1
            if getattr(row, field) is not None:
                present += 1
    completeness = present / total_fields if total_fields else 0.0

    snapshots = [Snapshot.from_model(s) for s in odds_rows]
    eligible = [s for s in snapshots if is_eligible_at(s, at)]
    has_both_odds = len({s.selection for s in eligible}) == EXPECTED_ODDS_SIDES

    freshness_seconds = 0.0
    overround_value = None
    if eligible:
        freshness_seconds = max((at - s.observed_at).total_seconds() for s in eligible)
        pair = de_vig_pair(snapshots, at)
        if pair is not None:
            overround_value = overround(pair.over.odds, pair.under.odds)

    present_entities = (1 if has_both_stats else 0) + (1 if has_both_odds else 0)
    coverage = present_entities / 2.0

    return QualityInputs(
        coverage_ratio=coverage,
        completeness_ratio=completeness,
        freshness_seconds=freshness_seconds,
        overround_value=overround_value,
        has_both_odds=has_both_odds,
        has_both_stats=has_both_stats,
    )

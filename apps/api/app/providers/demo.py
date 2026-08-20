"""Adaptadores demo que implementan los puertos canónicos leyendo de PostgreSQL.

Estos adaptadores cumplen exactamente los mismos contratos que los futuros
proveedores reales (`SportsDataProvider` y `OddsProvider`), de modo que el
dominio y la API no cambian al conectar un proveedor externo.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.session import async_session
from app.domain.providers import (
    DomainMatch,
    DomainOddsSnapshot,
    DomainTeam,
    DomainTeamMatchStats,
    InvalidProviderPayload,
    validate_match_status,
    validate_odds,
)
from app.models import Competition, Match, OddsSnapshot, Season, Team, TeamMatchStats


class DemoSportsDataProvider:
    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or async_session

    async def get_upcoming_matches(self) -> list[DomainMatch]:
        async with self._session_factory() as session:
            home = aliased(Team)
            away = aliased(Team)
            result = await session.execute(
                select(Match, Competition, home, away)
                .join(Season, Match.season_id == Season.id)
                .join(Competition, Season.competition_id == Competition.id)
                .join(home, Match.home_team_id == home.id)
                .join(away, Match.away_team_id == away.id)
                .where(Match.status == "scheduled")
                .order_by(Match.kickoff_at)
            )
            return [self._to_domain(m, c, h, a) for m, c, h, a in result.all()]

    async def get_match(self, match_id: str) -> DomainMatch | None:
        async with self._session_factory() as session:
            home = aliased(Team)
            away = aliased(Team)
            result = await session.execute(
                select(Match, Competition, home, away)
                .join(Season, Match.season_id == Season.id)
                .join(Competition, Season.competition_id == Competition.id)
                .join(home, Match.home_team_id == home.id)
                .join(away, Match.away_team_id == away.id)
                .where(Match.external_id == match_id)
            )
            row = result.first()
            if row is None:
                return None
            return self._to_domain(*row)

    async def get_team_match_stats(self, match_id: str) -> list[DomainTeamMatchStats]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TeamMatchStats, Team)
                .join(Match, TeamMatchStats.match_id == Match.id)
                .join(Team, TeamMatchStats.team_id == Team.id)
                .where(Match.external_id == match_id)
            )
            return [
                DomainTeamMatchStats(
                    match_id=match_id,
                    team_id=team.external_id,
                    goals=stats.goals,
                    shots=stats.shots,
                    shots_on_target=stats.shots_on_target,
                    possession=stats.possession,
                    corners=stats.corners,
                )
                for stats, team in result.all()
            ]

    @staticmethod
    def _to_domain(match: Match, competition: Competition, home: Team, away: Team) -> DomainMatch:
        return DomainMatch(
            id=match.external_id,
            competition=competition.name,
            kickoff_at=match.kickoff_at,
            home_team=DomainTeam(id=home.external_id, name=home.name, short_name=home.short_name or ""),
            away_team=DomainTeam(id=away.external_id, name=away.name, short_name=away.short_name or ""),
            status=validate_match_status(match.status),
        )


class DemoOddsProvider:
    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or async_session

    async def get_odds_snapshots(self, match_id: str) -> list[DomainOddsSnapshot]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OddsSnapshot)
                .join(Match, OddsSnapshot.match_id == Match.id)
                .where(Match.external_id == match_id)
                .order_by(OddsSnapshot.observed_at)
            )
            return [
                self._to_domain(match_id, snapshot)
                for snapshot in result.scalars().all()
            ]

    async def get_odds_snapshots_for_matches(self, match_ids: list[str]) -> dict[str, list[DomainOddsSnapshot]]:
        """Carga los snapshots de varios partidos en una sola consulta (evita N+1)."""
        if not match_ids:
            return {}
        async with self._session_factory() as session:
            result = await session.execute(
                select(Match, OddsSnapshot)
                .join(OddsSnapshot, OddsSnapshot.match_id == Match.id)
                .where(Match.external_id.in_(match_ids))
                .order_by(OddsSnapshot.observed_at)
            )
            grouped: dict[str, list[DomainOddsSnapshot]] = {}
            for match, snapshot in result.all():
                grouped.setdefault(match.external_id, []).append(
                    self._to_domain(match.external_id, snapshot)
                )
            return grouped

    @staticmethod
    def _to_domain(match_id: str, snapshot) -> DomainOddsSnapshot:
        return DomainOddsSnapshot(
            match_id=match_id,
            market=snapshot.market,
            selection=snapshot.selection,
            decimal_odds=snapshot.odds,
            captured_at=snapshot.observed_at,
            provider=snapshot.provider,
        )


class OddsSnapshotMapper:
    """Normaliza y valida snapshots de cuotas (para proveedores externos)."""

    @staticmethod
    def to_domain(
        match_id: str,
        market: str,
        selection: str,
        decimal_odds: float,
        captured_at,
        provider: str,
    ) -> DomainOddsSnapshot:
        validate_odds(market, selection, decimal_odds)
        return DomainOddsSnapshot(
            match_id=match_id,
            market=market,
            selection=selection,
            decimal_odds=decimal_odds,
            captured_at=captured_at,
            provider=provider,
        )


__all__ = [
    "DemoOddsProvider",
    "DemoSportsDataProvider",
    "InvalidProviderPayload",
    "OddsSnapshotMapper",
]

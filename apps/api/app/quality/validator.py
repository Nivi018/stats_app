"""Validador de integridad y calidad de datos.

La calidad de datos es una métrica **independiente de la probabilidad** de
acierto: describe cobertura, completitud, frescura y coherencia del dataset,
no cuán acertada es una predicción. Por eso el reporte expone
`metric_type = "data_quality"` y nunca "confidence".
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import VALID_MARKETS, VALID_SELECTIONS, VALID_STATUSES
from app.models import Match, OddsSnapshot, Team, TeamMatchStats

METRIC_TYPE = "data_quality"
_SEVERITY_PENALTY = {"critical": 10.0, "warning": 3.0, "info": 0.0}


@dataclass(frozen=True)
class DataAlert:
    severity: str
    check: str
    message: str
    provenance: list[str]
    count: int


@dataclass(frozen=True)
class DataQualityMetrics:
    teams: int
    matches_total: int
    matches_historical: int
    matches_upcoming: int
    stats_rows: int
    odds_rows: int
    coverage_stats: float
    coverage_odds: float


@dataclass(frozen=True)
class DataQualityReport:
    metric_type: str = METRIC_TYPE
    overall_score: float = 0.0
    metrics: DataQualityMetrics | None = None
    alerts: list[DataAlert] = field(default_factory=list)
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


async def _ids(session: AsyncSession, stmt) -> list[str]:
    return [r for r in (await session.execute(stmt)).scalars().all()]


class DataQualityValidator:
    async def analyze(self, session: AsyncSession) -> DataQualityReport:
        teams = (await session.execute(select(func.count()).select_from(Team))).scalar() or 0
        matches_total = (await session.execute(select(func.count()).select_from(Match))).scalar() or 0
        historical = (
            await session.execute(
                select(func.count()).select_from(Match).where(Match.status == "finished")
            )
        ).scalar() or 0
        upcoming = (
            await session.execute(
                select(func.count()).select_from(Match).where(Match.status == "scheduled")
            )
        ).scalar() or 0
        stats_rows = (await session.execute(select(func.count()).select_from(TeamMatchStats))).scalar() or 0
        odds_rows = (await session.execute(select(func.count()).select_from(OddsSnapshot))).scalar() or 0

        alerts: list[DataAlert] = []

        await self._check_missing_stats(session, alerts)
        await self._check_missing_odds(session, alerts)
        await self._check_duplicates(session, alerts)
        await self._check_invalid_odds(session, alerts)
        await self._check_invalid_stats(session, alerts)
        await self._check_invalid_status(session, alerts)

        with_stats = matches_total - sum(a.count for a in alerts if a.check == "missing_stats")
        coverage_stats = (with_stats / matches_total * 100.0) if matches_total else 100.0
        with_odds = upcoming - sum(a.count for a in alerts if a.check == "missing_odds")
        coverage_odds = (with_odds / upcoming * 100.0) if upcoming else 100.0

        metrics = DataQualityMetrics(
            teams=teams,
            matches_total=matches_total,
            matches_historical=historical,
            matches_upcoming=upcoming,
            stats_rows=stats_rows,
            odds_rows=odds_rows,
            coverage_stats=round(coverage_stats, 2),
            coverage_odds=round(coverage_odds, 2),
        )

        score = 100.0
        for alert in alerts:
            score -= _SEVERITY_PENALTY[alert.severity]
        score = max(0.0, round(score, 2))

        return DataQualityReport(overall_score=score, metrics=metrics, alerts=alerts)

    async def _check_missing_stats(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        with_stats = select(TeamMatchStats.match_id).distinct()
        missing = await session.execute(
            select(Match).where(~Match.id.in_(with_stats))
        )
        matches = missing.scalars().all()
        if matches:
            alerts.append(
                DataAlert(
                    severity="warning",
                    check="missing_stats",
                    message="Partidos sin estadísticas",
                    provenance=[m.external_id for m in matches],
                    count=len(matches),
                )
            )

    async def _check_missing_odds(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        with_odds = select(OddsSnapshot.match_id).distinct()
        missing = await session.execute(
            select(Match).where(Match.status == "scheduled", ~Match.id.in_(with_odds))
        )
        matches = missing.scalars().all()
        if matches:
            alerts.append(
                DataAlert(
                    severity="warning",
                    check="missing_odds",
                    message="Partidos próximos sin cuotas",
                    provenance=[m.external_id for m in matches],
                    count=len(matches),
                )
            )

    async def _check_duplicates(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        dup_matches = await session.execute(
            select(Match.external_id).group_by(Match.external_id).having(func.count() > 1)
        )
        dup_matches = dup_matches.scalars().all()
        if dup_matches:
            alerts.append(
                DataAlert("critical", "duplicate_match", "Partidos duplicados por external_id", list(dup_matches), len(dup_matches))
            )

        dup_teams = await session.execute(
            select(Team.external_id).group_by(Team.external_id).having(func.count() > 1)
        )
        dup_teams = dup_teams.scalars().all()
        if dup_teams:
            alerts.append(
                DataAlert("critical", "duplicate_team", "Equipos duplicados por external_id", list(dup_teams), len(dup_teams))
            )

        dup_odds = await session.execute(
            select(OddsSnapshot.idempotency_key).group_by(OddsSnapshot.idempotency_key).having(func.count() > 1)
        )
        dup_odds = dup_odds.scalars().all()
        if dup_odds:
            alerts.append(
                DataAlert("critical", "duplicate_odds", "Snapshots de cuota duplicados por idempotency key", list(dup_odds), len(dup_odds))
            )

    async def _check_invalid_odds(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        bad = await session.execute(
            select(OddsSnapshot).where(
                or_(
                    OddsSnapshot.odds <= 1.0,
                    ~OddsSnapshot.selection.in_(VALID_SELECTIONS),
                    ~OddsSnapshot.market.in_(VALID_MARKETS),
                )
            )
        )
        rows = bad.scalars().all()
        if rows:
            alerts.append(
                DataAlert(
                    "critical",
                    "invalid_odds",
                    "Cuotas fuera de contrato (<=1.0, selección o mercado inválido)",
                    [f"{r.idempotency_key}" for r in rows],
                    len(rows),
                )
            )

    async def _check_invalid_stats(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        bad = await session.execute(
            select(TeamMatchStats).where(
                or_(
                    TeamMatchStats.goals < 0,
                    TeamMatchStats.possession < 0,
                    TeamMatchStats.possession > 100,
                    TeamMatchStats.shots < 0,
                )
            )
        )
        rows = bad.scalars().all()
        if rows:
            alerts.append(
                DataAlert(
                    "critical",
                    "invalid_stats",
                    "Estadísticas fuera de rango (goles negativos, posesión fuera de [0,100])",
                    [f"{r.match_id}" for r in rows],
                    len(rows),
                )
            )

    async def _check_invalid_status(self, session: AsyncSession, alerts: list[DataAlert]) -> None:
        bad = await session.execute(
            select(Match).where(~Match.status.in_(VALID_STATUSES))
        )
        rows = bad.scalars().all()
        if rows:
            alerts.append(
                DataAlert(
                    "critical",
                    "invalid_status",
                    "Estado de partido fuera de contrato",
                    [r.external_id for r in rows],
                    len(rows),
                )
            )

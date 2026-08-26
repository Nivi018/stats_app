"""Caso de uso: contexto de partido (forma reciente y H2H) (Sprint 8)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.context import (
    FormEntry,
    MatchContext,
    TeamMatchRecord,
    build_context,
)
from app.models import Match, Team


class ContextService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get_context(self, match_id: str, *, limit: int = 5) -> MatchContext | None:
        async with self._session_factory() as session:
            match = (
                await session.execute(select(Match).where(Match.external_id == match_id))
            ).scalar_one_or_none()
            if match is None:
                return None

            involved = {match.home_team_id, match.away_team_id}
            rows = (
                await session.execute(
                    select(Match)
                    .where(
                        Match.status == "finished",
                        Match.kickoff_at < match.kickoff_at,
                        (
                            (Match.home_team_id.in_(involved))
                            | (Match.away_team_id.in_(involved))
                        ),
                    )
                    .order_by(Match.kickoff_at.desc())
                    .limit(200)
                )
            ).scalars().all()

            records = [
                TeamMatchRecord(
                    kickoff_at=r.kickoff_at,
                    home_team_id=str(r.home_team_id),
                    away_team_id=str(r.away_team_id),
                    home_score=r.home_score or 0,
                    away_score=r.away_score or 0,
                )
                for r in rows
            ]

            context = build_context(
                records,
                home_team_id=str(match.home_team_id),
                away_team_id=str(match.away_team_id),
                limit=limit,
            )
            return self._enrich(context, await self._team_map(session, involved))

    @staticmethod
    async def _team_map(session: AsyncSession, ids: set) -> dict:
        teams = (
            await session.execute(select(Team).where(Team.id.in_(ids)))
        ).scalars().all()
        return {str(t.id): (t.short_name or t.name) for t in teams}

    @staticmethod
    def _enrich(context: MatchContext, name_map: dict) -> MatchContext:
        def enrich(entries: list[FormEntry]) -> list[FormEntry]:
            return [
                FormEntry(
                    result=e.result,
                    opponent_short=name_map.get(e.opponent_short, e.opponent_short),
                    home_goals=e.home_goals,
                    away_goals=e.away_goals,
                    kickoff_at=e.kickoff_at,
                )
                for e in entries
            ]

        return MatchContext(
            home_form=enrich(context.home_form),
            away_form=enrich(context.away_form),
            h2h=enrich(context.h2h),
        )

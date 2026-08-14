"""Carga idempotente del dataset demo en PostgreSQL.

Usa claves naturales (external_id) para no duplicar entidades al ejecutar
varias veces. Todo el dataset se marca como `is_demo=True`.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competition, Match, OddsSnapshot, Season, Team, TeamMatchStats
from app.seeds.demo_dataset import (
    DemoDataset,
    DemoMatch,
    DemoOdds,
    DemoStats,
    DemoTeam,
    build_demo_dataset,
    dataset_counts,
)


@dataclass
class SeedManifest:
    version: str
    dataset_hash: str
    counts: dict[str, int]
    intentional_incomplete: list[str]
    generated_at: str


def _compute_dataset_hash(dataset: DemoDataset) -> str:
    payload = {
        "version": dataset.version,
        "competition": asdict(dataset.competition),
        "season": {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(dataset.season).items()},
        "teams": [asdict(t) for t in dataset.teams],
        "matches": [
            {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(m).items()}
            for m in dataset.matches
        ],
        "stats": [asdict(s) for s in dataset.stats],
        "odds": [
            {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(o).items()}
            for o in dataset.odds
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(dataset: DemoDataset) -> SeedManifest:
    return SeedManifest(
        version=dataset.version,
        dataset_hash=_compute_dataset_hash(dataset),
        counts=dataset_counts(dataset),
        intentional_incomplete=dataset.intentional_incomplete,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


async def _get_or_create_competition(session: AsyncSession, dataset: DemoDataset) -> Competition:
    stmt = select(Competition).where(Competition.external_id == dataset.competition.external_id)
    comp = (await session.execute(stmt)).scalar_one_or_none()
    if comp is None:
        comp = Competition(
            external_id=dataset.competition.external_id,
            name=dataset.competition.name,
            country=dataset.competition.country,
        )
        session.add(comp)
        await session.flush()
    return comp


async def _get_or_create_season(session: AsyncSession, competition_id, dataset: DemoDataset) -> Season:
    stmt = select(Season).where(
        Season.competition_id == competition_id,
        Season.name == dataset.season.name,
    )
    season = (await session.execute(stmt)).scalar_one_or_none()
    if season is None:
        season = Season(
            competition_id=competition_id,
            name=dataset.season.name,
            start_date=dataset.season.start_date,
            end_date=dataset.season.end_date,
        )
        session.add(season)
        await session.flush()
    return season


async def _load_teams(session: AsyncSession, teams: list[DemoTeam]) -> dict[str, Team]:
    result = await session.execute(select(Team).where(Team.external_id.in_([t.external_id for t in teams])))
    existing = {t.external_id: t for t in result.scalars()}

    for demo_team in teams:
        if demo_team.external_id not in existing:
            team = Team(
                external_id=demo_team.external_id,
                name=demo_team.name,
                short_name=demo_team.short_name,
            )
            session.add(team)
            existing[demo_team.external_id] = team
    await session.flush()
    return existing


async def _load_matches(
    session: AsyncSession,
    matches: list[DemoMatch],
    team_map: dict[str, Team],
    season: Season,
) -> dict[str, Match]:
    ids = [m.external_id for m in matches]
    result = await session.execute(select(Match).where(Match.external_id.in_(ids)))
    existing = {m.external_id: m for m in result.scalars()}

    for demo in matches:
        if demo.external_id not in existing:
            match = Match(
                external_id=demo.external_id,
                season_id=season.id,
                home_team_id=team_map[demo.home_external_id].id,
                away_team_id=team_map[demo.away_external_id].id,
                kickoff_at=demo.kickoff_at,
                status=demo.status,
                home_score=demo.home_score,
                away_score=demo.away_score,
                matchday=demo.matchday,
                is_demo=True,
            )
            session.add(match)
            existing[demo.external_id] = match
    await session.flush()
    return existing


async def _load_stats(
    session: AsyncSession,
    stats: list[DemoStats],
    match_map: dict[str, Match],
    team_map: dict[str, Team],
) -> None:
    pairs = [(s.match_external_id, s.team_external_id) for s in stats]
    for demo in stats:
        stmt = select(TeamMatchStats).where(
            TeamMatchStats.match_id == match_map[demo.match_external_id].id,
            TeamMatchStats.team_id == team_map[demo.team_external_id].id,
        )
        if (await session.execute(stmt)).scalar_one_or_none() is not None:
            continue
        session.add(
            TeamMatchStats(
                match_id=match_map[demo.match_external_id].id,
                team_id=team_map[demo.team_external_id].id,
                goals=demo.goals,
                shots=demo.shots,
                shots_on_target=demo.shots_on_target,
                possession=demo.possession,
                corners=demo.corners,
                is_demo=True,
            )
        )
    await session.flush()


async def _load_odds(session: AsyncSession, odds: list[DemoOdds], match_map: dict[str, Match]) -> None:
    for demo in odds:
        key = f"demo-{demo.match_external_id}-{demo.selection}"
        stmt = select(OddsSnapshot).where(OddsSnapshot.idempotency_key == key)
        if (await session.execute(stmt)).scalar_one_or_none() is not None:
            continue
        session.add(
            OddsSnapshot(
                match_id=match_map[demo.match_external_id].id,
                provider=demo.provider,
                market=demo.market,
                line=demo.line,
                selection=demo.selection,
                odds=demo.odds,
                observed_at=demo.observed_at,
                received_at=demo.observed_at,
                market_status="open",
                is_demo=True,
                idempotency_key=key,
            )
        )
    await session.flush()


async def load_demo_seed(session: AsyncSession) -> SeedManifest:
    """Carga el dataset demo de forma idempotente en una transacción."""
    dataset = build_demo_dataset()

    competition = await _get_or_create_competition(session, dataset)
    season = await _get_or_create_season(session, competition.id, dataset)
    team_map = await _load_teams(session, dataset.teams)
    match_map = await _load_matches(session, dataset.matches, team_map, season)
    await _load_stats(session, dataset.stats, match_map, team_map)
    await _load_odds(session, dataset.odds, match_map)

    await session.commit()
    return build_manifest(dataset)

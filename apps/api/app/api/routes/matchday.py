"""Endpoints de jornada y partido bajo `/api/v1`."""

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.matchday import MatchdayService
from app.core.errors import error_response
from app.schemas.matchday import (
    MatchDetailDto,
    MatchdayDto,
    OddsDto,
    TeamMatchStatsDto,
)

router = APIRouter()


def get_matchday_service(request: Request) -> MatchdayService:
    factory: Callable[[], AsyncSession] | None = getattr(request.app.state, "session_factory", None)
    return MatchdayService(session_factory=factory)


def _to_team_dto(team) -> dict:
    return {"id": team.id, "name": team.name, "short_name": team.short_name}


def _build_match_dto(match, over_odds: float | None = None, under_odds: float | None = None) -> dict:
    return {
        "id": match.id,
        "competition": match.competition,
        "kickoff_at": match.kickoff_at,
        "home_team": _to_team_dto(match.home_team),
        "away_team": _to_team_dto(match.away_team),
        "status": match.status,
        "over_odds": over_odds,
        "under_odds": under_odds,
    }


def _odds_selection(odds: list) -> tuple[float | None, float | None]:
    over = next((o.decimal_odds for o in odds if o.selection == "over"), None)
    under = next((o.decimal_odds for o in odds if o.selection == "under"), None)
    return over, under


def _to_odds_dto(o) -> OddsDto:
    return OddsDto(
        match_id=o.match_id,
        market=o.market,
        selection=o.selection,
        decimal_odds=o.decimal_odds,
        captured_at=o.captured_at,
        provider=o.provider,
    )


@router.get("/matchdays/current", response_model=MatchdayDto)
async def get_current_matchday(
    matchday: int = Query(1, ge=1, description="Número de jornada"),
    service: MatchdayService = Depends(get_matchday_service),
):
    matches = await service.get_current_matchday()
    result = []
    for match in matches:
        odds = await service.get_match_odds(match.id)
        over, under = _odds_selection(odds)
        result.append(_build_match_dto(match, over, under))
    return MatchdayDto(
        matchday=matchday,
        updated_at=datetime.now(timezone.utc),
        total_matches=len(result),
        matches=result,
    )


@router.get("/matches/{match_id}", response_model=MatchDetailDto)
async def get_match_detail(
    match_id: str,
    request: Request,
    service: MatchdayService = Depends(get_matchday_service),
):
    match = await service.get_match(match_id)
    if match is None:
        return error_response(404, "not_found", f"Partido no encontrado: {match_id}", request)

    odds = await service.get_match_odds(match_id)
    over, under = _odds_selection(odds)
    stats = await service.get_match_stats(match_id)

    return MatchDetailDto(
        match=_build_match_dto(match, over, under),
        stats=[TeamMatchStatsDto(**s.__dict__) for s in stats],
        odds=[_to_odds_dto(o) for o in odds],
    )


@router.get("/matches/{match_id}/odds", response_model=list[OddsDto])
async def get_match_odds(
    match_id: str,
    request: Request,
    service: MatchdayService = Depends(get_matchday_service),
):
    match = await service.get_match(match_id)
    if match is None:
        return error_response(404, "not_found", f"Partido no encontrado: {match_id}", request)
    odds = await service.get_match_odds(match_id)
    return [_to_odds_dto(o) for o in odds]

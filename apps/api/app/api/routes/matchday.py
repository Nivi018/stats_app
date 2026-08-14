"""Endpoints de jornada y partido bajo `/api/v1`."""

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.matchday import MatchdayService
from app.application.opportunities import OpportunityService
from app.core.errors import error_response
from app.explanation.builder import build_explanation
from app.models import Prediction
from app.schemas.matchday import (
    MatchDetailDto,
    MatchdayDto,
    OddsDto,
    OpportunityDto,
    PredictionDto,
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


def _to_prediction_dto(prediction: Prediction) -> PredictionDto:
    dto = PredictionDto.model_validate(prediction)
    dto.explanation = build_explanation(prediction)
    return dto


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
    predictions = await service.get_match_predictions(match_id)

    return MatchDetailDto(
        match=_build_match_dto(match, over, under),
        stats=[TeamMatchStatsDto(**s.__dict__) for s in stats],
        odds=[_to_odds_dto(o) for o in odds],
        predictions=[_to_prediction_dto(p) for p in predictions],
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


@router.get("/predictions/{prediction_id}", response_model=PredictionDto)
async def get_prediction(
    prediction_id: str,
    request: Request,
    service: MatchdayService = Depends(get_matchday_service),
):
    prediction = await service.get_prediction(prediction_id)
    if prediction is None:
        return error_response(404, "not_found", f"Predicción no encontrada: {prediction_id}", request)
    return _to_prediction_dto(prediction)


def get_opportunity_service(request: Request) -> OpportunityService:
    factory = getattr(request.app.state, "session_factory", None)
    return OpportunityService(factory)


@router.get("/opportunities", response_model=list[OpportunityDto])
async def get_opportunities(
    min_edge: float = Query(0, ge=-100, le=100, description="Edge mínimo en puntos porcentuales"),
    risk: str | None = Query(None, pattern="^(low|medium|high)$", description="Filtrar por nivel de riesgo"),
    matchday: int | None = Query(None, ge=1, description="Filtrar por jornada"),
    sort: str = Query("edge", pattern="^(edge|ev|probability)$", description="Orden"),
    service: OpportunityService = Depends(get_opportunity_service),
):
    opportunities = await service.get_opportunities(
        min_edge=min_edge,
        risk=risk,
        matchday=matchday,
        sort=sort,
    )
    return [
        OpportunityDto(
            match_id=o.match_id,
            home_team_short=o.home_team_short,
            away_team_short=o.away_team_short,
            kickoff_at=o.kickoff_at,
            market=o.market,
            selection=o.selection,
            model_probability=o.model_probability,
            market_no_vig_probability=o.market_no_vig_probability,
            observed_odds=o.observed_odds,
            fair_odds=o.fair_odds,
            edge_pp=o.edge_pp,
            ev=o.ev,
            data_quality=o.data_quality,
            risk_level=o.risk_level,
            is_signal=o.is_signal,
            signal_exclusions=o.signal_exclusions,
            snapshot_age_minutes=o.snapshot_age_minutes,
        )
        for o in opportunities
    ]

"""Endpoints del constructor de parlay bajo `/api/v1`."""

from fastapi import APIRouter, Depends, Request

from app.application.parlay import ParlayService, SelectionUnresolvable
from app.core.errors import error_response
from app.db.session import async_session
from app.schemas.parlay import (
    ParlayEstimateDto,
    ParlayEstimateRequest,
    ResolvedSelectionDto,
)

router = APIRouter()


def get_parlay_service(request: Request) -> ParlayService:
    factory = getattr(request.app.state, "session_factory", None)
    return ParlayService(factory or async_session)


@router.post("/parlays/estimate", response_model=ParlayEstimateDto)
async def estimate_parlay(
    body: ParlayEstimateRequest,
    request: Request,
    service: ParlayService = Depends(get_parlay_service),
):
    try:
        result = await service.estimate([s.model_dump() for s in body.selections])
    except SelectionUnresolvable as exc:
        return error_response(422, "unresolvable_selection", str(exc), request)

    return ParlayEstimateDto(
        selections=[
            ResolvedSelectionDto(
                key=s.key,
                match_id=s.match_id,
                market=s.market,
                selection=s.selection,
                home_team_short=s.home_team_short,
                away_team_short=s.away_team_short,
                kickoff_at=s.kickoff_at,
                probability=s.probability,
                odds=s.odds,
                fair_odds=s.fair_odds,
                edge_pp=s.edge_pp,
                data_quality=s.data_quality,
                risk_level=s.risk_level,
                confidence_level=s.confidence_level,
                confidence_score=s.confidence_score,
                confidence_factors=s.confidence_factors,
            )
            for s in result.selections
        ],
        combined_odds=result.combined_odds,
        naive_probability=result.naive_probability,
        estimated_probability=result.estimated_probability,
        fair_combined_odds=result.fair_combined_odds,
        risk_level=result.risk_level,
        risk_factors=result.risk_factors,
        correlation_warnings=result.correlation_warnings,
        assumes_independence=result.assumes_independence,
        selection_count=result.selection_count,
    )

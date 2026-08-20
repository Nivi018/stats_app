"""Endpoints de evaluación (métricas e historial) bajo `/api/v1`."""

from fastapi import APIRouter, Depends, Query, Request

from app.application.metrics import MetricsService
from app.db.session import async_session
from app.schemas.evaluation import (
    CalibrationBinDto,
    HistoryItemDto,
    HistoryPageDto,
    MetricsDto,
    ModelVersionDto,
)

router = APIRouter()


def get_metrics_service(request: Request) -> MetricsService:
    factory = getattr(request.app.state, "session_factory", None)
    return MetricsService(factory or async_session)


@router.get("/model-versions", response_model=list[ModelVersionDto])
async def get_model_versions(
    service: MetricsService = Depends(get_metrics_service),
):
    versions = await service.list_model_versions()
    return [
        ModelVersionDto(
            id=v.id,
            name=v.name,
            version=v.version,
            status=v.status,
            feature_set_version=v.feature_set_version,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/metrics", response_model=MetricsDto)
async def get_metrics(
    model_version_id: str | None = Query(None, description="Filtrar por versión de modelo"),
    threshold: int = Query(30, ge=1, description="Muestra mínima para considerar suficiente"),
    service: MetricsService = Depends(get_metrics_service),
):
    report = await service.get_metrics(model_version_id, threshold=threshold)
    return MetricsDto(
        model_version_id=report.model_version_id,
        sample_size=report.sample_size,
        wins=report.wins,
        losses=report.losses,
        voids=report.voids,
        hit_rate=report.hit_rate,
        unit_roi=report.unit_roi,
        brier=report.brier,
        calibration_bins=[
            CalibrationBinDto(
                label=b.label,
                lower=b.lower,
                upper=b.upper,
                n=b.n,
                mean_predicted=b.mean_predicted,
                observed_rate=b.observed_rate,
            )
            for b in report.calibration_bins
        ],
        sample_sufficient=report.sample_sufficient,
        threshold=report.threshold,
    )


@router.get("/history", response_model=HistoryPageDto)
async def get_history(
    model_version: str | None = Query(None, description="Filtrar por versión de modelo"),
    result: str | None = Query(
        None,
        pattern="^(win|loss|void)$",
        description="Filtrar por resultado",
    ),
    matchday: int | None = Query(None, ge=1, description="Filtrar por jornada"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MetricsService = Depends(get_metrics_service),
):
    from app.application.history import HistoryService

    history = HistoryService(service._session_factory)
    result_page = await history.get_history(
        model_version=model_version,
        result=result,
        matchday=matchday,
        page=page,
        page_size=page_size,
    )
    return HistoryPageDto(
        items=[
            HistoryItemDto(
                prediction_id=i.prediction_id,
                match_id=i.match_id,
                home_team_short=i.home_team_short,
                away_team_short=i.away_team_short,
                kickoff_at=i.kickoff_at,
                market=i.market,
                selection=i.selection,
                probability=i.probability,
                odds=i.odds,
                model_version=i.model_version,
                prediction_timestamp=i.prediction_timestamp,
                result=i.result,
                resolved_at=i.resolved_at,
            )
            for i in result_page.items
        ],
        page=result_page.page,
        page_size=result_page.page_size,
        total=result_page.total,
        total_pages=result_page.total_pages,
    )

"""Schemas de evaluación (métricas e historial) del API v1."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

OutcomeResult = Literal["win", "loss", "void"]


class CalibrationBinDto(BaseModel):
    label: str
    lower: float
    upper: float
    n: int
    mean_predicted: float | None = None
    observed_rate: float | None = None


class MetricsDto(BaseModel):
    model_version_id: str | None = None
    sample_size: int
    wins: int
    losses: int
    voids: int
    hit_rate: float | None = None
    unit_roi: float | None = None
    brier: float | None = None
    calibration_bins: list[CalibrationBinDto]
    sample_sufficient: bool
    threshold: int


class ModelVersionDto(BaseModel):
    id: UUID
    name: str
    version: str
    status: str
    feature_set_version: str
    created_at: datetime


class HistoryItemDto(BaseModel):
    prediction_id: UUID
    match_id: str
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    market: str
    selection: str
    probability: float
    odds: float | None = None
    model_version: str
    prediction_timestamp: datetime
    result: OutcomeResult
    resolved_at: datetime


class HistoryPageDto(BaseModel):
    items: list[HistoryItemDto]
    page: int
    page_size: int
    total: int
    total_pages: int

"""Schemas de respuesta del API v1.

Estos modelos son el contrato observable de la API; espejan el OpenAPI
canónico en `packages/contracts/openapi.yaml`.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TeamDto(BaseModel):
    id: str
    name: str
    short_name: str


class MatchDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    competition: str
    kickoff_at: datetime
    home_team: TeamDto
    away_team: TeamDto
    status: str
    over_odds: float | None = None
    under_odds: float | None = None


class MatchdayDto(BaseModel):
    matchday: int
    updated_at: datetime
    total_matches: int
    matches: list[MatchDto]


class TeamMatchStatsDto(BaseModel):
    match_id: str
    team_id: str
    goals: int
    shots: int | None = None
    shots_on_target: int | None = None
    possession: float | None = None
    corners: int | None = None


class OddsDto(BaseModel):
    match_id: str
    market: str
    selection: str
    decimal_odds: float
    captured_at: datetime
    provider: str


class MatchDetailDto(BaseModel):
    match: MatchDto
    stats: list[TeamMatchStatsDto]
    odds: list[OddsDto]


class PredictionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    model_version_id: UUID
    market: str
    selection: str
    probability: float
    fair_odds: float
    implied_probability: float | None = None
    no_vig_probability: float | None = None
    edge_pp: float | None = None
    ev: float | None = None
    data_quality: str
    risk_level: str
    inputs: str | None = None
    inputs_hash: str
    prediction_timestamp: datetime


class ErrorDto(BaseModel):
    code: str
    message: str
    details: dict | None = None
    correlation_id: str


class OpportunityDto(BaseModel):
    match_id: str
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    market: str
    selection: str
    model_probability: float
    market_no_vig_probability: float
    observed_odds: float
    fair_odds: float
    edge_pp: float
    ev: float
    data_quality: str
    risk_level: str
    is_signal: bool
    signal_exclusions: list[str]
    snapshot_age_minutes: int

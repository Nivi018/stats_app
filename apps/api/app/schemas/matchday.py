"""Schemas de respuesta del API v1.

Estos modelos son el contrato observable de la API; espejan el OpenAPI
canónico en `packages/contracts/openapi.yaml`.
"""

from datetime import datetime

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


class ErrorDto(BaseModel):
    code: str
    message: str
    details: dict | None = None
    correlation_id: str

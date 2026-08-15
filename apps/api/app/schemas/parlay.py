"""Schemas del parlay para el API v1.

El contrato observable del constructor de parlay; espeja el OpenAPI canónico.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SelectionName = Literal["over", "under"]


class ParlaySelectionRef(BaseModel):
    match_id: str
    market: str = "over_under_2_5"
    selection: SelectionName


class ParlayEstimateRequest(BaseModel):
    selections: list[ParlaySelectionRef]


class ResolvedSelectionDto(BaseModel):
    key: str
    match_id: str
    market: str
    selection: SelectionName
    home_team_short: str
    away_team_short: str
    kickoff_at: datetime
    probability: float
    odds: float
    fair_odds: float
    edge_pp: float
    data_quality: str
    risk_level: str


class ParlayEstimateDto(BaseModel):
    selections: list[ResolvedSelectionDto]
    combined_odds: float
    naive_probability: float
    estimated_probability: float
    fair_combined_odds: float | None = None
    risk_level: str
    risk_factors: list[str]
    correlation_warnings: list[str]
    assumes_independence: bool
    selection_count: int

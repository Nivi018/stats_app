"""Contratos canónicos del dominio para proveedores de datos.

Espeja `apps/web/src/lib/domain/providers.ts`. El dominio no depende de
ORM, bases de datos ni proveedores externos.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

VALID_STATUSES = frozenset({"scheduled", "finished"})
VALID_MARKETS = frozenset({"over_under_2_5"})
VALID_SELECTIONS = frozenset({"over", "under"})


class InvalidProviderPayload(Exception):
    """Payload de proveedor inválido (datos fuera de contrato)."""


@dataclass(frozen=True)
class DomainTeam:
    id: str
    name: str
    short_name: str


@dataclass(frozen=True)
class DomainMatch:
    id: str
    competition: str
    kickoff_at: datetime
    home_team: DomainTeam
    away_team: DomainTeam
    status: str


@dataclass(frozen=True)
class DomainTeamMatchStats:
    match_id: str
    team_id: str
    goals: int
    shots: int | None
    shots_on_target: int | None
    possession: float | None
    corners: int | None


@dataclass(frozen=True)
class DomainOddsSnapshot:
    match_id: str
    market: str
    selection: str
    decimal_odds: float
    captured_at: datetime
    provider: str


def validate_match_status(status: str) -> str:
    if status not in VALID_STATUSES:
        raise InvalidProviderPayload(f"status inválido: {status!r}")
    return status


def validate_odds(market: str, selection: str, decimal_odds: float) -> None:
    if market not in VALID_MARKETS:
        raise InvalidProviderPayload(f"mercado inválido: {market!r}")
    if selection not in VALID_SELECTIONS:
        raise InvalidProviderPayload(f"selección inválida: {selection!r}")
    if decimal_odds <= 1.0:
        raise InvalidProviderPayload(f"cuota inválida: {decimal_odds!r} (debe ser > 1.0)")


class SportsDataProvider(Protocol):
    async def get_upcoming_matches(self) -> list[DomainMatch]: ...

    async def get_match(self, match_id: str) -> DomainMatch | None: ...

    async def get_team_match_stats(self, match_id: str) -> list[DomainTeamMatchStats]: ...


class OddsProvider(Protocol):
    async def get_odds_snapshots(self, match_id: str) -> list[DomainOddsSnapshot]: ...

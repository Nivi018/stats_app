"""Contexto de partido: forma reciente y cara a cara (H2H) (Sprint 8).

Función pura sobre registros de partidos finalizados. NO inventa datos: solo
usa resultados reales anteriores al partido en cuestión. `home_form` /
`away_form` son los últimos N resultados de cada equipo; `h2h` son los
enfrentamientos directos entre ambos.
"""

from dataclasses import dataclass
from datetime import datetime

FORM_LIMIT = 5


@dataclass(frozen=True)
class TeamMatchRecord:
    kickoff_at: datetime
    home_team_id: str
    away_team_id: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class FormEntry:
    result: str  # W | D | L
    opponent_short: str
    home_goals: int
    away_goals: int
    kickoff_at: datetime


@dataclass(frozen=True)
class MatchContext:
    home_form: list[FormEntry]
    away_form: list[FormEntry]
    h2h: list[FormEntry]


def _result_for(record: TeamMatchRecord, team_id: str) -> str:
    if record.home_team_id == team_id:
        diff = record.home_score - record.away_score
    else:
        diff = record.away_score - record.home_score
    if diff > 0:
        return "W"
    if diff < 0:
        return "L"
    return "D"


def _opponent_of(record: TeamMatchRecord, team_id: str) -> str:
    return record.away_team_id if record.home_team_id == team_id else record.home_team_id


def _form_for(records: list[TeamMatchRecord], team_id: str, limit: int) -> list[FormEntry]:
    matches = [r for r in records if r.home_team_id == team_id or r.away_team_id == team_id]
    matches = sorted(matches, key=lambda r: r.kickoff_at, reverse=True)[:limit]
    return [
        FormEntry(
            result=_result_for(r, team_id),
            opponent_short=_opponent_of(r, team_id),
            home_goals=r.home_score,
            away_goals=r.away_score,
            kickoff_at=r.kickoff_at,
        )
        for r in matches
    ]


def _h2h(
    records: list[TeamMatchRecord],
    home_team_id: str,
    away_team_id: str,
    limit: int,
) -> list[FormEntry]:
    direct = [
        r
        for r in records
        if {r.home_team_id, r.away_team_id} == {home_team_id, away_team_id}
    ]
    direct = sorted(direct, key=lambda r: r.kickoff_at, reverse=True)[:limit]
    return [
        FormEntry(
            result=_result_for(r, home_team_id),
            opponent_short=away_team_id,
            home_goals=r.home_score,
            away_goals=r.away_score,
            kickoff_at=r.kickoff_at,
        )
        for r in direct
    ]


def build_context(
    records: list[TeamMatchRecord],
    *,
    home_team_id: str,
    away_team_id: str,
    limit: int = FORM_LIMIT,
) -> MatchContext:
    return MatchContext(
        home_form=_form_for(records, home_team_id, limit),
        away_form=_form_for(records, away_team_id, limit),
        h2h=_h2h(records, home_team_id, away_team_id, limit),
    )

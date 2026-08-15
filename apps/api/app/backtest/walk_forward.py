"""Splits cronológicos walk-forward deterministas (US7).

El mismo conjunto de partidos ordenados por kickoff produce siempre los mismos
pliegues: el orden se desempata por `external_id`. Cada pliegue usa SOLO partidos
anteriores como entrenamiento (ventana expandida) y predice un bloque contiguo
posterior; el último bloque es el holdout final y NO participa en decisiones de
promoción.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from app.domain.resolve import resolve_outcome

DEFAULT_N_FOLDS = 4


@dataclass(frozen=True)
class MatchRecord:
    external_id: str
    kickoff_at: datetime
    home_team_id: str
    away_team_id: str
    home_score: int | None
    away_score: int | None
    matchday: int | None = None
    over_odds: float | None = None
    under_odds: float | None = None

    @property
    def has_score(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def total_goals(self) -> int | None:
        if not self.has_score:
            return None
        return (self.home_score or 0) + (self.away_score or 0)

    def outcome_for(self, selection: str) -> str:
        return resolve_outcome("over_under_2_5", selection, self.home_score, self.away_score)


@dataclass(frozen=True)
class Fold:
    index: int
    train: tuple[MatchRecord, ...]
    test: tuple[MatchRecord, ...]

    @property
    def train_size(self) -> int:
        return len(self.train)

    @property
    def test_size(self) -> int:
        return len(self.test)


def sort_chronologically(matches: list[MatchRecord]) -> list[MatchRecord]:
    """Orden determinista por kickoff; desempate por external_id."""
    return sorted(matches, key=lambda m: (m.kickoff_at, m.external_id))


def walk_forward_splits(
    matches: list[MatchRecord],
    n_folds: int = DEFAULT_N_FOLDS,
) -> list[Fold]:
    """Divide cronológicamente en pliegues de ventana expandida."""
    if n_folds < 2:
        raise ValueError("n_folds debe ser >= 2")

    ordered = sort_chronologically(matches)
    n = len(ordered)
    folds: list[Fold] = []

    if n < n_folds:
        # Dataset pequeño: un solo pliegue con todo como test y entrenamiento vacío.
        return [Fold(index=0, train=(), test=tuple(ordered))]

    chunk = math.ceil(n / n_folds)
    for i in range(n_folds):
        start = i * chunk
        end = min((i + 1) * chunk, n)
        if end <= start:
            break
        folds.append(
            Fold(
                index=i,
                train=tuple(ordered[:start]),
                test=tuple(ordered[start:end]),
            )
        )
    return folds


def final_holdout(matches: list[MatchRecord], n_folds: int = DEFAULT_N_FOLDS) -> list[MatchRecord]:
    """Último bloque cronológico: no participa en tuning ni promoción."""
    ordered = sort_chronologically(matches)
    if not ordered:
        return []
    chunk = math.ceil(len(ordered) / n_folds)
    return ordered[-chunk:]

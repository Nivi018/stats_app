"""Mercados derivados de la distribución de marcadores (Sprint 10).

Parte de una matriz de marcadores P(home=i, away=j) construida como producto de
dos Poisson independientes. De ahí derivamos:

- **1X2**: P(local), P(empate), P(visitante).
- **Totales por equipo**: Over/Under con una línea (p. ej. 1.5 goles) para casa
  o visita.
- **Hándicap**: P(de que un equipo "cubra" un hándicap).

Todas las probabilidades de un mismo mercado son de-vig (suman 1) y repetibles.
"""

import math

MAX_GOALS = 10


def poisson_pmf(k: int, lam: float) -> float:
    if k < 0 or lam < 0:
        raise ValueError("k >= 0 y lam >= 0")
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = MAX_GOALS,
) -> list[list[float]]:
    """P(home=i, away=j) como producto de dos Poisson."""
    ph = [poisson_pmf(i, lambda_home) for i in range(max_goals + 1)]
    pa = [poisson_pmf(j, lambda_away) for j in range(max_goals + 1)]
    tail_home = 1 - sum(ph)
    tail_away = 1 - sum(pa)
    ph_adj = [p for p in ph]
    pa_adj = [p for p in pa]
    ph_adj[-1] += tail_home
    pa_adj[-1] += tail_away
    return [[ph_adj[i] * pa_adj[j] for j in range(max_goals + 1)] for i in range(max_goals + 1)]


def probability_1x2(matrix: list[list[float]]) -> tuple[float, float, float]:
    """P(local), P(empate), P(visitante)."""
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            if i > j:
                p_home += matrix[i][j]
            elif i == j:
                p_draw += matrix[i][j]
            else:
                p_away += matrix[i][j]
    total = p_home + p_draw + p_away
    if total <= 0:
        return 0.0, 0.0, 0.0
    return p_home / total, p_draw / total, p_away / total


def probability_team_total(
    matrix: list[list[float]],
    *,
    team: str,  # home | away
    outcome: str,  # over | under
    line: float,
) -> float:
    """P(over/under una línea) para los goles de un equipo."""
    if team not in ("home", "away") or outcome not in ("over", "under"):
        raise ValueError("team en home/away; outcome en over/under")
    p_over = 0.0
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            goals = i if team == "home" else j
            if goals > line:
                p_over += matrix[i][j]
    p_over = min(1.0, max(0.0, p_over))
    if outcome == "over":
        return p_over
    return 1.0 - p_over


def probability_handicap(
    matrix: list[list[float]],
    *,
    team: str,  # home | away
    line: float,  # hándicap aplicado al equipo (positivo = favorito; negativo = +goles)
    covers: bool,  # True -> cubre (margen > 0)
) -> float:
    """P(que el equipo cubra o no el hándicap sobre el margen)."""
    if team not in ("home", "away"):
        raise ValueError("team en home/away")
    p_cover = 0.0
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            if team == "home":
                margin = (i + line) - j
            else:
                margin = i - (j + line)
            if (margin > 0) if covers else (margin <= 0):
                p_cover += matrix[i][j]
    p_cover = min(1.0, max(0.0, p_cover))
    return p_cover

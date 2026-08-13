"""Motor Poisson: funciones puras para goles y Over/Under 2.5.

Independiente de FastAPI, ORM y proveedores. Misma entrada produce la misma
salida (reproducible); los fixtures dorados fijan tolerancias.
"""

import math

MAX_GOALS = 20  # tope de la matriz de marcadores


def poisson_pmf(k: int, lam: float) -> float:
    """P(X=k) para X ~ Poisson(lam)."""
    if k < 0 or lam < 0:
        raise ValueError("k >= 0 y lam >= 0")
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def total_goals_pmf(lambda_home: float, lambda_away: float, max_goals: int = MAX_GOALS) -> dict[int, float]:
    """Distribución de goles totales como convolución de dos Poisson."""
    probs: dict[int, float] = {}
    for h in range(max_goals + 1):
        p_h = poisson_pmf(h, lambda_home)
        if p_h == 0:
            continue
        for a in range(max_goals + 1):
            total = h + a
            probs[total] = probs.get(total, 0.0) + p_h * poisson_pmf(a, lambda_away)
    return probs


def over_under_2_5(lambda_home: float, lambda_away: float) -> tuple[float, float]:
    """Probabilidades de Over 2.5 y Under 2.5 (complementarias)."""
    pmf = total_goals_pmf(lambda_home, lambda_away)
    p_over = sum(p for total, p in pmf.items() if total >= 3)
    p_under = 1.0 - p_over
    return p_over, p_under


def expected_goals(lambda_home: float, lambda_away: float) -> float:
    """Goles esperados totales del partido."""
    return lambda_home + lambda_away

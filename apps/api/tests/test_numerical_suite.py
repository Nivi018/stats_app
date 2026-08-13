"""Suite numérica del motor estadístico.

Cubre: casos de referencia con tolerancias documentadas, propiedades
complementarias, invariantes, determinismo de fixtures y límites.
Cualquier regresión numérica falla aquí y bloquea CI.
"""

import math

import pytest

from app.domain.market import (
    DeVigResult,
    clv_price_ratio,
    clv_probability_pp,
    de_vig,
    de_vig_fair_odds,
    overround,
    remove_margin,
)
from app.domain.odds import edge_pp, expected_value, fair_odds, implied_probability
from app.model.baseline import PoissonBaseline
from app.model.poisson import expected_goals, over_under_2_5, poisson_pmf, total_goals_pmf

# Tolerancias documentadas por dominio.
TOL = {
    "probability": 1e-8,
    "odds": 1e-4,
    "pp": 1e-6,
    "sum": 1e-9,
}

# Fixtures dorados deterministas: (lambda_home, lambda_away, p_over).
# Valores precomputados con la implementación independiente; reproducibles.
GOLDEN_OVER_UNDER = [
    (1.5, 1.2, 0.5063755089),
    (1.0, 1.0, 0.3233235838),
    (1.8, 0.9, 0.5063755089),
    (2.2, 1.5, 0.7145668869),
    (0.8, 0.6, 0.1665022619),
]

# Rejilla de lambdas para invariantes.
LAMBDA_GRID = [(lh / 10, la / 10) for lh in range(5, 25, 3) for la in range(5, 25, 3)]


# --- Casos de referencia ---


@pytest.mark.parametrize(
    "odds,expected",
    [(2.00, 0.5), (1.50, 2 / 3), (3.00, 1 / 3), (1.80, 1 / 1.80)],
)
def test_implied_probability_reference(odds, expected):
    assert implied_probability(odds) == pytest.approx(expected, abs=TOL["probability"])


def test_fair_odds_reference_p060():
    assert fair_odds(0.60) == pytest.approx(1.6667, abs=TOL["odds"])


def test_ev_reference():
    assert expected_value(0.60, 2.00) == pytest.approx(0.20, abs=TOL["pp"] / 100)


def test_edge_reference():
    assert edge_pp(0.60, 0.50) == pytest.approx(10.0, abs=TOL["pp"])


def test_round_trip_fair_odds_implied():
    for odds in [1.50, 1.80, 2.00, 2.50, 3.00]:
        prob = implied_probability(odds)
        assert fair_odds(prob) == pytest.approx(odds, abs=TOL["odds"])


# --- Fixtures dorados del Poisson ---


@pytest.mark.parametrize("lh,la,p_over_expected", GOLDEN_OVER_UNDER)
def test_golden_poisson_fixtures(lh, la, p_over_expected):
    p_over, p_under = over_under_2_5(lh, la)
    assert p_over == pytest.approx(p_over_expected, abs=TOL["probability"])
    assert p_over + p_under == pytest.approx(1.0, abs=TOL["sum"])


# --- Propiedades complementarias e invariantes ---


@pytest.mark.parametrize("lh,la", LAMBDA_GRID)
def test_poisson_probabilities_complementary(lh, la):
    p_over, p_under = over_under_2_5(lh, la)
    assert p_over + p_under == pytest.approx(1.0, abs=TOL["sum"])
    assert 0.0 < p_over < 1.0
    assert 0.0 < p_under < 1.0


@pytest.mark.parametrize("lh,la", LAMBDA_GRID)
def test_total_goals_pmf_is_a_distribution(lh, la):
    pmf = total_goals_pmf(lh, la)
    assert sum(pmf.values()) == pytest.approx(1.0, abs=TOL["sum"])
    mean = sum(total * p for total, p in pmf.items())
    assert mean == pytest.approx(expected_goals(lh, la), abs=1e-6)


@pytest.mark.parametrize("lh,la", LAMBDA_GRID)
def test_de_vig_normalizes_to_one(lh, la):
    over_odds = 1.5 + lh / 10
    under_odds = 1.5 + la / 10
    result = de_vig(over_odds, under_odds)
    assert result.complete is True
    assert result.normalized_overround == pytest.approx(1.0, abs=TOL["sum"])
    assert result.over_probability + result.under_probability == pytest.approx(1.0, abs=TOL["sum"])


@pytest.mark.parametrize("prob", [0.1, 0.25, 0.5, 0.75, 0.9])
def test_ev_at_fair_odds_is_zero(prob):
    assert expected_value(prob, fair_odds(prob)) == pytest.approx(0.0, abs=1e-9)


def test_edge_is_antisymmetric():
    assert edge_pp(0.6, 0.4) == pytest.approx(-edge_pp(0.4, 0.6), abs=TOL["pp"])


def test_favoritism_preserved_by_de_vig():
    result = de_vig(2.50, 1.50)
    assert result.under_probability > result.over_probability


def test_overround_non_negative_with_margin():
    # Con margen (overround > 1), la suma de probabilidades sin margen es 1.
    p_over, p_under = remove_margin(1.90, 1.90)
    assert p_over + p_under == pytest.approx(1.0, abs=TOL["sum"])


# --- CLV ---


def test_clv_consistency_between_metrics():
    # Si el precio de entrada mejora frente al cierre, ambas métricas concuerdan.
    assert clv_price_ratio(2.00, 1.90) > 0
    assert clv_probability_pp(0.50, 0.55) > 0
    assert clv_price_ratio(1.90, 2.00) < 0
    assert clv_probability_pp(0.55, 0.50) < 0


# --- Determinismo ---


def test_poisson_deterministic_across_calls():
    a = over_under_2_5(1.5, 1.2)
    b = over_under_2_5(1.5, 1.2)
    assert a == b


def test_golden_fixtures_reproducible():
    baseline = PoissonBaseline()
    over1, _ = baseline.predict(1.5, 1.2)
    over2, _ = baseline.predict(1.5, 1.2)
    assert over1.probability == over2.probability == pytest.approx(GOLDEN_OVER_UNDER[0][2], abs=TOL["probability"])
    assert over1.inputs_hash == over2.inputs_hash


# --- Límites ---


def test_poisson_pmf_boundaries():
    assert poisson_pmf(0, 0) == pytest.approx(1.0)
    assert poisson_pmf(1, 0) == pytest.approx(0.0)
    assert poisson_pmf(0, 10) == pytest.approx(math.exp(-10), abs=1e-12)

import pytest

from app.domain.odds import (
    InvalidOddsError,
    InvalidProbabilityError,
    edge_pp,
    expected_value,
    fair_odds,
    implied_probability,
    round_to,
)


def test_reference_fair_odds_for_p_060():
    assert fair_odds(0.60) == pytest.approx(1.6667, abs=1e-4)


def test_reference_implied_probability_for_odds_200():
    assert implied_probability(2.00) == pytest.approx(0.50)


def test_reference_expected_value_for_p_060_odds_200():
    assert expected_value(0.60, 2.00) == pytest.approx(0.20)


def test_edge_pp_reference():
    assert edge_pp(0.60, 0.50) == pytest.approx(10.0)


def test_rejects_invalid_odds():
    for bad in [1.0, 0.9, float("nan"), float("inf"), -2.0]:
        with pytest.raises(InvalidOddsError):
            implied_probability(bad)


def test_rejects_invalid_probabilities():
    for bad in [0.0, -0.1, 1.5, float("nan"), float("inf")]:
        with pytest.raises(InvalidProbabilityError):
            fair_odds(bad)


def test_edge_rejects_out_of_range():
    with pytest.raises(InvalidProbabilityError):
        edge_pp(1.1, 0.5)
    with pytest.raises(InvalidProbabilityError):
        edge_pp(0.6, -0.1)


def test_precision_and_rounding_separated():
    raw = 1 / 0.6  # 1.666666...
    assert raw != pytest.approx(1.6667)
    assert round_to(raw, 4) == pytest.approx(1.6667)
    assert round_to(raw, 2) == pytest.approx(1.67)


def test_functions_are_pure():
    assert implied_probability(2.00) == implied_probability(2.00)
    assert fair_odds(0.5) == 2.0
    assert expected_value(0.5, 2.0) == 0.0

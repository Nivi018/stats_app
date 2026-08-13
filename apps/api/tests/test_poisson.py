import pytest

from app.model.baseline import (
    LambdaOutOfRange,
    MODEL_NAME,
    MODEL_VERSION,
    PoissonBaseline,
    clamp_lambda,
    inputs_hash,
)
from app.model.poisson import expected_goals, over_under_2_5, poisson_pmf, total_goals_pmf


# --- Poisson puro: fixtures dorados ---


def test_poisson_pmf_known_values():
    assert poisson_pmf(0, 1.0) == pytest.approx(0.367879, abs=1e-6)
    assert poisson_pmf(1, 1.0) == pytest.approx(0.367879, abs=1e-6)
    assert poisson_pmf(2, 1.0) == pytest.approx(0.183940, abs=1e-6)


def test_total_goals_distribution_sums_to_one():
    pmf = total_goals_pmf(1.5, 1.2)
    assert sum(pmf.values()) == pytest.approx(1.0, abs=1e-6)


def test_golden_over_under_2_5():
    # Valores dorados precomputados con la implementación independiente.
    golden = [
        ((1.5, 1.2), 0.5063755089),
        ((1.0, 1.0), 0.3233235838),
        ((1.8, 0.9), 0.5063755089),
        ((2.2, 1.5), 0.7145668869),
    ]
    for (lh, la), expected in golden:
        p_over, p_under = over_under_2_5(lh, la)
        assert p_over == pytest.approx(expected, abs=1e-8)
        assert p_over + p_under == pytest.approx(1.0, abs=1e-9)


def test_expected_goals():
    assert expected_goals(1.5, 1.2) == pytest.approx(2.7)


# --- Baseline reproducible ---


def test_baseline_reproducible_same_inputs_same_output():
    baseline = PoissonBaseline()
    over1, under1 = baseline.predict(1.5, 1.2)
    over2, under2 = baseline.predict(1.5, 1.2)

    assert over1.probability == over2.probability
    assert over1.fair_odds == over2.fair_odds
    assert over1.inputs_hash == over2.inputs_hash
    assert over1.model_version == MODEL_VERSION


def test_baseline_version_and_market():
    baseline = PoissonBaseline()
    over, under = baseline.predict(1.5, 1.2)

    assert baseline.MODEL_NAME == MODEL_NAME
    assert baseline.MODEL_VERSION == MODEL_VERSION
    assert over.selection == "over"
    assert under.selection == "under"
    assert over.market == "over_under_2_5"
    assert over.probability + under.probability == pytest.approx(1.0)


def test_inputs_hash_changes_with_lambdas():
    assert inputs_hash(1.5, 1.2) != inputs_hash(1.6, 1.2)
    assert inputs_hash(1.5, 1.2) == inputs_hash(1.5, 1.2)


def test_lambda_clamp_rejects_out_of_range():
    for bad in [0.01, 5.5]:
        with pytest.raises(LambdaOutOfRange):
            clamp_lambda(bad)
    assert clamp_lambda(0.5) == 0.5

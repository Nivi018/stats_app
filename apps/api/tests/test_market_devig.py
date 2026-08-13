import pytest

from app.domain.market import (
    DeVigResult,
    InvalidOddsError,
    de_vig,
    de_vig_fair_odds,
    remove_margin,
)


def test_balanced_market_normalizes_to_one():
    result = de_vig(2.00, 2.00)

    assert result.complete is True
    assert result.normalized_overround == pytest.approx(1.0)
    assert result.over_probability == pytest.approx(0.5)
    assert result.under_probability == pytest.approx(0.5)
    assert result.fair_over_odds == pytest.approx(2.00)
    assert result.fair_under_odds == pytest.approx(2.00)


def test_skewed_market_normalizes_and_preserves_originals():
    over_odds, under_odds = 2.50, 1.50
    result = de_vig(over_odds, under_odds)

    assert result.complete is True
    assert result.normalized_overround == pytest.approx(1.0)
    # Se conservan las cuotas originales.
    assert result.over_odds == over_odds
    assert result.under_odds == under_odds
    # El favorito (cuota baja) tiene mayor probabilidad sin margen.
    assert result.under_probability > result.over_probability


def test_remove_margin_skewed_market():
    p_over, p_under = remove_margin(2.50, 1.50)
    assert p_over + p_under == pytest.approx(1.0)


def test_de_vig_fair_odds_skewed():
    fair_over, fair_under = de_vig_fair_odds(2.50, 1.50)
    assert 1 / fair_over + 1 / fair_under == pytest.approx(1.0)


def test_missing_over_produces_explicit_state():
    result = de_vig(None, 1.80)

    assert result.complete is False
    assert result.missing == "over"
    assert result.under_odds == 1.80
    assert result.normalized_overround is None


def test_missing_under_produces_explicit_state():
    result = de_vig(2.20, None)

    assert result.complete is False
    assert result.missing == "under"
    assert result.over_odds == 2.20


def test_both_missing_produces_explicit_state():
    result = de_vig(None, None)

    assert result.complete is False
    assert result.missing == "both"


def test_invalid_odds_still_rejected():
    with pytest.raises(InvalidOddsError):
        de_vig(1.0, 1.80)
    with pytest.raises(InvalidOddsError):
        de_vig(2.00, 0.5)


def test_result_is_frozen_immutable():
    result = de_vig(2.00, 2.00)
    with pytest.raises(Exception):
        result.over_probability = 0.9  # type: ignore[misc]

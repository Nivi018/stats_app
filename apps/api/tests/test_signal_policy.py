import pytest

from app.model.signal import (
    SIGNAL_POLICY_VERSION,
    evaluate_signal,
)


def _signal(**overrides):
    defaults = dict(
        selection="over",
        edge_pp=7.0,
        ev=0.1,
        data_quality="high",
        snapshot_age_seconds=300,
    )
    defaults.update(overrides)
    return evaluate_signal(**defaults)


def test_signal_when_all_conditions_met():
    decision = _signal()
    assert decision.is_signal is True
    assert decision.policy_version == SIGNAL_POLICY_VERSION
    assert decision.exclusions == []
    assert len(decision.reasons) == 4


def test_edge_boundary_at_exactly_5pp():
    decision = _signal(edge_pp=5.0)
    assert decision.is_signal is True


def test_edge_below_threshold_excluded():
    decision = _signal(edge_pp=4.99)
    assert decision.is_signal is False
    assert any("edge" in e for e in decision.exclusions)


def test_ev_must_be_strictly_positive():
    decision = _signal(ev=0.0)
    assert decision.is_signal is False
    assert any("EV" in e for e in decision.exclusions)


def test_ev_positive_passes():
    decision = _signal(ev=0.0001)
    assert decision.is_signal is True


def test_quality_low_excluded():
    decision = _signal(data_quality="low")
    assert decision.is_signal is False
    assert any("calidad" in e for e in decision.exclusions)


def test_freshness_boundary_30min_passes():
    decision = _signal(snapshot_age_seconds=30 * 60)
    assert decision.is_signal is True


def test_freshness_over_30min_excluded():
    decision = _signal(snapshot_age_seconds=30 * 60 + 1)
    assert decision.is_signal is False
    assert any("antigüedad" in e for e in decision.exclusions)


def test_multiple_exclusions_are_observable():
    decision = _signal(edge_pp=3.0, ev=-0.2, data_quality="low", snapshot_age_seconds=3600)
    assert decision.is_signal is False
    assert len(decision.exclusions) == 4


def test_exclusion_reasons_are_observable_and_typed():
    decision = _signal(edge_pp=4.0, ev=0.1, data_quality="medium", snapshot_age_seconds=300)
    assert decision.is_signal is False
    assert decision.exclusions  # lista no vacía, legible
    assert all(isinstance(r, str) and r for r in decision.exclusions)


def test_selection_preserved_in_decision():
    decision = _signal(selection="under")
    assert decision.selection == "under"

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.market import (
    InvalidMarketError,
    InvalidOddsError,
    clv_price_ratio,
    clv_probability_pp,
    de_vig_fair_odds,
    implied_probability,
    overround,
    overround_is_anomalous,
    remove_margin,
    validate_odds,
)
from app.odds.snapshots import (
    MAX_PAIR_GAP,
    MAX_SNAPSHOT_AGE,
    CLOSED,
    OPEN,
    SUSPENDED,
    Snapshot,
    closing,
    consensus_probability,
    de_vig_pair,
    is_eligible_at,
    opening,
    validate_snapshots,
)

T0 = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 8, 20, 22, 0, tzinfo=timezone.utc)


def snap(
    provider: str,
    selection: str,
    odds: float,
    observed_at: datetime,
    status: str = OPEN,
    received_at: datetime | None = None,
    snap_id: str | None = None,
) -> Snapshot:
    return Snapshot(
        id=snap_id or f"{provider}-{selection}",
        match_id="match-1",
        provider=provider,
        market="over_under_2_5",
        line=2.5,
        selection=selection,
        odds=odds,
        observed_at=observed_at,
        received_at=received_at or observed_at,
        market_status=status,
    )


# --- Fórmulas base / de-vig / CLV ---


def test_implied_probability():
    assert implied_probability(2.0) == 0.5


def test_invalid_odds_rejected():
    for bad in [1.0, 0.9, float("nan"), float("inf")]:
        with pytest.raises(InvalidOddsError):
            validate_odds(bad)


def test_remove_margin_normalizes_to_one():
    p_over, p_under = remove_margin(2.00, 1.80)
    assert p_over + p_under == pytest.approx(1.0)
    assert p_under > p_over  # cuota menor -> probabilidad implícita mayor


def test_overround():
    assert overround(2.00, 2.00) == pytest.approx(1.0)  # sin margen
    assert overround(1.90, 1.90) == pytest.approx(1.0526, abs=1e-3)


def test_overround_anomaly_detection():
    assert overround_is_anomalous(1.90, 1.90) is False
    assert overround_is_anomalous(1.01, 1.01) is True  # sum > 1.30


def test_clv_formulas():
    assert clv_probability_pp(entry_no_vig_prob=0.50, closing_no_vig_prob=0.55) == pytest.approx(5.0)
    assert clv_price_ratio(entry_decimal_odds=2.00, closing_decimal_odds=1.90) == pytest.approx(2.0 / 1.9 - 1)


def test_de_vig_fair_odds():
    fair_over, fair_under = de_vig_fair_odds(2.00, 2.00)
    assert fair_over == pytest.approx(2.00)
    assert fair_under == pytest.approx(2.00)


# --- Elegibilidad temporal ---


def test_eligible_within_window():
    s = snap("a", "over", 1.90, T0)
    assert is_eligible_at(s, T0 + timedelta(minutes=10))


def test_eligible_respects_prediction_timestamp():
    s = snap("a", "over", 1.90, T0 + timedelta(minutes=5))
    assert not is_eligible_at(s, T0)  # snapshot posterior a la predicción


def test_eligible_respects_freshness():
    s = snap("a", "over", 1.90, T0 - timedelta(minutes=MAX_SNAPSHOT_AGE / 60 + 1))
    assert not is_eligible_at(s, T0)


def test_eligible_excludes_suspended_and_closed():
    assert not is_eligible_at(snap("a", "over", 1.90, T0, status=SUSPENDED), T0)
    assert not is_eligible_at(snap("a", "over", 1.90, T0, status=CLOSED), T0)


def test_eligible_excludes_snapshot_at_or_after_kickoff():
    s = snap("a", "over", 1.90, KICKOFF)
    assert not is_eligible_at(s, KICKOFF - timedelta(minutes=5), kickoff_at=KICKOFF)


# --- Opening / Closing ---


def test_opening_is_earliest_valid():
    snaps = [
        snap("a", "over", 1.90, T0),
        snap("a", "over", 1.85, T0 + timedelta(minutes=30)),
        snap("a", "over", 1.80, T0 + timedelta(minutes=60)),
    ]
    assert opening(snaps, kickoff_at=KICKOFF).observed_at == T0


def test_closing_is_latest_valid_before_kickoff():
    snaps = [
        snap("a", "over", 1.90, T0),
        snap("a", "over", 1.85, T0 + timedelta(minutes=90)),
        snap("a", "over", 1.80, KICKOFF + timedelta(minutes=1)),  # tras inicio, excluido
    ]
    result = closing(snaps, kickoff_at=KICKOFF)
    assert result.observed_at == T0 + timedelta(minutes=90)


# --- De-vig con pares comparables ---


def test_de_vig_pair_uses_comparable_pair():
    snaps = [
        snap("a", "over", 1.90, T0),
        snap("a", "under", 1.95, T0 + timedelta(seconds=30)),
    ]
    pair = de_vig_pair(snaps, T0 + timedelta(seconds=30))
    assert pair is not None
    assert pair.no_vig_probabilities[0] + pair.no_vig_probabilities[1] == pytest.approx(1.0)


def test_de_vig_pair_rejects_wide_gap():
    snaps = [
        snap("a", "over", 1.90, T0),
        snap("a", "under", 1.95, T0 + timedelta(seconds=MAX_PAIR_GAP + 30)),
    ]
    assert de_vig_pair(snaps, T0 + timedelta(seconds=MAX_PAIR_GAP + 30)) is None


# --- Consenso ---


def test_consensus_requires_three_sources():
    snaps = []
    for i, provider in enumerate(["a", "b", "c"]):
        at = T0 + timedelta(minutes=i)
        snaps.append(snap(provider, "over", 1.90, at))
        snaps.append(snap(provider, "under", 1.95, at))
    prob = consensus_probability(snaps, T0 + timedelta(minutes=5), "over")
    assert prob is not None
    assert 0.0 < prob < 1.0


def test_consensus_returns_none_with_few_sources():
    snaps = [snap("a", "over", 1.90, T0), snap("a", "under", 1.95, T0)]
    assert consensus_probability(snaps, T0, "over", min_sources=3) is None


# --- Validación / issues ---


def test_validation_flags_duplicate():
    snaps = [
        snap("a", "over", 1.90, T0),
        snap("a", "over", 1.90, T0),  # duplicado
    ]
    issues = validate_snapshots(snaps)
    assert any(i.kind == "duplicate" for i in issues)


def test_validation_flags_invalid_odds():
    snaps = [snap("a", "over", 0.8, T0)]
    issues = validate_snapshots(snaps)
    assert any(i.kind == "invalid_odds" for i in issues)


def test_validation_flags_out_of_order():
    s = snap("a", "over", 1.90, T0, received_at=T0 - timedelta(minutes=10))
    issues = validate_snapshots([s])
    assert any(i.kind == "out_of_order" for i in issues)


def test_validation_flags_suspended_as_info():
    s = snap("a", "over", 1.90, T0, status=SUSPENDED)
    issues = validate_snapshots([s])
    assert any(i.kind == "suspended" and i.severity == "info" for i in issues)


def test_validation_flags_overround_anomaly():
    snaps = [
        snap("a", "over", 1.02, T0),
        snap("a", "under", 1.02, T0),
    ]
    issues = validate_snapshots(snaps)
    assert any(i.kind == "overround_anomaly" for i in issues)


# --- Corrección sin sobrescribir ---


def test_correction_creates_new_snapshot_linked():
    original = snap("a", "over", 1.90, T0, snap_id="orig-1")
    corrected = Snapshot(
        id="corr-1",
        match_id="match-1",
        provider="a",
        market="over_under_2_5",
        line=2.5,
        selection="over",
        odds=1.92,
        observed_at=T0,
        received_at=T0 + timedelta(seconds=5),
        market_status=OPEN,
        correction_of_id="orig-1",
    )
    # Ambos coexisten: la corrección referencia al original, no lo sobrescribe.
    assert corrected.correction_of_id == "orig-1"
    assert corrected.odds != original.odds
    # El original sigue siendo elegible en su momento (historia intacta).
    assert is_eligible_at(original, T0)

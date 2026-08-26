"""Pruebas de la sugerencia de stake responsable (Sprint 7)."""

import pytest

from app.domain.stake import (
    KELLY_FRACTION_DEFAULT,
    MAX_STAKE_PCT,
    SINGLE_UNIT_PCT,
    suggest_stake,
)


def test_referencia_p60_odds2():
    # p=0.6, odds=2 -> EV=0.2, Kelly=0.2 -> fraccionado 25% = 0.05 -> 5% (tope).
    s = suggest_stake(probability=0.6, decimal_odds=2.0)
    assert s.recommended is True
    assert s.stake_pct == pytest.approx(5.0)
    assert s.stake_units == pytest.approx(2.5)


def test_referencia_p55_odds_2dot2_dentro_de_tope():
    # EV=0.21, Kelly=0.21/1.2=0.175 -> 25% = 0.04375 -> 4.38% -> 2.19u.
    s = suggest_stake(probability=0.55, decimal_odds=2.2)
    assert s.recommended is True
    assert 0 < s.stake_pct < MAX_STAKE_PCT
    assert s.stake_pct / SINGLE_UNIT_PCT == pytest.approx(s.stake_units, abs=0.01)


def test_ev_no_positivo_no_recomienda():
    s = suggest_stake(probability=0.5, decimal_odds=2.0)
    assert s.recommended is False
    assert s.stake_pct is None
    assert any("negativo" in r or "no positivo" in r for r in s.reasons)


def test_cuota_invalida_no_recomienda():
    s = suggest_stake(probability=0.8, decimal_odds=1.0)
    assert s.recommended is False
    assert s.stake_units is None


def test_probabilidad_fuera_de_rango_rechaza():
    assert suggest_stake(probability=1.1, decimal_odds=2.0).recommended is False
    assert suggest_stake(probability=0.0, decimal_odds=2.0).recommended is False


def test_fraccion_de_kelly_configurable():
    a = suggest_stake(probability=0.65, decimal_odds=1.9, kelly_fraction=0.5)
    b = suggest_stake(probability=0.65, decimal_odds=1.9, kelly_fraction=0.1)
    assert a.stake_pct > b.stake_pct


def test_tope_maximo_respetado():
    # EV muy alto -> Kelly grande -> fraccionado superaría el tope; se clampa.
    s = suggest_stake(probability=0.9, decimal_odds=3.0)
    assert s.stake_pct <= MAX_STAKE_PCT
    assert any("Tope" in r for r in s.reasons)


def test_constantes_de_politica():
    assert 0 < KELLY_FRACTION_DEFAULT < 1
    assert MAX_STAKE_PCT > SINGLE_UNIT_PCT
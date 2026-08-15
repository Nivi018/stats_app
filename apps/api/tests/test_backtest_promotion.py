"""Pruebas de la política de promoción de versiones (US7)."""

import pytest

from app.backtest.promotion import (
    PROMOTION_BRIER_IMPROVEMENT,
    PROMOTION_MIN_SAMPLE,
    ROLLBACK_BRIER_DEGRADATION,
    evaluate_candidate,
    evaluate_rollback,
)


def test_muestra_insuficiente_no_promueve():
    decision = evaluate_candidate("candidate", sample_size=5, brier=0.25, active_brier=0.26)
    assert decision.recommended_status == "candidate"
    assert decision.changed is False
    assert any("Muestra insuficiente" in r for r in decision.reasons)


def test_primer_activo_con_muestra_suficiente():
    decision = evaluate_candidate("candidate", sample_size=30, brier=0.25, active_brier=None)
    assert decision.recommended_status == "active"
    assert any("no hay baseline activo" in r for r in decision.reasons)


def test_mejora_brier_promueve_a_activo():
    decision = evaluate_candidate(
        "shadow",
        sample_size=30,
        brier=0.20,
        active_brier=0.23,
        improvement=0.02,
    )
    assert decision.recommended_status == "active"
    assert any("mejora" in r for r in decision.reasons)


def test_no_supera_activo_permanece_en_sombra():
    decision = evaluate_candidate(
        "shadow",
        sample_size=30,
        brier=0.24,
        active_brier=0.23,
        improvement=0.02,
    )
    assert decision.recommended_status == "shadow"
    assert decision.changed is False


def test_holdout_final_no_participa_en_promocion():
    decision = evaluate_candidate(
        "candidate",
        sample_size=30,
        brier=0.10,
        active_brier=0.30,
        final_holdout=True,
    )
    assert decision.recommended_status == "candidate"
    assert any("holdout final" in r for r in decision.reasons)


def test_sin_brier_permanece_en_sombra():
    decision = evaluate_candidate("shadow", sample_size=30, brier=None, active_brier=0.23)
    assert decision.recommended_status == "shadow"
    assert any("Sin Brier" in r for r in decision.reasons)


def test_umbral_minimo_configurable():
    decision = evaluate_candidate("candidate", sample_size=15, brier=0.1, active_brier=None, min_sample=20)
    assert decision.recommended_status == "candidate"


def test_rollback_por_degradacion():
    decision = evaluate_rollback(
        "active",
        active_brier=0.30,
        previous_brier=0.20,
        degradation=0.05,
    )
    assert decision.recommended_status == "candidate"
    assert decision.changed is True
    assert any("degradado" in r for r in decision.reasons)


def test_sin_degradacion_no_hay_rollback():
    decision = evaluate_rollback("active", active_brier=0.22, previous_brier=0.20)
    assert decision.recommended_status == "active"
    assert decision.changed is False


def test_constantes_del_policy():
    assert PROMOTION_MIN_SAMPLE >= 1
    assert PROMOTION_BRIER_IMPROVEMENT > 0
    assert ROLLBACK_BRIER_DEGRADATION > PROMOTION_BRIER_IMPROVEMENT

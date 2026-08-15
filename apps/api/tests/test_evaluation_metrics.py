"""Pruebas de las métricas de evaluación (US5) con casos de referencia."""

import pytest

from app.evaluation.metrics import (
    MIN_SAMPLE_DEFAULT,
    ResolvedPrediction,
    compute_metrics,
)


def rec(probability: float, odds: float | None, result: str) -> ResolvedPrediction:
    return ResolvedPrediction(probability=probability, odds=odds, result=result)


def test_referencia_brier_calibrado_perfecto():
    # 10 predicciones al 50% todas acertadas -> Brier 0.25, acierto 1.0.
    records = [rec(0.5, 2.0, "win") for _ in range(10)]
    report = compute_metrics(records)
    assert report.sample_size == 10
    assert report.wins == 10
    assert report.hit_rate == 1.0
    assert report.brier == pytest.approx(0.25)


def test_referencia_mitad_aciertos():
    records = [rec(0.5, 2.0, "win")] * 5 + [rec(0.5, 2.0, "loss")] * 5
    report = compute_metrics(records)
    assert report.hit_rate == pytest.approx(0.5)
    assert report.brier == pytest.approx(0.25)
    assert report.unit_roi == pytest.approx(0.0)  # 5*(2-1) - 5*1 = 0


def test_roi_unitario_con_cuotas():
    records = [
        rec(0.6, 1.8, "win"),   # +0.8
        rec(0.6, 1.8, "loss"),  # -1.0
        rec(0.6, 1.8, "win"),   # +0.8
    ]
    report = compute_metrics(records)
    assert report.unit_roi == pytest.approx((0.8 - 1.0 + 0.8) / 3)


def test_voids_no_cuentan_en_muestra_ni_roi():
    records = [
        rec(0.5, 2.0, "win"),
        rec(0.5, 2.0, "void"),
        rec(0.5, 2.0, "void"),
    ]
    report = compute_metrics(records)
    assert report.sample_size == 1
    assert report.voids == 2
    assert report.wins == 1
    assert report.losses == 0


def test_division_por_cero_devuelve_none():
    report = compute_metrics([])
    assert report.sample_size == 0
    assert report.hit_rate is None
    assert report.unit_roi is None
    assert report.brier is None
    assert report.sample_sufficient is False


def test_calibracion_por_bin():
    # Todo en el bin 40-50%: media predicha 0.45, observada 1.0 (todas ganan).
    records = [rec(0.45, 2.2, "win")] * 4
    report = compute_metrics(records)
    bins = {b.label: b for b in report.calibration_bins}
    assert bins["[40%, 50%)"].n == 4
    assert bins["[40%, 50%)"].mean_predicted == pytest.approx(0.45)
    assert bins["[40%, 50%)"].observed_rate == pytest.approx(1.0)
    assert bins["[60%, 100%]"].n == 0
    assert bins["[60%, 100%]"].observed_rate is None


def test_calibracion_cubre_todos_los_bins():
    records = [
        rec(0.35, 2.8, "loss"),
        rec(0.45, 2.2, "win"),
        rec(0.55, 1.8, "loss"),
        rec(0.7, 1.4, "win"),
    ]
    report = compute_metrics(records)
    assert len(report.calibration_bins) == 4
    assert all(b.n >= 0 for b in report.calibration_bins)


def test_muestra_suficiente_por_umbral():
    records = [rec(0.5, 2.0, "win")] * MIN_SAMPLE_DEFAULT
    report = compute_metrics(records)
    assert report.sample_sufficient is True
    assert report.threshold == MIN_SAMPLE_DEFAULT

    small = compute_metrics(records[:5])
    assert small.sample_sufficient is False

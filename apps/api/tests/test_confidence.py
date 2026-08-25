"""Pruebas de la confianza compuesta por predicción (US6)."""

import pytest

from app.domain.confidence import (
    LEVEL_ALTA,
    LEVEL_BAJA,
    LEVEL_MEDIA,
    assess_confidence,
    level_for,
)


def test_probabilidad_decidida_calidad_alta_cuota_fresca_es_alta():
    confidence = assess_confidence(
        probability=0.75,
        data_quality="high",
        freshness_seconds=300,
    )
    assert confidence.level == LEVEL_ALTA
    assert confidence.score >= 70
    assert any("decidida" in f for f in confidence.factors)
    assert any("Calidad de datos: high" in f for f in confidence.factors)


def test_probabilidad_cercana_al_azar_es_baja():
    confidence = assess_confidence(
        probability=0.5,
        data_quality="high",
        freshness_seconds=300,
    )
    assert confidence.level == LEVEL_BAJA
    assert any("azar" in f for f in confidence.factors)


def test_cuota_vieja_reduce_confianza():
    fresca = assess_confidence(probability=0.7, data_quality="high", freshness_seconds=300)
    vieja = assess_confidence(probability=0.7, data_quality="high", freshness_seconds=2 * 3600)
    assert vieja.score < fresca.score


def test_calidad_baja_reduce_confianza():
    alta = assess_confidence(probability=0.7, data_quality="high", freshness_seconds=300)
    baja = assess_confidence(probability=0.7, data_quality="low", freshness_seconds=300)
    assert baja.score < alta.score


def test_score_en_rango_0_100():
    for p in (0.5, 0.6, 0.7, 0.9, 0.1):
        confidence = assess_confidence(probability=p, data_quality="low", freshness_seconds=3600 * 3)
        assert 0 <= confidence.score <= 100


def test_nivel_deriva_del_score():
    assert level_for(80) == LEVEL_ALTA
    assert level_for(50) == LEVEL_MEDIA
    assert level_for(20) == LEVEL_BAJA


def test_factores_siempre_presentes():
    confidence = assess_confidence(probability=0.6, data_quality="medium", freshness_seconds=600)
    assert len(confidence.factors) >= 3


def test_probabilidad_extrema_tambien_decidida():
    confidence = assess_confidence(probability=0.95, data_quality="high", freshness_seconds=0)
    assert confidence.level == LEVEL_ALTA

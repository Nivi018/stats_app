"""Confianza compuesta por predicción (US6).

La confianza es un indicador compuesto que combina:

- **Decisión**: qué tan lejos está la probabilidad del azar (0.5).
- **Calidad de datos**: high / medium / low.
- **Frescura**: antigüedad del snapshot de cuota.

NO es una probabilidad de acierto ni una garantía: una predicción con confianza
alta puede fallar. La política es versionada para poder evolucionarla sin
romper consumidores.
"""

import math
from dataclasses import dataclass
from datetime import timedelta

CONFIDENCE_POLICY_VERSION = "1.0.0"

FRESH_WINDOW_SECONDS = int(timedelta(minutes=30).total_seconds())
STALE_WINDOW_SECONDS = int(timedelta(hours=2).total_seconds())

WEIGHT_DECISION = 0.40
WEIGHT_QUALITY = 0.35
WEIGHT_FRESHNESS = 0.25

LEVEL_ALTA = "alta"
LEVEL_MEDIA = "media"
LEVEL_BAJA = "baja"

# Debajo de este umbral de decisión, la predicción es casi un volado y la
# confianza es baja aunque la calidad y la frescura sean buenas.
DECISION_FLOOR = 30.0

# Umbrales de los factores textuales de decisión.
DECISION_DECIDIDA = 40.0
DECISION_AZAR = 15.0

_QUALITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class Confidence:
    score: float  # 0-100
    level: str  # baja | media | alta
    factors: list[str]


def _decision_score(probability: float) -> float:
    clamped = min(1.0, max(0.0, probability))
    extremeness = abs(clamped - 0.5) * 2  # 0 en 50%, 1 en 0%/100%
    return extremeness * 100.0


def _quality_score(data_quality: str) -> float:
    return _QUALITY_RANK.get(data_quality, 0) / 3 * 100.0


def _freshness_score(age_seconds: float) -> float:
    if age_seconds <= FRESH_WINDOW_SECONDS:
        return 100.0
    if age_seconds >= STALE_WINDOW_SECONDS:
        return 0.0
    span = STALE_WINDOW_SECONDS - FRESH_WINDOW_SECONDS
    return max(0.0, 100.0 * (STALE_WINDOW_SECONDS - age_seconds) / span)


def level_for(score: float) -> str:
    if score >= 70:
        return LEVEL_ALTA
    if score >= 45:
        return LEVEL_MEDIA
    return LEVEL_BAJA


def assess_confidence(
    *,
    probability: float,
    data_quality: str,
    freshness_seconds: float,
    version: str = CONFIDENCE_POLICY_VERSION,
) -> Confidence:
    decision = _decision_score(probability)
    quality = _quality_score(data_quality)
    freshness = _freshness_score(freshness_seconds)

    score = (
        WEIGHT_DECISION * decision
        + WEIGHT_QUALITY * quality
        + WEIGHT_FRESHNESS * freshness
    )
    score = round(min(100.0, max(0.0, score)), 1)
    level = level_for(score) if decision >= DECISION_FLOOR else LEVEL_BAJA

    probability_pct = round(probability * 100, 1)
    factors: list[str] = []
    if decision >= DECISION_DECIDIDA:
        factors.append(f"Probabilidad decidida ({probability_pct}%)")
    elif decision <= DECISION_AZAR:
        factors.append(f"Probabilidad cercana al azar ({probability_pct}%)")
    else:
        factors.append(f"Probabilidad moderada ({probability_pct}%)")

    factors.append(f"Calidad de datos: {data_quality}")
    if math.isfinite(freshness_seconds):
        minutes = int(freshness_seconds // 60)
        factors.append(f"Cuota con {minutes} min de antigüedad")
    else:
        factors.append("Sin snapshot de cuota conocido")
    if level == LEVEL_BAJA:
        factors.append("Confianza baja: revisa calidad y frescura antes de decidir")

    return Confidence(score=score, level=level, factors=factors)

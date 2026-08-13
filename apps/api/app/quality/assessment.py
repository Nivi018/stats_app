"""Evaluación de calidad de datos y riesgo de una predicción.

**Calidad** (cobertura, completitud, frescura, coherencia) y **riesgo**
(volatilidad, muestra) son conceptos separados, y **ninguno es una
probabilidad de acierto**: `Assessment.is_probability` es siempre False.
"""

from dataclasses import dataclass

FRESH_WINDOW_SECONDS = 30 * 60  # 30 min
STALE_WINDOW_SECONDS = 2 * 60 * 60  # 120 min: frescura -> 0

OVERROUND_MIN = 1.00
OVERROUND_MAX = 1.30

# Muestra mínima por equipo (diccionario de features).
SAMPLE_HIGH = 10
SAMPLE_MEDIUM = 6


@dataclass(frozen=True)
class Assessment:
    metric_type: str  # "data_quality" | "risk"
    level: str  # "low" | "medium" | "high"
    score: float  # 0-100
    factors: list[str]

    @property
    def is_probability(self) -> bool:
        return False


@dataclass(frozen=True)
class QualityInputs:
    coverage_ratio: float = 1.0  # fracción de entidades requeridas presentes
    completeness_ratio: float = 1.0  # fracción de campos requeridos no nulos
    freshness_seconds: float = 0.0  # antigüedad del snapshot de cuota
    overround_value: float | None = None  # None si no hay par comparable
    has_both_odds: bool = True
    has_both_stats: bool = True


@dataclass(frozen=True)
class RiskInputs:
    sample_size_total: int = 0  # partidos elegibles por equipo
    sample_size_context: int = 0  # partidos en condición local/visita
    quality_score: float = 100.0  # score de calidad de datos (0-100)


def _freshness_score(age_seconds: float) -> float:
    if age_seconds <= FRESH_WINDOW_SECONDS:
        return 100.0
    if age_seconds >= STALE_WINDOW_SECONDS:
        return 0.0
    span = STALE_WINDOW_SECONDS - FRESH_WINDOW_SECONDS
    return max(0.0, 100.0 * (STALE_WINDOW_SECONDS - age_seconds) / span)


def assess_data_quality(inputs: QualityInputs) -> Assessment:
    coverage = inputs.coverage_ratio * 100.0
    completeness = inputs.completeness_ratio * 100.0
    freshness = _freshness_score(inputs.freshness_seconds)

    coherence = 100.0
    factors: list[str] = []
    if not inputs.has_both_odds:
        coherence -= 25.0
        factors.append("Falta uno de los lados del mercado (over/under)")
    if not inputs.has_both_stats:
        coherence -= 25.0
        factors.append("Faltan estadísticas de uno de los equipos")
    if inputs.overround_value is not None and not (OVERROUND_MIN <= inputs.overround_value <= OVERROUND_MAX):
        coherence -= 25.0
        factors.append(f"Overround {inputs.overround_value:.3f} fuera de rango")
    coherence = max(0.0, coherence)

    score = 0.25 * coverage + 0.25 * completeness + 0.25 * freshness + 0.25 * coherence

    if inputs.coverage_ratio < 1.0:
        factors.append("Cobertura incompleta del partido")
    if inputs.completeness_ratio < 1.0:
        factors.append("Campos de estadística faltantes")
    if inputs.freshness_seconds > FRESH_WINDOW_SECONDS:
        factors.append(f"Snapshot de cuota con {int(inputs.freshness_seconds / 60)} min de antigüedad")
    if not factors:
        factors.append("Datos completos, frescos y coherentes")

    return Assessment(metric_type="data_quality", level=_level(score), score=round(score, 2), factors=factors)


def assess_risk(inputs: RiskInputs) -> Assessment:
    total, context = inputs.sample_size_total, inputs.sample_size_context
    if total >= SAMPLE_HIGH and context >= 5:
        sample_score = 0.0
    elif total >= SAMPLE_MEDIUM:
        sample_score = 40.0
    elif total >= 3:
        sample_score = 70.0
    else:
        sample_score = 100.0

    factors: list[str] = []
    if sample_score == 0.0:
        factors.append("Muestra suficiente de partidos históricos")
    else:
        factors.append(f"Muestra reducida: {total} partidos totales, {context} en condición")
    if inputs.quality_score < 60:
        factors.append("Calidad de datos baja")
    elif inputs.quality_score < 85:
        factors.append("Calidad de datos media")

    risk = round(0.6 * sample_score + 0.4 * (100.0 - inputs.quality_score), 2)

    if risk < 40:
        level = "low"
    elif risk < 70:
        level = "medium"
    else:
        level = "high"
    return Assessment(metric_type="risk", level=level, score=risk, factors=factors)


def _level(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"

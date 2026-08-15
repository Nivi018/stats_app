"""Métricas de evaluación por ModelVersion (US5).

Métricas calculadas sobre predicciones ya resueltas (win/loss/void):

- **ROI unitario**: retorno neto por unidad apostada; void no apuesta.
- **Brier**: error cuadrático medio de la probabilidad frente al resultado
  (1 = acierto, 0 = fallo).
- **Acierto (hit rate)**: ganadas / (ganadas + perdidas).
- **Calibración**: por bin de probabilidad, media predicha vs frecuencia
  observada.

El tamaño de muestra es SIEMPRE visible. Divisiones por cero devuelven `None`.
"""

from dataclasses import dataclass

MIN_SAMPLE_DEFAULT = 30
VOID = "void"
WIN = "win"
LOSS = "loss"

# Bins de calibración para probabilidades de Over/Under 2.5.
CALIBRATION_BINS: list[tuple[float, float]] = [
    (0.0, 0.4),
    (0.4, 0.5),
    (0.5, 0.6),
    (0.6, 1.0001),
]


@dataclass(frozen=True)
class ResolvedPrediction:
    """Predicción resuelta necesaria para las métricas."""

    probability: float
    odds: float | None
    result: str  # win | loss | void


@dataclass(frozen=True)
class CalibrationBin:
    label: str
    lower: float
    upper: float
    n: int
    mean_predicted: float | None
    observed_rate: float | None


@dataclass(frozen=True)
class MetricsReport:
    model_version_id: str | None
    sample_size: int
    wins: int
    losses: int
    voids: int
    hit_rate: float | None
    unit_roi: float | None
    brier: float | None
    calibration_bins: list[CalibrationBin]
    sample_sufficient: bool
    threshold: int


def _bin_for(probability: float) -> tuple[float, float] | None:
    for lower, upper in CALIBRATION_BINS:
        if lower <= probability < upper:
            return lower, upper
    return None


def compute_metrics(
    records: list[ResolvedPrediction],
    *,
    model_version_id: str | None = None,
    threshold: int = MIN_SAMPLE_DEFAULT,
) -> MetricsReport:
    non_void = [r for r in records if r.result not in (WIN, LOSS)]
    resolved = [r for r in records if r.result in (WIN, LOSS)]
    n = len(resolved)
    wins = sum(1 for r in resolved if r.result == WIN)
    losses = n - wins
    voids = len(non_void)

    hit_rate = wins / n if n > 0 else None

    unit_roi = None
    if n > 0:
        profit = sum(
            (r.odds - 1.0) if (r.odds is not None and r.result == WIN) else -1.0
            for r in resolved
        )
        unit_roi = profit / n

    brier = None
    if n > 0:
        errors = [(r.probability - (1.0 if r.result == WIN else 0.0)) ** 2 for r in resolved]
        brier = sum(errors) / n

    bins: list[CalibrationBin] = []
    by_bin: dict[tuple[float, float], list[ResolvedPrediction]] = {}
    for record in resolved:
        bucket = _bin_for(record.probability)
        if bucket is None:
            continue
        by_bin.setdefault(bucket, []).append(record)

    for lower, upper in CALIBRATION_BINS:
        group = by_bin.get((lower, upper), [])
        if not group:
            bins.append(CalibrationBin(
                label=_bin_label(lower, upper),
                lower=lower,
                upper=upper,
                n=0,
                mean_predicted=None,
                observed_rate=None,
            ))
            continue
        mean_predicted = sum(r.probability for r in group) / len(group)
        wins_in_bin = sum(1 for r in group if r.result == WIN)
        bins.append(CalibrationBin(
            label=_bin_label(lower, upper),
            lower=lower,
            upper=upper,
            n=len(group),
            mean_predicted=round(mean_predicted, 4),
            observed_rate=round(wins_in_bin / len(group), 4),
        ))

    return MetricsReport(
        model_version_id=model_version_id,
        sample_size=n,
        wins=wins,
        losses=losses,
        voids=voids,
        hit_rate=round(hit_rate, 4) if hit_rate is not None else None,
        unit_roi=round(unit_roi, 4) if unit_roi is not None else None,
        brier=round(brier, 4) if brier is not None else None,
        calibration_bins=bins,
        sample_sufficient=n >= threshold,
        threshold=threshold,
    )


def _bin_label(lower: float, upper: float) -> str:
    if upper > 1.0:
        return f"[{lower:.0%}, 100%]"
    return f"[{lower:.0%}, {upper:.0%})"

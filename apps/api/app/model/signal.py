"""Política de sugerencias: decide si una selección es una oportunidad.

La regla vive solo en el servidor (dominio); la web consume el resultado y no
replica la lógica. La política es versionada para poder evolucionarla sin
romper consumidores ni historial.
"""

from dataclasses import dataclass

SIGNAL_POLICY_VERSION = "1.0.0"

MIN_EDGE_PP = 5.0
MIN_EV = 0.0  # se exige EV > 0
MIN_DATA_QUALITY = "medium"  # high > medium > low
MAX_SNAPSHOT_AGE_SECONDS = 30 * 60  # 30 min

_QUALITY_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class SignalDecision:
    is_signal: bool
    selection: str
    policy_version: str
    reasons: list[str]
    exclusions: list[str]


def evaluate_signal(
    *,
    selection: str,
    edge_pp: float,
    ev: float,
    data_quality: str,
    snapshot_age_seconds: float,
    policy_version: str = SIGNAL_POLICY_VERSION,
    min_edge_pp: float = MIN_EDGE_PP,
    min_ev: float = MIN_EV,
    min_data_quality: str = MIN_DATA_QUALITY,
    max_snapshot_age_seconds: float = MAX_SNAPSHOT_AGE_SECONDS,
) -> SignalDecision:
    exclusions: list[str] = []

    if edge_pp < min_edge_pp:
        exclusions.append(f"edge {edge_pp:.1f}pp por debajo del umbral {min_edge_pp:g}pp")

    if ev <= min_ev:
        exclusions.append(f"EV {ev:.3f} no es positivo (se exige > {min_ev:g})")

    if _quality_rank(data_quality) < _quality_rank(min_data_quality):
        exclusions.append(f"calidad de datos '{data_quality}' inferior a '{min_data_quality}'")

    if snapshot_age_seconds > max_snapshot_age_seconds:
        minutes = int(snapshot_age_seconds / 60)
        exclusions.append(f"cuota con {minutes} min de antigüedad supera el máximo de {int(max_snapshot_age_seconds / 60)} min")

    is_signal = not exclusions
    reasons = (
        [
            f"edge >= {min_edge_pp:g}pp",
            f"EV > {min_ev:g}",
            f"calidad de datos >= {min_data_quality}",
            f"cuota fresca (<= {int(max_snapshot_age_seconds / 60)} min)",
        ]
        if is_signal
        else []
    )
    return SignalDecision(
        is_signal=is_signal,
        selection=selection,
        policy_version=policy_version,
        reasons=reasons,
        exclusions=exclusions,
    )


def _quality_rank(level: str) -> int:
    return _QUALITY_RANK.get(level, 0)

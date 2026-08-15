"""Política de promoción de versiones de modelo (US7).

Ciclo: `candidate` -> `shadow` -> `active`. La promoción usa métricas
FUERA DE MUESTRA (walk-forward), nunca el holdout final. El rollback devuelve
una versión activa a candidato si su desempeño se degrada más allá de un
umbral.

Principios:
- La muestra mínima y el umbral de mejora evitan promocionar por ruido.
- El holdout final no participa en tuning ni en decisiones de promoción.
- Sin un baseline activo, la primera versión con muestra suficiente se
  promueve directamente.
"""

from dataclasses import dataclass

PROMOTION_MIN_SAMPLE = 20
PROMOTION_BRIER_IMPROVEMENT = 0.02
ROLLBACK_BRIER_DEGRADATION = 0.05


@dataclass(frozen=True)
class PromotionDecision:
    current_status: str
    recommended_status: str
    reasons: list[str]

    @property
    def changed(self) -> bool:
        return self.current_status != self.recommended_status


def evaluate_candidate(
    current_status: str,
    *,
    sample_size: int,
    brier: float | None,
    active_brier: float | None,
    min_sample: int = PROMOTION_MIN_SAMPLE,
    improvement: float = PROMOTION_BRIER_IMPROVEMENT,
    final_holdout: bool = False,
) -> PromotionDecision:
    if final_holdout:
        return PromotionDecision(
            current_status,
            current_status,
            ["El holdout final no participa en decisiones de promoción"],
        )

    if sample_size < min_sample:
        return PromotionDecision(
            current_status,
            current_status,
            [f"Muestra insuficiente para promocionar: {sample_size} < {min_sample}"],
        )

    if active_brier is None:
        return PromotionDecision(
            current_status,
            "active",
            ["Primera versión con muestra suficiente; no hay baseline activo"],
        )

    if brier is None:
        return PromotionDecision(
            current_status,
            "shadow",
            ["Sin Brier comparable; permanece en sombra"],
        )

    if brier <= active_brier - improvement:
        return PromotionDecision(
            current_status,
            "active",
            [f"Brier {brier:.4f} mejora al activo {active_brier:.4f} en ≥ {improvement}"],
        )

    return PromotionDecision(
        current_status,
        "shadow",
        [f"Brier {brier:.4f} no supera al activo {active_brier:.4f}"],
    )


def evaluate_rollback(
    current_status: str,
    *,
    active_brier: float | None,
    previous_brier: float | None,
    degradation: float = ROLLBACK_BRIER_DEGRADATION,
) -> PromotionDecision:
    """Devuelve a candidato una versión activa cuyo desempeño se degradó."""
    if (
        active_brier is not None
        and previous_brier is not None
        and active_brier > previous_brier + degradation
    ):
        return PromotionDecision(
            current_status,
            "candidate",
            [
                f"Brier activo {active_brier:.4f} degradado vs "
                f"{previous_brier:.4f} (≥ {degradation})"
            ],
        )
    return PromotionDecision(current_status, current_status, ["Sin degradación relevante"])

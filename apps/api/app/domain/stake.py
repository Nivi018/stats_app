"""Sugerencia de stake responsable por unidad (Sprint 7).

Usa el criterio de Kelly fraccionado: `f* = (p*odds - 1) / (odds - 1)`,
multiplicado por una fracción (por defecto 25%) y limitado a un máximo del
bankroll. 1 unidad = `UNIT_PCT`% del bankroll.

NO es consejo financiero: es una sugerencia de dimensionado para una sola
apuesta; cada usuario debe definir su propio bankroll. Con EV no positivo o
cuota inválida no se sugiere apostar.
"""

from dataclasses import dataclass

SINGLE_UNIT_PCT = 2.0          # 1 unidad = 2% del bankroll
KELLY_FRACTION_DEFAULT = 0.25  # Kelly fraccionado (conservador)
MAX_STAKE_PCT = 5.0            # nunca más del 5% del bankroll por apuesta


@dataclass(frozen=True)
class StakeSuggestion:
    recommended: bool
    stake_pct: float | None  # % del bankroll sugerido
    stake_units: float | None  # unidades (stake_pct / SINGLE_UNIT_PCT)
    reasons: list[str]


def _bin_units(stake_pct: float, unit_pct: float) -> float:
    return round(stake_pct / unit_pct, 2)


def suggest_stake(
    *,
    probability: float,
    decimal_odds: float,
    kelly_fraction: float = KELLY_FRACTION_DEFAULT,
    max_stake_pct: float = MAX_STAKE_PCT,
    unit_pct: float = SINGLE_UNIT_PCT,
) -> StakeSuggestion:
    if not (0.0 < probability < 1.0) or decimal_odds <= 1.0:
        return StakeSuggestion(
            recommended=False,
            stake_pct=None,
            stake_units=None,
            reasons=["Cuota o probabilidad inválida: no se sugiere apostar"],
        )

    ev = probability * decimal_odds - 1
    if ev <= 0:
        return StakeSuggestion(
            recommended=False,
            stake_pct=None,
            stake_units=None,
            reasons=["EV no positivo: no se sugiere apostar (Kelly negativo)"],
        )

    kelly = ev / (decimal_odds - 1)
    fraction = kelly * kelly_fraction
    stake_pct = round(min(fraction * 100, max_stake_pct), 2)

    reasons = [
        f"Kelly fraccionado {kelly_fraction:.0%} sobre {kelly * 100:.1f}%",
        f"Límite aplicado: {max_stake_pct:g}% del bankroll",
        f"1 unidad = {unit_pct:g}% del bankroll",
    ]
    if stake_pct >= max_stake_pct:
        reasons.append("Tope alcanzado")
    return StakeSuggestion(
        recommended=True,
        stake_pct=stake_pct,
        stake_units=_bin_units(stake_pct, unit_pct),
        reasons=reasons,
    )

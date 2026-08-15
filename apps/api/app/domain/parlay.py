"""Dominio del parlay responsable: correlaciones y riesgo agregado (US2).

Principios del producto:
- No asumir independencia entre selecciones.
- No ocultar el tamaño de la combinación ni el efecto de las dependencias.
- La estimación agregada explica sus factores.

La cuota combinada se multiplica (producto de las cuotas observadas). La
probabilidad agregada SOLO se multiplica cuando no hay dependencias conocidas;
si las hay, se reporta el producto bajo independencia con advertencia explícita
(`assumes_independence=True`) y se eleva el riesgo.
"""

from dataclasses import dataclass
from functools import reduce
from operator import mul

PARLAY_MIN = 2
PARLAY_MAX = 3

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
_RISK_BY_ORDER = ("low", "medium", "high")


@dataclass(frozen=True)
class SelectionRef:
    """Referencia canónica a una selección dentro de un parlay.

    `teams` son los IDs de los equipos del partido: permiten detectar
    dependencias conocidas (mismo equipo en varios partidos).
    """

    match_id: str
    market: str
    selection: str
    teams: frozenset[str] = frozenset()

    def canonical_key(self) -> str:
        return f"{self.match_id}::{self.market}::{self.selection}"


@dataclass(frozen=True)
class SelectionEstimate:
    """Selección resuelta con su probabilidad y cuota observada."""

    ref: SelectionRef
    probability: float
    odds: float


@dataclass(frozen=True)
class CorrelationReport:
    """Dependencias conocidas entre selecciones."""

    same_match_pairs: tuple[tuple[str, str], ...] = ()
    same_selection_duplicates: tuple[str, ...] = ()
    shared_team_pairs: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def has_dependencies(self) -> bool:
        return bool(
            self.same_match_pairs or self.same_selection_duplicates or self.shared_team_pairs
        )


def detect_correlations(refs: list[SelectionRef]) -> CorrelationReport:
    """Detecta selecciones del mismo partido, duplicados y equipos repetidos."""
    same_match_pairs: list[tuple[str, str]] = []
    same_selection_duplicates: list[str] = []
    shared_team_pairs: list[tuple[str, str]] = []
    warnings: list[str] = []

    by_match: dict[str, list[SelectionRef]] = {}
    by_team: dict[str, list[SelectionRef]] = {}

    for ref in refs:
        by_match.setdefault(ref.match_id, []).append(ref)
        for team in ref.teams:
            by_team.setdefault(team, []).append(ref)

    for _match_id, group in by_match.items():
        if len(group) < 2:
            continue
        pairs = _pairs(group)
        if all(ref.selection == group[0].selection for ref in group):
            for ref in group[1:]:
                same_selection_duplicates.append(ref.canonical_key())
                warnings.append(
                    f"Selección duplicada en el mismo partido: {ref.canonical_key()}"
                )
        else:
            for a, b in pairs:
                if a.selection != b.selection:
                    same_match_pairs.append((a.canonical_key(), b.canonical_key()))
                    warnings.append(
                        f"{a.match_id}: {a.selection} y {b.selection} son excluyentes; "
                        "no pueden ganar ambas (riesgo de que el parlay quede anulado)"
                    )

    for team, group in by_team.items():
        if len(group) < 2:
            continue
        for a, b in _pairs(group):
            if a.match_id == b.match_id:
                continue
            key = _ordered_pair(a.canonical_key(), b.canonical_key())
            if key in shared_team_pairs:
                continue
            shared_team_pairs.append(key)
            warnings.append(
                f"El equipo {team} participa en dos selecciones; sus resultados "
                "pueden estar correlacionados y NO se asume independencia"
            )

    return CorrelationReport(
        same_match_pairs=tuple(same_match_pairs),
        same_selection_duplicates=tuple(same_selection_duplicates),
        shared_team_pairs=tuple(shared_team_pairs),
        warnings=tuple(warnings),
    )


def combined_odds(selections: list[SelectionEstimate]) -> float:
    if not selections:
        return 0.0
    return round(reduce(mul, (s.odds for s in selections), 1.0), 2)


def naive_combined_probability(selections: list[SelectionEstimate]) -> float:
    """Producto de probabilidades bajo independencia total."""
    if not selections:
        return 0.0
    return reduce(mul, (s.probability for s in selections), 1.0)


def aggregate_risk_level(
    selection_risks: list[str],
    *,
    correlation: CorrelationReport,
) -> str:
    """Combina el riesgo de las selecciones y lo ajusta por dependencias."""
    base = _max_risk(selection_risks)
    if correlation.same_match_pairs or correlation.same_selection_duplicates:
        return "high"
    if correlation.shared_team_pairs:
        return _lift(base)
    return base


def estimate_parlay(
    selections: list[SelectionEstimate],
    selection_risks: list[str],
) -> tuple["ParlayEstimate", CorrelationReport]:
    """Calcula la estimación agregada y el reporte de correlaciones."""
    refs = [s.ref for s in selections]
    correlation = detect_correlations(refs)

    odds = combined_odds(selections)
    naive = naive_combined_probability(selections)

    has_exclusive = bool(correlation.same_match_pairs or correlation.same_selection_duplicates)
    estimated = 0.0 if has_exclusive else naive

    assumes_independence = bool(correlation.shared_team_pairs) and not has_exclusive

    risk_level = aggregate_risk_level(selection_risks, correlation=correlation)
    factors = _risk_factors(selection_risks, risk_level, correlation, len(selections))

    estimate = ParlayEstimate(
        combined_odds=odds,
        naive_probability=round(naive, 6),
        estimated_probability=round(estimated, 6),
        fair_combined_odds=round(1 / estimated, 2) if estimated > 0 else None,
        risk_level=risk_level,
        risk_factors=factors,
        correlation_warnings=list(correlation.warnings),
        assumes_independence=assumes_independence,
        selection_count=len(selections),
    )
    return estimate, correlation


def _risk_factors(
    selection_risks: list[str],
    risk_level: str,
    correlation: CorrelationReport,
    selection_count: int,
) -> list[str]:
    factors: list[str] = []
    if selection_count < PARLAY_MIN:
        factors.append(f"El parlay necesita al menos {PARLAY_MIN} selecciones")
    factors.append(f"{selection_count} selección(es) combinada(s)")
    if selection_risks:
        worst = _max_risk(selection_risks)
        factors.append(f"Riesgo de la selección más riesgosa: {worst}")
    if correlation.same_match_pairs:
        factors.append("Selecciones del mismo partido: la probabilidad conjunta es 0")
    if correlation.same_selection_duplicates:
        factors.append("Selecciones duplicadas detectadas")
    if correlation.shared_team_pairs:
        factors.append("Equipos compartidos entre partidos: resultados correlacionados")
    if (
        risk_level == "high"
        and not correlation.same_match_pairs
        and not correlation.same_selection_duplicates
        and not correlation.shared_team_pairs
    ):
        factors.append("Riesgo alto por el nivel de riesgo de las selecciones")
    return factors


@dataclass(frozen=True)
class ParlayEstimate:
    combined_odds: float
    naive_probability: float
    estimated_probability: float
    fair_combined_odds: float | None
    risk_level: str
    risk_factors: list[str]
    correlation_warnings: list[str]
    assumes_independence: bool
    selection_count: int


def _max_risk(levels: list[str]) -> str:
    if not levels:
        return "low"
    ranks = [_RISK_ORDER[level] for level in levels if level in _RISK_ORDER]
    return _RISK_BY_ORDER[max(ranks)]


def _lift(level: str) -> str:
    order = _RISK_ORDER[level]
    return _RISK_BY_ORDER[min(order + 1, len(_RISK_BY_ORDER) - 1)]


def _pairs(items: list) -> list[tuple]:
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            out.append((items[i], items[j]))
    return out


def _ordered_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)

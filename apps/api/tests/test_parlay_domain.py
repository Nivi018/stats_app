"""Pruebas del dominio del parlay: correlaciones, cuota y riesgo agregado (US2)."""

import pytest

from app.domain.parlay import (
    PARLAY_MAX,
    PARLAY_MIN,
    SelectionEstimate,
    SelectionRef,
    aggregate_risk_level,
    combined_odds,
    detect_correlations,
    estimate_parlay,
    naive_combined_probability,
)


def ref(match_id: str, selection: str, teams=()) -> SelectionRef:
    return SelectionRef(match_id=match_id, market="over_under_2_5", selection=selection, teams=frozenset(teams))


def sel(match_id: str, selection: str, teams=(), probability: float = 0.6, odds: float = 1.8) -> SelectionEstimate:
    return SelectionEstimate(ref=ref(match_id, selection, teams), probability=probability, odds=odds)


def test_combined_odds_multiplica_y_redondea():
    a = sel("m1", "over", odds=1.80)
    b = sel("m2", "over", odds=2.10)
    assert combined_odds([a, b]) == pytest.approx(round(1.80 * 2.10, 2))


def test_naive_probability_es_el_producto():
    a = sel("m1", "over", probability=0.6)
    b = sel("m2", "over", probability=0.5)
    assert naive_combined_probability([a, b]) == pytest.approx(0.3)


def test_partidos_independientes_no_generan_advertencias():
    a = sel("m1", "over", teams={"T1", "T2"})
    b = sel("m2", "under", teams={"T3", "T4"})
    estimate, correlation = estimate_parlay([a, b], ["low", "medium"])

    assert correlation.has_dependencies is False
    assert correlation.warnings == ()
    assert estimate.assumes_independence is False
    assert estimate.estimated_probability == pytest.approx(estimate.naive_probability)
    assert estimate.risk_level == "medium"


def test_selecciones_excluyentes_del_mismo_partido_anulan_probabilidad():
    over = sel("m1", "over", teams={"T1", "T2"})
    under = sel("m1", "under", teams={"T1", "T2"})
    estimate, correlation = estimate_parlay([over, under], ["low", "low"])

    assert correlation.same_match_pairs
    assert estimate.estimated_probability == 0.0
    assert estimate.fair_combined_odds is None
    assert estimate.risk_level == "high"
    assert any("excluyentes" in w for w in estimate.correlation_warnings)


def test_equipo_compartido_no_asume_independencia():
    a = sel("m1", "over", teams={"T1", "T2"})
    b = sel("m2", "over", teams={"T2", "T3"})  # T2 repite
    estimate, correlation = estimate_parlay([a, b], ["low", "low"])

    assert correlation.shared_team_pairs
    assert estimate.assumes_independence is True
    assert estimate.estimated_probability == pytest.approx(estimate.naive_probability)
    assert any("correlacionados" in w for w in estimate.correlation_warnings)


def test_equipo_compartido_eleva_el_riesgo_un_nivel():
    a = sel("m1", "over", teams={"T1", "T2"})
    b = sel("m2", "over", teams={"T2", "T3"})
    estimate, _ = estimate_parlay([a, b], ["low", "low"])
    assert estimate.risk_level == "medium"

    estimate_hi, _ = estimate_parlay([a, b], ["medium", "low"])
    assert estimate_hi.risk_level == "high"


def test_seleccion_duplicada_detectada():
    a = sel("m1", "over", teams={"T1", "T2"})
    b = sel("m1", "over", teams={"T1", "T2"})
    estimate, correlation = estimate_parlay([a, b], ["low", "low"])

    assert correlation.same_selection_duplicates
    assert estimate.risk_level == "high"
    assert estimate.estimated_probability == 0.0


def test_agregacion_de_riesgo_toma_el_maximo():
    assert aggregate_risk_level(["low", "high"], correlation=detect_correlations([])) == "high"
    assert aggregate_risk_level(["low", "medium"], correlation=detect_correlations([])) == "medium"
    assert aggregate_risk_level([], correlation=detect_correlations([])) == "low"


def test_factores_de_riesgo_explican_el_resultado():
    a = sel("m1", "over", teams={"T1", "T2"})
    b = sel("m2", "over", teams={"T2", "T3"})
    estimate, _ = estimate_parlay([a, b], ["medium", "low"])

    assert estimate.risk_factors
    assert any("más riesgosa: medium" in f for f in estimate.risk_factors)
    assert any("correlacionados" in f for f in estimate.risk_factors)


def test_constantes_de_limite():
    assert PARLAY_MIN == 2
    assert PARLAY_MAX == 3


def test_cuota_justa_combinada():
    a = sel("m1", "over", teams={"T1", "T2"}, probability=0.5)
    b = sel("m2", "over", teams={"T3", "T4"}, probability=0.5)
    estimate, _ = estimate_parlay([a, b], ["low", "low"])
    assert estimate.fair_combined_odds == pytest.approx(4.0, abs=0.01)

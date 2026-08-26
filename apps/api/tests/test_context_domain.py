"""Pruebas del contexto de partido: forma y H2H (Sprint 8)."""

from datetime import datetime, timezone

from app.domain.context import TeamMatchRecord, build_context
import pytest


def rec(
    kickoff: int,
    home: str,
    away: str,
    hs: int,
    as_: int,
) -> TeamMatchRecord:
    return TeamMatchRecord(
        kickoff_at=datetime(2026, 7, kickoff, tzinfo=timezone.utc),
        home_team_id=home,
        away_team_id=away,
        home_score=hs,
        away_score=as_,
    )


def test_form_incluye_resultados_w_d_l():
    records = [
        rec(1, "T1", "T2", 2, 1),  # T1 gana
        rec(2, "T3", "T1", 1, 1),  # T1 empata (visitante)
        rec(3, "T1", "T4", 0, 2),  # T1 pierde
    ]
    context = build_context(records, home_team_id="T1", away_team_id="T9")
    assert [e.result for e in context.home_form] == ["L", "D", "W"]
    assert [e.result for e in context.away_form] == []


def test_form_solo_partidos_del_equipo_y_ordenados():
    records = [
        rec(1, "T1", "T2", 1, 0),
        rec(2, "T3", "T4", 1, 1),  # no involucra T1
        rec(3, "T5", "T1", 0, 2),  # T1 gana de visitante
        rec(4, "T1", "T6", 2, 2),  # T1 empata
    ]
    context = build_context(records, home_team_id="T1", away_team_id="T9")
    assert [e.result for e in context.home_form] == ["D", "W", "W"]
    assert [e.opponent_short for e in context.home_form] == ["T6", "T5", "T2"]


def test_resultado_visitante_proporciona_equipo():
    context = build_context(
        [rec(2, "T3", "T1", 0, 1)],  # T1 gana 1-0 fuera
        home_team_id="T1",
        away_team_id="T9",
    )
    assert context.home_form[0].result == "W"


def test_h2h_solo_cuando_se_enfrentan():
    records = [
        rec(1, "T1", "T2", 2, 1),
        rec(2, "T1", "T3", 0, 0),  # no vs T2
        rec(3, "T2", "T1", 1, 0),  # T2 gana; T1 visitante pierde
    ]
    context = build_context(records, home_team_id="T1", away_team_id="T2")
    assert len(context.h2h) == 2
    # El último H2H es T2 vs T1 -> T1 pierde (L).
    assert context.h2h[0].result == "L"


def test_limite_configurable():
    records = [rec(i, "T1", "T9", 1, 0) for i in range(1, 11)]
    context = build_context(records, home_team_id="T1", away_team_id="T9", limit=3)
    assert len(context.home_form) == 3


def test_sin_historial_estado_vacio():
    context = build_context([], home_team_id="T1", away_team_id="T2")
    assert context.home_form == []
    assert context.away_form == []
    assert context.h2h == []
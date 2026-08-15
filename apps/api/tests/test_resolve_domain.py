"""Pruebas de la resolución de resultados demo (US4)."""

import pytest

from app.domain.resolve import LOSS, VOID, WIN, resolve_outcome


@pytest.mark.parametrize(
    "selection,home,away,expected",
    [
        ("over", 2, 1, WIN),   # 3 > 2.5
        ("over", 1, 1, LOSS),  # 2 < 2.5
        ("over", 0, 0, LOSS),
        ("under", 1, 1, WIN),  # 2 < 2.5
        ("under", 2, 1, LOSS), # 3 > 2.5
    ],
)
def test_over_under_2_5(selection, home, away, expected):
    assert resolve_outcome("over_under_2_5", selection, home, away) == expected


def test_void_sin_marcador():
    assert resolve_outcome("over_under_2_5", "over", None, 1) == VOID
    assert resolve_outcome("over_under_2_5", "under", 0, None) == VOID


def test_void_mercado_desconocido():
    assert resolve_outcome("1x2", "home", 2, 1) == VOID


def test_void_empate_con_la_linea_push():
    assert resolve_outcome("over_under_2", "over", 1, 1, line=2) == VOID


def test_void_seleccion_desconocida():
    assert resolve_outcome("over_under_2_5", "draw", 2, 1) == VOID

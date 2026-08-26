"""Pruebas numéricas de los mercados derivados (Sprint 10)."""

import pytest

from app.model.markets import (
    probability_1x2,
    probability_handicap,
    probability_team_total,
    score_matrix,
)


@pytest.mark.parametrize("lam_h,lam_a", [(1.5, 1.5), (2.0, 0.8), (0.7, 2.4), (1.9, 1.1)])
def test_1x2_probabilidades_suman_1(lam_h, lam_a):
    matrix = score_matrix(lam_h, lam_a)
    p_home, p_draw, p_away = probability_1x2(matrix)
    assert sum([p_home, p_draw, p_away]) == pytest.approx(1.0, abs=1e-6)
    assert all(0 <= p <= 1 for p in (p_home, p_draw, p_away))


def test_1x2_simetrico_equaliza_local_visitante():
    matrix = score_matrix(1.5, 1.5)
    p_home, p_draw, p_away = probability_1x2(matrix)
    assert p_home == pytest.approx(p_away, abs=1e-9)
    assert p_draw > 0


def test_1x2_favorito_local_gana_al_visitante():
    matrix = score_matrix(2.0, 0.8)
    p_home, _, p_away = probability_1x2(matrix)
    assert p_home > p_away


def test_total_por_equipo_over_y_under_complementarios():
    matrix = score_matrix(1.5, 1.5)
    over = probability_team_total(matrix, team="home", outcome="over", line=1.5)
    under = probability_team_total(matrix, team="home", outcome="under", line=1.5)
    assert over + under == pytest.approx(1.0, abs=1e-9)


def test_total_equipo_mas_goleador_te_eleva_over():
    matrix = score_matrix(2.4, 0.7)
    home_over = probability_team_total(matrix, team="home", outcome="over", line=1.5)
    away_over = probability_team_total(matrix, team="away", outcome="over", line=1.5)
    assert home_over > away_over


def test_handicap_cover_complementario_de_no_cover():
    matrix = score_matrix(1.5, 1.5)
    cover = probability_handicap(matrix, team="home", line=-1, covers=True)
    no_cover = probability_handicap(matrix, team="home", line=-1, covers=False)
    assert cover + no_cover == pytest.approx(1.0, abs=1e-9)


def test_handicap_favorito_te_aumenta_cover():
    matrix = score_matrix(2.0, 0.8)
    cover_pos = probability_handicap(matrix, team="home", line=1, covers=True)
    cover_neg = probability_handicap(matrix, team="home", line=-1, covers=True)
    assert 0.5 < cover_pos < 1.0
    assert cover_neg < cover_pos


def test_invalidos_rechazados():
    matrix = score_matrix(1.0, 1.0)
    with pytest.raises(ValueError):
        probability_team_total(matrix, team="banco", outcome="over", line=1.5)
    with pytest.raises(ValueError):
        probability_team_total(matrix, team="home", outcome="push", line=1.5)
"""Pruebas de los splits walk-forward (US7)."""

from datetime import datetime, timezone

import pytest

from app.backtest.walk_forward import (
    MatchRecord,
    final_holdout,
    sort_chronologically,
    walk_forward_splits,
)


def record(external_id: str, day: int) -> MatchRecord:
    return MatchRecord(
        external_id=external_id,
        kickoff_at=datetime(2026, 7, day, 19, tzinfo=timezone.utc),
        home_team_id="t-home",
        away_team_id="t-away",
        home_score=1,
        away_score=1,
        matchday=1,
    )


def make(n: int) -> list[MatchRecord]:
    return [record(f"m-{i:02d}", 2 + i) for i in range(n)]


def test_sort_is_chronological_and_deterministic():
    matches = [record("m-b", 5), record("m-a", 3), record("m-c", 3)]
    ordered = sort_chronologically(matches)
    assert [m.external_id for m in ordered] == ["m-a", "m-c", "m-b"]
    assert sort_chronologically(matches) == ordered


def test_walk_forward_split_contiguo_y_expandido():
    folds = walk_forward_splits(make(12), n_folds=4)
    assert len(folds) == 4

    seen = []
    for fold in folds:
        seen.extend(fold.test)
        # Ventana expandida: train son TODOS los anteriores.
        assert len(fold.train) == len(seen) - len(fold.test)
    assert len(seen) == 12


def test_walk_forward_deterministic():
    a = walk_forward_splits(make(10), n_folds=3)
    b = walk_forward_splits(make(10), n_folds=3)
    assert [(f.index, f.train_size, f.test_size) for f in a] == [
        (f.index, f.train_size, f.test_size) for f in b
    ]


def test_fold_test_is_strictly_after_train():
    folds = walk_forward_splits(make(12), n_folds=4)
    for fold in folds:
        for train_match in fold.train:
            for test_match in fold.test:
                assert train_match.kickoff_at < test_match.kickoff_at


def test_holdout_final_es_el_ultimo_bloque():
    matches = make(12)
    holdout = final_holdout(matches, n_folds=4)
    assert len(holdout) == 3
    assert holdout == sort_chronologically(matches)[-3:]


def test_holdout_final_no_participa_en_train_de_promocion():
    # out-of-sample = folds[:-1]; el último fold solo se reporta.
    folds = walk_forward_splits(make(12), n_folds=4)
    last = folds[-1]
    assert last.index == 3
    assert list(last.test) == final_holdout(make(12), n_folds=4)


def test_rechaza_folds_invalidos():
    with pytest.raises(ValueError):
        walk_forward_splits(make(6), n_folds=1)


def test_dataset_pequeno_un_solo_fold():
    folds = walk_forward_splits(make(3), n_folds=4)
    assert len(folds) == 1
    assert folds[0].test_size == 3
    assert folds[0].train_size == 0

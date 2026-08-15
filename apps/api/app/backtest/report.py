"""Motor y ensamblado del reporte de backtesting (US7)."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.baselines import (
    league_probability,
    market_odds,
    market_probability,
    poisson_probabilities,
)
from app.backtest.walk_forward import (
    Fold,
    MatchRecord,
    walk_forward_splits,
)
from app.evaluation.metrics import MetricsReport, ResolvedPrediction, compute_metrics

BASELINES = ("market", "league", "poisson")
DEFAULT_RANDOM_SEED = 42
BACKTEST_MIN_SAMPLE = 20


@dataclass(frozen=True)
class BaselineMetrics:
    name: str
    metrics: MetricsReport
    coverage: float  # fracción de candidatos con predicción disponible
    coverage_n: int
    candidates_n: int


@dataclass(frozen=True)
class FoldReport:
    index: int
    train_size: int
    test_size: int
    baselines: list[BaselineMetrics]


@dataclass(frozen=True)
class BacktestReport:
    n_folds: int
    dataset_version: str
    random_seed: int
    folds: list[FoldReport]
    overall: list[BaselineMetrics]
    out_of_sample: list[BaselineMetrics]
    final_holdout: list[BaselineMetrics]

    def to_dict(self) -> dict[str, Any]:
        def metrics_to_dict(m: BaselineMetrics) -> dict[str, Any]:
            return {
                "name": m.name,
                "coverage": m.coverage,
                "coverage_n": m.coverage_n,
                "candidates_n": m.candidates_n,
                "metrics": {
                    "sample_size": m.metrics.sample_size,
                    "wins": m.metrics.wins,
                    "losses": m.metrics.losses,
                    "voids": m.metrics.voids,
                    "hit_rate": m.metrics.hit_rate,
                    "unit_roi": m.metrics.unit_roi,
                    "brier": m.metrics.brier,
                    "sample_sufficient": m.metrics.sample_sufficient,
                    "calibration_bins": [
                        asdict(b) for b in m.metrics.calibration_bins
                    ],
                },
            }

        return {
            "n_folds": self.n_folds,
            "dataset_version": self.dataset_version,
            "random_seed": self.random_seed,
            "folds": [
                {
                    "index": f.index,
                    "train_size": f.train_size,
                    "test_size": f.test_size,
                    "baselines": [metrics_to_dict(b) for b in f.baselines],
                }
                for f in self.folds
            ],
            "overall": [metrics_to_dict(b) for b in self.overall],
            "out_of_sample": [metrics_to_dict(b) for b in self.out_of_sample],
            "final_holdout": [metrics_to_dict(b) for b in self.final_holdout],
        }


async def _baseline_probs(
    session: AsyncSession,
    fold: Fold,
    record: MatchRecord,
) -> dict[str, tuple[float, float] | None]:
    p_market = (
        (market_probability(record, "over"), market_probability(record, "under"))
        if market_probability(record, "over") is not None
        else None
    )
    p_league = None
    if league_probability(fold.train, "over") is not None:
        rate = league_probability(fold.train, "over")
        p_league = (rate, 1.0 - rate)
    p_poisson = await poisson_probabilities(session, record.external_id, record.kickoff_at)
    return {"market": p_market, "league": p_league, "poisson": p_poisson}


def _evaluate(
    records_by_baseline: dict[str, list[ResolvedPrediction]],
    candidates_n: int,
) -> list[BaselineMetrics]:
    result: list[BaselineMetrics] = []
    for name in BASELINES:
        records = records_by_baseline[name]
        metrics = compute_metrics(records, threshold=BACKTEST_MIN_SAMPLE)
        coverage = len(records) / candidates_n if candidates_n else 0.0
        result.append(
            BaselineMetrics(
                name=name,
                metrics=metrics,
                coverage=round(coverage, 4),
                coverage_n=len(records),
                candidates_n=candidates_n,
            )
        )
    return result


async def run_backtest(
    session_factory,
    matches: list[MatchRecord],
    *,
    n_folds: int = 4,
    dataset_version: str = "demo-2026-apertura",
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> BacktestReport:
    folds = walk_forward_splits(matches, n_folds)
    fold_records: list[dict[str, list[ResolvedPrediction]]] = []
    fold_candidates: list[int] = []
    fold_reports: list[FoldReport] = []

    async with session_factory() as session:
        for fold in folds:
            records: dict[str, list[ResolvedPrediction]] = defaultdict(list)
            candidates = 0
            for record in fold.test:
                if market_odds(record, "over") is None or market_odds(record, "under") is None:
                    continue
                candidates += 2  # over + under
                probs = await _baseline_probs(session, fold, record)
                for selection in ("over", "under"):
                    odds = market_odds(record, selection)
                    result = record.outcome_for(selection)
                    for name in BASELINES:
                        pair = probs[name]
                        if pair is None:
                            continue
                        probability = pair[0] if selection == "over" else pair[1]
                        records[name].append(
                            ResolvedPrediction(probability=probability, odds=odds, result=result)
                        )
            fold_records.append(records)
            fold_candidates.append(candidates)
            fold_reports.append(
                FoldReport(
                    index=fold.index,
                    train_size=fold.train_size,
                    test_size=fold.test_size,
                    baselines=_evaluate(records, candidates),
                )
            )

    overall = _aggregate(fold_records, sum(fold_candidates))
    out_of_sample = _aggregate(fold_records[:-1], sum(fold_candidates[:-1]))
    final_records = fold_records[-1] if fold_records else defaultdict(list)
    final_candidates = fold_candidates[-1] if fold_candidates else 0
    final_holdout = _evaluate(final_records, final_candidates)

    return BacktestReport(
        n_folds=len(folds),
        dataset_version=dataset_version,
        random_seed=random_seed,
        folds=fold_reports,
        overall=overall,
        out_of_sample=out_of_sample,
        final_holdout=final_holdout,
    )


def _aggregate(
    fold_records: list[dict[str, list[ResolvedPrediction]]],
    candidates_n: int,
) -> list[BaselineMetrics]:
    merged: dict[str, list[ResolvedPrediction]] = defaultdict(list)
    for records in fold_records:
        for name, items in records.items():
            merged[name].extend(items)
    return _evaluate(merged, candidates_n)

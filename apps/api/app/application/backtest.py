"""Caso de uso: reporte de backtesting walk-forward (Sprint 9).

Reutiliza el motor de `app/backtest` (mismo cálculo y determinismo que el CLI)
y expone el reporte por pliegue + overall + out-of-sample + holdout.
"""

from app.backtest.report import run_backtest
from app.backtest.run import load_match_records


class BacktestService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def report(self, n_folds: int = 4) -> dict:
        async with self._session_factory() as session:
            matches = await load_match_records(session)
        report = await run_backtest(
            self._session_factory,
            matches,
            n_folds=n_folds,
            dataset_version="demo-2026-apertura",
            random_seed=42,
        )
        return report.to_dict()

"""CLI de backtesting walk-forward y reporte de promoción (US7).

Uso:
    python -m app.backtest.run [--folds N] [--out PATH]

Genera un reporte determinista con baselines (mercado, frecuencia de liga y
Poisson), métricas por pliegue + overall + out-of-sample + holdout final, y
aplica la política candidate->shadow->active sobre la versión Poisson usando
solo métricas out-of-sample.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.backtest.promotion import evaluate_candidate
from app.backtest.report import BacktestReport, run_backtest
from app.backtest.walk_forward import MatchRecord
from app.db.session import async_session
from app.model.baseline import MODEL_NAME, MODEL_VERSION
from app.models import Match, ModelVersion, OddsSnapshot
from app.seeds.loader import load_demo_seed

DATASET_VERSION = "demo-2026-apertura"
RANDOM_SEED = 42


async def load_match_records(session) -> list[MatchRecord]:
    """Carga partidos finalizados con su par de cuotas prepartido."""
    matches = (
        (await session.execute(select(Match).where(Match.status == "finished")))
        .scalars()
        .all()
    )
    odds = (await session.execute(select(OddsSnapshot))).scalars().all()
    odds_by_match: dict = {}
    for o in odds:
        odds_by_match.setdefault(o.match_id, {})[o.selection] = o.odds

    records: list[MatchRecord] = []
    for m in matches:
        pair = odds_by_match.get(m.id, {})
        records.append(
            MatchRecord(
                external_id=m.external_id,
                kickoff_at=m.kickoff_at,
                home_team_id=str(m.home_team_id),
                away_team_id=str(m.away_team_id),
                home_score=m.home_score,
                away_score=m.away_score,
                matchday=m.matchday,
                over_odds=pair.get("over"),
                under_odds=pair.get("under"),
            )
        )
    return records


async def _apply_promotion(report: BacktestReport) -> dict:
    """Aplica candidate->shadow->active a la versión Poisson usando out-of-sample."""
    def metrics_by_name(baselines):
        return {b.name: b for b in baselines}

    oos = metrics_by_name(report.out_of_sample)
    poisson = oos.get("poisson")
    market = oos.get("market")
    if poisson is None or market is None:
        return {"applied": False, "reason": "sin baselines comparables"}

    async with async_session() as session:
        mv = (
            await session.execute(
                select(ModelVersion).where(
                    ModelVersion.name == MODEL_NAME,
                    ModelVersion.version == MODEL_VERSION,
                )
            )
        ).scalar_one_or_none()
        if mv is None:
            mv = ModelVersion(
                name=MODEL_NAME,
                version=MODEL_VERSION,
                status="candidate",
                feature_set_version="1.0.0",
            )
            session.add(mv)
            await session.flush()

        decision = evaluate_candidate(
            mv.status,
            sample_size=poisson.metrics.sample_size,
            brier=poisson.metrics.brier,
            active_brier=market.metrics.brier,
        )
        if decision.changed:
            mv.status = decision.recommended_status
            if decision.recommended_status == "active":
                mv.activated_at = datetime.now(UTC)
        parameters = {
            "backtest": {
                "n_folds": report.n_folds,
                "dataset_version": report.dataset_version,
                "random_seed": report.random_seed,
                "out_of_sample": {
                    "brier": poisson.metrics.brier,
                    "hit_rate": poisson.metrics.hit_rate,
                    "unit_roi": poisson.metrics.unit_roi,
                    "sample_size": poisson.metrics.sample_size,
                    "market_brier": market.metrics.brier,
                },
            }
        }
        mv.parameters = json.dumps(parameters, sort_keys=True)
        await session.commit()
        return {
            "applied": True,
            "status": mv.status,
            "recommended": decision.recommended_status,
            "reasons": decision.reasons,
        }


async def _run(folds: int, out: str | None) -> None:
    async with async_session() as session:
        await load_demo_seed(session)
        matches = await load_match_records(session)

    report = await run_backtest(
        async_session,
        matches,
        n_folds=folds,
        dataset_version=DATASET_VERSION,
        random_seed=RANDOM_SEED,
    )
    promotion = await _apply_promotion(report)

    payload = report.to_dict()
    payload["promotion"] = promotion
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"\nReporte guardado en {out}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtesting walk-forward (US7)")
    parser.add_argument("--folds", type=int, default=4, help="Número de pliegues walk-forward")
    parser.add_argument("--out", type=str, default=None, help="Ruta del archivo JSON de reporte")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run(args.folds, args.out))


if __name__ == "__main__":
    main()

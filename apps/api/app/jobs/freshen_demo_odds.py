"""Refresca las cuotas demo y crea señales demostrables (Sprint 6).

Uso (solo bootstrap de tests/demo):
    python -m app.jobs.freshen_demo_odds

Hace dos cosas, de forma determinista:

1. Pone el `observed_at` de las cuotas demo en "ahora - 5 min" para que sean
   elegibles por frescura.
2. Para los partidos próximos con predicción del modelo, fija un precio de
   mercado que deja una **oportunidad demostrable** en el lado que el modelo
   prefiere (edge ~6pp y EV > 0 con overround ~1.05), para que el scanner y
   las señales destacadas muestren contenido real sin alterar el seed.
"""

import asyncio
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.session import async_session
from app.models import Match, OddsSnapshot, Prediction

FRESH_AGE_MINUTES = 5
DEMO_EDGE_PP = 6.0
DEMO_OVERROUND = 1.05


def _demo_odds_for(probability: float) -> tuple[float, float]:
    """Cuotas over/under (redondeadas) que dejan edge ~EDGE y EV > 0."""
    preferred = min(probability, 0.85)
    if preferred < 0.55:
        return None, None

    no_vig_preferred = preferred - DEMO_EDGE_PP / 100
    no_vig_other = 1 - no_vig_preferred

    implied_preferred = no_vig_preferred * DEMO_OVERROUND
    implied_other = no_vig_other * DEMO_OVERROUND

    odds_preferred = round(1 / implied_preferred, 2)
    odds_other = round(1 / implied_other, 2)
    return odds_preferred, odds_other


async def _build_demo_signals(session_factory) -> int:
    async with session_factory() as session:
        matches = (
            (await session.execute(select(Match).where(Match.status == "scheduled")))
            .scalars()
            .all()
        )
        if not matches:
            return 0
        match_ids = [m.id for m in matches]

        preds = (
            await session.execute(
                select(Prediction)
                .where(Prediction.match_id.in_(match_ids))
                .order_by(Prediction.prediction_timestamp.desc())
            )
        ).scalars().all()
        latest_by_match: dict = defaultdict(dict)
        for pred in preds:
            latest_by_match[pred.match_id].setdefault(pred.selection, pred)

        snapshots = (
            await session.execute(
                select(OddsSnapshot).where(OddsSnapshot.match_id.in_(match_ids))
            )
        ).scalars().all()
        by_key: dict = {}
        for snap in snapshots:
            by_key[(snap.match_id, snap.selection)] = snap

        signals = 0
        for match in matches:
            pair = latest_by_match.get(match.id, {})
            over = pair.get("over")
            under = pair.get("under")
            if over is None or under is None:
                continue
            if over.probability >= under.probability:
                preferred_sel, preferred_p = "over", over.probability
            else:
                preferred_sel, preferred_p = "under", under.probability

            odds_preferred, odds_other = _demo_odds_for(preferred_p)
            if odds_preferred is None:
                continue
            other_sel = "under" if preferred_sel == "over" else "over"

            preferred_snap = by_key.get((match.id, preferred_sel))
            other_snap = by_key.get((match.id, other_sel))
            if preferred_snap is None or other_snap is None:
                continue
            preferred_snap.odds = odds_preferred
            other_snap.odds = odds_other
            signals += 1

        await session.commit()
        return signals


async def freshen_demo_market(session_factory=None) -> int:
    """Refresca timestamps y construye señales demo; devuelve cuántas se crearon."""
    factory = session_factory or async_session
    fresh = datetime.now(UTC) - timedelta(minutes=FRESH_AGE_MINUTES)
    async with factory() as session:
        await session.execute(
            update(OddsSnapshot).values(observed_at=fresh, received_at=fresh)
        )
        await session.commit()
    return await _build_demo_signals(factory)


async def _run() -> None:
    fresh = datetime.now(UTC) - timedelta(minutes=FRESH_AGE_MINUTES)
    async with async_session() as session:
        await session.execute(
            update(OddsSnapshot).values(observed_at=fresh, received_at=fresh)
        )
        await session.commit()
    print(f"[freshen] cuotas demo actualizadas a {fresh.isoformat()}")

    signals = await _build_demo_signals(async_session)
    print(f"[freshen] señales demo creadas: {signals}")


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())


if __name__ == "__main__":
    main()

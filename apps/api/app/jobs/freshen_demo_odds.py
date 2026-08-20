"""Refresca el observed_at de las cuotas demo para pruebas E2E.

Uso (solo bootstrap de tests):
    python -m app.jobs.freshen_demo_odds

Simula cuotas frescas (ahora - 5 min) para que el scanner y el parlay tengan
datos elegibles sin alterar el seed determinista.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db.session import async_session
from app.models import OddsSnapshot

FRESH_AGE_MINUTES = 5


async def _run() -> None:
    fresh = datetime.now(timezone.utc) - timedelta(minutes=FRESH_AGE_MINUTES)
    async with async_session() as session:
        await session.execute(
            update(OddsSnapshot).values(observed_at=fresh, received_at=fresh)
        )
        await session.commit()
    print(f"[freshen] cuotas demo actualizadas a {fresh.isoformat()}")


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())


if __name__ == "__main__":
    main()

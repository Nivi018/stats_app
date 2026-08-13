"""Punto de entrada para cargar el seed demo.

Uso:
    python -m app.seeds.run
"""

import asyncio
import json
import sys

from app.db.session import async_session
from app.seeds.loader import load_demo_seed


async def _run() -> None:
    async with async_session() as session:
        manifest = await load_demo_seed(session)
    print(json.dumps(manifest.__dict__, indent=2, ensure_ascii=False))


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())


if __name__ == "__main__":
    main()

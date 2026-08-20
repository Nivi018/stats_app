"""Punto de entrada del worker.

Depende de `stats-api` (paquete `app`), que contiene el dominio, la cola y los
handlers. Ejecuta el bucle de consumo con observabilidad (US7).
"""

import asyncio
import signal
import sys
from typing import NoReturn


def handle_shutdown(signum: int, frame: object) -> None:
    print(f"[worker] Received signal {signum}, shutting down...", flush=True)
    sys.exit(0)


def main() -> NoReturn:
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    from app.jobs.worker import run

    asyncio.run(run())


if __name__ == "__main__":
    main()

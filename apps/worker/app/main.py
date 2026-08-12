import os
import signal
import sys
import time
from typing import NoReturn

from app.settings import settings


def handle_shutdown(signum: int, frame: object) -> None:
    print(f"[worker] Received signal {signum}, shutting down...")
    sys.exit(0)


def main() -> NoReturn:
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    print(f"[worker] Starting stats-worker v{settings.VERSION}")
    print(f"[worker] Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("[worker] Interrupted, exiting.")


if __name__ == "__main__":
    main()

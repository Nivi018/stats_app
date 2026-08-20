# Imagen del worker (consume la cola del API). Contexto de build: raíz del repo.
# Ejecuta el bucle de `stats-api` (app.jobs.worker) con observabilidad.
# Uso: docker build -f apps/worker/Dockerfile -t stats-worker:<commit> .
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATS_ENV=staging

WORKDIR /srv

RUN addgroup --system app && adduser --system --ingroup app app

COPY apps/api apps/api
COPY packages packages
RUN pip install --no-cache-dir -e apps/api

USER app

CMD ["python", "-m", "app.jobs.worker"]

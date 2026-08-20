# Imagen del API (FastAPI). Contexto de build: raíz del repo.
# Uso: docker build -f apps/api/Dockerfile -t stats-api:<commit> .
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATS_ENV=staging

WORKDIR /srv

RUN addgroup --system app && adduser --system --ingroup app app

# Copiar las fuentes del paquete y dependencias.
COPY apps/api apps/api
COPY packages packages
RUN pip install --no-cache-dir -e apps/api

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

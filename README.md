# Stats App

Monorepo para análisis estadístico de fútbol — Liga MX, Over/Under 2.5 prepartido, datos demo reproducibles.

## Estructura

```
apps/
  web/       # Next.js — UI, rutas, cliente API y E2E (Playwright)
  api/       # FastAPI — dominio, persistencia y endpoints
  worker/    # Consumidor de cola (ejecuta app.jobs.worker de stats-api)
packages/
  contracts/ # Especificación OpenAPI y tipos compartidos
  config/    # Configuración de tooling
infra/       # Docker Compose (dev y staging) y smoke test
docs/adr/    # Decisiones arquitectónicas
docs/runbooks/# Runbooks operativos (release y rollback)
```

## Requisitos

- Node.js 22+
- Python 3.12+
- Docker (para PostgreSQL y Redis locales)

## Arranque rápido

```bash
# Instalar dependencias
npm install

# Levantar PostgreSQL y Redis
docker compose -f infra/docker-compose.yml up -d

# Python venvs (primera vez)
python -m venv apps/api/.venv
apps/api/.venv/Scripts/pip install -e "apps/api[dev]"
python -m venv apps/worker/.venv
apps/worker/.venv/Scripts/pip install -e "apps/api[dev]"   # el worker usa el paquete stats-api

# Migrar y sembrar
npm run db:migrate
npm run db:seed

# Calcular y resolver predicciones demo (puebla scanner, parlay, historial y métricas)
apps/api/.venv/Scripts/python -m app.jobs.run_resolution

# Refrescar el mercado demo (timestamp fresco y señales demostrables)
apps/api/.venv/Scripts/python -m app.jobs.freshen_demo_odds
```

> **Nota:** `pytest` limpia el esquema de la base al terminar. Si tras correr las
> pruebas el API falla con "relation ... does not exist", vuelve a ejecutar los
> pasos de *migrar y sembrar*.

## Comandos

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Inicia web, API y worker en modo desarrollo |
| `npm run dev:web` | Solo web (Next.js) |
| `npm run dev:api` | Solo API (uvicorn, puerto 8000) |
| `npm run dev:worker` | Solo worker (consume la cola, puerto Redis) |
| `npm run build` | Compila todas las aplicaciones |
| `npm run lint` | Lint de todas las unidades |
| `npm test` | Tests unitarios de todas las unidades |
| `npm test -w @stats/web` | Tests de vitest del frontend |
| `npm run test:e2e -w @stats/web` | E2E Playwright (stack integrado) |
| `npm run db:migrate` | `alembic upgrade head` |
| `npm run db:seed` | Carga el seed demo |
| `npm run infra:up` | Levanta PostgreSQL y Redis (dev) |

### Por unidad

```bash
# Web
npm run dev -w @stats/web
npm test -w @stats/web
npm run lint -w @stats/web
npm run test:e2e -w @stats/web   # requiere API + PostgreSQL + Redis

# API
apps/api/.venv/Scripts/uvicorn app.main:app --reload --port 8000
apps/api/.venv/Scripts/python -m pytest apps/api/tests -v

# Worker
apps/api/.venv/Scripts/python -m app.jobs.worker
```

## Variables de entorno

Copiar `.env.example` a `.env` y ajustar según entorno. Prefijo `STATS_`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `STATS_POSTGRES_HOST` | localhost | Host de PostgreSQL |
| `STATS_POSTGRES_PORT` | 5434 | Puerto (Docker remapea 5432→5434) |
| `STATS_POSTGRES_USER` | stats | Usuario |
| `STATS_POSTGRES_PASSWORD` | stats | Contraseña |
| `STATS_POSTGRES_DB` | stats_app | Base de datos |
| `STATS_REDIS_HOST` | localhost | Host de Redis |
| `STATS_REDIS_PORT` | 6380 | Puerto de Redis (Docker remapea 6379?6380) |
| `STATS_API_URL` | http://localhost:8000 | URL del API (web: proxy SSR + rewrite) |
| `STATS_ENV` | development | Entorno (echo SQL en desarrollo) |

## Pruebas

- **Unitarias**: vitest (web) y pytest (API). El API requiere PostgreSQL y Redis.
- **E2E**: Playwright cubre dashboard, scanner, detalle, parlay e historial contra
  el stack integrado, en desktop y móvil. El bootstrap migra, siembra, calcula y
  refresca cuotas automáticamente.
- **Rendimiento**: regresiones de N+1 con conteo de queries (`tests/test_performance.py`).
- **Accesibilidad**: auditoría axe-core WCAG AA en flujos críticos
  (`e2e/a11y.spec.ts`). Ver `apps/web/ACCESSIBILITY.md`.

## Observabilidad

- Logs JSON con `service`, `release`, `correlation_id` y `job_id` (sin secretos).
- `X-Correlation-Id` se propaga web→API→worker.
- Métricas Prometheus en `/api/v1/ops/metrics` (latencia, errores, backlog,
  retry, DLQ, frescura de cuotas).
- Guía "cómo confiar en el modelo" en `apps/web/VERIFICATION.md`.

## Stake responsable (Sprint 7)

El scanner y el parlay muestran una sugerencia de stake por unidad:

- **Fórmula**: Kelly fraccionado (`(p·cuota − 1) / (cuota − 1) × 25%`).
- **Tope**: 5% del bankroll por apuesta; 1 unidad = 2% del bankroll.
- No se sugiere apostar con EV ≤ 0 ni cuota inválida.
- **No es consejo financiero**: cada usuario define su propio bankroll.

## Demo

```bash
apps/api/.venv/Scripts/python -m app.seeds.run          # siembra
apps/api/.venv/Scripts/python -m app.jobs.run_resolution # calcula + resuelve demo
apps/api/.venv/Scripts/python -m app.backtest.run        # backtesting walk-forward
```

Rutas web: `/` jornada · `/scanner` oportunidades · `/matches/{id}` detalle ·
`/parlay` constructor · `/history` historial y métricas.

## Despliegue (staging)

Ver `docs/runbooks/release.md` para el runbook completo (expand-contract,
backup, smoke y rollback de apps/esquema/cola) y la checklist con responsables.

```bash
docker build -f apps/api/Dockerfile    -t stats-api:latest .
docker build -f apps/worker/Dockerfile -t stats-worker:latest .
docker build -f apps/web/Dockerfile --build-arg STATS_API_URL=http://api:8000 -t stats-web:latest .
docker compose -f infra/docker-compose.staging.yml up --build --abort-on-container-exit
```

## CI/CD

`.github/workflows/ci.yml` valida web (lint/test/build), API (pytest contra
PostgreSQL/Redis) y contratos (OpenAPI).

## Limitaciones (MVP demo)

- Datos demo reproducibles; sin API real aún (decisión go/no-go en `docs/adr/0007-*`).
- Solo mercado Over/Under 2.5 prepartido.
- Sin pagos, cuentas de casas de apuestas ni datos live.
- Las probabilidades son estimaciones, no garantías.

## Troubleshooting

**`python` no encontrado**: instalar Python 3.12 o desactivar los alias del
Microsoft Store.

**`eslint.config.mjs` no encontrado al ejecutar lint**: correr eslint desde la
app: `npx eslint src` en `apps/web`.

**PostgreSQL o Redis no responden**: `docker compose -f infra/docker-compose.yml ps`.

**Conflicto de puerto con PostgreSQL local**: Docker usa el 5434 (Redis el 6380), lejos del PostgreSQL local; detener el
servicio local o ajustar `STATS_POSTGRES_PORT`.

**E2E no hidrata (403 en `/_next/static/chunks`)**: asegurar `allowedDevOrigins`
incluye `127.0.0.1` y que no haya un `next dev` previo usando el puerto 3000.

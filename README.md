# Stats App

Monorepo para análisis estadístico de fútbol — Liga MX, Over/Under 2.5 prepartido, datos demo reproducibles.

## Estructura

```
apps/
  web/       # Next.js — UI, rutas y cliente API
  api/       # FastAPI — dominio, persistencia y endpoints
  worker/    # Consumidor de cola — ingesta y cálculo asíncrono
packages/
  contracts/ # Especificación OpenAPI y tipos compartidos
  config/    # Configuración de tooling
infra/       # Docker Compose y configuración de despliegue
docs/adr/    # Decisiones arquitectónicas
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
apps/worker/.venv/Scripts/pip install -e "apps/worker[dev]"
```

## Comandos

| Comando | Descripción |
|---------|-------------|
| `npm run dev` | Inicia todos los procesos en modo desarrollo |
| `npm run build` | Compila todas las aplicaciones |
| `npm run lint` | Ejecuta lint en todas las unidades |
| `npm test` | Ejecuta todas las pruebas |
| `npm test -w @stats/web` | Solo pruebas del frontend |
| `npm run build -w @stats/web` | Solo build del frontend |

### Por unidad

```bash
# Web (Next.js)
npm run dev -w @stats/web
npm test -w @stats/web
npm run lint -w @stats/web

# API (FastAPI)
apps/api/.venv/Scripts/uvicorn app.main:app --reload --port 8000
apps/api/.venv/Scripts/python -m pytest apps/api/tests -v

# Worker
apps/worker/.venv/Scripts/python -m app.main
```

## Variables de entorno

Copiar `.env.example` a `.env` y ajustar según entorno. Las variables usan el prefijo `STATS_`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `STATS_POSTGRES_HOST` | localhost | Host de PostgreSQL |
| `STATS_POSTGRES_PORT` | 5433 | Puerto de PostgreSQL (Docker remapea 5432→5433) |
| `STATS_POSTGRES_USER` | stats | Usuario |
| `STATS_POSTGRES_PASSWORD` | stats | Contraseña |
| `STATS_POSTGRES_DB` | stats_app | Base de datos |
| `STATS_REDIS_HOST` | localhost | Host de Redis |
| `STATS_REDIS_PORT` | 6379 | Puerto de Redis |

## CI/CD

El pipeline en `.github/workflows/ci.yml` valida:

- **Web:** lint, test y build de Next.js
- **API:** pytest contra FastAPI con servicios PostgreSQL y Redis
- **Contracts:** validación del esquema OpenAPI

## Troubleshooting

**Error: `python` no encontrado**
Instalar Python 3.12 desde https://python.org o `winget install Python.Python.3.12`.

**Error: `eslint.config.mjs` no encontrado al ejecutar lint**
Ejecutar eslint desde el directorio de la app: `npx eslint src` en `apps/web`.

**PostgreSQL o Redis no responden**
Verificar que los contenedores están activos: `docker compose -f infra/docker-compose.yml ps`.

**Conflicto de puertos con PostgreSQL local**
Si tienes PostgreSQL instalado localmente, ocupa el puerto 5432. Docker usa el puerto 5433 del host para evitarlo. Si el error de conexión persiste, detén el servicio local (`net stop postgresql-x64-16`) o ajusta `STATS_POSTGRES_PORT`.

**python.exe del Microsoft Store**
Desactivar los alias de ejecución en Configuración > Aplicaciones > Configuración avanzada > Alias de ejecución de aplicaciones, o usar la ruta completa a Python 3.12.

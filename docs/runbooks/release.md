# Runbook de release y rollback (MVP demo)

Objetivo: promover web, API y worker con una versión común, migraciones seguras
(expand-contract) y rollback comprobable de aplicación, esquema y cola.

## Versión común y artefactos

- Una sola versión `STATS_VERSION` (release) identifica el despliegue; las
  imágenes se etiquetan con el commit: `stats-web:<sha>`, `stats-api:<sha>`,
  `stats-worker:<sha>`.
- `apps/web/package.json`, `apps/api/pyproject.toml` y `apps/worker/pyproject.toml`
  declaran `0.1.0`; el release coordina las tres con la misma etiqueta.

## Promoción (expand → deploy → contract)

1. **Expand**: publicar la migración que SOLO añade columnas/tablas opcionales
   (`alembic upgrade head` es idempotente; se ejecuta antes del deploy de apps).
2. **Deploy**: levantar las nuevas imágenes (web, API, worker) sin cambiar
   contratos antiguos que sigan en ejecución.
3. **Contract**: una vez verificadas las apps, eliminar código/migración que
   dependa del estado anterior.

## Comandos de staging

```bash
# Construir imágenes
docker build -f apps/api/Dockerfile    -t stats-api:<sha> .
docker build -f apps/worker/Dockerfile -t stats-worker:<sha> .
docker build -f apps/web/Dockerfile --build-arg STATS_API_URL=http://api:8000 -t stats-web:<sha> .

# Desplegar coordinado (migración + seed + smoke al final)
docker compose -f infra/docker-compose.staging.yml up --build --abort-on-container-exit

# Solo infraestructura
docker compose -f infra/docker-compose.yml up -d
```

## Checklist de release

| Paso | Acción | Responsable |
|------|--------|-------------|
| 1 | `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` en verde | Autor |
| 2 | `pytest tests -v` en el API (PostgreSQL/Redis locales) | Autor |
| 3 | `npm run test:e2e -w @stats/web` (Playwright, stack integrado) | Autor |
| 4 | Backup de PostgreSQL antes de migrar (`pg_dump`) | Operador |
| 5 | Backup de Redis (`redis-cli --rdb` / snapshot) | Operador |
| 6 | Migraciones expand en staging (`migrate` + `seed`) | Operador |
| 7 | Smoke test de staging (`infra/smoke/smoke.sh`) | Operador |
| 8 | Registrar versión + sha en el release | Operador |

## Rollback

### Aplicación
- Revertir la etiqueta de imagen a la versión anterior (`stats-*:<prev-sha>`)
  y redeployar. El esquema expandido sigue siendo compatible.

### Esquema (migración)
- Las migraciones son idempotentes y aditivas. Si una migración falla a mitad,
  se corrige y se re-ejecuta (`alembic upgrade head`).
- Un downgrade real se hace SOLO con una migración nueva que revierta (nunca
  borrar tablas con datos en producción); el demo usa expand-contract.

### Cola
- Los trabajos viven durables en PostgreSQL (`job_runs`); vaciar Redis
  (`redis-cli flushdb`) NO pierde historia (ADR-003).
- Si el worker quedó atrás en una entrega duplicada, el runner es idempotente:
  re-enviar el mismo `idempotency_key` no duplica efectos.
- Para drenar la DLQ: usar `QueueBroker.drain_dlq()` o re-encolar manualmente
  con la misma clave.

## Observabilidad para el diagnóstico

- Cada request lleva `X-Correlation-Id`; los logs son JSON con `service`,
  `release`, `correlation_id` y `job_id`.
- Métricas operativas en `/api/v1/ops/metrics` (latencia, errores, backlog,
  retry, DLQ, frescura de cuotas).

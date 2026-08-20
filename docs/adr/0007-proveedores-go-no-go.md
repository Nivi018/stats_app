# ADR-007: Spike de proveedores de datos y decisión go/no-go

- **Estado:** Aceptado
- **Fecha:** 2026-08-14
- **Sprint:** 5 | Operación y release MVP
- **Tipo:** Spike

## Contexto

El MVP usa datos demo reproducibles. Para la fase post-MVP se necesita una API
real con (a) estadísticas de equipos/partidos para el FeatureSet Poisson y (b)
cuotas Over/Under de múltiples casas para el mercado y CLV. Evaluamos los
proveedores más probables y dejamos constancia de la decisión.

## Criterios

- Cobertura de Liga MX (partidos, marcadores, estadísticas).
- Cuotas prepartido Over/Under 2.5 (varias casas cuando sea posible).
- Coste, límites y licencia de uso.
- Estabilidad de IDs (league/team/season) y capacidad de backfill histórico.

## Matriz de evaluación (al 2026-08-14)

| Criterio | API-Football (API Sports) | The Odds API | Football-Data.org |
|----------|---------------------------|--------------|-------------------|
| Estadísticas/features | Sí (fixtures, lineups, stats, standings, jugadores) | No (solo scores/results v4) | Parcial (competitions/matches; stats limitadas) |
| Cuotas Over/Under | Sí (mercados de betting incl. totals) | Sí (totals de múltiples bookmakers) | No (sin cuotas) |
| Cobertura Liga MX | Alta (competición mexicana completa) | Presente en soccer (regiones MX), cubre mercados | Liga MX disponible en plan superior |
| Límites free | 100 req/día (trial 7 días) | 500 créditos/mes | 10 req/min, 50/día (plan 0) |
| Coste (pago) | Desde ~25 USD/mes | Desde 30 USD/mes (20K créditos) | Desde ~8-80 USD/mes según plan |
| Histórico/backfill | Profundo por competición/temporada | Cuotas históricas desde 2020 | Resultados históricos limitados |
| IDs estables | Sí (league/team/season/fixture) | `sport_key` + IDs de eventos | Sí (competition/team/match) |
| Formato/auth | REST + clave de API | REST + clave de API | REST + token |

> Nota: API-Football y Football-Data.org bloquean el scraping automatizado de
> sus sitios; los precios exactos deben confirmarse en el dashboard antes de
> contratar. The Odds API fue verificado directamente en the-odds-api.com.

## Fallos y límites simulados

Ambos proveedores exponen límites por clave (requests por día/mes). La
arquitectura actual ya aísla esto: los adaptadores (`app/providers/*`) cumplen
puertos canónicos y la ingesta es asíncrona e idempotente, por lo que un
proveedor con rate-limit solo retrasa la cola sin duplicar datos. La política de
snapshots y CLV ya contempla opening/closing y consenso por fuente.

## Decisión go/no-go

- **GO** para **API-Football** como proveedor primario post-MVP (cubre
  estadísticas + cuotas + Liga MX en una sola fuente).
- **NO-GO** para integrarlo en el MVP: el producto demo se libera sin
  dependencia externa (costo/rate-limit cero, datos reproducibles).
- **Futuro**: The Odds API como fuente complementaria de cuotas multi-casa para
  CLV cuando el MVP pase a producción.

## Consecuencias

- El MVP demo se mantiene independiente de proveedores (no hay credenciales ni
  costos).
- La capa de adaptadores (`DemoSportsDataProvider`, `DemoOddsProvider`) es el
  punto único de sustitución por API-Football.
- Se agrega una tarea post-MVP: adaptador API-Football + backfill de una
  temporada con la política de snapshots existente.

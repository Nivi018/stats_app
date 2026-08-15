# ADR-006: Backtesting walk-forward determinista y política de promoción

- **Estado:** Aceptado
- **Fecha:** 2026-08-14
- **Sprint:** 4 | Parlays, historial y evaluación

## Contexto

Para verificar desempeño histórico de las versiones del modelo fuera de
muestra necesitamos un método reproducible que compare candidatos contra
baselines y decida cuándo promover (candidate → shadow → active) o revertir
una versión. La evaluación no puede usar el mismo partido que entrena el
modelo (lookahead) ni el último bloque cronológico para decidir promociones.

## Decisión

1. **Split walk-forward determinista** en `app/backtest/walk_forward.py`:
   partidos ordenados por `kickoff_at` (desempate por `external_id`), bloques
   contiguos con ventana expandida. Cada pliegue usa SOLO partidos anteriores
   como entrenamiento y predice un bloque posterior. El último bloque es el
   **holdout final** y no participa en promoción.

2. **Baselines** en `app/backtest/baselines.py`:
   - **Mercado**: probabilidad no-vig del par de cuotas prepartido.
   - **Frecuencia de liga**: tasa de Over del bloque de entrenamiento.
   - **Poisson**: `FeatureSet` evaluado en el kickoff del partido (sin datos
     futuros) + baseline Poisson existente.

3. **Métricas** reutilizan `app/evaluation/metrics.py` (US5): Brier,
   calibración por bin, acierto, ROI unitario y muestra; se reportan por
   pliegue, overall, out-of-sample y holdout final.

4. **Política de promoción** en `app/backtest/promotion.py`:
   - Muestra mínima (20) antes de promocionar.
   - Sin baseline activo → la primera versión con muestra suficiente se
     promueve.
   - Mejora de Brier ≥ 0.02 sobre el activo → active; si no, se queda en shadow.
   - Rollback a candidate si el Brier activo se degrada ≥ 0.05.
   - El holdout final nunca decide promociones.

5. **CLI** `python -m app.backtest.run --folds N [--out reporte.json]`:
   siembra, corre el backtest, aplica la política sobre la versión Poisson
   (`model_versions.status`), registra parámetros del backtest y emite el
   reporte JSON.

## Consecuencias

- Reportes comparables entre ejecuciones (determinismo).
- El dataset demo ahora genera cuotas prepartido para partidos históricos,
  necesarias para el baseline de mercado.
- La cobertura se reporta por baseline; faltantes (datos incompletos o
  muestra insuficiente) reducen la cobertura sin falsear métricas.
- La promoción queda trazable: versión, semilla, split y métricas en
  `model_versions.parameters`.

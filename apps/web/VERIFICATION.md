# Cómo confiar en el modelo (y cómo no)

Esta guía explica qué significan las métricas de Stats App y cómo verificar por
cuenta propia que una predicción merece la pena — sin caer en la falacia de que
"acertó ayer, acierta mañana".

## 1. La salida real es una probabilidad, no un resultado

Una predicción "Over 2.5 al 60%" significa "el modelo estima un 60% de que
haya más de 2.5 goles". No es un resultado garantizado. Para decidir, mira:

- **Probabilidad del modelo** vs **probabilidad implícita del mercado**
  (`1/cuota` sin margen).
- **Edge** (modelo − mercado, en puntos porcentuales) y **EV** (probabilidad ×
  cuota − 1). Con EV ≤ 0 no hay ventaja sobre el precio.

## 2. Calibración: ¿el modelo acierta al ritmo que predice?

En **Historial y métricas** mira la tabla de calibración por bin:

| Probabilidad predicha | Si el modelo está bien calibrado… |
|-----------------------|-----------------------------------|
| 40–50% | acierta ~45–50% de las veces |
| 55–60% | acierta ~55–60% de las veces |

Si la frecuencia observada se aleja mucho de la predicción, el modelo no está
bien calibrado aunque el Brier sea "bajo".

## 3. Muestra: el tamaño importa

- Una **muestra insuficiente** (< 30 resoluciones) hace que métricas como ROI,
  Brier o acierto no sean concluyentes. La UI lo avisa con un recuadro.
- No confíes en un ROI de +40% con 10 resultados: es ruido.

## 4. Backtesting walk-forward (ver /backtest)

El reporte usa un split cronológico: entrena con el pasado y mide con el
futuro, sin datos futuros filtrados (sin lookahead).

- **Brier**: menor es mejor; 0 = perfecto, 0.25 = predecir siempre 50%.
- **ROI unitario**: retorno por unidad apostada (una apuesta = 1 unidad).
- **Cobertura**: qué fracción de partidos pudo predecir el baseline.
- **Final hold out**: NO participa en la promoción del modelo; es la verificación
  final.

## 5. Riesgo y calidad NO son probabilidad de acierto

- **Riesgo** = muestra y volatilidad de los datos.
- **Calidad de datos** = cobertura, completitud, frescura, coherencia.
- Ninguno de los dos es "probabilidad de que gane". La app los muestra por
  separado para no confundirlos con la probabilidad del modelo.

## 6. Confianza (Sprint 6)

La "confianza" combina decisión + calidad + frescura. **No es exactitud**:
una predicción con confianza alta puede fallar.

## 7. Verificación técnica y soporte

- Cada error de la UI muestra un **ID de correlación** (X-Correlation-Id) para
  soporte.
- Logs JSON con `service`, `release`, `correlation_id` y `job_id`.
- Métricas operativas en `/api/v1/ops/metrics`.

## Resultado

Una predicción es **útil** cuando: EV > 0, calidad ≥ media, cuota fresca y el
modelo está razonablemente calibrado con muestra suficiente. Si alguna pieza
falta, la app lo dice — y esa es exactamente la manera de confiar.
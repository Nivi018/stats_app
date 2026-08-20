# Roadmap post-MVP (visión, no compromiso)

Este documento conserva la visión de expansión del producto. **Ninguna
capacidad futura aquí descrita forma parte del MVP demo** salvo que se indique.
Cada fase tiene entrada (qué se necesita antes), salida (qué se entrega) y una
puerta de decisión (criterio para avanzar). Lo que no está comprometido se
marca como explícitamente fuera de alcance.

## MVP (entregado, Sprint 5)

Mercado Over/Under 2.5 prepartido, Liga MX, datos demo reproducibles, motor
Poisson trazable, scanner con señales, parlay responsable, evaluación con
backtesting, operación con observabilidad y despliegue coordinado.

## Fase A — Datos reales (API-Football)

- **Entrada**: ADR-007 go (aceptado), suscripción de prueba, adaptador
  `SportsDataProvider` para API-Football, backfill de una temporada.
- **Salida**: jornadas, marcadores y estadísticas reales de Liga MX.
- **Puerta**: contrato de la API validado en staging; snapshot real coincide
  con el modelo de `odds_snapshots`; coste/límites documentados.

## Fase B — CLV y cuotas multi-casa

- **Entrada**: datos reales de una temporada; The Odds API como fuente
  complementaria (ADR-007).
- **Salida**: CLV por selección, comparación de consenso por fuente y reporte
  de calidad de línea.
- **Puerta**: el CLV medio es negativo o cercano a cero en demo; sin señales
  engañosas.

## Fase C — Más mercados y modalidades

- **Entrada**: motor de probabilidades por marcador estable (Poisson u otro).
- **Salida**: 1X2, hándicap y totales por equipo con la misma trazabilidad.
- **Puerta**: cada mercado expone edge, EV, calidad y riesgo por separado.

## Fase D — Datos live

- **Entrada**: contratos y límites verificados; arquitectura de snapshots en
  ventana corta.
- **Salida**: cuotas y marcadores live con degradación explícita.
- **Puerta**: latencia y frescura dentro del objetivo; el producto no depende
  de datos live.

## Fase E — Contexto y modelos avanzados

- **Entrada**: histórico real acumulado (≥ 2 temporadas).
- **Salida**: features de contexto (lesiones, calendario, clima), modelos
  candidatos frente a Poisson con backtesting walk-forward.
- **Puerta**: el candidato supera al baseline activo fuera de muestra y es
  promovido por la política candidate→shadow→active.

## Fase F — Asistentes e IA

- **Entrada**: modelo promovido y datos confiables.
- **Salida**: resúmenes e interpretación asistida de señales, siempre con
  evidencia trazable y sin garantías.
- **Puerta**: el texto asistido cita métricas y jamás promete resultados.

## Fase G — Más ligas y deportes

- **Entrada**: modelo generalizable y contratos por competición.
- **Salida**: ampliación de cobertura (otras ligas, deportes).
- **Puerta**: expansión explícita y versionada; la cobertura nueva no degrada
  la calidad mínima.

## Fuera de alcance (no comprometido)

- Aceptar apuestas, dinero o cuentas de casas de apuestas.
- Garantías o consejos de inversión.
- Datos live como fuente única en el MVP.
- Rendimiento predictivo garantizado.

## Revisión de release

Antes de cada release se revisa que **ninguna historia futura del backlog haya
ampliado accidentalmente el MVP**: cualquier funcionalidad que no esté marcada
como parte del MVP se mantiene tras su puerta de decisión.

# Accesibilidad (WCAG 2.2 AA)

## Objetivo

Todos los flujos críticos del MVP cumplen WCAG 2.2 AA y son utilizables con
teclado desde pantallas de 360 px.

## Auditoría automatizada

La auditoría corre con **axe-core** dentro de Playwright (`e2e/a11y.spec.ts`)
sobre los flujos críticos, en viewport de escritorio y móvil:

- `/` (dashboard de jornada)
- `/scanner` (oportunidades)
- `/matches/{id}` (detalle de partido)
- `/parlay` (constructor)
- `/history` (historial y métricas)

La prueba falla ante cualquier violación de impacto `critical` o `serious`.

## Medidas aplicadas

- Skip link "Saltar al contenido" en el layout raíz.
- Regiones desplazables (tablas con `overflow-x-auto`) accesibles por teclado
  con `tabIndex=0` y `aria-label`.
- Roles semánticos: `alert` para errores y `status` para avisos (frescura,
  muestra insuficiente).
- Texto además de color: el riesgo y los resultados usan etiquetas textuales,
  no solo color.
- Estados loading/vacío/error accesibles en cada página.
- Navegación por teclado verificada: el skip link y los enlaces/botones reciben
  foco.

## Excepciones documentadas

- No hay contenido multimedia, carruseles ni modales; no aplican criterios
  relacionados.
- Las cifras se muestran con `tabular-nums` y se omiten (`—`) cuando el dato no
  es finito (nunca se renderiza una cifra inválida).
- El anunciador de ruta de Next.js (`#__next-route-announcer__`) aporta
  `role="alert"` adicional; la UI no depende de él.

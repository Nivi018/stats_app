// Medidor de confianza compuesta (US6).
// Confianza = decisión + calidad de datos + frescura; NO es una probabilidad
// de acierto ni una garantía.

export function ConfidenceMeter({
  level,
  score,
  factors = [],
  compact = false,
}: {
  level: string;
  score: number;
  factors?: string[];
  compact?: boolean;
}) {
  const pct = Math.min(100, Math.max(0, score));
  const barClass =
    level === "alta"
      ? "bg-[var(--accent)]"
      : level === "media"
        ? "bg-[#b4891c]"
        : "bg-[var(--muted)]";
  const label = `Confianza ${level}`;

  return (
    <div className="text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold capitalize">{label}</span>
        <span className="tabular-nums text-[var(--muted)]">{Math.round(pct)}/100</span>
      </div>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-valuetext={label}
        aria-label="Confianza de la predicción"
        className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--rule)]"
      >
        <span className={`block h-full rounded-full ${barClass}`} style={{ width: `${pct}%` }} />
      </div>
      {!compact && factors.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-[var(--muted)] underline-offset-2 hover:underline">
            Por qué
          </summary>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-[var(--muted)]">
            {factors.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p className="mt-1 text-[var(--muted)]">
            La confianza no es una garantía de acierto.
          </p>
        </details>
      )}
    </div>
  );
}

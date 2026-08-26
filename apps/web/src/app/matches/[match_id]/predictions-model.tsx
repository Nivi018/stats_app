"use client";

import { useMemo, useState } from "react";
import { ConfidenceMeter } from "@/components/confidence";
import { safeFixed, safePct, type PredictionDto } from "@/lib/api/client";

type MarketGroup = "todos" | "over_under_2_5" | "1x2" | "totales" | "handicap";

const MARKETS: Array<{ id: MarketGroup; label: string }> = [
  { id: "todos", label: "Todos" },
  { id: "over_under_2_5", label: "Over/Under 2.5" },
  { id: "1x2", label: "1X2" },
  { id: "totales", label: "Totales" },
  { id: "handicap", label: "Hándicap" },
];

function selectionLabel(p: PredictionDto): string {
  if (p.market === "over_under_2_5") {
    return p.selection === "over" ? "Over 2.5" : "Under 2.5";
  }
  if (p.market === "1x2") {
    const name = p.selection === "home" ? "Local" : p.selection === "draw" ? "Empate" : "Visitante";
    return `1X2 · ${name}`;
  }
  if (p.market === "home_total" || p.market === "away_total") {
    const team = p.market === "home_total" ? "Casa" : "Visita";
    return `${team} ${p.selection === "over" ? "Over" : "Under"} ${p.line ?? ""}`.trim();
  }
  if (p.market === "handicap_home" || p.market === "handicap_away") {
    const team = p.market === "handicap_home" ? "Casa" : "Visita";
    return `Hándicap -1 · ${p.selection === "cover" ? "Cubre" : "No cubre"} (${team})`;
  }
  return `${p.market} · ${p.selection}`;
}

function matches(p: PredictionDto, group: MarketGroup): boolean {
  if (group === "todos") return true;
  if (group === "totales") return p.market === "home_total" || p.market === "away_total";
  if (group === "handicap") return p.market.startsWith("handicap_");
  return p.market === group;
}

export default function PredictionsModel({ predictions }: { predictions: PredictionDto[] }) {
  const [group, setGroup] = useState<MarketGroup>("todos");
  const filtered = useMemo(() => predictions.filter((p) => matches(p, group)), [predictions, group]);

  if (predictions.length === 0) {
    return <p className="text-sm text-[var(--muted)]">Sin predicción para este partido aún.</p>;
  }

  return (
    <div>
      <div role="group" aria-label="Seleccionar mercado" className="flex flex-wrap gap-2 text-xs">
        {MARKETS.map((m) => {
          const active = group === m.id;
          return (
            <button
              key={m.id}
              type="button"
              aria-pressed={active}
              onClick={() => setGroup(m.id)}
              className={`border px-3 py-1.5 ${
                active
                  ? "border-[var(--foreground)] font-semibold"
                  : "border-[var(--rule)] text-[var(--muted)]"
              }`}
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--muted)]">Sin predicciones en este mercado.</p>
      ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <div key={`${p.market}-${p.selection}-${p.line ?? ""}`} className="border border-[var(--rule)] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                {selectionLabel(p)}
              </p>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-[var(--muted)]">Probabilidad</dt>
                  <dd className="font-medium tabular-nums">{safePct(p.probability)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--muted)]">Cuota justa</dt>
                  <dd className="font-medium tabular-nums">{safeFixed(p.fair_odds, 3)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--muted)]">Calidad</dt>
                  <dd>{p.data_quality}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--muted)]">Riesgo</dt>
                  <dd>{p.risk_level}</dd>
                </div>
              </dl>
              {p.confidence_score != null && p.confidence_level && (
                <div className="mt-4">
                  <ConfidenceMeter
                    level={p.confidence_level}
                    score={p.confidence_score}
                    factors={p.confidence_factors}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
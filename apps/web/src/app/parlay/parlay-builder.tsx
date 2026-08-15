"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  estimateParlay,
  type OpportunityDto,
  type ParlayEstimateDto,
  type ResolvedSelectionDto,
} from "@/lib/api/client";
import {
  PARLAY_MAX,
  PARLAY_MIN,
  addSelection,
  canonicalKey,
  fromKeys,
  hasSelection,
  isFull,
  loadKeys,
  removeSelection,
  replaceSelection,
  saveKeys,
  toKeys,
  type ParlaySelection,
  type ParlayState,
} from "@/lib/parlay/store";

type EstimateState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; estimate: ParlayEstimateDto };

function marketLabel(selection: string): string {
  return selection === "over" ? "Over 2.5" : "Under 2.5";
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function keyOf(op: OpportunityDto): string {
  return canonicalKey(op.match_id, op.market, op.selection);
}

function toRef(selection: ParlaySelection) {
  return { match_id: selection.match_id, market: selection.market, selection: selection.selection };
}

export default function ParlayBuilder({
  opportunities,
}: {
  opportunities: OpportunityDto[];
}) {
  const [ticket, setTicket] = useState<ParlayState>([]);
  const [estimateState, setEstimateState] = useState<EstimateState>({ status: "idle" });
  const [notice, setNotice] = useState<string | null>(null);
  const hydrated = useRef(false);

  function updateTicket(next: ParlayState) {
    setEstimateState(next.length === 0 ? { status: "idle" } : { status: "loading" });
    setTicket(next);
  }

  useEffect(() => {
    if (typeof window === "undefined" || hydrated.current) return;
    hydrated.current = true;
    const keys = loadKeys(window.sessionStorage);
    if (keys.length > 0) {
      // Post-paint: evita mismatch de hidratación y renders en cascada.
      queueMicrotask(() => updateTicket(fromKeys(keys)));
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    saveKeys(toKeys(ticket), window.sessionStorage);

    if (ticket.length === 0) return;

    let cancelled = false;
    estimateParlay(ticket.map(toRef))
      .then((result) => {
        if (cancelled) return;
        setEstimateState({ status: "ready", estimate: result });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setEstimateState({
          status: "error",
          message: e instanceof Error ? e.message : "No se pudo estimar el parlay",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [ticket]);

  const full = isFull(ticket);
  const inTicket = useMemo(
    () => new Set(ticket.map((s) => s.key)),
    [ticket],
  );

  function lowestEdgeKey(): string | null {
    if (estimateState.status !== "ready") return null;
    let min: ResolvedSelectionDto | null = null;
    for (const sel of estimateState.estimate.selections) {
      if (min === null || sel.edge_pp < min.edge_pp) min = sel;
    }
    return min?.key ?? null;
  }

  function handleAdd(op: OpportunityDto) {
    const key = keyOf(op);
    if (hasSelection(ticket, key)) return;

    let next: ParlayState;
    if (isFull(ticket)) {
      const victim = lowestEdgeKey();
      if (victim === null) return;
      const result = replaceSelection(ticket, victim, {
        match_id: op.match_id,
        market: op.market,
        selection: op.selection,
      });
      if (result.result !== "replaced") return;
      next = result.state;
      setNotice(`Ticket lleno: se sustituyó la selección de menor edge (${victim}).`);
    } else {
      const result = addSelection(ticket, {
        match_id: op.match_id,
        market: op.market,
        selection: op.selection,
      });
      if (result.result !== "added") return;
      next = result.state;
      setNotice(null);
    }
    updateTicket(next);
  }

  function handleRemove(key: string) {
    updateTicket(removeSelection(ticket, key));
    setNotice(null);
  }

  const resolvedByKey = useMemo(() => {
    const map = new Map<string, ResolvedSelectionDto>();
    if (estimateState.status === "ready") {
      for (const sel of estimateState.estimate.selections) map.set(sel.key, sel);
    }
    return map;
  }, [estimateState]);

  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_360px]">
      {/* Selecciones disponibles */}
      <section>
        <h2 className="mb-4 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
          SELECCIONES DISPONIBLES
        </h2>
        <p className="mb-4 text-sm text-[var(--muted)]">
          Elige entre 2 y {PARLAY_MAX} selecciones. La cuota y la probabilidad se
          combinan solo si no hay dependencias conocidas; si las hay, se advierte.
        </p>

        {opportunities.length === 0 ? (
          <p className="border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
            No hay oportunidades para añadir. Ejecuta el job de predicciones para poblar el
            constructor.
          </p>
        ) : (
          <ul className="border-t border-[var(--rule)]">
            {opportunities.map((op) => {
              const key = keyOf(op);
              const added = inTicket.has(key);
              return (
                <li
                  key={key}
                  className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rule)] py-4 text-sm"
                >
                  <div>
                    <p className="font-semibold">
                      {op.home_team_short} – {op.away_team_short}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">
                      {marketLabel(op.selection)} · Cuota {op.observed_odds.toFixed(2)} · P modelo{" "}
                      {pct(op.model_probability)}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={added}
                    aria-disabled={added}
                    onClick={() => handleAdd(op)}
                    className="border border-[var(--foreground)] px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:border-[var(--rule)] disabled:text-[var(--muted)]"
                  >
                    {added ? "En el ticket" : full ? "Sustituir" : "Añadir"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Ticket */}
      <aside>
        <h2 className="mb-4 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
          TU PARLAY
        </h2>

        {ticket.length === 0 ? (
          <p className="border border-[var(--rule)] p-4 text-sm text-[var(--muted)]">
            Aún no hay selecciones. Añade al menos {PARLAY_MIN} para ver la estimación.
          </p>
        ) : (
          <div className="border border-[var(--rule)]">
            <ul>
              {ticket.map((selection) => {
                const resolved = resolvedByKey.get(selection.key);
                return (
                  <li
                    key={selection.key}
                    className="flex items-start justify-between gap-3 border-b border-[var(--rule)] p-4 text-sm"
                  >
                    <div>
                      <p className="font-semibold">
                        {resolved
                          ? `${resolved.home_team_short} – ${resolved.away_team_short}`
                          : selection.match_id}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--muted)]">
                        {marketLabel(selection.selection)}
                        {resolved ? ` · Cuota ${resolved.odds.toFixed(2)}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemove(selection.key)}
                      aria-label={`Quitar ${selection.match_id} ${selection.selection}`}
                      className="text-xs font-semibold underline"
                    >
                      Quitar
                    </button>
                  </li>
                );
              })}
            </ul>

            <div aria-live="polite" className="p-4">
              {notice && <p className="mb-3 text-xs text-[var(--muted)]">{notice}</p>}

              {ticket.length < PARLAY_MIN ? (
                <p className="text-sm text-[var(--muted)]">
                  Necesitas al menos {PARLAY_MIN} selecciones para formar un parlay
                  (máximo {PARLAY_MAX}).
                </p>
              ) : estimateState.status === "loading" ? (
                <p className="text-sm text-[var(--muted)]">Estimando…</p>
              ) : estimateState.status === "error" ? (
                <p role="alert" className="text-sm text-red-800">
                  {estimateState.message}
                </p>
              ) : estimateState.status === "ready" ? (
                <EstimatePanel estimate={estimateState.estimate} />
              ) : null}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function EstimatePanel({ estimate }: { estimate: ParlayEstimateDto }) {
  const viable = estimate.estimated_probability > 0;
  return (
    <div>
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Cuota combinada</dt>
          <dd className="font-semibold tabular-nums">{estimate.combined_odds.toFixed(2)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Prob. estimada</dt>
          <dd className="font-medium tabular-nums">
            {viable ? pct(estimate.estimated_probability) : "No viable"}
          </dd>
        </div>
        {estimate.fair_combined_odds != null && (
          <div className="flex justify-between">
            <dt className="text-[var(--muted)]">Cuota justa</dt>
            <dd className="font-medium tabular-nums">{estimate.fair_combined_odds.toFixed(2)}</dd>
          </div>
        )}
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Riesgo agregado</dt>
          <dd className="font-semibold capitalize">{estimate.risk_level}</dd>
        </div>
      </dl>

      {estimate.correlation_warnings.length > 0 && (
        <div role="alert" className="mt-4 border border-yellow-300 bg-yellow-50 p-3 text-xs text-yellow-900">
          <p className="font-semibold">Advertencia de correlación</p>
          <ul className="mt-2 list-inside list-disc space-y-1">
            {estimate.correlation_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {estimate.assumes_independence && (
        <p className="mt-3 text-xs text-[var(--muted)]">
          La probabilidad combinada asume independencia entre selecciones con equipos
          compartidos; esto puede sobreestimar el resultado.
        </p>
      )}

      <p className="mt-3 text-xs text-[var(--muted)]">
        Las probabilidades son estimaciones, no garantías. La cuota combinada multiplica las
        cuotas observadas; el riesgo y la calidad de datos no predicen el acierto.
      </p>

      {estimate.risk_factors.length > 0 && (
        <div className="mt-4 border-t border-[var(--rule)] pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Factores de riesgo
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-xs">
            {estimate.risk_factors.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { ErrorAlert } from "@/components/error-alert";
import { errorCorrelationId, fetchOpportunities, type OpportunityDto, type OpportunityFilters } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Scanner de oportunidades | Stats App",
  description: "Oportunidades Over/Under 2.5 con filtros y orden.",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function buildFilters(sp: Awaited<SearchParams>): OpportunityFilters {
  const filters: OpportunityFilters = {};
  const minEdge = first(sp.min_edge);
  const risk = first(sp.risk);
  const matchday = first(sp.matchday);
  const sort = first(sp.sort);

  if (minEdge != null && minEdge !== "" && !Number.isNaN(Number(minEdge))) filters.minEdge = Number(minEdge);
  if (risk === "low" || risk === "medium" || risk === "high") filters.risk = risk;
  if (matchday != null && matchday !== "" && !Number.isNaN(Number(matchday))) filters.matchday = Number(matchday);
  if (sort === "ev" || sort === "probability" || sort === "edge") filters.sort = sort;
  return filters;
}

function signalLabel(op: OpportunityDto): string {
  if (op.is_signal) return "Señal";
  if (op.signal_exclusions.length > 0) return "Bajo umbral";
  return "—";
}

function fieldSet(label: string, value: string | undefined): boolean {
  return value != null && value !== "";
}

export default async function ScannerPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const filters = buildFilters(sp);
  const rawMinEdge = first(sp.min_edge);
  const rawRisk = first(sp.risk);
  const rawMatchday = first(sp.matchday);
  const activeFilters = fieldSet("edge", rawMinEdge) || fieldSet("riesgo", rawRisk) || fieldSet("jornada", rawMatchday);

  let opportunities: OpportunityDto[] = [];
  let error: string | null = null;
  let correlationId: string | null = null;

  try {
    opportunities = await fetchOpportunities(filters);
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
    correlationId = errorCorrelationId(e);
  }

  const currentSort = filters.sort ?? "edge";
  const maxSnapshotAge = opportunities.length > 0 ? Math.max(...opportunities.map((o) => o.snapshot_age_minutes)) : 0;
  const stale = !error && opportunities.length > 0 && maxSnapshotAge > 30;

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / SCANNER</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Oportunidades</h1>
        </div>
        <div className="flex gap-4 text-sm">
          <Link href="/parlay" className="text-[var(--muted)] underline">
            Parlay
          </Link>
          <Link href="/" className="text-[var(--muted)] underline">
            Jornada
          </Link>
        </div>
      </header>

      {/* Filtros: el estado vive en la URL */}
      <section className="mx-auto mt-8 max-w-6xl border-b border-[var(--rule)] pb-5">
        <form method="get" className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
            Edge mín (pp)
            <input
              type="number"
              name="min_edge"
              defaultValue={first(sp.min_edge) ?? ""}
              step="0.5"
              min={-100}
              max={100}
              className="w-24 border border-[var(--rule)] bg-white px-2 py-1.5 text-sm text-[var(--foreground)]"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
            Riesgo
            <select name="risk" defaultValue={first(sp.risk) ?? ""} className="border border-[var(--rule)] bg-white px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              <option value="low">Bajo</option>
              <option value="medium">Medio</option>
              <option value="high">Alto</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
            Jornada
            <input
              type="number"
              name="matchday"
              defaultValue={first(sp.matchday) ?? ""}
              min={1}
              className="w-20 border border-[var(--rule)] bg-white px-2 py-1.5 text-sm text-[var(--foreground)]"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
            Orden
            <select name="sort" defaultValue={currentSort} className="border border-[var(--rule)] bg-white px-2 py-1.5 text-sm">
              <option value="edge">Edge</option>
              <option value="ev">EV</option>
              <option value="probability">Probabilidad</option>
            </select>
          </label>
          <button type="submit" className="border border-[var(--foreground)] px-4 py-1.5 text-sm font-semibold">
            Aplicar
          </button>
          {activeFilters && (
            <Link href="/scanner" className="text-xs text-[var(--muted)] underline">
              Limpiar filtros
            </Link>
          )}
        </form>
      </section>

      {error && (
        <div className="mx-auto mt-8 max-w-6xl">
          <ErrorAlert
            title="No se pudieron cargar las oportunidades"
            message={error}
            correlationId={correlationId}
            hint={
              <>
                Ejecuta <code>npm run dev:api</code> y el worker de predicciones (
                <code>compute_prediction</code>) para ver señales.
              </>
            }
          />
        </div>
      )}

      {stale && (
        <div role="status" className="mx-auto mt-8 max-w-6xl border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900">
          Algunas cuotas tienen más de 30 minutos de antigüedad. La información puede estar desactualizada.
        </div>
      )}

      {!error && opportunities.length === 0 && (
        <div className="mx-auto mt-10 max-w-6xl border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
          {activeFilters
            ? "Ninguna oportunidad cumple los filtros seleccionados. Ajusta el edge mínimo o el nivel de riesgo."
            : "No hay oportunidades aún. Ejecuta el job compute_prediction para cada partido."}
        </div>
      )}

      {!error && opportunities.length > 0 && (
        <section className="mx-auto mt-10 max-w-6xl">
          <div className="overflow-x-auto border-t border-[var(--rule)]">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                  <th scope="col" className="py-3 pr-4 font-semibold">Partido</th>
                  <th scope="col" className="py-3 pr-4 font-semibold">Mercado</th>
                  <th scope="col" className="py-3 pr-4 font-semibold text-right">P. modelo</th>
                  <th scope="col" className="py-3 pr-4 font-semibold text-right">Cuota</th>
                  <th scope="col" className="py-3 pr-4 font-semibold text-right">Edge</th>
                  <th scope="col" className="py-3 pr-4 font-semibold text-right">EV</th>
                  <th scope="col" className="py-3 pr-4 font-semibold">Calidad</th>
                  <th scope="col" className="py-3 pr-4 font-semibold">Riesgo</th>
                  <th scope="col" className="py-3 font-semibold">Estado</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((op) => (
                  <tr key={`${op.match_id}-${op.selection}`} className="border-b border-[var(--rule)]">
                    <td className="py-3 pr-4 font-semibold">
                      <Link href={`/matches/${op.match_id}`} className="underline decoration-[var(--rule)] underline-offset-2 hover:decoration-[var(--foreground)]">
                        {op.home_team_short} – {op.away_team_short}
                      </Link>
                    </td>
                    <td className="py-3 pr-4">
                      {op.selection === "over" ? "Over 2.5" : "Under 2.5"}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">
                      {(op.model_probability * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">{op.observed_odds.toFixed(2)}</td>
                    <td className="py-3 pr-4 text-right font-medium tabular-nums">
                      {op.edge_pp > 0 ? "+" : ""}
                      {op.edge_pp.toFixed(1)}
                    </td>
                    <td className="py-3 pr-4 text-right tabular-nums">{op.ev.toFixed(3)}</td>
                    <td className="py-3 pr-4">{op.data_quality}</td>
                    <td className="py-3 pr-4">
                      <span className="inline-flex items-center gap-1.5" title={`Riesgo ${op.risk_level}`}>
                        <span
                          className="inline-block h-2 w-2 rounded-full"
                          style={{
                            background:
                              op.risk_level === "high"
                                ? "var(--foreground)"
                                : op.risk_level === "medium"
                                  ? "#b4891c"
                                  : "var(--accent)",
                          }}
                        />
                        {op.risk_level}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={op.is_signal ? "font-semibold text-[var(--accent)]" : "text-[var(--muted)]"}>
                        {signalLabel(op)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-[var(--muted)]">
            Señal: edge ≥ 5pp, EV &gt; 0, calidad ≥ media y cuota fresca (≤ 30 min).
          </p>
        </section>
      )}
    </main>
  );
}

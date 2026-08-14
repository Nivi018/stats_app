import type { Metadata } from "next";
import Link from "next/link";
import { fetchOpportunities, type OpportunityDto } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Scanner de oportunidades | Stats App",
  description: "Oportunidades Over/Under 2.5 ordenadas por edge y EV.",
};

function signalLabel(op: OpportunityDto): string {
  if (op.is_signal) return "Señal";
  if (op.signal_exclusions.length > 0) return "Bajo umbral";
  return "—";
}

export default async function ScannerPage() {
  let opportunities: OpportunityDto[] = [];
  let error: string | null = null;

  try {
    opportunities = await fetchOpportunities();
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / SCANNER</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Oportunidades</h1>
        </div>
        <Link href="/" className="text-sm text-[var(--muted)] underline">
          Jornada
        </Link>
      </header>

      {error && (
        <div role="alert" className="mx-auto mt-8 max-w-6xl border border-red-300 bg-red-50 p-5 text-sm text-red-800">
          <p className="font-semibold">No se pudieron cargar las oportunidades</p>
          <p className="mt-1">{error}</p>
          <p className="mt-2 text-xs">
            Ejecuta <code>npm run dev:api</code> y el worker de predicciones (
            <code>compute_prediction</code>) para ver señales.
          </p>
        </div>
      )}

      {!error && opportunities.length === 0 && (
        <div className="mx-auto mt-10 max-w-6xl border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
          No hay oportunidades aún. Ejecuta el job <code>compute_prediction</code> para cada partido.
        </div>
      )}

      {!error && opportunities.length > 0 && (
        <section className="mx-auto mt-10 max-w-6xl">
          <div className="overflow-x-auto border-t border-[var(--rule)]">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                  <th className="py-3 pr-4 font-semibold">Partido</th>
                  <th className="py-3 pr-4 font-semibold">Mercado</th>
                  <th className="py-3 pr-4 font-semibold text-right">P. modelo</th>
                  <th className="py-3 pr-4 font-semibold text-right">Cuota</th>
                  <th className="py-3 pr-4 font-semibold text-right">Edge</th>
                  <th className="py-3 pr-4 font-semibold text-right">EV</th>
                  <th className="py-3 pr-4 font-semibold">Calidad</th>
                  <th className="py-3 pr-4 font-semibold">Riesgo</th>
                  <th className="py-3 font-semibold">Estado</th>
                </tr>
              </thead>
              <tbody>
                {opportunities.map((op) => (
                  <tr key={`${op.match_id}-${op.selection}`} className="border-b border-[var(--rule)]">
                    <td className="py-3 pr-4 font-semibold">
                      {op.home_team_short} – {op.away_team_short}
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
                      <span
                        className="inline-flex items-center gap-1.5"
                        title={`Riesgo ${op.risk_level}`}
                      >
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
                      <span
                        className={
                          op.is_signal
                            ? "font-semibold text-[var(--accent)]"
                            : "text-[var(--muted)]"
                        }
                      >
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

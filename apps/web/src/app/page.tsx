import Link from "next/link";
import { ConfidenceMeter } from "@/components/confidence";
import { ErrorAlert } from "@/components/error-alert";
import {
  errorCorrelationId,
  fetchFeaturedSignals,
  fetchMatchday,
  type MatchDto,
  type OpportunityDto,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

function isStale(updatedAt: string, maxAgeMs = 30 * 60 * 1000): boolean {
  const age = Date.now() - new Date(updatedAt).getTime();
  return age > maxAgeMs;
}

function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleDateString("es-MX", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function OddsBadge({ match }: { match: MatchDto }) {
  if (match.over_odds != null && match.under_odds != null) {
    return (
      <span className="text-xs text-[var(--muted)]">
        <span>O {match.over_odds.toFixed(2)}</span>
        <span className="mx-2">·</span>
        <span>U {match.under_odds.toFixed(2)}</span>
      </span>
    );
  }
  return <span className="text-xs text-[var(--muted)]">Sin cuotas</span>;
}

export default async function Home() {
  let matchday;
  let error: string | null = null;
  let correlationId: string | null = null;

  let signals: OpportunityDto[] = [];
  let signalsError: string | null = null;

  try {
    matchday = await fetchMatchday();
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
    correlationId = errorCorrelationId(e);
  }

  try {
    signals = await fetchFeaturedSignals(3);
  } catch (e) {
    signalsError = e instanceof Error ? e.message : "No se pudieron cargar las señales";
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / MVP</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Mesa de inteligencia</h1>
        </div>
        <p className="text-sm text-[var(--muted)]">Liga MX · FastAPI</p>
      </header>

      <section className="mx-auto grid max-w-6xl gap-10 py-10 lg:grid-cols-[220px_1fr]">
        <aside className="border-t-2 border-[var(--foreground)] pt-4">
          <p className="text-sm font-semibold">Sprint 3</p>
          <p className="mt-1 text-sm text-[var(--muted)]">End-to-end vía API</p>
          <dl className="mt-8 space-y-5 text-sm">
            <div>
              <dt className="text-[var(--muted)]">Jornada</dt>
              <dd className="mt-1 font-medium">{matchday?.matchday ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Partidos</dt>
              <dd className="mt-1 font-medium">{matchday?.total_matches ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Actualizado</dt>
              <dd className="mt-1 font-medium">
                {matchday ? new Date(matchday.updated_at).toLocaleTimeString("es-MX") : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Mercado</dt>
              <dd className="mt-1 font-medium">Over/Under 2.5</dd>
            </div>
          </dl>
        </aside>

        <div>
          <p className="max-w-3xl text-xl leading-8">
            La jornada se sirve desde FastAPI/PostgreSQL. Cada partido muestra las cuotas
            Over/Under 2.5 del snapshot vigente.
          </p>

          {error && (
            <ErrorAlert
              className="mt-8"
              title="No se pudo cargar la jornada"
              message={error}
              correlationId={correlationId}
              hint={
                <>
                  Verifica que el API esté corriendo (<code>npm run dev:api</code>) o el estado de
                  PostgreSQL/Redis (<code>npm run infra:up</code>).
                </>
              }
            />
          )}

          {!error && matchday && isStale(matchday.updated_at) && (
            <div
              role="status"
              className="mt-8 border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900"
            >
              Los datos tienen más de 30 minutos. La información puede estar desactualizada.
            </div>
          )}

          {!error && matchday && (
            <div className="mt-10">
              <h2 className="mb-4 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
                PRÓXIMA JORNADA
              </h2>
              {matchday.matches.length === 0 ? (
                <div className="border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
                  No hay partidos en esta jornada.
                </div>
              ) : (
                <div className="border-t border-[var(--rule)]">
                  {matchday.matches.map((match) => (
                    <div
                      key={match.id}
                      className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-[var(--rule)] py-4 text-sm"
                    >
                      <div>
                        <p className="font-semibold">
                          {match.home_team.short_name} – {match.away_team.short_name}
                        </p>
                        <p className="mt-0.5 text-xs text-[var(--muted)]">
                          {formatKickoff(match.kickoff_at)}
                        </p>
                      </div>
                      <OddsBadge match={match} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      <section aria-label="Señales destacadas" className="mx-auto mt-2 max-w-6xl pb-10">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">
            SEÑALES DESTACADAS
          </h2>
          <Link href="/scanner" className="text-xs text-[var(--muted)] underline">
            Ver todas
          </Link>
        </div>

        {signalsError ? (
          <p role="status" className="mt-3 text-sm text-[var(--muted)]">
            No se pudieron cargar las señales destacadas.
          </p>
        ) : signals.length === 0 ? (
          <p className="mt-3 border-t border-[var(--rule)] py-6 text-sm text-[var(--muted)]">
            Aún no hay señales destacadas. Ejecuta el worker de predicciones para generarlas.
          </p>
        ) : (
          <ul className="mt-3 border-t border-[var(--rule)]">
            {signals.map((signal) => (
              <li
                key={`${signal.match_id}-${signal.selection}`}
                className="grid gap-3 border-b border-[var(--rule)] py-4 text-sm sm:grid-cols-[1fr_auto] sm:items-center"
              >
                <div>
                  <p className="font-semibold">
                    <Link href={`/matches/${signal.match_id}`} className="underline decoration-[var(--rule)] underline-offset-2 hover:decoration-[var(--foreground)]">
                      {signal.home_team_short} – {signal.away_team_short}
                    </Link>
                    <span className="ml-2 text-xs text-[var(--muted)]">
                      {signal.selection === "over" ? "Over 2.5" : "Under 2.5"}
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">
                    Edge +{signal.edge_pp.toFixed(1)}pp · EV {signal.ev.toFixed(3)} · cuota{" "}
                    {signal.observed_odds.toFixed(2)}
                  </p>
                </div>
                <div className="max-w-[220px] sm:w-[220px]">
                  <ConfidenceMeter
                    level={signal.confidence_level}
                    score={signal.confidence_score}
                    factors={signal.confidence_factors}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-[var(--muted)]">
          Las señales destacadas son las de mayor edge según la política del producto; son
          evidencia trazable, no una garantía de resultado.
        </p>
      </section>
    </main>
  );
}

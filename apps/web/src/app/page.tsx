import { DemoOddsProvider, DemoSportsDataProvider } from "@/lib/data/demo-providers";
import type { Match } from "@/lib/domain/providers";

const sports = new DemoSportsDataProvider();
const odds = new DemoOddsProvider();

async function ScannedMatch({ match }: { match: Match }) {
  const snapshots = await odds.getOddsSnapshots(match.id);
  const overOdds = snapshots.find((s) => s.selection === "over")?.decimalOdds;
  const underOdds = snapshots.find((s) => s.selection === "under")?.decimalOdds;

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-[var(--rule)] py-4 text-sm">
      <div>
        <p className="font-semibold">{match.homeTeam.shortName} – {match.awayTeam.shortName}</p>
        <p className="mt-0.5 text-xs text-[var(--muted)]">
          {new Date(match.kickoffAt).toLocaleDateString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>
      <div className="text-right text-xs text-[var(--muted)]">
        {overOdds != null && underOdds != null ? (
          <>
            <span>O {overOdds.toFixed(2)}</span>
            <span className="mx-2">·</span>
            <span>U {underOdds.toFixed(2)}</span>
          </>
        ) : (
          <span>Sin cuotas</span>
        )}
      </div>
    </div>
  );
}

export default async function Home() {
  const upcoming = await sports.getUpcomingMatches();
  const historical = 30;

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / MVP</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Mesa de inteligencia</h1>
        </div>
        <p className="text-sm text-[var(--muted)]">Liga MX · datos demo</p>
      </header>

      <section className="mx-auto grid max-w-6xl gap-10 py-10 lg:grid-cols-[220px_1fr]">
        <aside className="border-t-2 border-[var(--foreground)] pt-4">
          <p className="text-sm font-semibold">Sprint 1</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Datos demo</p>
          <dl className="mt-8 space-y-5 text-sm">
            <div>
              <dt className="text-[var(--muted)]">Equipos</dt>
              <dd className="mt-1 font-medium">12</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Históricos</dt>
              <dd className="mt-1 font-medium">{historical}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Próximos</dt>
              <dd className="mt-1 font-medium">{upcoming.length}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Mercado</dt>
              <dd className="mt-1 font-medium">Over/Under 2.5</dd>
            </div>
          </dl>
        </aside>

        <div>
          <p className="max-w-3xl text-xl leading-8">
            Datos demo deterministas cargados desde seeds locales. Cada partido incluye estadísticas históricas y cuotas Over/Under 2.5.
          </p>

          <div className="mt-10">
            <h2 className="mb-4 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">PRÓXIMA JORNADA</h2>
            <div className="border-t border-[var(--rule)]">
              {upcoming.map((m) => (
                <ScannedMatch key={m.id} match={m} />
              ))}
            </div>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            <article className="border border-[var(--rule)] p-5">
              <p className="text-sm text-[var(--muted)]">Datos</p>
              <h2 className="mt-2 font-semibold">12 equipos · 30 partidos históricos</h2>
              <p className="mt-2 text-xs text-[var(--muted)]">Generados con seed fija; trazables y repetibles.</p>
            </article>
            <article className="border border-[var(--rule)] p-5">
              <p className="text-sm text-[var(--muted)]">Cuotas</p>
              <h2 className="mt-2 font-semibold">Over/Under con ambos lados</h2>
              <p className="mt-2 text-xs text-[var(--muted)]">Snapshots inmutables para comparación con modelo.</p>
            </article>
            <article className="border border-[var(--rule)] p-5">
              <p className="text-sm text-[var(--muted)]">Siguiente</p>
              <h2 className="mt-2 font-semibold">Probabilidad, edge y EV</h2>
              <p className="mt-2 text-xs text-[var(--muted)]">Motor Poisson sobre datos históricos validados.</p>
            </article>
          </div>
        </div>
      </section>
    </main>
  );
}

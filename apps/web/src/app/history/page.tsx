import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import {
  fetchHistory,
  fetchMetrics,
  fetchModelVersions,
  type HistoryItemDto,
  type HistoryPageDto,
  type MetricsDto,
  type ModelVersionDto,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Historial y métricas | Stats App",
  description: "Resultados persistidos, ROI, Brier, acierto y calibración por versión de modelo.",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function intOr(value: string | undefined, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signedPct(value: number): string {
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function resultLabel(result: string): string {
  if (result === "win") return "Ganada";
  if (result === "loss") return "Perdida";
  return "Void";
}

function MetricCard({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="border border-[var(--rule)] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-1 text-xs text-[var(--muted)]">{note}</p>}
    </div>
  );
}

function MetricsPanel({
  metrics,
  versions,
  selectedVersion,
}: {
  metrics: MetricsDto;
  versions: ModelVersionDto[];
  selectedVersion: ModelVersionDto | undefined;
}) {
  return (
    <section aria-label="Métricas de evaluación">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">MÉTRICAS</h2>
        <nav aria-label="Versión de modelo" className="flex flex-wrap gap-2 text-xs">
          <Link
            href="/history"
            className={`border px-2 py-1 ${selectedVersion ? "border-[var(--rule)] text-[var(--muted)]" : "border-[var(--foreground)] font-semibold"}`}
          >
            Todas
          </Link>
          {versions.map((v) => {
            const active = selectedVersion?.id === v.id;
            return (
              <Link
                key={v.id}
                href={`/history?version=${encodeURIComponent(v.id)}`}
                aria-current={active ? "page" : undefined}
                className={`border px-2 py-1 ${active ? "border-[var(--foreground)] font-semibold" : "border-[var(--rule)] text-[var(--muted)]"}`}
              >
                {v.name} {v.version} · {v.status}
              </Link>
            );
          })}
        </nav>
      </div>

      {!metrics.sample_sufficient && metrics.sample_size > 0 && (
        <div role="status" className="mt-4 border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900">
          Muestra insuficiente: {metrics.sample_size} resultados (mínimo {metrics.threshold}). Las
          métricas no son concluyentes.
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Muestra" value={metrics.sample_size} note={`${metrics.wins} ganadas · ${metrics.losses} perdidas · ${metrics.voids} voids`} />
        <MetricCard
          label="Acierto"
          value={metrics.hit_rate != null ? pct(metrics.hit_rate) : "—"}
          note="Ganadas / (ganadas + perdidas)"
        />
        <MetricCard
          label="ROI unitario"
          value={metrics.unit_roi != null ? signedPct(metrics.unit_roi) : "—"}
          note="Retorno neto por unidad apostada"
        />
        <MetricCard
          label="Brier"
          value={metrics.brier != null ? metrics.brier.toFixed(4) : "—"}
          note="Menor es mejor (0 ideal)"
        />
      </div>

      <h3 className="mt-8 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">CALIBRACIÓN</h3>
      <div className="mt-3 overflow-x-auto border border-[var(--rule)]">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <th scope="col" className="py-2 pr-4 font-semibold">Probabilidad</th>
              <th scope="col" className="py-2 pr-4 font-semibold text-right">N</th>
              <th scope="col" className="py-2 pr-4 font-semibold text-right">Media predicha</th>
              <th scope="col" className="py-2 font-semibold text-right">Frecuencia observada</th>
            </tr>
          </thead>
          <tbody>
            {metrics.calibration_bins.map((bin) => (
              <tr key={bin.label} className="border-b border-[var(--rule)]">
                <td className="py-2 pr-4 tabular-nums">{bin.label}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{bin.n}</td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {bin.mean_predicted != null ? pct(bin.mean_predicted) : "—"}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {bin.observed_rate != null ? pct(bin.observed_rate) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HistoryTable({ page }: { page: HistoryPageDto }) {
  return (
    <section aria-label="Historial de resultados">
      <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">HISTORIAL</h2>
      <div className="mt-3 overflow-x-auto border border-[var(--rule)]">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <th scope="col" className="py-3 pr-4 font-semibold">Partido</th>
              <th scope="col" className="py-3 pr-4 font-semibold">Selección</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">P. modelo</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">Cuota</th>
              <th scope="col" className="py-3 pr-4 font-semibold">Versión</th>
              <th scope="col" className="py-3 pr-4 font-semibold">Resuelto</th>
              <th scope="col" className="py-3 font-semibold">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {page.items.map((item) => (
              <HistoryRow key={item.prediction_id} item={item} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HistoryRow({ item }: { item: HistoryItemDto }) {
  const badge =
    item.result === "win"
      ? "text-[var(--accent)]"
      : item.result === "loss"
        ? "text-[var(--foreground)]"
        : "text-[var(--muted)]";
  return (
    <tr className="border-b border-[var(--rule)]">
      <td className="py-3 pr-4 font-semibold">
        <Link href={`/matches/${item.match_id}`} className="underline decoration-[var(--rule)] underline-offset-2 hover:decoration-[var(--foreground)]">
          {item.home_team_short} – {item.away_team_short}
        </Link>
      </td>
      <td className="py-3 pr-4">{item.selection === "over" ? "Over 2.5" : "Under 2.5"}</td>
      <td className="py-3 pr-4 text-right tabular-nums">{pct(item.probability)}</td>
      <td className="py-3 pr-4 text-right tabular-nums">{item.odds != null ? item.odds.toFixed(2) : "—"}</td>
      <td className="py-3 pr-4 tabular-nums">{item.model_version}</td>
      <td className="py-3 pr-4 tabular-nums">{new Date(item.resolved_at).toLocaleString("es-MX")}</td>
      <td className={`py-3 font-semibold ${badge}`}>{resultLabel(item.result)}</td>
    </tr>
  );
}

export default async function HistoryPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const versionId = first(sp.version);
  const result = first(sp.result);
  const matchday = first(sp.matchday);
  const page = intOr(first(sp.page), 1);

  let versions: ModelVersionDto[] = [];
  let metrics: MetricsDto | null = null;
  let history: HistoryPageDto | null = null;
  let error: string | null = null;

  try {
    versions = await fetchModelVersions();
    const selected = versions.find((v) => v.id === versionId);
    metrics = await fetchMetrics(selected?.id);
    history = await fetchHistory({
      modelVersion: selected?.version,
      result: result === "win" || result === "loss" || result === "void" ? result : undefined,
      matchday: matchday != null && matchday !== "" ? Number(matchday) : undefined,
      page,
    });
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
  }

  const selected = versions.find((v) => v.id === versionId);
  const filterResult = result === "win" || result === "loss" || result === "void" ? result : undefined;

  const buildHref = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    if (versionId) params.set("version", versionId);
    if (filterResult) params.set("result", filterResult);
    if (matchday != null && matchday !== "") params.set("matchday", matchday);
    for (const [key, value] of Object.entries(updates)) {
      if (value == null || value === "") params.delete(key);
      else params.set(key, value);
    }
    const q = params.toString();
    return q ? `/history?${q}` : "/history";
  };

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-3 border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / HISTORIAL</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            Historial y métricas
          </h1>
        </div>
        <div className="flex gap-4 text-sm">
          <Link href="/parlay" className="text-[var(--muted)] underline">Parlay</Link>
          <Link href="/scanner" className="text-[var(--muted)] underline">Scanner</Link>
          <Link href="/" className="text-[var(--muted)] underline">Jornada</Link>
        </div>
      </header>

      <section className="mx-auto mt-8 max-w-6xl">
        {error ? (
          <div role="alert" className="border border-red-300 bg-red-50 p-5 text-sm text-red-800">
            <p className="font-semibold">No se pudieron cargar las métricas</p>
            <p className="mt-1">{error}</p>
            <p className="mt-2 text-xs">
              Ejecuta <code>npm run dev:api</code> y el runner demo de resolución (
              <code>python -m app.jobs.run_resolution</code>) para poblar resultados.
            </p>
          </div>
        ) : (
          <>
            {metrics && (
              <MetricsPanel metrics={metrics} versions={versions} selectedVersion={selected} />
            )}

            <form method="get" className="mt-10 flex flex-wrap items-end gap-4 border-b border-[var(--rule)] pb-5">
              <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
                Resultado
                <select
                  name="result"
                  defaultValue={filterResult ?? ""}
                  className="border border-[var(--rule)] bg-white px-2 py-1.5 text-sm text-[var(--foreground)]"
                >
                  <option value="">Todos</option>
                  <option value="win">Ganada</option>
                  <option value="loss">Perdida</option>
                  <option value="void">Void</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--muted)]">
                Jornada
                <input
                  type="number"
                  name="matchday"
                  defaultValue={matchday ?? ""}
                  min={1}
                  className="w-20 border border-[var(--rule)] bg-white px-2 py-1.5 text-sm text-[var(--foreground)]"
                />
              </label>
              {versionId && <input type="hidden" name="version" value={versionId} />}
              <button type="submit" className="border border-[var(--foreground)] px-4 py-1.5 text-sm font-semibold">
                Aplicar
              </button>
              <Link href={buildHref({ result: undefined, matchday: undefined, page: undefined })} className="text-xs text-[var(--muted)] underline">
                Limpiar filtros
              </Link>
            </form>

            {history && history.items.length === 0 ? (
              <div className="mt-10 border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
                No hay resultados resueltos con estos filtros. Ejecuta el runner demo de resolución.
              </div>
            ) : history ? (
              <div className="mt-10">
                <HistoryTable page={history} />

                <nav aria-label="Paginación" className="mt-4 flex items-center gap-4 text-sm">
                  <Link
                    href={buildHref({ page: String(Math.max(1, page - 1)) })}
                    aria-disabled={page <= 1}
                    className={page <= 1 ? "pointer-events-none text-[var(--muted)]" : "underline"}
                  >
                    Anterior
                  </Link>
                  <span className="text-[var(--muted)]">
                    Página {history.page} de {history.total_pages || 1} · {history.total} resultados
                  </span>
                  <Link
                    href={buildHref({ page: String(page + 1) })}
                    aria-disabled={page >= history.total_pages}
                    className={page >= history.total_pages ? "pointer-events-none text-[var(--muted)]" : "underline"}
                  >
                    Siguiente
                  </Link>
                </nav>
              </div>
            ) : null}
          </>
        )}
      </section>
    </main>
  );
}

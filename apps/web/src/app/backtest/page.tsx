import type { Metadata } from "next";
import Link from "next/link";
import { ErrorAlert } from "@/components/error-alert";
import {
  errorCorrelationId,
  fetchBacktest,
  type BacktestBaseline,
  type BacktestReportDto,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Backtesting | Stats App",
  description: "Reporte walk-forward del modelo: pliegues, Brier, ROI y calibración por baseline.",
};

const BASELINE_LABELS: Record<string, string> = {
  market: "Mercado",
  league: "Frecuencia de liga",
  poisson: "Poisson",
};

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signedPct(value: number): string {
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function BaselineCard({ baseline }: { baseline: BacktestBaseline }) {
  const m = baseline.metrics;
  return (
    <div className="border border-[var(--rule)] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {BASELINE_LABELS[baseline.name] ?? baseline.name}
      </p>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Brier</dt>
          <dd className="font-medium tabular-nums">{m.brier != null ? m.brier.toFixed(4) : "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">ROI unitario</dt>
          <dd className="font-medium tabular-nums">{m.unit_roi != null ? signedPct(m.unit_roi) : "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Acierto</dt>
          <dd className="font-medium tabular-nums">{m.hit_rate != null ? pct(m.hit_rate) : "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Cobertura</dt>
          <dd className="font-medium tabular-nums">{pct(baseline.coverage)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-[var(--muted)]">Muestra</dt>
          <dd className="font-medium tabular-nums">{m.sample_size}</dd>
        </div>
      </dl>
    </div>
  );
}

function BrierBars({ baselines }: { baselines: BacktestBaseline[] }) {
  const values = baselines.map((b) => ({ name: BASELINE_LABELS[b.name] ?? b.name, brier: b.metrics.brier }));
  const max = Math.max(...values.map((v) => v.brier ?? 0), 0.01);
  return (
    <div aria-label="Comparación de Brier por baseline" className="border border-[var(--rule)] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">BRIER (menor es mejor)</p>
      <ul className="mt-3 space-y-2 text-sm">
        {values.map((v) => (
          <li key={v.name} className="flex items-center gap-3">
            <span className="w-36 shrink-0 text-[var(--muted)]">{v.name}</span>
            <div className="h-3 flex-1 overflow-hidden rounded bg-[var(--rule)]">
              <div
                className="h-full bg-[var(--foreground)]"
                style={{ width: `${((v.brier ?? 0) / max) * 100}%` }}
              />
            </div>
            <span className="w-16 text-right tabular-nums">{v.brier != null ? v.brier.toFixed(4) : "—"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Section({ title, baselines }: { title: string; baselines: BacktestBaseline[] }) {
  if (!baselines || baselines.length === 0) return null;
  return (
    <section aria-label={title}>
      <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">{title}</h2>
      <div className="mt-3 grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="grid gap-4 sm:grid-cols-3">
          {baselines.map((b) => (
            <BaselineCard key={b.name} baseline={b} />
          ))}
        </div>
        <BrierBars baselines={baselines} />
      </div>
    </section>
  );
}

function FoldsTable({ report }: { report: BacktestReportDto }) {
  return (
    <section aria-label="Pliegues walk-forward">
      <h2 className="text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">PLIEGUES</h2>
      <div tabIndex={0} aria-label="Tabla de pliegues walk-forward" className="mt-3 overflow-x-auto border border-[var(--rule)]">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
              <th scope="col" className="py-3 pr-4 font-semibold">Pliegue</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">Entrenamiento</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">Test</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">Brier Poisson</th>
              <th scope="col" className="py-3 pr-4 font-semibold text-right">Cobertura Poisson</th>
            </tr>
          </thead>
          <tbody>
            {report.folds.map((fold) => {
              const poisson = fold.baselines.find((b) => b.name === "poisson");
              return (
                <tr key={fold.index} className="border-b border-[var(--rule)]">
                  <td className="py-3 pr-4">#{fold.index + 1}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{fold.train_size}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">{fold.test_size}</td>
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {poisson?.metrics.brier != null ? poisson.metrics.brier.toFixed(4) : "—"}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums">
                    {poisson ? pct(poisson.coverage) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default async function BacktestPage() {
  let report: BacktestReportDto | null = null;
  let error: string | null = null;
  let correlationId: string | null = null;

  try {
    report = await fetchBacktest(4);
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
    correlationId = errorCorrelationId(e);
  }

  const insufficient = (report?.out_of_sample ?? []).some(
    (b) => b.metrics.sample_size > 0 && !b.metrics.sample_sufficient,
  );

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-3 border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / BACKTEST</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Backtesting</h1>
        </div>
        <div className="flex gap-4 text-sm">
          <Link href="/history" className="text-[var(--muted)] underline">Historial</Link>
          <Link href="/scanner" className="text-[var(--muted)] underline">Scanner</Link>
          <Link href="/" className="text-[var(--muted)] underline">Jornada</Link>
        </div>
      </header>

      <section className="mx-auto mt-8 max-w-6xl">
        <p className="max-w-3xl text-lg leading-8">
          El desempeño del modelo se mide fuera de muestra con un split cronológico (walk-forward).
          El holdout final no participa en la evaluación out-of-sample.
        </p>

        {error ? (
          <div className="mt-8">
            <ErrorAlert
              title="No se pudo cargar el backtest"
              message={error}
              correlationId={correlationId}
              hint="Ejecuta npm run dev:api y el seed demo para generar el reporte."
            />
          </div>
        ) : !report ? (
          <p role="status" className="mt-10 border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]">
            Cargando reporte…
          </p>
        ) : (
          <div className="mt-10 space-y-10">
            {insufficient && (
              <div role="status" className="border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900">
                Muestra insuficiente en al menos un baseline: las métricas no son concluyentes.
              </div>
            )}

            <Section title="OUT-OF-SAMPLE" baselines={report.out_of_sample} />
            <Section title="OVERALL" baselines={report.overall} />
            <Section title="HOLD OUT FINAL" baselines={report.final_holdout} />
            <FoldsTable report={report} />

            <p className="text-xs text-[var(--muted)]">
              Reporte determinista · dataset {report.dataset_version} · seed {report.random_seed} ·
              {report.n_folds} pliegues. Las métricas son evidencia trazable, no una garantía de
              resultados futuros.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { ConfidenceMeter } from "@/components/confidence";
import { ErrorAlert } from "@/components/error-alert";
import { errorCorrelationId, fetchMatchDetail, type PredictionDto, type TeamMatchStatsDto } from "@/lib/api/client";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ match_id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { match_id } = await params;
  return { title: `Partido ${match_id} | Stats App` };
}

function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleDateString("es-MX", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function StatsTable({
  stats,
  homeId,
  awayId,
  homeName,
  awayName,
}: {
  stats: TeamMatchStatsDto[];
  homeId: string;
  awayId: string;
  homeName: string;
  awayName: string;
}) {
  const home = stats.find((s) => s.team_id === homeId);
  const away = stats.find((s) => s.team_id === awayId);
  const rows: Array<[string, (s: TeamMatchStatsDto) => ReactNode]> = [
    ["Goles", (s) => s.goals],
    ["Tiros", (s) => s.shots ?? "—"],
    ["A puerta", (s) => s.shots_on_target ?? "—"],
    ["Posesión", (s) => (s.possession != null ? `${s.possession.toFixed(1)}%` : "—")],
    ["Córners", (s) => s.corners ?? "—"],
  ];

  if (!home && !away) return null;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-[var(--rule)] text-left text-xs uppercase text-[var(--muted)]">
          <th scope="col" className="py-2">Métrica</th>
          {home && <th scope="col" className="py-2 text-right">{homeName}</th>}
          {away && <th scope="col" className="py-2 text-right">{awayName}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, render]) => (
          <tr key={label} className="border-b border-[var(--rule)]">
            <td className="py-2">{label}</td>
            {home && <td className="py-2 text-right tabular-nums">{render(home)}</td>}
            {away && <td className="py-2 text-right tabular-nums">{render(away)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ModelPanel({ predictions }: { predictions: PredictionDto[] }) {
  if (predictions.length === 0) {
    return <p className="text-sm text-[var(--muted)]">Sin predicción para este partido aún.</p>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {predictions.map((p) => (
        <div key={p.selection} className="border border-[var(--rule)] p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            {p.selection === "over" ? "Over 2.5" : "Under 2.5"}
          </p>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Probabilidad</dt>
              <dd className="font-medium tabular-nums">{pct(p.probability)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Cuota justa</dt>
              <dd className="font-medium tabular-nums">{p.fair_odds.toFixed(3)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Calidad</dt>
              <dd>{p.data_quality}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Riesgo</dt>
              <dd>{p.risk_level}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Timestamp</dt>
              <dd className="tabular-nums">
                {new Date(p.prediction_timestamp).toLocaleString("es-MX")}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[var(--muted)]">Versión</dt>
              <dd>
                {p.inputs ? JSON.parse(p.inputs).model_version : "—"}
              </dd>
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
  );
}

function ExplanationPanel({ predictions }: { predictions: PredictionDto[] }) {
  const first = predictions[0];
  if (!first?.explanation) return null;
  const e = first.explanation;

  return (
    <div className="mt-4 space-y-4 border border-[var(--rule)] p-5 text-sm">
      <p>{e.summary}</p>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Factores</p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          {e.factors.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Riesgos</p>
        <ul className="mt-2 list-inside list-disc space-y-1">
          {e.risks.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Fórmula</p>
        <p className="mt-1 font-mono text-xs">{e.formula}</p>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Procedencia</p>
        <dl className="mt-2 space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Dataset</dt>
            <dd className="tabular-nums">{e.provenance.dataset ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">FeatureSet</dt>
            <dd className="tabular-nums">{e.provenance.feature_set_version ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Modelo</dt>
            <dd className="tabular-nums">{e.model_version ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Hash de inputs</dt>
            <dd className="max-w-[180px] truncate font-mono" title={e.provenance.inputs_hash}>
              {e.provenance.inputs_hash}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

export default async function MatchDetailPage({ params }: Props) {
  const { match_id } = await params;

  let detail;
  let error: string | null = null;
  let correlationId: string | null = null;
  try {
    detail = await fetchMatchDetail(match_id);
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
    correlationId = errorCorrelationId(e);
  }

  if (error) {
    return (
      <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
        <div className="mx-auto mt-8 max-w-3xl">
          <ErrorAlert
            title="No se pudo cargar el partido"
            message={error}
            correlationId={correlationId}
            hint={
              <Link href="/scanner" className="underline">
                Volver al scanner
              </Link>
            }
          />
        </div>
      </main>
    );
  }

  const { match } = detail!;
  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-5xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / PARTIDO</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            {match.home_team.name} – {match.away_team.name}
          </h1>
        </div>
        <Link href="/scanner" className="text-sm text-[var(--muted)] underline">
          Scanner
        </Link>
      </header>

      <section className="mx-auto mt-8 max-w-5xl">
        <p className="text-sm text-[var(--muted)]">
          {match.competition} · {formatKickoff(match.kickoff_at)} ·{" "}
          {match.status === "scheduled" ? "Prepartido" : "Finalizado"}
        </p>

        {match.over_odds != null && match.under_odds != null && (
          <p className="mt-2 text-sm">
            Mercado: <span className="font-medium">O {match.over_odds.toFixed(2)}</span>
            <span className="mx-2 text-[var(--muted)]">·</span>
            <span className="font-medium">U {match.under_odds.toFixed(2)}</span>
          </p>
        )}

        <h2 className="mt-10 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">MODELO</h2>
        <div className="mt-4">
          <ModelPanel predictions={detail!.predictions} />
        </div>

        {detail!.predictions.length > 0 && (
          <>
            <h2 className="mt-10 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">EXPLICACIÓN</h2>
            <ExplanationPanel predictions={detail!.predictions} />
          </>
        )}

        <h2 className="mt-10 text-sm font-semibold tracking-[0.15em] text-[var(--muted)]">ESTADÍSTICAS</h2>
        <div className="mt-4">
          {detail!.stats.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">
              Sin estadísticas registradas para este partido (datos incompletos).
            </p>
          ) : (
            <div className="max-w-md">
              <StatsTable
                stats={detail!.stats}
                homeId={match.home_team.id}
                awayId={match.away_team.id}
                homeName={match.home_team.name}
                awayName={match.away_team.name}
              />
            </div>
          )}
        </div>

        {detail!.predictions.length > 0 && (
          <p className="mt-6 text-xs text-[var(--muted)]">
            Predicción generada con el modelo Poisson (versión{" "}
            {detail!.predictions[0].inputs
              ? JSON.parse(detail!.predictions[0].inputs).model_version
              : "—"}
            ). El timestamp y el hash de inputs garantizan trazabilidad.
          </p>
        )}
      </section>
    </main>
  );
}

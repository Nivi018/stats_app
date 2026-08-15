import type { Metadata } from "next";
import Link from "next/link";
import { fetchOpportunities } from "@/lib/api/client";
import ParlayBuilder from "./parlay-builder";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Constructor de parlay | Stats App",
  description: "Arma parlays de 2-3 selecciones con cuota, estimación, riesgo y advertencias de correlación.",
};

export default async function ParlayPage() {
  let opportunities;
  let error: string | null = null;

  try {
    opportunities = await fetchOpportunities();
  } catch (e) {
    error = e instanceof Error ? e.message : "No se pudo contactar la API";
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl flex-wrap items-baseline justify-between gap-3 border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / PARLAY</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            Constructor de parlay
          </h1>
        </div>
        <div className="flex gap-4 text-sm">
          <Link href="/scanner" className="text-[var(--muted)] underline">
            Scanner
          </Link>
          <Link href="/" className="text-[var(--muted)] underline">
            Jornada
          </Link>
        </div>
      </header>

      <section className="mx-auto mt-8 max-w-6xl">
        <p className="max-w-3xl text-lg leading-8">
          Combina 2-3 selecciones Over/Under 2.5. Se muestra cuota combinada, estimación,
          riesgo agregado y advertencias cuando las selecciones comparten partido o equipo.
        </p>

        {error ? (
          <div role="alert" className="mt-8 border border-red-300 bg-red-50 p-5 text-sm text-red-800">
            <p className="font-semibold">No se pudieron cargar las selecciones disponibles</p>
            <p className="mt-1">{error}</p>
            <p className="mt-2 text-xs">
              Ejecuta <code>npm run dev:api</code> y el worker de predicciones.
            </p>
          </div>
        ) : (
          <div className="mt-10">
            <ParlayBuilder opportunities={opportunities ?? []} />
          </div>
        )}
      </section>
    </main>
  );
}

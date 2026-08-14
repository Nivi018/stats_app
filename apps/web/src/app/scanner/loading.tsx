export default function Loading() {
  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-[var(--accent)]">STATS APP / SCANNER</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Oportunidades</h1>
        </div>
      </header>
      <div className="mx-auto mt-10 max-w-6xl border-t border-[var(--rule)] py-8 text-sm text-[var(--muted)]" role="status">
        Cargando oportunidades…
      </div>
    </main>
  );
}

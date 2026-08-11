export default function Home() {
  // THESIS: a research desk, not a betting lobby. OWN-WORLD: mineral paper,
  // blue ink, fine rules, and a single green signal. STORY: users see what is
  // ready now and why analysis is traceable. FIRST VIEWPORT: status at left,
  // editorial briefing and research queue at right. FORM: operate dashboard.
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
          <p className="text-sm font-semibold">Sprint 0</p><p className="mt-1 text-sm text-[var(--muted)]">Preparacion</p>
          <dl className="mt-8 space-y-5 text-sm"><div><dt className="text-[var(--muted)]">Objetivo</dt><dd className="mt-1 font-medium">Base tecnica y visual</dd></div><div><dt className="text-[var(--muted)]">Estado</dt><dd className="mt-1 font-medium text-[var(--accent)]">En progreso</dd></div><div><dt className="text-[var(--muted)]">Mercado inicial</dt><dd className="mt-1 font-medium">Over/Under 2.5</dd></div></dl>
        </aside>
        <div>
          <p className="max-w-3xl text-xl leading-8">El producto transformara datos deportivos y cuotas en investigacion explicable. Esta primera entrega establece sus controles, contratos y lenguaje visual.</p>
          <div className="mt-10 border-y border-[var(--rule)]"><div className="grid grid-cols-[1fr_auto] gap-4 py-4 text-sm"><span className="font-semibold">Preparacion del sistema</span><span className="text-[var(--accent)]">5 historias · 13 pts</span></div><div className="border-t border-[var(--rule)] py-4 text-sm text-[var(--muted)]">Siguiente: datos demo reproducibles, proveedores intercambiables y validacion de integridad.</div></div>
          <div className="mt-10 grid gap-4 md:grid-cols-3"><article className="border border-[var(--rule)] p-5"><p className="text-sm text-[var(--muted)]">Principio</p><h2 className="mt-2 font-semibold">Evidencia antes que intuicion</h2></article><article className="border border-[var(--rule)] p-5"><p className="text-sm text-[var(--muted)]">Trazabilidad</p><h2 className="mt-2 font-semibold">Modelo, datos y tiempo visibles</h2></article><article className="border border-[var(--rule)] p-5"><p className="text-sm text-[var(--muted)]">Limite</p><h2 className="mt-2 font-semibold">Analisis, no ejecucion de apuestas</h2></article></div>
        </div>
      </section>
    </main>
  );
}

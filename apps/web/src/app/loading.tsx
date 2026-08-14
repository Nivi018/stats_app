export default function Loading() {
  return (
    <main className="min-h-screen bg-[var(--background)] px-5 py-6 text-[var(--foreground)] md:px-10 md:py-10">
      <div className="mx-auto max-w-6xl" role="status">
        <p className="text-sm text-[var(--muted)]">Cargando jornada…</p>
      </div>
    </main>
  );
}

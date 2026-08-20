// Bootstrap del API para E2E: migra, siembra, calcula/resuelve demo y sirve uvicorn.
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiDir = path.resolve(__dirname, "../../api");

function pythonBin() {
  const candidates = [
    path.join(apiDir, ".venv", "Scripts", "python.exe"),
    path.join(apiDir, ".venv", "bin", "python"),
  ];
  for (const candidate of candidates) {
    try {
      const result = spawnSync(candidate, ["--version"], { stdio: "ignore" });
      if (result.status === 0) return candidate;
    } catch {
      // continúa con el siguiente candidato
    }
  }
  throw new Error("No se encontró el venv del API. Ejecuta: python -m venv apps/api/.venv");
}

function run(moduleSpec) {
  const args = ["-m", ...moduleSpec.split(" ")];
  const result = spawnSync(pythonBin(), args, {
    cwd: apiDir,
    stdio: "inherit",
    env: { ...process.env },
  });
  if (result.status !== 0) {
    throw new Error(`Fallo al ejecutar: python ${args.join(" ")}`);
  }
}

run("alembic upgrade head");
run("app.seeds.run");
run("app.jobs.run_resolution");
run("app.jobs.freshen_demo_odds");

const server = spawn(
  pythonBin(),
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
  { cwd: apiDir, stdio: "inherit", env: { ...process.env } },
);

server.on("exit", (code) => {
  process.exit(code ?? 0);
});

process.on("SIGTERM", () => server.kill("SIGTERM"));
process.on("SIGINT", () => server.kill("SIGINT"));

import { test, expect } from "@playwright/test";

test.describe("recorridos críticos end-to-end (US1)", () => {
  test("dashboard muestra la jornada con partidos", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Mesa de inteligencia/ })).toBeVisible();
    await expect(page.getByText(/PRÓXIMA JORNADA/)).toBeVisible();
    // Al menos un enfrentamiento local – visitante.
    await expect(page.getByText(/–/).first()).toBeVisible();
  });

  test("dashboard muestra señales destacadas", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/SEÑALES DESTACADAS/)).toBeVisible();
    await expect(page.getByText(/Edge \+/).first()).toBeVisible();
    const links = page.getByRole("link", { name: /–/ });
    expect(await links.count()).toBeGreaterThanOrEqual(1);
  });

  test("scanner muestra oportunidades y navega al detalle", async ({ page }) => {
    await page.goto("/scanner");
    await expect(page.getByRole("heading", { name: "Oportunidades" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Confianza" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Stake" })).toBeVisible();
    const firstMatch = page.getByRole("link", { name: /–/ }).first();
    await firstMatch.click();
    await expect(page).toHaveURL(/\/matches\//);
    await expect(page.getByText(/MODELO/)).toBeVisible();
  });

  test("detalle de partido muestra modelo y estadísticas", async ({ page }) => {
    await page.goto("/matches/match-up-01");
    await expect(page.getByText(/MODELO/)).toBeVisible();
    await expect(page.getByText(/ESTADÍSTICAS/)).toBeVisible();
    await expect(page.getByText(/CONTEXTO/)).toBeVisible();
  });

  test("constructor de parlay añade selecciones y estima", async ({ page }) => {
    await page.goto("/parlay");
    await expect(page.getByRole("heading", { name: /Constructor de parlay/ })).toBeVisible();

    const addButtons = page.getByRole("button", { name: "Añadir" });
    await addButtons.first().click();
    await addButtons.nth(1).click();

    await expect(page.getByText(/TU PARLAY/)).toBeVisible();
    await expect(page.getByText(/Cuota combinada/)).toBeVisible();
    await expect(page.getByText(/Riesgo agregado/)).toBeVisible();
  });

  test("historial muestra panel de métricas y tabla", async ({ page }) => {
    await page.goto("/history");
    await expect(page.getByRole("heading", { name: /Historial y métricas/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "MÉTRICAS", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "HISTORIAL", exact: true })).toBeVisible();
  });

  test("backtest muestra el reporte walk-forward", async ({ page }) => {
    await page.goto("/backtest");
    await expect(page.getByRole("heading", { name: "Backtesting" })).toBeVisible();
    await expect(page.getByText(/OUT-OF-SAMPLE/)).toBeVisible();
    await expect(page.getByText(/Poisson/).first()).toBeVisible();
    await expect(page.getByText(/PLIEGUES/)).toBeVisible();
  });

  test("degradación: el error del parlay muestra correlation_id para soporte", async ({ page }) => {
    await page.goto("/parlay");
    await page.waitForLoadState("networkidle");

    // Simula un fallo del API en la estimación del parlay (fetch del cliente).
    await page.route("**/api/v1/parlays/estimate", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          code: "internal_error",
          message: "Error interno del servidor",
          details: null,
          correlation_id: "e2e-corr-123",
        }),
      }),
    );

    const addButtons = page.getByRole("button", { name: "Añadir" });
    await addButtons.first().click();
    await addButtons.nth(1).click();

    await expect(page.getByText(/e2e-corr-123/)).toBeVisible();
  });
});

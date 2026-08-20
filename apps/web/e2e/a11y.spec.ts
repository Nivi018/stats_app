import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Flujos críticos sujetos a la auditoría WCAG AA (US2).
const criticalRoutes = ["/", "/scanner", "/parlay", "/history"];

test.describe("auditoría de accesibilidad WCAG AA", () => {
  for (const route of criticalRoutes) {
    test(`${route} sin violaciones críticas ni serias`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page }).analyze();
      const blocking = results.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious",
      );
      expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
    });
  }

  test("detalle de partido sin violaciones críticas ni serias", async ({ page }) => {
    await page.goto("/matches/match-up-01");
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page }).analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });

  test("teclado: el skip link salta al contenido principal", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const focusedText = await page.evaluate(() => document.activeElement?.textContent ?? "");
    expect(focusedText).toContain("Saltar al contenido");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main/);
  });

  test("teclado: los enlaces y botones del scanner reciben foco", async ({ page }) => {
    await page.goto("/scanner");
    await page.waitForLoadState("networkidle");
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.tagName ?? "");
    expect(focused).not.toBe("BODY");
  });
});

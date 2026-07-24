import { expect, test } from "@playwright/test";

/**
 * Smoke test: invariante universale — la home carica senza errori
 * e il contenuto principale è visibile.
 */
test("la home carica e mostra il titolo", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: /hostpilot/i }),
  ).toBeVisible();
});

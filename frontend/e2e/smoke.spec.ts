import { expect, test } from "@playwright/test";

/**
 * Smoke test: la home smista verso /accesso quando non c'è sessione
 * (anche senza backend raggiungibile) e il form di accesso è visibile.
 */
test("senza sessione la home porta all'accesso", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/accesso/);
  await expect(page.getByRole("heading", { level: 1, name: "Accedi" })).toBeVisible();
});

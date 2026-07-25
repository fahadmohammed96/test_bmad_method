import { expect, test } from "@playwright/test";
import { violazioniGravi } from "./axe-utils";

/**
 * Baseline a11y (NFR-8, WCAG 2.1 AA): nessuna violazione axe di impatto
 * serious/critical sulle superfici pubbliche.
 */

test("la pagina di accesso non ha violazioni a11y gravi", async ({ page }) => {
  await page.goto("/accesso");
  await expect(
    page.getByRole("heading", { level: 1, name: "Accedi" }),
  ).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);
});

test("la pagina di registrazione non ha violazioni a11y gravi", async ({
  page,
}) => {
  await page.goto("/registrazione");
  await expect(
    page.getByRole("heading", { level: 1, name: "Crea il tuo account" }),
  ).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);
});

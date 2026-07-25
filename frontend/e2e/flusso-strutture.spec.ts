import { expect, test } from "@playwright/test";
import { violazioniGravi } from "./axe-utils";

/**
 * Flusso E2E della fondazione (UJ-1 parte account/strutture): l'Host si
 * registra, entra nella shell e registra la prima Struttura dal wizard —
 * col backend reale. Include la baseline a11y della shell autenticata (C1).
 */
test("registrazione, shell e prima Struttura senza CIN", async ({
  page,
}, testInfo) => {
  const email = `host.e2e.${Date.now()}.${testInfo.project.name}@example.com`;

  await page.goto("/registrazione");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("una-password-lunga");
  await page.getByRole("button", { name: "Registrati" }).click();

  await page.waitForURL("**/dashboard");
  await expect(
    page.getByRole("heading", { level: 1, name: "Dashboard" }),
  ).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);

  await page.goto("/strutture");
  await page.getByRole("link", { name: "Nuova Struttura" }).click();

  await expect(page.getByText("Passo 1 di 3")).toBeVisible();
  await page.getByLabel("Nome della Struttura").fill("Bologna Centro");
  await page.getByRole("button", { name: "Avanti" }).click();
  await page.getByLabel("Comune").fill("Bologna");
  await page.getByLabel("Regione").fill("Emilia-Romagna");
  await page.getByRole("button", { name: "Avanti" }).click();
  await expect(page.getByText("Passo 3 di 3")).toBeVisible();
  await page.getByRole("button", { name: "Salta per ora e registra" }).click();

  await page.waitForURL("**/strutture");
  const lista = page.getByRole("main");
  await expect(lista.getByText("Bologna Centro")).toBeVisible();
  await expect(lista.getByText("CIN mancante")).toBeVisible();
  // La Struttura appena creata popola anche il selettore trasversale.
  await expect(
    page.getByRole("option", { name: "Bologna Centro" }),
  ).toBeAttached();
  expect(await violazioniGravi(page)).toEqual([]);
});

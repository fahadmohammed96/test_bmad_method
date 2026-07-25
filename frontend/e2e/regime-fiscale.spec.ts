import { expect, test } from "@playwright/test";
import { violazioniGravi } from "./axe-utils";

/**
 * Regime fiscale derivato (FR-17, UJ-4, UX-DR14): il pannello a schermo
 * intero compare alla 3ª Struttura, il pannello persistente resta sempre
 * accessibile col disclaimer, e la ridiscesa a 2 non lascia notifiche.
 *
 * I parametri fiscali si impostano dagli endpoint interni: sono dati,
 * non costanti nel codice.
 */
const ADMIN_TOKEN = "token-e2e-endpoint-interni";
const API = "http://localhost:8000/api/v1";

test.beforeAll(async ({ request }) => {
  const risposta = await request.put(`${API}/interno/parametri-fiscali`, {
    headers: { "X-Admin-Token": ADMIN_TOKEN },
    data: {
      attore: "e2e@example.com",
      soglia_strutture: 3,
      regime_sotto_soglia: "cedolare_secca",
      regime_da_soglia: "imprenditoriale",
      testo_sotto_soglia: "Con 1-2 Strutture rientri nella cedolare secca.",
      testo_da_soglia:
        "Con 3 Strutture scatta la presunzione di imprenditorialità: serve la Partita IVA.",
      aliquote_citate: "cedolare secca 21% / 26%",
      valido_dal: "2026-01-01",
    },
  });
  expect(risposta.ok()).toBeTruthy();
});

test("il pannello compare alla 3ª Struttura e la ridiscesa lo ritira", async ({
  page,
}, testInfo) => {
  const email = `host.regime.${Date.now()}.${testInfo.project.name}@example.com`;

  await page.goto("/registrazione");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("una-password-lunga");
  await page.getByRole("button", { name: "Registrati" }).click();
  await page.waitForURL("**/dashboard");

  async function registraStruttura(nome: string) {
    await page.goto("/strutture/nuova");
    await page.getByLabel("Nome della Struttura").fill(nome);
    await page.getByRole("button", { name: "Avanti" }).click();
    await page.getByLabel("Comune").fill("Testopoli");
    await page.getByLabel("Regione").selectOption("Emilia-Romagna");
    await page.getByRole("button", { name: "Avanti" }).click();
    await page.getByRole("button", { name: "Salta per ora e registra" }).click();
    await page.waitForURL("**/strutture");
  }

  // Con 1-2 Strutture: pannello persistente informativo, nessun modale.
  await registraStruttura("Prima");
  await expect(page.getByRole("heading", { name: "Regime fiscale" })).toBeVisible();
  await expect(page.getByText(/commercialista/).first()).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await registraStruttura("Seconda");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Alla 3ª scatta il pannello a schermo intero, con disclaimer e CTA.
  await registraStruttura("Terza");
  const modale = page.getByRole("dialog");
  await expect(modale).toBeVisible();
  await expect(
    modale.getByRole("heading", { name: /cambia il tuo regime fiscale/i }),
  ).toBeVisible();
  await expect(modale.getByText(/Partita IVA/)).toBeVisible();
  await expect(modale.getByText(/consulenza fiscale/)).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);

  await modale.getByRole("button", { name: "Ho capito, continua" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Ridiscesa a 2: nessuna notifica residua, il regime torna informativo.
  // L'archiviazione chiede conferma (window.confirm): accettiamola.
  page.once("dialog", (finestra) => finestra.accept());
  await page
    .getByRole("listitem")
    .filter({ hasText: "Terza" })
    .getByRole("button", { name: "Archivia" })
    .click();
  await expect(page.getByText("Archiviata")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("2 Strutture attive · Soglia: 3")).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);
});

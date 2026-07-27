import { expect, test } from "@playwright/test";
import { violazioniGravi } from "./axe-utils";

/**
 * `calendario.spec.ts` — spec e2e **ammesso** dall'elenco chiuso del test
 * design (§2.5). Il difetto che solo lui vede, come da elenco:
 *
 * > **Coerenza fra cache correlate sulla stessa superficie.** Griglia delle
 * > Prenotazioni ed etichetta «dati aggiornati alle HH:MM» sono valori
 * > derivati dalla stessa sorgente. Una mutazione che ne aggiorna una sola
 * > lascia l'altra ferma, e l'etichetta ferma è esattamente la falsa
 * > sincronia che NFR-2 vieta. I test di componente non possono vederlo: lì
 * > gli hook sono mockati, quindi la cache non esiste nel loro mondo.
 *
 * Più la baseline **axe serious/critical = 0** sulla nuova superficie (AC 8),
 * che misura l'albero accessibile RENDERIZZATO e quindi esiste solo qui.
 *
 * **Cosa questo spec NON copre, dichiarato invece che taciuto.** La metà
 * «sync concluso» dell'AC 6 non è esercitabile in questo ambiente: il
 * `webServer` di Playwright avvia l'API ma non il worker, e la politica di
 * uscita di rete rifiuta il loopback (NFR-17), quindi nessun import può
 * concludersi qui. La prima Prenotazione scrivibile dall'Host arriva con la
 * Story 2.4. Fino ad allora la mutazione osservabile è il collegamento di un
 * Feed, e quella è la metà coperta sotto.
 */

const CREDENZIALI = { password: "una-password-lunga" };

async function registra(page: import("@playwright/test").Page, etichetta: string) {
  const email = `host.calendario.${Date.now()}.${etichetta}@example.com`;
  await page.goto("/registrazione");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(CREDENZIALI.password);
  await page.getByRole("button", { name: "Registrati" }).click();
  await page.waitForURL("**/dashboard");
}

async function registraStruttura(
  page: import("@playwright/test").Page,
  nome: string,
) {
  await page.goto("/strutture/nuova");
  await page.getByLabel("Nome della Struttura").fill(nome);
  await page.getByRole("button", { name: "Avanti" }).click();
  await page.getByLabel("Comune").fill("Bologna");
  await page.getByLabel("Regione").selectOption("Emilia-Romagna");
  await page.getByRole("button", { name: "Avanti" }).click();
  await page.getByRole("button", { name: "Salta per ora e registra" }).click();
  await page.waitForURL("**/strutture");
  // L'URL cambia prima che la lista sia renderizzata: cliccare la
  // navigazione mentre la pagina si sta ancora componendo fallisce sul
  // layout mobile, e il sintomo sarebbe un timeout che sembra un difetto
  // della barra di navigazione.
  await expect(page.getByRole("main").getByText(nome)).toBeVisible();
}

test("la griglia e l'etichetta del timestamp si muovono insieme", async ({
  page,
}, testInfo) => {
  await registra(page, testInfo.project.name);
  await registraStruttura(page, "Bologna Centro");

  await page.goto("/calendario");
  await expect(
    page.getByRole("heading", { level: 1, name: "Calendario" }),
  ).toBeVisible();

  // Stato di partenza: nessun Feed collegato. Il prodotto lo DICE, invece di
  // mostrare una griglia vuota che si legge come «non hai prenotazioni».
  await expect(page.getByText(/Nessun calendario collegato/)).toBeVisible();
  const griglia = page.getByRole("table");
  await expect(griglia).toBeVisible();
  await expect(griglia.getByText("Bologna Centro")).toBeVisible();

  // Mutazione su un'ALTRA superficie, con navigazione lato client (mai un
  // `goto`, che ricaricherebbe la pagina e azzererebbe la cache: senza cache
  // non c'è niente da tenere coerente, e il test passerebbe per il motivo
  // sbagliato). È il confine che nessun livello sotto attraversa — nei test
  // di componente la cache non esiste.
  await page.getByRole("link", { name: /Account/ }).first().click();
  await page.waitForURL("**/account");
  await page.getByRole("link", { name: /Gestisci le tue Strutture/ }).click();
  await page.waitForURL("**/strutture");
  await page.getByRole("link", { name: "Modifica" }).first().click();
  const campoUrl = page.getByLabel("Indirizzo del calendario (iCal)");
  await campoUrl.fill("https://feed.example.com/calendario.ics");
  // Invio da tastiera invece del click sul bottone: il pannello dei Feed
  // cresce mentre carica, e su viewport mobile la posizione del bottone si
  // sposta sotto il cursore. È anche il gesto reale di chi ha appena
  // incollato un indirizzo.
  await campoUrl.press("Enter");
  await expect(page.getByText(/Importazione in corso|Mai sincronizzato/)).toBeVisible();

  // Ritorno per storia del browser: è ancora navigazione lato client, quindi
  // la cache sopravvive. Un `goto` la butterebbe via, e il test non
  // controllerebbe più niente.
  await page.goBack();
  await page.goBack();
  await page.goBack();
  await page.waitForURL("**/calendario");

  // L'etichetta è cambiata insieme al perimetro: adesso un calendario c'è, e
  // non ha ancora importato nulla. Il testo vecchio sarebbe un'affermazione
  // falsa sullo stato del calendario dell'Host.
  await expect(page.getByText(/Nessun calendario collegato/)).toHaveCount(0);
  await expect(page.getByText(/potrebbe essere incompleta/)).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);
});

test("il selettore Struttura filtra griglia ed etichetta senza cambiare schermata", async ({
  page,
}, testInfo) => {
  await registra(page, `filtro-${testInfo.project.name}`);
  await registraStruttura(page, "Bologna Centro");
  await registraStruttura(page, "Mare Rimini");

  await page.goto("/calendario");
  const griglia = page.getByRole("table");
  await expect(griglia.getByText("Bologna Centro")).toBeVisible();
  await expect(griglia.getByText("Mare Rimini")).toBeVisible();

  // Griglia ed etichetta derivano dallo STESSO perimetro: se vivessero in due
  // cache con chiavi diverse, il filtro ne muoverebbe una sola — e l'Host
  // leggerebbe la freschezza di una Struttura sopra le prenotazioni di
  // un'altra. Solo il browser attraversa quel confine.
  await page.getByRole("combobox", { name: /struttura/i }).selectOption({
    label: "Mare Rimini",
  });

  await expect(griglia.getByText("Mare Rimini")).toBeVisible();
  await expect(griglia.getByText("Bologna Centro")).toHaveCount(0);
  // Stessa schermata: nessuna navigazione, il titolo è ancora quello (UX-DR1).
  await expect(
    page.getByRole("heading", { level: 1, name: "Calendario" }),
  ).toBeVisible();
  expect(page.url()).toContain("/calendario");
  expect(await violazioniGravi(page)).toEqual([]);
});

test("la vista settimanale e la navigazione fra periodi restano accessibili", async ({
  page,
}, testInfo) => {
  await registra(page, `viste-${testInfo.project.name}`);
  await registraStruttura(page, "Bologna Centro");

  await page.goto("/calendario");
  await expect(page.getByRole("table")).toBeVisible();

  await page.getByRole("button", { name: "Settimana" }).click();
  await expect(page.getByRole("button", { name: "Settimana" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // Sette notti: la settimana lunedì → domenica.
  await expect(page.getByRole("columnheader")).toHaveCount(8);
  expect(await violazioniGravi(page)).toEqual([]);

  await page.getByRole("button", { name: "Periodo precedente" }).click();
  await expect(page.getByRole("table")).toBeVisible();
  expect(await violazioniGravi(page)).toEqual([]);
});

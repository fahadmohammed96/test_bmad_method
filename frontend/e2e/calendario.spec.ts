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
 * **Attenzione a cosa misura la baseline.** I tre test che seguono girano su
 * una griglia **vuota**: l'ambiente non può creare Prenotazioni, quindi lì
 * axe vede il telaio e non il contenuto. Il chip — badge di Canale,
 * etichetta di stato, date, notti — è auditato dal test dedicato in fondo,
 * che intercetta la risposta dell'API per farlo renderizzare davvero
 * (E2-F4). Senza quello, «axe verde sulla superficie» sarebbe
 * un'affermazione più larga di ciò che è stato guardato.
 *
 * **Cosa questo spec NON copre, dichiarato invece che taciuto.** La metà
 * «sync concluso» dell'AC 6 non è esercitabile in questo ambiente: il
 * `webServer` di Playwright avvia l'API ma non il worker, e la politica di
 * uscita di rete rifiuta il loopback (NFR-17), quindi nessun import può
 * concludersi qui. Resta **non chiudibile** anche dopo la Story 2.4, e la
 * ragione non è il perimetro della Story: è l'ambiente.
 *
 * Quello che la Story 2.4 chiude è l'altra metà dello stesso AC — la
 * **mutazione reale della sorgente** —, e la chiude per davvero: l'ultimo test
 * di questo file inserisce una Prenotazione dal form, non da un payload
 * intercettato, e osserva che griglia ed etichetta si muovono **insieme** senza
 * ricaricare la pagina. Con quella Prenotazione la baseline axe smette di
 * misurare un chip finto (AC 8).
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

/**
 * La griglia **con dentro le Prenotazioni** (E2-F4).
 *
 * Le altre baseline axe di questo file girano su una griglia vuota — è
 * dichiarato al primo test — quindi il contenuto principale della superficie
 * non veniva mai auditato: `ChipPrenotazione` è dove vivono il badge di
 * Canale, l'etichetta di stato, le date e le notti, cioè tutto ciò che AC 1,
 * 2 e 12 chiedono di leggere. Una baseline che non lo vede misura il telaio.
 *
 * Le Prenotazioni non si possono creare qui — l'ambiente e2e non avvia il
 * worker e la politica di uscita di rete rifiuta il loopback, quindi nessun
 * import può concludersi, e la prima scrittura dell'Host è la Story 2.4.
 * Quindi si **intercetta la risposta dell'API**: il browser è vero, il CSS è
 * vero, il DOM renderizzato è vero, e axe misura il contrasto reale. Ciò che
 * è finto è il solo payload, ed è la parte che questo test non sta
 * verificando (la copre `test_calendario_griglia.py`).
 */
const BOLOGNA = "11111111-1111-1111-1111-111111111111";
const RIMINI = "22222222-2222-2222-2222-222222222222";

/** `AAAA-MM-GG` spostato di `giorni`, senza fusi (come `griglia.ts`). */
function giornoPiu(giorno: string, giorni: number): string {
  const [anno, mese, data] = giorno.split("-").map(Number);
  return new Date(Date.UTC(anno, mese - 1, data + giorni))
    .toISOString()
    .slice(0, 10);
}

/**
 * Le voci si costruiscono a partire dal `da` REALMENTE richiesto.
 *
 * Fissarle su un mese scelto a mano le farebbe cadere fuori dal periodo che
 * la pagina apre — cioè il mese corrente — e i chip non verrebbero
 * renderizzati: il test resterebbe verde misurando di nuovo una griglia
 * vuota, che è esattamente il difetto che esiste per chiudere.
 */
function calendarioConPrenotazioni(da: string) {
  return {
    da,
    a: giornoPiu(da, 27),
    stato_sync: "riuscito",
    ultimo_sync_riuscito_il: "2026-08-17T12:35:00Z",
    feed_collegati: 2,
    feed_mai_sincronizzati: 0,
    feed_in_errore: 0,
    strutture: [
      { id: BOLOGNA, nome: "Bologna Centro" },
      { id: RIMINI, nome: "Mare Rimini" },
    ],
    voci: [
      {
        id: "aaaaaaaa-0000-0000-0000-000000000001",
        struttura_id: BOLOGNA,
        canale: "airbnb",
        check_in: giornoPiu(da, 2),
        check_out: giornoPiu(da, 6),
        notti: 4,
        sommario: "Testo opaco del portale",
        stato: "attiva",
        ospite_principale: "Ospite Inventato",
        altri_ospiti: 2,
      },
      {
        id: "aaaaaaaa-0000-0000-0000-000000000002",
        struttura_id: BOLOGNA,
        canale: "booking",
        // Sovrapposta alla precedente: apre una seconda corsia, che è la
        // forma che axe non ha mai visto.
        check_in: giornoPiu(da, 4),
        check_out: giornoPiu(da, 9),
        notti: 5,
        sommario: null,
        stato: "attiva",
        ospite_principale: null,
        altri_ospiti: 0,
      },
      {
        id: "aaaaaaaa-0000-0000-0000-000000000003",
        struttura_id: RIMINI,
        canale: "altro",
        check_in: giornoPiu(da, 12),
        check_out: giornoPiu(da, 15),
        notti: 3,
        sommario: null,
        // Il caso di E2-F4: è il testo di QUESTO chip che l'opacità rendeva
        // illeggibile, ed è quello che porta lo stato.
        stato: "rimossa_dal_feed",
        ospite_principale: "Ospite Passato",
        altri_ospiti: 0,
      },
    ],
  };
}

test("la griglia CON Prenotazioni non ha violazioni a11y gravi", async ({
  page,
}, testInfo) => {
  await registra(page, `chip-${testInfo.project.name}`);
  await registraStruttura(page, "Bologna Centro");

  await page.route("**/api/v1/calendario**", async (rotta) => {
    const da =
      new URL(rotta.request().url()).searchParams.get("da") ?? "2026-08-01";
    await rotta.fulfill({
      status: 200,
      contentType: "application/json",
      // L'API sta su un'altra origin e il client manda il cookie di
      // sessione: senza le intestazioni CORS il browser scarterebbe la
      // risposta intercettata, la pagina mostrerebbe l'errore di
      // caricamento, e axe finirebbe di nuovo per misurare una griglia
      // senza chip — cioè il difetto che questo test chiude.
      headers: {
        "access-control-allow-origin": "http://localhost:3000",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify(calendarioConPrenotazioni(da)),
    });
  });
  await page.goto("/calendario");

  // I chip ci sono davvero: senza questa attesa axe misurerebbe di nuovo una
  // griglia vuota, cioè il difetto che questo test esiste per chiudere.
  await expect(page.getByText("Ospite Inventato")).toBeVisible();
  await expect(page.getByText("Ospite non indicato")).toBeVisible();
  await expect(page.getByText("Non più nel portale")).toBeVisible();
  await expect(page.getByText("e altri 2 Ospiti")).toBeVisible();

  expect(await violazioniGravi(page)).toEqual([]);
});

/**
 * La mutazione REALE della sorgente (AC 6 della Story 2.3, metà «Prenotazione
 * manuale») e la baseline axe su un chip **vero** (AC 8).
 *
 * Erano i due residui QA lasciati aperti dalla Story 2.3, e la ragione era la
 * stessa per entrambi: fino alla 2.4 in questo ambiente non esisteva **nessun
 * modo di scrivere** nel calendario. Il collegamento di un Feed cambia il
 * perimetro (quanti calendari ci sono) ma non le Prenotazioni; l'import non può
 * concludersi perché il worker non gira; e i chip si potevano solo intercettare,
 * cioè axe misurava un payload finto in un DOM vero.
 *
 * Qui la Prenotazione la scrive l'Host, dal form, e tutto il resto è vero: la
 * griglia si aggiorna **senza ricaricare la pagina** — è l'unico posto in cui la
 * cache esiste, nei test di componente gli hook sono mockati — e l'etichetta
 * «dati aggiornati alle HH:MM» viene interrogata sullo stesso istante.
 *
 * L'asserzione che porta più valore è quella **negativa**: inserire una
 * Prenotazione a mano NON deve far comparire un orario di aggiornamento. Un
 * dato scritto dall'Host non rende più freschi quelli dei portali, e un'etichetta
 * che dicesse «dati aggiornati alle 14:32» perché è stata inserita una manuale
 * sarebbe falsa sincronia prodotta dal prodotto stesso (NFR-2).
 */

/** Il primo giorno mostrato dalla griglia, letto DALLA PAGINA.
 *
 * Non si calcola dall'orologio del runner: la pagina apre il mese corrente in
 * Europe/Rome, e a cavallo della mezzanotte di fine mese i due potrebbero non
 * essere lo stesso mese — cioè le date inserite cadrebbero fuori dal periodo
 * visibile e il test tornerebbe a misurare una griglia vuota, verde per il
 * motivo sbagliato. Si legge `textContent` via `evaluate` perché il testo è
 * `sr-only`.
 */
async function primoGiornoVisibile(
  page: import("@playwright/test").Page,
): Promise<string> {
  const testo = await page
    .getByRole("columnheader")
    .nth(1)
    .evaluate((elemento) => elemento.querySelector("span.sr-only")?.textContent ?? "");
  const [giorno, mese, anno] = testo.trim().split("/");
  return `${anno}-${mese}-${giorno}`;
}

test("una Prenotazione inserita a mano aggiorna griglia ed etichetta senza reload", async ({
  page,
}, testInfo) => {
  await registra(page, `manuale-${testInfo.project.name}`);
  await registraStruttura(page, "Bologna Centro");

  // Si collega un Feed perché l'etichetta parli di dati da Feed: senza, direbbe
  // «nessun calendario collegato» e la metà «etichetta» dell'AC non avrebbe
  // niente da affermare.
  await page.getByRole("link", { name: "Modifica" }).first().click();
  const campoUrl = page.getByLabel("Indirizzo del calendario (iCal)");
  await campoUrl.fill("https://feed.example.com/manuale.ics");
  await campoUrl.press("Enter");
  await expect(
    page.getByText(/Importazione in corso|Mai sincronizzato/),
  ).toBeVisible();

  // `goto` QUI è deliberato, e non indebolisce il test: la cache che deve
  // restare coerente è quella che **questo** caricamento popola, e ciò che non
  // deve esserci in mezzo è un reload fra il salvataggio della Prenotazione e
  // le asserzioni. Arrivare invece cliccando la navigazione costerebbe, sul
  // progetto `mobile`, un click su una barra `fixed` che il pannello dei Feed —
  // che cresce mentre carica — intercetta.
  await page.goto("/calendario");
  await expect(page.getByText(/potrebbe essere incompleta/)).toBeVisible();

  const primo = await primoGiornoVisibile(page);
  const arrivo = giornoPiu(primo, 9);
  const partenza = giornoPiu(primo, 13);

  await page
    .getByRole("button", { name: "Inserisci una prenotazione" })
    .click();
  // Il form è una superficie nuova: la baseline axe la copre da aperto, dove
  // esistono i suoi campi e le sue etichette.
  expect(await violazioniGravi(page)).toEqual([]);

  await page.getByLabel("Arrivo").fill(arrivo);
  await page.getByLabel("Partenza").fill(partenza);
  const campoNome = page.getByLabel(/Nome dell'Ospite/);
  await campoNome.fill("Ospite Inventato");
  // Invio da tastiera: è il gesto reale di chi ha appena finito di scrivere, e
  // non dipende dalla posizione del bottone su viewport mobile.
  await campoNome.press("Enter");

  await expect(page.getByText(/Prenotazione inserita/)).toBeVisible();

  // La griglia si è mossa, e SENZA reload: nessun `goto` fra il salvataggio e
  // questa asserzione.
  const griglia = page.getByRole("table");
  await expect(griglia.getByText("Ospite Inventato")).toBeVisible();
  await expect(griglia.getByText("Inserita a mano")).toBeVisible();

  // E l'etichetta non ha inventato niente: la freschezza dei dati da Feed è
  // quella di prima, perché nessun portale è stato interrogato (NFR-2).
  await expect(page.getByText(/potrebbe essere incompleta/)).toBeVisible();
  await expect(page.getByText(/Dati aggiornati alle/)).toHaveCount(0);

  // Baseline axe su un chip VERO, non su un payload intercettato: chiude il
  // residuo dell'AC 8 della Story 2.3.
  expect(await violazioniGravi(page)).toEqual([]);

  // Si chiude il pannello prima di agire sulla griglia: è il gesto reale
  // dell'Host che ha finito di inserire, e su viewport mobile è anche ciò che
  // evita di cliccare un chip mentre un pannello alto mezza pagina sta ancora
  // sopra di lui.
  await page.getByRole("button", { name: "Chiudi" }).click();
  await expect(page.getByLabel("Arrivo")).toHaveCount(0);

  // Cancellazione: transizione, non sparizione (AD-19, AD-20). Anche questa
  // senza reload.
  await page
    .getByRole("button", { name: /Cancella la prenotazione del/ })
    .click();
  await page.getByRole("button", { name: "Sì, cancella" }).click();

  await expect(griglia.getByText("Cancellata")).toBeVisible();
  // Resta lì, con la sua etichetta: è «archiviare, mai distruggere» visto dagli
  // occhi dell'Host, che quella prenotazione l'ha appena inserita.
  await expect(griglia.getByText("Ospite Inventato")).toBeVisible();
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

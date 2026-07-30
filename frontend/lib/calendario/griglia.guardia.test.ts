import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guardia strutturale sulla superficie Calendario (AC 5 — AD-14, AD-3).
 *
 * L'AC dice che i valori derivati di dominio arrivano dall'API e il frontend
 * li **presenta**, mai li ricalcola. Un test funzionale non lo può dimostrare:
 * finché il conto del client e quello del server coincidono, ogni asserzione
 * passa. Smettono di coincidere il giorno del cambio d'ora, o sul browser di
 * un Host che viaggia — cioè quando nessuno sta guardando.
 *
 * Tre proprietà, ognuna con il difetto che nomina:
 *
 * 1. il modulo della griglia non tocca il fuso del browser;
 * 2. la superficie non ha un orologio proprio — «dati aggiornati alle HH:MM»
 *    non può nascere dal client;
 * 3. i valori derivati che mostra esistono nel contratto: se qualcuno li
 *    togliesse dall'API per ricalcolarli qui, questa guardia cadrebbe.
 */

const RADICE = path.resolve(__dirname, "..", "..");

const sorgente = (relativo: string) =>
  readFileSync(path.join(RADICE, relativo), "utf-8");

// Accessor che leggono o scrivono una data nel fuso del BROWSER. Su una
// stringa `AAAA-MM-GG`, che è una data di calendario Europe/Rome (AD-3), il
// risultato dipende da dove si trova chi guarda: a ovest di Greenwich
// `getDate()` restituisce il giorno prima, e ogni Prenotazione slitta di una
// cella.
const ACCESSOR_LOCALI = [
  ".getFullYear(",
  ".getMonth(",
  ".getDate(",
  ".getDay(",
  ".getHours(",
  ".setDate(",
  ".setMonth(",
  ".setFullYear(",
  ".toLocaleDateString(",
  ".toDateString(",
];

// Sorgenti dell'istante corrente. Su questa superficie non ne serve nessuna:
// l'unico orario mostrato è quello dell'ultimo sync riuscito, che arriva
// dall'API. Un `new Date()` qui sarebbe la falsa sincronia nella sua forma
// più pura — un'etichetta che dice «aggiornato adesso» perché è adesso.
const OROLOGI = ["new Date()", "Date.now("];

const SUPERFICIE_CALENDARIO = [
  "components/CalendarioGriglia.tsx",
  "components/BadgeCanale.tsx",
  "app/(app)/calendario/page.tsx",
  // Story 2.4. `FormPrenotazioneManuale` è il file con più motivi di tutti per
  // toccare una data: prende due date dall'Host e potrebbe «aiutarlo»
  // proponendo oggi, o calcolando la partenza dall'arrivo. Le date restano le
  // stringhe `AAAA-MM-GG` che l'input produce, e la guardia lo impone qui
  // invece di sperarlo — è la stessa correzione di E2-F5, applicata prima che
  // il difetto nasca anziché dopo.
  "components/FormPrenotazioneManuale.tsx",
  "components/AzioneCancellaPrenotazione.tsx",
];

// Dove il divieto di accessor locali si applica (E2-F5). Puntarlo sul solo
// `griglia.ts` lo metteva **dove il difetto non può nascere**: quel modulo
// non riceve mai una voce dell'API, mentre `CalendarioGriglia.tsx` le riceve
// tutte ed è il file che ha più motivi di ricalcolare. Un
// `new Date(voce.check_in).getDate()` lì dentro — testualmente la
// ricomputazione che AD-14 vieta — lasciava la guardia verde, e nemmeno i
// test di componente lo avrebbero visto: sotto `TZ=UTC` le due computazioni
// coincidono.
const SENZA_ACCESSOR_LOCALI = [
  ...SUPERFICIE_CALENDARIO,
  "lib/calendario/griglia.ts",
  "lib/calendario/oggi.ts",
  "lib/formati.ts",
];

/** Gli accessor locali presenti in un SORGENTE (non in un percorso).
 *
 * Prende il testo e non il file, così la sentinella può farle esaminare un
 * caso costruito: una guardia si verifica facendole trovare qualcosa, non
 * rileggendo la propria lista.
 */
export function accessoriLocaliIn(codice: string): string[] {
  return ACCESSOR_LOCALI.filter((accessor) => codice.includes(accessor));
}

export function orologiIn(codice: string): string[] {
  return OROLOGI.filter((orologio) => codice.includes(orologio));
}

// Valori derivati di DOMINIO che la griglia mostra. Devono venire dal
// contratto: `notti` è la lunghezza dell'intervallo semiaperto (AD-3),
// `ospite_principale` e `altri_ospiti` sono la scelta fra più Ospiti
// registrati, `stato` è la macchina a stati di AD-19.
const DERIVATI_DELLA_VOCE = [
  "notti",
  "stato",
  "ospite_principale",
  "altri_ospiti",
];

// Gli stessi derivati sulla risposta dell'inserimento manuale: `notti` e
// `stato` li decide il server anche lì (AD-14).
const DERIVATI_DELLA_RISPOSTA_MANUALE = ["notti", "stato"];

const DERIVATI_DELLA_VISTA = [
  "ultimo_sync_riuscito_il",
  "stato_sync",
  "feed_collegati",
  "feed_mai_sincronizzati",
  "feed_in_errore",
];

describe("nessuna data di calendario passa dal fuso del browser", () => {
  it.each(SENZA_ACCESSOR_LOCALI)(
    "%s non usa nessun accessor di data locale",
    (file) => {
      expect(accessoriLocaliIn(sorgente(file))).toEqual([]);
    },
  );

  it("la guardia copre la superficie, non solo il modulo delle date", () => {
    // Il difetto di E2-F5 era proprio qui: l'elenco esisteva ma era puntato
    // dove la ricomputazione non può nascere. Se qualcuno restringesse di
    // nuovo il perimetro, questo test lo dice.
    for (const file of SUPERFICIE_CALENDARIO) {
      expect(SENZA_ACCESSOR_LOCALI).toContain(file);
    }
  });

  it.each([
    ["new Date(voce.check_in).getDate()", ".getDate("],
    ["const m = new Date(iso).getMonth();", ".getMonth("],
    ["d.setDate(d.getDate() + 1)", ".getDate("],
    ["data.toLocaleDateString('it-IT')", ".toLocaleDateString("],
  ])("la guardia segnala %s", (finto, atteso) => {
    // Sentinella sulla FUNZIONE, non sulla lista: le si fa esaminare un
    // sorgente costruito e si pretende che lo segnali. La versione
    // precedente confrontava l'elenco con sé stesso e sarebbe rimasta verde
    // anche se la funzione non fosse mai stata applicata a un file.
    expect(accessoriLocaliIn(finto)).toContain(atteso);
  });

  it("la guardia non segnala un sorgente innocuo", () => {
    // L'altra metà: una guardia che segnala tutto non discrimina.
    expect(
      accessoriLocaliIn("const giorno = iso.slice(8, 10); formatGiornoIt(iso);"),
    ).toEqual([]);
  });
});

describe("la superficie Calendario non ha un orologio proprio", () => {
  it.each(SUPERFICIE_CALENDARIO)("%s non legge l'istante corrente", (file) => {
    expect(orologiIn(sorgente(file))).toEqual([]);
  });

  it("la guardia segnala un orologio", () => {
    expect(orologiIn("const adesso = new Date();")).toEqual(["new Date()"]);
    expect(orologiIn("const t = Date.now();")).toEqual(["Date.now("]);
  });

  it("i file sorvegliati esistono davvero", () => {
    // Una guardia puntata su un percorso rinominato passerebbe ispezionando
    // zero file. `readFileSync` solleva, ed è ciò che si pretende qui.
    for (const file of SENZA_ACCESSOR_LOCALI) {
      expect(sorgente(file).length).toBeGreaterThan(0);
    }
  });
});

describe("i valori derivati vengono dal contratto (AD-14)", () => {
  const contratto = sorgente("lib/api/schema.d.ts");

  const blocco = (nome: string) => {
    const inizio = contratto.indexOf(`${nome}: {`);
    expect(inizio, `${nome} assente dal contratto generato`).toBeGreaterThan(-1);
    return contratto.slice(inizio, contratto.indexOf("};", inizio));
  };

  it.each(DERIVATI_DELLA_VOCE)(
    "VoceCalendarioOutput dichiara %s",
    (campo) => {
      expect(blocco("VoceCalendarioOutput")).toContain(campo);
    },
  );

  it.each(DERIVATI_DELLA_VISTA)("CalendarioOutput dichiara %s", (campo) => {
    expect(blocco("CalendarioOutput")).toContain(campo);
  });

  it.each(DERIVATI_DELLA_RISPOSTA_MANUALE)(
    "PrenotazioneManualeOutput dichiara %s",
    (campo) => {
      // La risposta dell'inserimento manuale è l'altra strada per cui gli
      // stessi derivati arrivano al client (Story 2.4). Senza questa riga,
      // togliere `notti` da QUELLA risposta non farebbe cadere nulla — e la
      // strada più breve per rimetterlo in pagina sarebbe che il browser
      // rifaccia il conto sulle due date, cioè AD-14 aggirato dalla porta
      // accanto.
      expect(blocco("PrenotazioneManualeOutput")).toContain(campo);
    },
  );
});

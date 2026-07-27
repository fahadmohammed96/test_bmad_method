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
];

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

const DERIVATI_DELLA_VISTA = [
  "ultimo_sync_riuscito_il",
  "stato_sync",
  "feed_collegati",
  "feed_mai_sincronizzati",
  "feed_in_errore",
];

describe("la griglia non conosce il fuso del browser", () => {
  it("non usa nessun accessor di data locale", () => {
    const codice = sorgente("lib/calendario/griglia.ts");
    const trovati = ACCESSOR_LOCALI.filter((accessor) =>
      codice.includes(accessor),
    );
    expect(trovati).toEqual([]);
  });

  it("non legge l'orologio", () => {
    const codice = sorgente("lib/calendario/griglia.ts");
    expect(OROLOGI.filter((orologio) => codice.includes(orologio))).toEqual([]);
  });

  it("la guardia riconoscerebbe un accessor locale", () => {
    // Sentinella: le si fa esaminare un sorgente costruito e si pretende che
    // lo segnali. Una guardia mai vista mordere è un'affermazione sulla
    // propria correttezza, non un test.
    const finto = "const giorno = new Date(iso).getDate();";
    expect(ACCESSOR_LOCALI.filter((a) => finto.includes(a))).toEqual([
      ".getDate(",
    ]);
  });
});

describe("la superficie Calendario non ha un orologio proprio", () => {
  it.each(SUPERFICIE_CALENDARIO)("%s non legge l'istante corrente", (file) => {
    const codice = sorgente(file);
    expect(OROLOGI.filter((orologio) => codice.includes(orologio))).toEqual([]);
  });

  it("i file sorvegliati esistono davvero", () => {
    // Una guardia puntata su un percorso rinominato passerebbe ispezionando
    // zero file. `readFileSync` solleva, ed è ciò che si pretende qui.
    for (const file of SUPERFICIE_CALENDARIO) {
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
});

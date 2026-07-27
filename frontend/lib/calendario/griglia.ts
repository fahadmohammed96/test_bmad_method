/**
 * Mappatura intervallo → celle della griglia (AC 11, AD-3) — funzioni PURE.
 *
 * Una Prenotazione occupa l'intervallo semiaperto `[check_in, check_out)`:
 * la notte del check-out non è sua. Tradurre quell'intervallo in celle è un
 * off-by-one di presentazione, ed è la ragione per cui vive qui invece che
 * dentro un componente: qui la si prova su ogni confine — attraversamento di
 * mese, di anno, cambio di ora legale — in millisecondi.
 *
 * **Perché le date restano stringhe ISO.** I giorni di calendario sono date
 * locali Europe/Rome (AD-3), non istanti. Costruire un `Date` da `"2026-10-25"`
 * lo interpreta nel fuso del BROWSER, e da lì `getDate()` può restituire il
 * giorno prima: un Host con l'orologio su un fuso a ovest vedrebbe ogni
 * Prenotazione scalata di una cella, e la sera del cambio d'ora la vedrebbero
 * tutti. Qui l'unica aritmetica è sul NUMERO DI GIORNO dall'epoca, calcolato
 * con `Date.UTC`, che di fusi non ne conosce nessuno.
 *
 * `lib/calendario/griglia.guardia.test.ts` impone che resti così: in questo
 * modulo non entra nessun accessor di data locale.
 *
 * Nessun valore di DOMINIO si calcola qui (AD-14): stati, notti e conteggi
 * arrivano dall'API. Questo modulo dispone celle, non decide fatti.
 */

const MILLISECONDI_PER_GIORNO = 86_400_000;

/** Una data di calendario in forma ISO `AAAA-MM-GG`. */
export type GiornoIso = string;

/** Il minimo che serve per collocare qualcosa nella griglia. */
export type Soggiorno = {
  readonly check_in: GiornoIso;
  readonly check_out: GiornoIso;
};

export type Periodo = { readonly da: GiornoIso; readonly a: GiornoIso };

/** Dove una Prenotazione cade nella striscia di giorni visibili. */
export type Collocazione = { readonly inizio: number; readonly celle: number };

export type Segmento<T> =
  | { readonly tipo: "vuoto"; readonly celle: number }
  | { readonly tipo: "voce"; readonly celle: number; readonly voce: T };

/** Numero di giorni dall'epoca. Nessun fuso: `Date.UTC` non ne ha uno. */
function numeroDiGiorno(giorno: GiornoIso): number {
  const [anno, mese, data] = giorno.split("-").map(Number);
  return Date.UTC(anno, mese - 1, data) / MILLISECONDI_PER_GIORNO;
}

function giornoDaNumero(numero: number): GiornoIso {
  return new Date(numero * MILLISECONDI_PER_GIORNO).toISOString().slice(0, 10);
}

/**
 * Giorno della settimana con lunedì = 0.
 *
 * Si deriva dal numero di giorno e non da un accessor: il 1° gennaio 1970 —
 * il giorno numero 0 — è un giovedì, cioè 3 in questa numerazione.
 */
export function giornoDellaSettimana(giorno: GiornoIso): number {
  return (((numeroDiGiorno(giorno) + 3) % 7) + 7) % 7;
}

/** I giorni del periodo, estremi inclusi. */
export function giorniDelPeriodo(periodo: Periodo): GiornoIso[] {
  const primo = numeroDiGiorno(periodo.da);
  const ultimo = numeroDiGiorno(periodo.a);
  if (ultimo < primo) return [];
  const giorni: GiornoIso[] = [];
  for (let numero = primo; numero <= ultimo; numero += 1) {
    giorni.push(giornoDaNumero(numero));
  }
  return giorni;
}

/** Il mese di calendario che contiene `riferimento`, dal 1 all'ultimo. */
export function periodoDelMese(riferimento: GiornoIso): Periodo {
  const [anno, mese] = riferimento.split("-").map(Number);
  const primo = Date.UTC(anno, mese - 1, 1) / MILLISECONDI_PER_GIORNO;
  // Giorno 0 del mese successivo = ultimo giorno di questo. `Date.UTC`
  // normalizza da sé il passaggio d'anno: dicembre → gennaio senza casi
  // speciali da ricordarsi.
  const ultimo = Date.UTC(anno, mese, 0) / MILLISECONDI_PER_GIORNO;
  return { da: giornoDaNumero(primo), a: giornoDaNumero(ultimo) };
}

/** La settimana lunedì → domenica che contiene `riferimento`. */
export function periodoDellaSettimana(riferimento: GiornoIso): Periodo {
  const numero = numeroDiGiorno(riferimento);
  const lunedi = numero - giornoDellaSettimana(riferimento);
  return { da: giornoDaNumero(lunedi), a: giornoDaNumero(lunedi + 6) };
}

/** Sposta di `quanti` mesi, restando sul giorno 1 (il periodo è il mese). */
export function meseSpostato(riferimento: GiornoIso, quanti: number): GiornoIso {
  const [anno, mese] = riferimento.split("-").map(Number);
  return giornoDaNumero(
    Date.UTC(anno, mese - 1 + quanti, 1) / MILLISECONDI_PER_GIORNO,
  );
}

export function settimanaSpostata(
  riferimento: GiornoIso,
  quante: number,
): GiornoIso {
  return giornoDaNumero(numeroDiGiorno(riferimento) + quante * 7);
}

/**
 * Dove cade il soggiorno nella striscia di giorni, o `null` se non la tocca.
 *
 * Le notti sono `[check_in, check_out)`: l'ultima cella occupata è quella
 * del giorno PRIMA del check-out. Il conteggio è **ritagliato** sui giorni
 * visibili — una Prenotazione che comincia il mese prima parte dalla cella 0
 * e non da un indice negativo, e una che sfora a destra si ferma al bordo.
 * Senza il ritaglio, un soggiorno a cavallo produrrebbe una cella con
 * ampiezza maggiore della tabella, e la riga si allungherebbe oltre le
 * altre.
 */
export function collocazione(
  soggiorno: Soggiorno,
  giorni: readonly GiornoIso[],
): Collocazione | null {
  if (giorni.length === 0) return null;
  const primoVisibile = numeroDiGiorno(giorni[0]);
  const ultimoVisibile = numeroDiGiorno(giorni[giorni.length - 1]);
  const primaNotte = numeroDiGiorno(soggiorno.check_in);
  const ultimaNotte = numeroDiGiorno(soggiorno.check_out) - 1;
  if (ultimaNotte < primoVisibile || primaNotte > ultimoVisibile) return null;
  const inizio = Math.max(primaNotte, primoVisibile);
  const fine = Math.min(ultimaNotte, ultimoVisibile);
  return { inizio: inizio - primoVisibile, celle: fine - inizio + 1 };
}

/**
 * Distribuisce le voci in corsie che non si sovrappongono.
 *
 * Due Prenotazioni sovrapposte sulla stessa Struttura esistono già oggi: due
 * portali che vendono la stessa notte sono il difetto che l'Epic esiste per
 * scoprire (FR-5), e la griglia deve poterle mostrare **entrambe** invece di
 * disegnarne una sopra l'altra. Ogni corsia diventa una riga in più sotto la
 * stessa Struttura.
 *
 * L'assegnazione è **prima corsia libera** e dipende dall'ordine in cui le
 * voci arrivano: l'API le ordina in modo stabile apposta, altrimenti le righe
 * salterebbero da una corsia all'altra fra due letture identiche.
 */
export function corsie<T extends Soggiorno>(
  voci: readonly T[],
  giorni: readonly GiornoIso[],
): T[][] {
  const disposte: T[][] = [];
  const occupate: Collocazione[][] = [];
  for (const voce of voci) {
    const dove = collocazione(voce, giorni);
    if (dove === null) continue;
    let indice = 0;
    while (
      indice < occupate.length &&
      occupate[indice].some((altra) => _siSovrappongono(altra, dove))
    ) {
      indice += 1;
    }
    if (indice === occupate.length) {
      occupate.push([]);
      disposte.push([]);
    }
    occupate[indice].push(dove);
    disposte[indice].push(voce);
  }
  return disposte;
}

function _siSovrappongono(una: Collocazione, altra: Collocazione): boolean {
  return (
    una.inizio < altra.inizio + altra.celle &&
    altra.inizio < una.inizio + una.celle
  );
}

/**
 * Una corsia come sequenza di celle: vuoti e voci, in ordine.
 *
 * La somma delle ampiezze è SEMPRE il numero di giorni visibili — è ciò che
 * tiene allineate le colonne fra una riga e l'altra quando le celle occupate
 * usano `colSpan`.
 */
export function segmenti<T extends Soggiorno>(
  corsia: readonly T[],
  giorni: readonly GiornoIso[],
): Segmento<T>[] {
  const collocate = corsia
    .map((voce) => ({ voce, dove: collocazione(voce, giorni) }))
    .filter(
      (riga): riga is { voce: T; dove: Collocazione } => riga.dove !== null,
    )
    .sort((una, altra) => una.dove.inizio - altra.dove.inizio);

  const celle: Segmento<T>[] = [];
  let cursore = 0;
  for (const { voce, dove } of collocate) {
    if (dove.inizio > cursore) {
      celle.push({ tipo: "vuoto", celle: dove.inizio - cursore });
    }
    celle.push({ tipo: "voce", celle: dove.celle, voce });
    cursore = dove.inizio + dove.celle;
  }
  if (cursore < giorni.length) {
    celle.push({ tipo: "vuoto", celle: giorni.length - cursore });
  }
  return celle;
}

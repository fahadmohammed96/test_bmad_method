/**
 * Formati italiani (UX-DR11, NFR-9): date gg/mm/aaaa, valuta € con virgola
 * decimale. Unico punto di formattazione: i componenti non formattano a mano.
 */

const formatoData = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Rome",
});

const formatoEuro = new Intl.NumberFormat("it-IT", {
  style: "currency",
  currency: "EUR",
});

const formatoOra = new Intl.DateTimeFormat("it-IT", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

/** Data in formato italiano: 25/07/2026. */
export function formatDataIt(data: Date): string {
  return formatoData.format(data);
}

/**
 * Data di calendario ISO `AAAA-MM-GG` → "25/07/2026".
 *
 * Riordina i pezzi della stringa e non passa da `Date`: le date di
 * Prenotazione sono date locali Europe/Rome (AD-3), non istanti, e
 * costruirci un `Date` le farebbe interpretare nel fuso del browser — dove,
 * a ovest di Greenwich, il 25 diventa il 24.
 */
export function formatGiornoIt(giorno: string): string {
  const [anno, mese, data] = giorno.split("-");
  return `${data}/${mese}/${anno}`;
}

/** Orario locale Europe/Rome: "14:35" — è l'HH:MM di «ultimo aggiornamento». */
export function formatOraIt(istante: Date): string {
  return formatoOra.format(istante);
}

/** Importo in centesimi interi (convenzione `_cent`) → "1.234,56 €". */
export function formatEuroCent(cent: number): string {
  if (!Number.isInteger(cent)) {
    throw new TypeError("importo non intero: gli importi viaggiano in centesimi");
  }
  return formatoEuro.format(cent / 100);
}

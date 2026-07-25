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

/** Data in formato italiano: 25/07/2026. */
export function formatDataIt(data: Date): string {
  return formatoData.format(data);
}

/** Importo in centesimi interi (convenzione `_cent`) → "1.234,56 €". */
export function formatEuroCent(cent: number): string {
  if (!Number.isInteger(cent)) {
    throw new TypeError("importo non intero: gli importi viaggiano in centesimi");
  }
  return formatoEuro.format(cent / 100);
}

/**
 * L'unico punto della superficie Calendario che legge l'orologio del client.
 *
 * Serve a una cosa sola: decidere su quale mese aprire la griglia. È
 * navigazione, non dominio — nessun valore mostrato all'Host dipende da qui,
 * e in particolare non ci dipende «dati aggiornati alle HH:MM», che arriva
 * dall'API (AD-14, NFR-2).
 *
 * Sta in un modulo suo perché la guardia strutturale
 * (`griglia.guardia.test.ts`) vieta l'orologio nel resto della superficie: un
 * `new Date()` dentro il componente che disegna l'etichetta del timestamp
 * sarebbe la falsa sincronia nella sua forma più pura — «aggiornato adesso»
 * perché è adesso. Concentrarlo qui rende quella regola verificabile invece
 * che raccomandata.
 *
 * Il fuso è dichiarato: le date di calendario sono Europe/Rome (AD-3), non
 * quelle del browser di chi guarda. `en-CA` è la locale che rende
 * `AAAA-MM-GG`, cioè la forma che il resto del modulo si aspetta.
 */
const FORMATO_ISO = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Rome",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function oggiIso(): string {
  return FORMATO_ISO.format(new Date());
}

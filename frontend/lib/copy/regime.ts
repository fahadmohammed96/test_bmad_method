/** Copy it-IT del Regime fiscale (FR-17, UX-DR14). */
export const regimeCopy = {
  titolo: "Regime fiscale",
  strutture: (n: number) =>
    n === 1 ? "1 Struttura attiva" : `${n} Strutture attive`,
  sogliaEtichetta: "Soglia",
  aliquoteEtichetta: "Aliquote citate",
  nonDisponibile: "Non ancora disponibile",
  disponibile: "Informativo",

  // Pannello a schermo intero alla transizione (UX-DR14).
  transizioneTitolo: "Con 3 Strutture cambia il tuo regime fiscale",
  transizioneTitoloGenerico: (soglia: number) =>
    `Con ${soglia} Strutture cambia il tuo regime fiscale`,
  hoCapito: "Ho capito, continua",
  parlaConCommercialista: "Parlane con un commercialista",
} as const;

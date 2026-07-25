/** Copy it-IT della configurazione normativa (FR-2, AD-9, UX §5.1). */
export const configurazioneCopy = {
  titolo: "Adempimenti configurati per te",
  tassaTitolo: "Tassa di soggiorno",
  istatTitolo: "Rilevazione ISTAT",
  configurata: "Configurata",
  nonDisponibile: "Non ancora configurata",
  promemoriaManuale: "Te lo ricorderemo: per ora si gestisce a mano.",
  importoPerNotte: "a persona, per notte",
  periodicitaEtichetta: "Periodicità",
  esenzioneEta: (eta: number) => `Esenti i minori di ${eta} anni`,
  esenzioneNotti: (notti: number) => `Esenti le notti oltre la ${notti}ª`,
  tracciatoEtichetta: "Tracciato",
  periodicita: {
    mensile: "Mensile",
    trimestrale: "Trimestrale",
    semestrale: "Semestrale",
    annuale: "Annuale",
  },
} as const;

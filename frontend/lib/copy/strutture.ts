/** Copy it-IT del modulo Strutture (FR-1, UX-DR3, UX-DR4). */
export const struttureCopy = {
  titolo: "Strutture",
  sottotitolo: "Da 1 a 3 appartamenti attivi nel pilota.",
  nessuna: "Non hai ancora registrato Strutture. Inizia dalla prima!",
  nuova: "Nuova Struttura",
  capRaggiunto:
    "Il pilota copre da 1 a 3 Strutture attive: archivia una Struttura per registrarne una nuova.",
  statoAttiva: "Attiva",
  statoArchiviata: "Archiviata",
  cinMancante: "CIN mancante",
  cinMancanteNota: "Puoi aggiungerlo in ogni momento: non blocca nulla.",
  modifica: "Modifica",
  archivia: "Archivia",
  archiviaConferma:
    "La Struttura resterà nello storico ma uscirà dal conteggio delle attive. Continuare?",
  salva: "Salva",

  // Wizard di registrazione (UX-DR3): guidato, con progress, sempre leggero.
  wizardTitolo: "Registra una Struttura",
  wizardPasso: (corrente: number, totale: number) =>
    `Passo ${corrente} di ${totale}`,
  wizardAvanti: "Avanti",
  wizardIndietro: "Indietro",
  wizardRegistra: "Registra la Struttura",
  wizardSaltaCin: "Salta per ora e registra",
  nomeEtichetta: "Nome della Struttura",
  nomeAiuto: "Come la chiami tu: es. “Bologna Centro”.",
  comuneEtichetta: "Comune",
  regioneEtichetta: "Regione",
  regioneSegnaposto: "Scegli la Regione",
  comuneAiutoTitolo: "Perché li chiediamo?",
  comuneAiuto:
    "Tassa di soggiorno e rilevazione ISTAT dipendono dal Comune e dalla Regione della Struttura: li useremo per configurare i tuoi adempimenti.",
  cinEtichetta: "CIN (Codice Identificativo Nazionale)",
  cinAiutoTitolo: "Cos'è il CIN?",
  cinAiuto:
    "È il codice nazionale della tua Struttura ricettiva, da esporre negli annunci. Se non lo hai ancora, puoi aggiungerlo più tardi: la registrazione non si blocca.",
} as const;

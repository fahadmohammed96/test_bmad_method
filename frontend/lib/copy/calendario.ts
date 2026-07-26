/** Copy it-IT del collegamento dei Feed iCal (FR-3, UJ-1, NFR-2). */
export const calendarioCopy = {
  feedTitolo: "Calendari collegati",
  feedSottotitolo:
    "Incolla l'indirizzo del calendario esportato da Airbnb o Booking: importiamo subito le prenotazioni.",
  urlEtichetta: "Indirizzo del calendario (iCal)",
  urlAiuto:
    "Lo trovi nel portale, alla voce «esporta calendario». Inizia con http:// o https://.",
  canaleEtichetta: "Canale",
  canale: {
    airbnb: "Airbnb",
    booking: "Booking",
    altro: "Altro",
  },
  collega: "Collega il calendario",
  nessunFeed: "Nessun calendario collegato a questa Struttura.",
  // Distinto da `nessunFeed`: «non ci sono calendari» e «non riusciamo a
  // leggerli» sono affermazioni diverse, e confonderle fa dire al
  // prodotto una cosa falsa sullo stato del calendario dell'Host.
  feedNonCaricati:
    "Non riusciamo a caricare i calendari collegati a questa Struttura. Riprova fra poco: i calendari collegati non sono stati toccati.",

  // Progresso dell'import (UJ-1): dal collegamento alla prova che ha funzionato.
  importoInCorso: "Importazione in corso…",
  maiSincronizzato: "Mai sincronizzato",
  importate: (quante: number, orario: string) =>
    quante === 1
      ? `Importata 1 prenotazione — ultimo aggiornamento ${orario}`
      : `Importate ${quante} prenotazioni — ultimo aggiornamento ${orario}`,

  // NFR-2: il sistema dice «non so» invece di tacere in modo ambiguo.
  nonRiuscito: "Ultimo tentativo non riuscito",
  errore: {
    url_non_raggiungibile:
      "Non riusciamo a raggiungere questo indirizzo. Controlla di averlo copiato per intero dal portale.",
    timeout:
      "Il portale non ha risposto in tempo. Riproviamo al prossimo aggiornamento.",
    risposta_troppo_grande:
      "Il calendario ricevuto è troppo grande per essere importato.",
    esito_http_inatteso:
      "Il portale ha risposto in modo inatteso. Verifica che il link del calendario sia ancora valido.",
    feed_non_valido:
      "Il calendario ricevuto è incompleto: non abbiamo modificato nulla delle tue prenotazioni.",
    feed_senza_eventi:
      "Il calendario ricevuto non contiene prenotazioni identificabili: non abbiamo modificato nulla delle tue prenotazioni.",
  },

  rimosseDalFeed: (quante: number) =>
    quante === 1
      ? "1 prenotazione non è più nel calendario del portale: l'abbiamo conservata."
      : `${quante} prenotazioni non sono più nel calendario del portale: le abbiamo conservate.`,
  eventiMalformati: (quanti: number) =>
    quanti === 1
      ? "1 evento del calendario non era leggibile e non è stato importato."
      : `${quanti} eventi del calendario non erano leggibili e non sono stati importati.`,
  ricorrentiNonEspansi: (quanti: number) =>
    quanti === 1
      ? "1 evento ricorrente è stato importato come singola prenotazione."
      : `${quanti} eventi ricorrenti sono stati importati come singole prenotazioni.`,
} as const;

/**
 * Copy it-IT dell'app shell (spine Consistency: le stringhe di dominio
 * vivono in moduli copy per feature, mai hardcoded nei componenti).
 */
export const appCopy = {
  nome: "HostPilot",
  descrizione:
    "Gestionale per host di affitti brevi: calendario unificato, adempimenti italiani, regole di prezzo e operatività.",
  scaffoldEtichetta: "Fondamenta del progetto",
  scaffoldNota:
    "Questo è il punto di partenza di HostPilot: struttura, contratto API e strumenti sono pronti. La navigazione e la Dashboard arrivano con la Story 1.3.",
} as const;

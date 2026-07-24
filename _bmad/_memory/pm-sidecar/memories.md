# Memorie — John — Product Manager (Fase 2 Planning, leader squad)

_Fatti durevoli e decisioni apprese durante il progetto HostPilot. Un fatto per voce, con data. Aggiornare via PR. Non duplicare `docs/project-context.md`._

<!-- Esempio:
- 2026-07-24 — <fatto appreso e perché conta>.
-->

- 2026-07-24 — PRD HostPilot v1 consegnato (`docs/prd.md`, draft) in attesa del gate **G2** (approvato insieme alla UX Spec di Sally). Cinque decisioni di prodotto lasciate esplicitamente a Fahad: **G2-A** livello di automazione degli adempimenti (raccomandato: promemoria + compilazione assistita, invio automatico come fast-follow dove sostenibile — Alloggiati Web ha un web service, gli altri portali sono eterogenei); **G2-B** perimetro iniziale Comuni/Regioni; **G2-C** profondità segnalazione regime fiscale 3° immobile; **G2-D** retention documenti d'identità; **G2-E** target metriche. Conta perché al ritorno del gate questi sono i bivi su cui iterare, non ridiscutere lo scope.
- 2026-07-24 — Vincolo di prodotto ereditato dal brief e riflesso nel PRD: tutto ciò che è normativo (aliquote tassa di soggiorno, tracciati ISTAT/Regione, termini Alloggiati Web) è **configurabile, mai hardcoded** (NFR-4) — così una correzione post-verifica del commercialista non richiede rilascio di codice. Le fonti normative del brief sono editoriali, non primarie: verifica legale obbligatoria prima dell'implementazione compliance (Fase 3/4), non prima del PRD.

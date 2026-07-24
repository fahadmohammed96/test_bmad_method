# Memorie — Winston — System Architect (Fase 3 Solutioning)

_Fatti durevoli e decisioni apprese durante il progetto HostPilot. Un fatto per voce, con data. Aggiornare via PR. Non duplicare `docs/project-context.md`._

<!-- Esempio:
- 2026-07-24 — <fatto appreso e perché conta>.
-->

- 2026-07-24 — Gli esiti espliciti delle [DECISIONE G2-A…E] del PRD non sono registrati nel repo (PRD/UX mergiati con frontmatter `draft`): l'architettura di Fase 3 è stata progettata parametrica rispetto a G2-A/B/D; gli esiti vanno fatti registrare al più tardi al gate G3. Conta perché ogni artefatto a valle rischia di poggiare su raccomandazioni scambiate per decisioni.
- 2026-07-24 — WS_ALLOGGIATI è un web service SOAP ufficiale della Polizia di Stato (manuale su questure.poliziadistato.it, endpoint Service.asmx, GenerateToken con WSKEY per account attivata dal portale): l'invio automatico Alloggiati Web ha un canale ufficiale — la scelta di tenerlo fast-follow è di rischio/legale, non di fattibilità tecnica.
- 2026-07-24 — Cassazione SS.UU. ord. n. 1527 del 23/01/2026 confermata su fonte primaria durante il reviewer gate: l'host è responsabile d'imposta per la tassa di soggiorno anche se l'ospite non paga; il Modello 21 è abolito, resta la dichiarazione annuale telematica all'AdE. Impatta il modello del registro tassa.
- 2026-07-24 — Il reviewer gate multi-lente (riconciliazione PRD/UX + rubrica + verifica web + attacco avversariale in subagent paralleli) ha trovato buchi reali che il drafting aveva mancato (archi del grafo dipendenze, ownership entità, lifecycle Prenotazione, semantica di cancellazione, pin di stack stantii): da rifare a ogni spine futuro, non è cerimonia.


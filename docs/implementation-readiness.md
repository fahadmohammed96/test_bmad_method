---
title: 'Implementation Readiness Report — HostPilot'
status: approved
gate: G3
gate_status: 'gate G3 approvato da Fahad (2026-07-24). R-5 (owner verifica legale) e il set G2-B chiusi il 2026-07-25 (issue MYL-33, registrati in PRD §14.1): nessun punto di gate resta aperto. Mandato R-5 ESTESO il 2026-07-26 (MYL-40, PRD §14.2): base giuridica dei contatti Ospite e retention dell''anagrafica.'
created: 2026-07-24
updated: 2026-07-26
assessor: John — Product Manager (leader squad), con l'architettura di Winston
phase: '3 · Solutioning (co-artefatto del gate G3)'
stepsCompleted: ['step-01-document-discovery', 'step-02-prd-analysis', 'step-03-epic-coverage-validation', 'step-04-ux-alignment', 'step-05-epic-quality-review', 'step-06-final-assessment']
inputDocuments:
  - docs/prd.md
  - docs/ux-spec.md
  - docs/architecture.md
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md
  - docs/epics.md
  - docs/project-brief.md
  - docs/project-context.md
---

# Implementation Readiness Assessment Report

**Data:** 2026-07-24
**Progetto:** HostPilot — Pilota BMAD Squad
**Assessor:** John (PM, leader squad), in riconciliazione con l'Architecture Spec di Winston

Verifica di prontezza per la Fase 4 (Implementation, Amelia): PRD, UX Spec, Architettura, Epics e Stories sono **completi, allineati e tracciabili**? Questo report è il terzo artefatto del gate **G3**, insieme all'Architettura (`docs/architecture.md`) e agli Epics/Stories (`docs/epics.md`). Segue il metodo `bmad-check-implementation-readiness` (discovery → PRD → coverage → UX → qualità epic → assessment finale).

---

## Step 1 — Document Discovery

| Documento | File | Stato | Note |
| --- | --- | --- | --- |
| Project Brief | `docs/project-brief.md` | ✅ presente | approvato G1 (main) |
| Project Context | `docs/project-context.md` | ✅ presente | costituzione (main) |
| PRD | `docs/prd.md` | ✅ presente | frontmatter `draft`, gate G2 (main) |
| UX Spec | `docs/ux-spec.md` | ✅ presente | frontmatter `draft`, gate G2 (main) |
| Architettura | `docs/architecture.md` + `docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md` + `.memlog.md` | ✅ presente | **PR #6, non ancora mergiata** — co-input del G3 |
| Epics & Stories | `docs/epics.md` | ✅ presente | questo bundle G3 |

**Duplicati:** nessuno (nessuna coppia whole+sharded in conflitto). **Documenti mancanti:** nessuno tra quelli richiesti.

**Nota di consegna (non un difetto):** l'Architecture Spec vive nella PR #6 e gli Epics/Readiness in questa PR. Il gate **G3 approva i tre artefatti insieme**: le due PR vanno **mergiate insieme** da Fahad. Finché la PR #6 non è mergiata, `docs/architecture.md` non è su `main`; è coerente con la sequenza di fase, non un'incoerenza.

---

## Step 2 — PRD Analysis

### Functional Requirements (19)

FR-1 Registrazione Strutture (cap 3) · FR-2 Anagrafica Comune/Regione · FR-3 Import Feed iCal · FR-4 Calendario unificato · FR-5 Rilevazione Conflitti · FR-6 Finestra di riconciliazione · FR-7 Prenotazioni manuali · FR-8 Definizione Regole di prezzo · FR-9 Calcolo/anteprima prezzo · FR-10 Esportazione prezzi · FR-11 Alloggiati Web · FR-12 Tassa di soggiorno · FR-13 ISTAT/ROSS1000 · FR-14 CIN · FR-15 Cruscotto Adempimenti · FR-16 Livello di automazione · FR-17 Regime fiscale · FR-18 Turni di pulizia · FR-19 Messaggi automatici. **Totale: 19.**

### Non-Functional Requirements (16)

NFR-1 Affidabilità sync · NFR-2 Verità temporale OTA · NFR-3 Affidabilità notifiche/scadenze · NFR-4 Configurabilità normativa · NFR-5 Usabilità non tecnica · NFR-6 Sicurezza dati personali · NFR-7 Osservabilità compliance · NFR-8 Accessibilità · NFR-9 Localizzazione · NFR-10…16 Privacy/GDPR (base giuridica, minimizzazione, retention, cifratura, controllo accessi, diritti interessato, no dati reali nei test). **Totale: 16.**

### Additional Requirements / Constraints

- Vincoli G1 (PRD §2, §14): copertura normativa "in regola" nell'MVP; 4 Adempimenti; soglia 3 immobili con regimi fiscali differenziati.
- 5 decisioni di prodotto aperte **G2-A…E** (PRD §14) e 7 rischi (PRD §12), tra cui fonti normative non primarie → verifica legale prima dell'implementazione compliance.
- Non-Goals espliciti (PRD §8): no channel manager bidirezionale, no commercialista, no PMS multi-unità, no pagamenti/fatturazione, no emissione CIN.

### PRD Completeness Assessment

PRD completo, ben strutturato, requisiti numerati e stabili con "Consequences (testable)". Le lacune sono **decisioni di prodotto note e marcate** (`[DECISIONE G2]`, `[ASSUNZIONE]`), non omissioni. Idoneo come input per epics e architettura.

---

## Step 3 — Epic Coverage Validation

### Matrice di copertura FR → Epic/Story

| FR | Requisito (sintesi) | Copertura Epic/Story | Stato |
| --- | --- | --- | --- |
| FR-1 | Registrazione Strutture (cap 3) | Epic 1 — 1.4 | ✅ |
| FR-2 | Anagrafica Comune/Regione | Epic 1 — 1.5 | ✅ |
| FR-3 | Import Feed iCal | Epic 2 — 2.1, 2.2 | ✅ |
| FR-4 | Calendario unificato | Epic 2 — 2.3 | ✅ |
| FR-5 | Rilevazione Conflitti | Epic 2 — 2.5, 2.6 | ✅ |
| FR-6 | Finestra di riconciliazione | Epic 2 — 2.7 | ✅ |
| FR-7 | Prenotazioni manuali | Epic 2 — 2.4 | ✅ |
| FR-8 | Definizione Regole di prezzo | Epic 4 — 4.1 | ✅ |
| FR-9 | Calcolo/anteprima prezzo | Epic 4 — 4.2 | ✅ |
| FR-10 | Esportazione prezzi | Epic 4 — 4.3 | ✅ |
| FR-11 | Alloggiati Web | Epic 3 — 3.5 (+3.4 privacy) | ✅ |
| FR-12 | Tassa di soggiorno | Epic 3 — 3.6 | ✅ |
| FR-13 | ISTAT/ROSS1000 | Epic 3 — 3.7 | ✅ |
| FR-14 | CIN | Epic 3 — 3.3 | ✅ |
| FR-15 | Cruscotto Adempimenti | Epic 3 — 3.1, 3.2, 3.8 | ✅ |
| FR-16 | Livello di automazione | Epic 3 — 3.1 | ✅ |
| FR-17 | Regime fiscale | Epic 1 — 1.6 | ✅ |
| FR-18 | Turni di pulizia | Epic 5 — 5.1 | ✅ |
| FR-19 | Messaggi automatici | Epic 5 — 5.2 | ✅ |

### Copertura NFR → Story

| NFR | Copertura |
| --- | --- |
| NFR-1 (affidabilità sync) | 2.2 (job durevole, resilienza), 2.1 (idempotenza) |
| NFR-2 (verità temporale) | 2.1, 2.2, 2.3, 2.7, 2.8 |
| NFR-3 (affidabilità notifiche/scadenze) | 2.6, 3.2 |
| NFR-4 (configurabilità normativa) | 1.5, 3.6, 3.7, 3.5 (termini) |
| NFR-5 (usabilità non tecnica) | 1.3, 1.4 (onboarding guidato); target numerici → **aperto G2-E (R-7)** |
| NFR-6 (sicurezza dati personali) | 3.4 |
| NFR-7 (osservabilità compliance) | 3.1, 3.8 |
| NFR-8 (accessibilità WCAG 2.1 AA) | ACs distribuiti su 2.7, 3.2, 3.5 (UX-DR4/9/10); **nessuna story a11y dedicata → R-7** |
| NFR-9 (localizzazione) | 1.3 |
| NFR-10…16 (GDPR) | 3.4 (+3.5, 3.8) — **documenti d'identità**. Dal 2026-07-26 anche **2.3** (+2.4) per l'**anagrafica Ospite**: NFR-11 minimizzazione, NFR-12 retention per azzeramento, NFR-14 accesso del solo Host, NFR-15 diritti dell'interessato, NFR-16 nessun dato reale nei test — invariante **AD-21**, decisione MYL-40 (PRD §14.2). I due regimi restano distinti: `ospite_documento` (AD-11) ≠ anagrafica (AD-21) |

### Statistiche di copertura

- FR totali PRD: **19** — coperti negli Epic: **19** — **copertura 100%**.
- NFR totali PRD: **16** — indirizzati: **16** (NFR-5 e NFR-8 con riserve tracciate in R-7).
- FR presenti negli Epic ma non nel PRD: **0** (nessun scope creep). Un solo requisito **derivato** non-PRD è tracciato: pannello Account/preferenze (Story 1.3) → da ratificare come FR (R-3).

---

## Step 4 — UX Alignment

**Stato UX:** ✅ presente (`docs/ux-spec.md`), co-input del G2, mirrorata dagli Epic.

### UX ↔ PRD

- Le UX Spec mirrorano **verbatim** gli ID UJ-1…UJ-5 del PRD (UX §3) e usano il Glossario PRD §4 senza sinonimi. Nessuna divergenza di vocabolario.
- I gap che la UX Spec dichiara (UX §7.3) sono **estensioni di dettaglio o dipendenze da decisioni già note del PRD** (retention G2-D, profondità Regime fiscale G2-C, automazione G2-A, precedenza prezzi), non conflitti — confermato qui.

### UX ↔ Architettura

- L'architettura **supporta** tutti i vincoli UX di specifica: badge testo+icona (design system §8 → AD-14 stati come campo API), countdown/urgenza server-side (`livello_urgenza`, AD-14/AD-3), verità temporale "dati aggiornati alle HH:MM" (AD-4), pattern compliance senza falsa certezza (AD-7/AD-8), flusso dati identità minimizzato (AD-11), responsive/densità 1-3 Strutture (frontend).
- La raccomandazione UX UJ-2 (ri-verifica dopo `gestito`) è stata **accolta** dall'architettura (AD-5) e portata in Story 2.7. Allineamento pieno.

### Warning UX

- **NFR-8 accessibilità**: baseline WCAG 2.1 AA confermata da Sally, ma i criteri a11y sono **distribuiti** nelle story di UI, senza una story/strategia di verifica a11y dedicata → **R-7** (raccomando coinvolgimento di Murat/TEA).
- **NFR-5 usabilità**: i target numerici (onboarding ≤10min, riconciliazione ≤3 interazioni, Alloggiati ≤2min) sono **proposte di Sally da confermare** con **G2-E**, non decisi → **R-7**.

---

## Step 5 — Epic Quality Review

Valutazione rispetto agli standard `bmad-create-epics-and-stories`.

### A. Valore utente (non milestone tecnici)

- ✅ I 5 Epic sono orientati al valore utente ("collega gli appartamenti", "evita la doppia prenotazione", "resta in regola", "imposta i prezzi", "coordina l'operatività").
- ⚠️ **Nota (accettata, non difetto):** Epic 1 front-carica fondamenta tecniche nelle Story 1.1 (scaffolding) e 1.2 (auth). È l'**eccezione sanzionata** dallo standard: progetto greenfield con starter template → "Epic 1 Story 1 = set up from starter template". Le fondamenta sono **just-in-time** (solo l'infrastruttura e le tabelle necessarie a Epic 1), e l'Epic nel suo insieme consegna valore utente (registrazione + gestione Strutture + Regime fiscale). Nessun Epic "Database Setup" o "API Development" separato e privo di valore.

### B. Indipendenza degli Epic

- ✅ Epic 1 è autoconsistente; Epic 2/3/4/5 costruiscono su Epic 1 e sono **indipendenti tra loro**. Nessun Epic richiede feature di un Epic successivo.
- ⚠️ **Riuso `notifiche`:** Epic 3 (promemoria) ed Epic 5 (messaggi) riusano la fondazione `notifiche` introdotta in **Story 2.6** (Epic 2). Mitigazione **documentata in `epics.md`**: se un Epic diverso da Epic 2 fosse consegnato per primo dopo Epic 1, la Story 2.6 va anticipata come sua prima Story. Non è una dipendenza in avanti (Epic 2 è raccomandato per primo), ma è una nota di sequenziamento esplicita.

### C. Dipendenze in avanti (forward dependencies)

- ✅ **Nessuna forward dependency** rilevata. Ogni Story dipende solo da Story **precedenti** (stesso Epic) o da Epic già consegnati.
- Punto verificato: FR-1 (§PRD) dice "CIN assente ⇒ Adempimento aperto", ma l'entità `adempimento` nasce in Epic 3. Risolto **senza forward dep**: Story 1.4 registra il campo CIN e mostra un indicatore "CIN mancante" autoconsistente; il tracciamento come Adempimento completo (FR-14) è Story 3.3, che costruisce sul campo già esistente. Documentato esplicitamente nelle due story.
- Punto verificato: il "check-in registrato" (trigger Alloggiati) è l'azione dell'Host sulla Prenotazione (`calendario`, esistente da Epic 2), consumata dall'Adempimento in Story 3.5 — cross-modulo ma non forward (AD-17).

### D. Sizing e AC

- ✅ Story dimensionate per un singolo agente dev; AC in formato **Given/When/Then**, testabili, con edge case ed errori (URL invalido, movimento zero, documento illeggibile, feed vuoto, regola di prezzo in conflitto, contatto Ospite mancante).
- ✅ Ogni AC referenzia FR/NFR/AD/UX-DR specifici (tracciabilità mantenuta).

### E. Timing creazione tabelle (just-in-time)

- ✅ Nessuna story crea "tutte le tabelle in anticipo". 1.1 posa solo infrastruttura `core` (outbox, job) senza tabelle di dominio; ogni tabella nasce nella prima story che la usa (`struttura`→1.4, `comune/regione_config`→1.5, `feed_ical/prenotazione/sync_run`→2.1, `conflitto`→2.5, `adempimento/evento_compliance`→3.1, `ospite_documento`→3.4, `regola_prezzo`→4.1, `turno_pulizia/messaggio`→5.1/5.2). Conforme.

### F. Starter template

- ✅ L'architettura specifica lo starter (template di squadra `frontend-next`, `backend-fastapi`) → **Story 1.1** è esplicitamente lo scaffolding (clone/init dai template, dipendenze, CI, migrazioni). Conforme.

### Violazioni

- 🔴 Critiche: **nessuna.**
- 🟠 Maggiori: **nessuna.** (Le due note B/riuso e A/front-load fondamenta sono sanzionate dallo standard e mitigate/documentate.)
- 🟡 Minori: accessibilità e usabilità senza story/strategia di verifica dedicata (R-7); vocabolario esteso da registrare (R-2).

---

## Punti di riconciliazione tra artefatti (finding di readiness)

Questi non sono difetti di planning: sono i **bivi che il gate umano G3 deve chiudere** e le precisazioni da mettere per iscritto. Alcuni li ha già segnalati Winston (Architecture §9.3); li consolido qui come lista d'azione per Fahad.

- **R-1 — Esiti delle [DECISIONE G2-A…E] da registrare.** PRD e UX Spec sono mergiati ma con frontmatter `draft` e le decisioni presentate come opzioni. Vanno chiuse e **messe per iscritto al G3** (idealmente aggiornando i frontmatter di PRD/UX a `approved` nella stessa PR degli esiti). *Owner: Fahad (decisione) + John (registrazione).*
- **R-2 — Estensioni del Glossario da registrare.** Stato Conflitto `decaduto`; stati Prenotazione `attiva/cancellata/rimossa_dal_feed`; archiviazione Struttura. Non contraddicono il PRD; vanno aggiunti al Glossario (PRD §4 o addendum) così le story/UI usano il vocabolario uniforme. *Owner: John, via PR.*
- **R-3 — Pannello Account/preferenze di notifica senza FR.** UX §2.3 `[GAP PRD]`, Architecture §9.3 raccomanda una FR minima. Rappresentato come Story 1.3 ma senza FR nel PRD. **Raccomando a Fahad di ratificare una FR minima (es. FR-20) al G3** per tracciabilità. *Owner: Fahad (scope) + John.*
- **R-4 — Decisioni architetturali [G3-1…5] da ratificare.** Stack (G3-1), precedenza Regole di prezzo (G3-2), retention default 30/90 (G3-3), monorepo (G3-4), parametri operativi sync 15'/ri-verifica 24h (G3-5). Le Story sono **parametriche**; la ratifica non cambia gli invarianti dello spine. *Owner: Fahad, con raccomandazioni di Winston in Architecture §10.*
- **R-5 — Verifica legale + retention (G2-D) come gate di rilascio compliance.** Le fonti normative sono editoriali, non primarie (PRD §12.1). Catturato come **Story 3.9** (gate di rilascio, non di sviluppo). **CHIUSO il 2026-07-25** (MYL-33, PRD §14.1): owner = **il commercialista di Fahad**, con mandato esplicito (termini Alloggiati 24h/6h, tassa di soggiorno dei Comuni G2-B, ISTAT, CIN, regime fiscale/soglia 3 immobili) e obbligo di segnalare se la **retention documenti Ospiti (G2-D)** richiede un **parere privacy separato** — è GDPR, non materia fiscale. Ingaggio a cura di Fahad, risposta attesa **entro la fine dell'Epic 2**. Resta un gate di **rilascio**, non di sviluppo. *Owner: Fahad (ingaggio) → commercialista (risposta).*
  - **MANDATO ESTESO il 2026-07-26** (MYL-40, PRD §14.2 — decisione "anagrafica Ospite, opzione B"). Due punti si aggiungono ai cinque di §14.1, **senza sostituirli**, e sono **materia privacy, non fiscale**: (a) la **base giuridica del trattamento dei contatti dell'Ospite** (nome, email, telefono) per i Messaggi automatici (FR-19) e la precompilazione degli Adempimenti — trattamento **distinto** dall'obbligo legale che copre i documenti d'identità (NFR-10), e riguardante dati personali **di terzi**, non del cliente; (b) la **retention dell'anagrafica Ospite**, separata da quella dei documenti (G2-D) e parametrica sul ciclo della Prenotazione. **Se il commercialista non copre questi due punti, va segnalato a Fahad come parere privacy separato** — vale qui la stessa regola di G2-D: una risposta rassicurante data fuori competenza vale meno del silenzio. **L'anagrafica si sviluppa** (Story 2.3/2.4, parametri configurabili): il gate resta di **rilascio**.
  - **Il punto (b) ha una cifra da confermare, non una domanda aperta** (aggiornato il 2026-07-26, MYL-46): lo spine registra la retention dell'anagrafica come invariante **AD-21** e propone **90 giorni** come valore iniziale provvisorio, con decorrenza al `check_out` o all'uscita da `attiva` se precedente. Al parere si chiede se quel valore è difendibile per la base giuridica del punto (a) e, se no, quale sia. Conseguenza di prodotto da mettere davanti a Fahad insieme alla risposta: **alla scadenza lo storico del calendario perde i nomi** (si presenta "Ospite non indicato"), quindi un valore breve è la scelta prudente sui dati e costosa sull'esperienza dell'Host. È un parametro: la revisione non richiede un rilascio.
- **R-6 — Billing dell'abbonamento SaaS.** Il prodotto è "in abbonamento" ma nessuna FR copre pagamento/gestione abbonamenti. Assunzione: pilota gestito manualmente (nessun impatto architetturale ora). **Da decidere post-pilota.** *Owner: Fahad, post-pilota.*
- **R-7 — Strategia di test per usabilità (NFR-5, G2-E) e accessibilità (NFR-8).** Target usabilità non fissati (G2-E); criteri a11y distribuiti senza verifica dedicata. **Raccomando di coinvolgere Murat (modulo TEA)** per una strategia di test risk-based su compliance, a11y e usabilità prima/durante la Fase 4. *Owner: John (routing) → Murat.*
- **R-8 — Aspettativa "channel manager".** Il push prezzi/disponibilità verso OTA è Non-Goal esplicito (PRD §8/§9.2) ma emotivamente rilevante per l'host. Nessun blocco: assicurarsi che la UX comunichi bene l'aspettativa (export manuale). *Owner: Sally/John in Fase 4.*

---

## Summary and Recommendations

### Overall Readiness Status

**PRONTO PER IL GATE G3 — NON ANCORA PRONTO PER APRIRE LA FASE 4.**

I tre artefatti del bundle G3 (Architettura, Epics/Stories, Readiness) sono **internamente completi, allineati e tracciabili**: copertura FR **100%** (19/19), NFR indirizzati (16/16, con R-7 tracciato), **nessuna dipendenza in avanti**, **nessun Epic tecnico privo di valore**, starter template e timing tabelle conformi, AC testabili. Non ci sono difetti di planning critici o maggiori.

L'implementazione (Fase 4) **non deve però iniziare** finché il gate umano G3 non chiude e registra le decisioni aperte **R-1, R-3, R-4** (e ingaggia R-5). È lo stato **progettato** dal metodo, non una lacuna: i gate sono umani e guidati dai documenti (`project-context.md` §2). Nessuno scaffolding applicativo (Story 1.1) prima dell'approvazione.

### Critical Issues Requiring Immediate Action

Nessun *difetto* critico negli artefatti. Le **azioni di gate** indispensabili prima della Fase 4 sono:
1. **R-1** — chiudere e registrare G2-A…E (aggiornare i frontmatter PRD/UX a `approved`).
2. **R-4** — ratificare G3-1…5 (in particolare lo **stack G3-1**: senza di esso la Story 1.1 non può partire).
3. **R-3** — decidere se ratificare la FR del pannello Account/preferenze.
4. **R-5** — assegnare l'owner della verifica legale (gate di rilascio compliance).

### Recommended Next Steps

1. **Fahad**: al gate G3, approvare Architettura + Epics + Readiness e **chiudere G2-A…E e G3-1…5** (le raccomandazioni sono in PRD §14 e Architecture §10). Mergiare **insieme** la PR #6 (architettura) e questa PR (epics + readiness).
2. **John** (post-gate, via PR): registrare gli esiti — aggiornare i frontmatter PRD/UX a `approved`, aggiungere le estensioni di Glossario (R-2), aggiornare `project-context.md` §6 *Technology Stack* con le versioni esatte (come richiede la costituzione), ed eventualmente la FR pannello Account (R-3).
3. **John** (routing): coinvolgere **Murat (TEA)** per la strategia di test (R-7) e assicurare l'ingaggio legale per R-5 prima del rilascio compliance.
4. **A G3 superato**: aprire la **Fase 4 (Amelia)** partendo dalla Story 1.1 (scaffolding), poi Epic 1 → Epic 2 (funzione di fiducia n.1) → Epic 3 (differenziatore) → Epic 4 → Epic 5 (ordine raccomandato, priorità finale di Fahad).

### Final Note

L'assessment ha esaminato **6 categorie** (discovery, PRD, coverage FR/NFR, UX, qualità epic, riconciliazione) e ha rilevato **0 difetti critici/maggiori** di planning e **8 punti di riconciliazione (R-1…R-8)** che sono decisioni di gate e precisazioni da registrare — coerenti con quanto già segnalato dall'architettura. Il pacchetto è pronto per essere presentato a Fahad al gate **G3**; l'implementazione parte solo dopo l'approvazione e la chiusura delle decisioni aperte.

---

_Fine Implementation Readiness Report. Co-artefatto del gate umano **G3**. Nessuna issue chiusa prima del merge umano; nessun avvio della Fase 4 prima dell'approvazione (`project-context.md` §2, §4)._

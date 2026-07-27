---
title: 'Epics & Stories — HostPilot'
status: approved
gate: G3
gate_status: 'approvato da Fahad al gate G3 (2026-07-24). Esiti G2-A…E e G3-1…5 registrati (PRD §14, project-context §6). Fase 4 aperta ad Amelia.'
created: 2026-07-24
updated: 2026-07-26
author: John — Product Manager (leader squad)
phase: '3 · Solutioning (co-artefatto del gate G3, con Winston)'
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - docs/prd.md
  - docs/ux-spec.md
  - docs/architecture.md
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md
  - docs/project-brief.md
  - docs/project-context.md
depends_on:
  - docs/prd.md (FR-1…FR-19, NFR-1…NFR-16, UJ-1…UJ-5) — gate G2
  - docs/ux-spec.md (UX-DR estratte da §1…§8) — gate G2
  - docs/architecture.md + ARCHITECTURE-SPINE.md (invarianti AD-n; AD-1…AD-21 al 2026-07-26 — AD-21 aggiunto dopo il G3) — gate G3
related:
  - docs/implementation-readiness.md (verifica di readiness, stesso gate G3)
---

# HostPilot — Epic Breakdown

## Overview

Questo documento decompone i requisiti di **HostPilot** (PRD `docs/prd.md`, UX Spec `docs/ux-spec.md`) e le decisioni architetturali (Architecture `docs/architecture.md` e ARCHITECTURE-SPINE `docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md`) in **Epics** organizzati per valore utente e **Stories** implementabili da un singolo agente sviluppatore (Amelia, Fase 4), ciascuna con acceptance criteria testabili.

È il co-artefatto di John (PM) del gate **G3**, insieme all'Architecture Spec di Winston e alla verifica di Implementation Readiness (`docs/implementation-readiness.md`). Non duplica i documenti a monte: referenzia per ID (FR-N, NFR-N, UJ-N, AD-N, UX-DR-N).

**Vincoli ereditati** (`docs/project-context.md` §2, §4): il metodo è guidato dai documenti e i gate sono umani. Le decisioni di prodotto ancora aperte — **G2-A…E** (PRD §14) e **G3-1…5** (Architecture §10) — **non sono decise qui**: le Stories sono scritte in modo **parametrico** rispetto a esse (come l'architettura), e la loro chiusura è attesa a G3. Documento in italiano, consegnato via Pull Request verso `main`; nessuno scaffolding applicativo prima dell'approvazione del G3.

> **Nota di lettura per Amelia (Fase 4):** il contratto vincolante per l'implementazione è lo **spine** — **tutti** gli invarianti `AD-n` elencati in `ARCHITECTURE-SPINE.md`, più le Consistency Conventions. Vale la lista del documento, **non** un intervallo ricopiato qui: lo spine cresce quando una decisione lo richiede (AD-21 è stato aggiunto il 2026-07-26, dopo il G3, per l'anagrafica `ospite`), e un intervallo scritto a mano escluderebbe in silenzio gli invarianti più recenti. Dove una Story cita un AD, quell'invariante è legge, non suggerimento. I sostantivi del Glossario PRD §4 restano **in italiano verbatim** in codice/DB/API (spine).

---

## Requirements Inventory

### Functional Requirements

_Sintesi; testo completo e "Consequences (testable)" in PRD §5._

- **FR-1** — Registrazione delle Strutture (crea/modifica/elimina fino a 3 attive; CIN opzionale; la 3ª attiva la segnalazione Regime fiscale). [UJ-1, UJ-4]
- **FR-2** — Anagrafica Comune/Regione della Struttura (parametrizza Tassa di soggiorno e ISTAT/ROSS1000; degrado sicuro se non configurati).
- **FR-3** — Import Feed iCal Airbnb/Booking (collegamento via URL, import periodico, timestamp ultimo sync, errore visibile). [UJ-1]
- **FR-4** — Calendario unificato multi-Struttura (griglia aggregata Canali/Strutture, distinzione per Canale). [UJ-1, UJ-2]
- **FR-5** — Rilevazione dei Conflitti (sovrapposizione ⇒ un Conflitto `rilevato`; notifica; fonte+timestamp). [UJ-2]
- **FR-6** — Finestra di riconciliazione (scelta prenotazione da tenere, istruzioni guidate, `gestito`, nessuna scrittura OTA). [UJ-2]
- **FR-7** — Inserimento manuale di Prenotazioni (partecipa alla rilevazione Conflitti).
- **FR-8** — Definizione delle Regole di prezzo (base, stagione, weekend, last-minute, soggiorno minimo; precedenza deterministica). [UJ-5]
- **FR-9** — Calcolo e anteprima del prezzo (per data/Struttura, con Regola determinante e soggiorno minimo). [UJ-5]
- **FR-10** — Esportazione/consultazione dei prezzi (formato riportabile sui portali; no push OTA). [UJ-5]
- **FR-11** — Alloggiati Web (raccolta minimizzata documento, tracciato, scadenza 24h/6h, stato). [UJ-3]
- **FR-12** — Tassa di soggiorno (calcolo da configurazione Comune, registro incassi/versamenti, riepilogo periodico).
- **FR-13** — ISTAT/ROSS1000 (compilazione da tracciato Regione, periodicità, movimento zero).
- **FR-14** — CIN (tracciamento per Struttura, checklist esposizione). [UJ-1]
- **FR-15** — Cruscotto Adempimenti e scadenze (stati, ordinamento urgenza, notifiche, scaduto evidenziato).
- **FR-16** — Livello di automazione configurabile per Adempimento (Promemoria / Compilazione assistita / Invio automatico).
- **FR-17** — Segnalazione del Regime fiscale per numero di Strutture (1-2 vs. 3; informativo, con disclaimer). [UJ-4]
- **FR-18** — Calendario Turni di pulizia (legati a check-out/check-in; marcabili completati).
- **FR-19** — Messaggi automatici agli Ospiti (pre-arrivo/check-in/check-out; template per evento/Struttura).

### NonFunctional Requirements

_Testo completo in PRD §6 e §7._

- **NFR-1** — Affidabilità della sincronizzazione (import periodico resiliente; nessuna Prenotazione persa).
- **NFR-2** — Verità temporale sui dati OTA (timestamp ultimo sync sempre visibile; mai falsa sincronia).
- **NFR-3** — Affidabilità delle notifiche/scadenze (una scadenza non deve essere persa per errore di sistema — severità alta).
- **NFR-4** — Configurabilità normativa (aliquote/tracciati/periodicità/termini = dati, mai hardcoded; update senza rilascio).
- **NFR-5** — Usabilità per utente non tecnico (flussi principali completabili senza supporto; target → UX).
- **NFR-6** — Sicurezza dei dati personali (GDPR by design sui documenti d'identità).
- **NFR-7** — Osservabilità degli esiti di compliance (stato tracciato e verificabile; storico audit).
- **NFR-8** — Accessibilità (WCAG 2.1 AA come baseline, confermata da Sally).
- **NFR-9** — Localizzazione (UI/contenuti it-IT; date, valute, formati italiani).
- **NFR-17** — Politica di uscita di rete sui contenuti scaricati dall'Host (URL del Feed = input non fidato: solo `http(s)`, blocco di loopback/reti private/link-local/metadati d'istanza validato sull'indirizzo risolto e dopo ogni redirect, timeout e cap di dimensione come configurazione). Requisito di hardening accolto su proposta del Test Architect (MYL-39), in attesa di ratifica di Fahad.
- **NFR-10…NFR-16** — Privacy/GDPR: base giuridica obbligo legale (10), minimizzazione (11), retention (12, = G2-D), cifratura at-rest (13), controllo accessi Host proprietario (14), diritti dell'interessato/cancellazione (15), nessun dato reale nei test (16).

### Additional Requirements

_Requisiti tecnici che impattano la decomposizione, estratti da Architecture e ARCHITECTURE-SPINE._

- **AR-1 — Starter template / scaffolding (impatta Epic 1, Story 1.1).** Stack proposto (decisione **G3-1**): backend Python 3.14 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2; DB PostgreSQL 18; frontend Next.js 16.2 (App Router, TS) + Node 24; UI seed Tailwind 4 + shadcn/ui + TanStack Query. Basato sui **template di squadra** (`frontend-next`, `backend-fastapi`). **Monorepo applicativo** (`backend/` + `frontend/` accanto a `docs/`) — decisione **G3-4** (assunzione da confermare).
- **AR-2 — Monolite modulare + worker (AD-1).** Moduli: `identity · strutture · calendario · prezzi · adempimenti · operativita · notifiche · config_normativa · privacy`, con `core` (shared kernel). Effetti asincroni solo via **transactional outbox** + eventi di dominio; grafo delle dipendenze dello spine è una regola.
- **AR-3 — Shared kernel `core` (AD-1, AD-3, AD-10, AD-17).** `date_range` (semantica temporale unica Europe/Rome), catalogo unico eventi/job `core/events.py`, tabella `outbox`, tabella `job` + worker con `SELECT … FOR UPDATE SKIP LOCKED`, `db`, `config`.
- **AR-4 — Tenancy (AD-2, NFR-14).** Ogni tabella tenant-owned ha `host_id` NOT NULL; scoping imposto nel layer repository; `host_id` risolto dalla sessione, mai da input client.
- **AR-5 — Contratto API unico e tipizzato (AD-14).** REST JSON sotto `/api/v1`, errori RFC 9457 (`application/problem+json`), OpenAPI generato da FastAPI, client TypeScript **generato** consumato dal frontend; i valori derivati di dominio (`livello_urgenza`, prezzi con catena Regole, stati) sono campi API, mai ricalcolati dal frontend.
- **AR-6 — AuthN/AuthZ di sessione server-side (AD-15).** email+password argon2id; sessione server-side con cookie HttpOnly Secure SameSite=Lax; TLS ovunque; segreti nel secret manager, `.env.example` come contratto.
- **AR-7 — Configurazione normativa versionata (AD-9, AD-12).** `comune_config`, `regione_config`, termini Alloggiati (24h/6h) e parametri fiscali (soglia presunzione, aliquote citate) in tabelle con validità temporale (`valido_dal/al`); anagrafica base seedata da codici ISTAT; aggiornamenti via endpoint interni auditati; stato `configurazione_non_disponibile` + promemoria manuale dove manca.
- **AR-8 — Scheduling durevole (AD-10, NFR-1, NFR-3).** Ogni azione futura (sync tick, promemoria, escalation, messaggio, purge retention) è una riga in `job`; consegna at-least-once + handler idempotenti; nessun timer solo in-memory.
- **AR-9 — GDPR come architettura (AD-11).** `ospite_documento` segregata, cifratura a campo AES-256-GCM (envelope: DEK per record, KEK nel secret manager), retention automatica (job) N giorni dopo `completato` e comunque non oltre M dal check-out; evidenza non sensibile (timestamp/esito/hash); non-esposizione in log/eventi/outbox/API.
- **AR-10 — Osservabilità e audit di compliance (AD-16, NFR-7).** Log JSON strutturati (`request_id`, `host_id`), error tracking centralizzato, metriche + alert (fallimenti sync consecutivi, ritardo coda `job`); `evento_compliance` append-only alimenta SM-1/2/C1/C2.
- **AR-11 — Envelope operativo (spine).** Ambienti `dev/staging/prod`; **regione UE esclusiva** per ogni componente che tocca dati personali; CI GitHub Actions (lint, typecheck, test, build); migrazioni Alembic forward-only; backup giornalieri con test di restore (RPO 24h / RTO 4h pilota); canali notifica Host MVP = in-app + email.
- **AR-12 — Prerequisiti di rilascio compliance (Architecture §9.3.4, PRD §12.1, §7).** Verifica legale delle fonti normative e conferma della retention (G2-D) sono **attività esplicite da pianificare** come gate di rilascio delle feature di compliance (non dell'approvazione dell'architettura).
- **AR-13 — Fast-follow WS_ALLOGGIATI (Deferred spine, AD-7 `submit`).** L'invio automatico Alloggiati (SOAP `WS_ALLOGGIATI`) è fuori MVP: l'MVP parte in compilazione assistita; l'adapter è un fast-follow dietro il contratto plugin, previa WSKEY per Host e verifica legale/stabilità in staging.

### UX Design Requirements

_Estratti dalla UX Spec `docs/ux-spec.md` (§1…§8) come input di prima classe. Ogni UX-DR è coperto da almeno una Story (vedi FR Coverage Map → colonna UX)._

- **UX-DR1** — Navigazione primaria a 5 voci (Dashboard, Calendario, Prezzi, Adempimenti, Operatività); Strutture in impostazioni/account; **selettore Struttura trasversale** con "Tutte le Strutture" di default (UX §2.2).
- **UX-DR2** — **Dashboard "un solo posto"**: riassume calendario, adempimenti in scadenza, prezzi, banner Regime fiscale e stato Conflitti — mai moduli scollegati (UX §1 pr.1, §2.3).
- **UX-DR3** — Onboarding guidato passo-passo con progress indicator + tooltip contestuali sui termini normativi alla prima occorrenza, sempre skippabile (UX §1 `[OPZIONE UX]`, UJ-1).
- **UX-DR4** — Badge di stato **testo + icona (mai solo colore)**, contrasto ≥ 4.5:1 (UX §6, §8); 4 stati Adempimento distinguibili anche senza colore.
- **UX-DR5** — **Gerarchia di urgenza a 3 livelli** (normale / urgente / critico-scaduto) coerente su Dashboard e Cruscotto, con livello dedicato < 2h per soggiorni < 24h (UX §4.6, UJ-3); calcolata lato server (`livello_urgenza`, AD-14).
- **UX-DR6** — Etichetta persistente **"dati aggiornati alle HH:MM"** su ogni superficie con dati da Feed (UX §5.1, NFR-2), mai un tooltip nascosto.
- **UX-DR7** — Pattern **assistenza alla compliance senza falsa certezza**: linguaggio di stato onesto, disclaimer contestuale accanto al contenuto, azione umana esplicita prima di `completato`, trasparenza sull'esito (inviato vs. tentato/errore) (UX §4).
- **UX-DR8** — Flusso dati identità Ospite: form minimizzato (solo campi Alloggiati), scopo dichiarato inline, nessuna ri-esposizione visiva superflua dopo `completato`, retention comunicata nel copy, target di tocco 44×44px (UX §5.2, §6).
- **UX-DR9** — Countdown / scadenza relativa leggibile per Adempimenti urgenti, con equivalente testuale (UX §8, UJ-3).
- **UX-DR10** — Navigazione da tastiera completa sui flussi critici (Finestra di riconciliazione, compilazione Alloggiati) + equivalenti testuali per screen reader (UX §6).
- **UX-DR11** — Formati italiani ovunque (date gg/mm/aaaa, valuta €, separatore decimale virgola); copy it-IT in moduli per feature (UX §6, spine Consistency).
- **UX-DR12** — Layout responsive **mobile-first plausibile** (flussi ad alta frequenza a una mano su schermo piccolo); densità variabile 1-3 Strutture senza degrado (UX §1 pr.5, §8).
- **UX-DR13** — **Spiegabilità del prezzo in UI**: catena delle Regole applicate sempre visibile ("€145 — Weekend + Alta stagione"); qualunque sia la precedenza, la Regola "vincente" è resa esplicita (UX UJ-5).
- **UX-DR14** — Regime fiscale: **pannello a schermo intero** alla conferma della 3ª Struttura + **pannello persistente** con disclaimer sempre visibile (UX UJ-4).
- **UX-DR15** — Pannello **Account / preferenze di notifica** (email, password, preferenze) — infrastruttura implicita, `[GAP PRD §2.3]`: da tracciare come Story e da **ratificare come FR a G3**.
- **UX-DR16** — Target di usabilità misurabili proposti da Sally (onboarding ≤ 10 min, riconciliazione ≤ 3 interazioni, Alloggiati ≤ 2 min) — **da confermare con G2-E** (non decisi qui) (UX §6).

### FR Coverage Map

| Requisito | Epic — Story | UX-DR rilevanti |
| --- | --- | --- |
| FR-1 (Registrazione Strutture, cap 3) | Epic 1 — 1.4 | UX-DR3, UX-DR12 |
| FR-2 (Anagrafica Comune/Regione) | Epic 1 — 1.5 | UX-DR11 |
| FR-17 (Regime fiscale) | Epic 1 — 1.6 | UX-DR14 |
| FR-3 (Import Feed iCal) | Epic 2 — 2.1, 2.2 | UX-DR6 |
| FR-4 (Calendario unificato) | Epic 2 — 2.3 | UX-DR6, UX-DR12 |
| FR-7 (Prenotazioni manuali) | Epic 2 — 2.4 | — |
| FR-5 (Rilevazione Conflitti) | Epic 2 — 2.5, 2.6 | UX-DR4 |
| FR-6 (Finestra di riconciliazione) | Epic 2 — 2.7 | UX-DR6, UX-DR10 |
| FR-15 (Motore + Cruscotto Adempimenti) | Epic 3 — 3.1, 3.2, 3.8 | UX-DR4, UX-DR5, UX-DR7, UX-DR9 |
| FR-16 (Livello di automazione) | Epic 3 — 3.1 | UX-DR7 |
| FR-14 (CIN) | Epic 3 — 3.3 | UX-DR4 |
| FR-11 (Alloggiati Web) | Epic 3 — 3.5 (+3.4 privacy) | UX-DR7, UX-DR8, UX-DR9, UX-DR10 |
| FR-12 (Tassa di soggiorno) | Epic 3 — 3.6 | UX-DR7, UX-DR11 |
| FR-13 (ISTAT/ROSS1000) | Epic 3 — 3.7 | UX-DR7 |
| FR-8 (Definizione Regole di prezzo) | Epic 4 — 4.1 | UX-DR11 |
| FR-9 (Calcolo e anteprima prezzo) | Epic 4 — 4.2 | UX-DR13 |
| FR-10 (Esportazione prezzi) | Epic 4 — 4.3 | UX-DR11 |
| FR-18 (Turni di pulizia) | Epic 5 — 5.1 | UX-DR12 |
| FR-19 (Messaggi automatici) | Epic 5 — 5.2 | UX-DR7 |

_UX-DR trasversali (coperti da Story di fondazione/UI): UX-DR1, UX-DR2 → 1.3 (shell/dashboard frame) + widget per epic (2.8, 3.8, 4.4, 5.3); UX-DR15 → 1.3; UX-DR16 → non un requisito implementativo ma un target da confermare a G2-E (tracciato nella readiness)._

_Anagrafica `ospite` (entità dell'ERD, non una FR a sé — decisione MYL-40 del 2026-07-26, PRD §14.2): **creazione** → Epic 2 — Story **2.3**; **scrittura volontaria dell'Host** → Story **2.4**; **lettura/presentazione** → 2.3, 2.7; consumatori a valle → Epic 3 (Alloggiati, via service) ed Epic 5 (Messaggi, FR-19). NFR applicati negli AC della 2.3: **NFR-11** (minimizzazione), **NFR-12** (retention parametrica), **NFR-14** (accesso del solo Host proprietario), **NFR-16** (nessun dato reale nei test). L'invariante architetturale corrispondente è **AD-21** (spine, registrato il 2026-07-26): dove questo documento e AD-21 sembrano dire cose diverse, vale AD-21._

---

## Epic List

Ordine di consegna **raccomandato** (non deciso: la priorità è di Fahad, `project-context.md` §2 — vedi readiness). Ogni Epic è standalone dopo la fondazione (Epic 1) e non richiede Epic futuri per funzionare.

### Epic 1: Fondamenta della piattaforma e gestione delle Strutture
L'Host crea l'account, entra in un'app navigabile e italiana, registra da 1 a 3 Strutture con Comune/Regione/CIN, e vede segnalato il Regime fiscale corretto. Posa le fondamenta tecniche (scaffolding, `core` kernel, tenancy, contratto API, auth, config normativa, job/outbox) che tutti gli Epic successivi riusano — senza costruire tabelle o feature non ancora necessarie.
**FR coperte:** FR-1, FR-2, FR-17. **Fondazione:** AR-1…AR-11.

### Epic 2: Calendario unificato e anti double-booking
L'Host collega i Feed iCal di Airbnb/Booking, vede tutte le Prenotazioni in un'unica griglia, inserisce prenotazioni manuali, e viene avvisato e guidato quando due prenotazioni si sovrappongono — senza che il prodotto finga mai una sincronia che i Feed non hanno. È la funzione di fiducia n.1 (zero double-booking).
**FR coperte:** FR-3, FR-4, FR-5, FR-6, FR-7. **NFR:** NFR-1, NFR-2, NFR-3, NFR-17.

### Epic 3: Adempimenti italiani "in regola"
L'Host tiene sotto controllo i quattro Adempimenti (Alloggiati Web, Tassa di soggiorno, ISTAT/ROSS1000, CIN) da un unico cruscotto, con scadenze, promemoria affidabili e compilazione assistita — e i dati d'identità degli Ospiti trattati con GDPR by design. È il differenziatore nativo e la funzione di fiducia n.2 (nessuna scadenza persa).
**FR coperte:** FR-11, FR-12, FR-13, FR-14, FR-15, FR-16. **NFR:** NFR-3, NFR-4, NFR-6, NFR-7, NFR-10…NFR-16.

### Epic 4: Motore di Regole di prezzo
L'Host configura Regole di prezzo per stagione, weekend, last-minute e soggiorno minimo, vede l'anteprima del prezzo calcolato su ogni data con la spiegazione della Regola vincente, ed esporta i prezzi da riportare sui portali. È un motore di calcolo consultabile, non un channel manager.
**FR coperte:** FR-8, FR-9, FR-10.

### Epic 5: Operatività — pulizie e messaggi Ospiti
L'Host pianifica i Turni di pulizia legati ai check-out e configura Messaggi automatici agli Ospiti per gli eventi del soggiorno — riducendo il coordinamento manuale, senza mai marcare come inviato un messaggio che non è partito.
**FR coperte:** FR-18, FR-19.

**Dipendenze tra Epic:** Epic 1 è la fondazione; Epic 2, 3, 4, 5 costruiscono su Epic 1 e sono indipendenti tra loro. Note di riuso non bloccanti: Epic 3 e Epic 5 riusano il modulo `notifiche` (canali in-app + email) introdotto in **Epic 2 — Story 2.6**; se un Epic diverso da Epic 2 venisse consegnato per primo dopo Epic 1, la Story 2.6 (fondazione `notifiche`) va anticipata come sua prima Story. Nessun Epic **richiede** feature di un Epic successivo per funzionare.

---

## Epic 1: Fondamenta della piattaforma e gestione delle Strutture

L'Host crea l'account, entra in un'app navigabile in italiano, registra da 1 a 3 Strutture con Comune/Regione/CIN e vede segnalato il Regime fiscale corretto. Le Stories 1.1–1.3 posano fondamenta **just-in-time** (solo l'infrastruttura e le tabelle necessarie a questo Epic); le Stories 1.4–1.6 consegnano il valore utente (Strutture + Regime fiscale). Governato da AD-1, AD-2, AD-3, AD-9, AD-10, AD-12, AD-14, AD-15, AD-17, AD-18, AD-20.

### Story 1.1: Scaffolding del monorepo, `core` kernel e CI

As a squad di sviluppo (Amelia, Fase 4),
I want un monorepo applicativo inizializzato dai template di squadra con lo shared kernel `core` e la pipeline CI/migrazioni,
So that ogni Story successiva costruisca su fondamenta coerenti, con confini di modulo e contratto API già imposti dalla struttura.

**Acceptance Criteria:**

**Given** l'approvazione dello stack a G3 (G3-1) e del monorepo (G3-4)
**When** si inizializza il repository dai template `frontend-next` e `backend-fastapi`
**Then** esistono `backend/` (FastAPI, Python 3.14, SQLAlchemy 2, Alembic, Pydantic v2) e `frontend/` (Next.js 16.2 App Router, TS, Node 24) accanto a `docs/`
**And** è presente il package `core` con `date_range` (intervallo semiaperto `[check_in, check_out)` su date Europe/Rome, sovrapposizione = intersezione non vuota; timestamp UTC), il catalogo eventi/job versionato `core/events.py`, la tabella `outbox`, la tabella `job` con claim `SELECT … FOR UPDATE SKIP LOCKED`, `db` e `config` (AD-1, AD-3, AD-10, AD-17)
**And** il worker è un processo dedicato dello stesso codebase che consegna gli eventi outbox dopo il commit ed esegue i `job` con handler idempotenti (AD-1, AD-10)
**And** l'API espone `/api/v1`, genera l'OpenAPI da FastAPI e il frontend consuma **solo** il client TypeScript generato; gli errori seguono RFC 9457 `application/problem+json` (AD-14)
**And** la CI GitHub Actions esegue lint, typecheck, test e build su ogni PR, le migrazioni Alembic sono forward-only, ed esiste `.env.example` come contratto dei segreti (AR-11)
**And** `date_range`, il catalogo eventi e le convenzioni (UUIDv7 PK, importi in centesimi interi, enum di stato) hanno test dedicati (spine Consistency, NFR-16: nessun dato reale nei fixture)

### Story 1.2: Registrazione e autenticazione dell'Host

As an Host,
I want registrarmi con email e password e accedere in modo sicuro,
So that i miei dati e quelli delle mie Strutture siano protetti e accessibili solo a me.

**Acceptance Criteria:**

**Given** il modulo `identity` e la tabella `host`
**When** l'Host si registra con email e password
**Then** la password è salvata con argon2id e viene creata una sessione server-side con cookie HttpOnly Secure SameSite=Lax (AD-15)
**And** ogni endpoint (salvo login/registrazione/health) richiede una sessione valida e risolve `host_id` dalla sessione, mai da input client (AD-2, AD-15)
**And** ogni tabella tenant-owned introdotta d'ora in poi porta `host_id` NOT NULL e ogni query passa dal repository che impone il filtro `host_id` (AD-2, NFR-14)
**And** TLS è richiesto su tutti gli ambienti e i segreti vivono nel secret manager, non nel repo (AR-6)

### Story 1.3: App shell, navigazione, Dashboard frame, i18n e pannello Account

As an Host,
I want un'app in italiano con una navigazione chiara e un pannello dove gestire account e preferenze di notifica,
So that trovi "un solo posto dove guardare" e sappia sempre dove sono le mie cose.

**Acceptance Criteria:**

**Given** l'Host autenticato
**When** entra nell'app
**Then** vede una navigazione primaria a 5 voci — Dashboard, Calendario, Prezzi, Adempimenti, Operatività — (tab bar in basso su mobile, sidebar su desktop) con **Strutture** raggiungibile da impostazioni/account (UX-DR1)
**And** è presente un **selettore Struttura trasversale** con "Tutte le Strutture" come default (UX-DR1)
**And** esiste una **Dashboard frame** che ospiterà i riepiloghi contribuiti dagli Epic successivi (calendario, adempimenti, prezzi) — inizialmente uno stato vuoto rassicurante (UX-DR2)
**And** tutta l'UI è in italiano con formati italiani (date gg/mm/aaaa, valuta €, virgola decimale) e le stringhe vivono in moduli copy per feature (UX-DR11, NFR-9)
**And** esiste un pannello **Account / preferenze di notifica** (email, password, canale di notifica preferito) come infrastruttura di `identity` (UX-DR15) — `[da ratificare come FR a G3: vedi readiness R-3]`
**And** il layout è responsive mobile-first e regge densità variabile 1-3 Strutture senza degrado (UX-DR12)

### Story 1.4: Registrazione delle Strutture con cap di 3 unità

As an Host,
I want registrare, modificare e archiviare le mie Strutture fino a un massimo di 3 attive,
So that gestisca i miei appartamenti in un unico posto senza superare lo scope del pilota.

**Acceptance Criteria:**

**Given** il modulo `strutture` e la tabella `struttura` (proprietario unico scrittore, AD-18)
**When** l'Host crea una Struttura
**Then** richiede almeno nome, Comune e Regione; il CIN è opzionale alla creazione (FR-1)
**And** se il CIN è assente, la Struttura mostra un indicatore non bloccante "CIN mancante" — il tracciamento completo come Adempimento (FR-14) è consegnato in Epic 3, l'onboarding non è mai bloccato (UJ-1)
**And** al tentativo di aggiungere la **4ª Struttura attiva** il sistema mostra un messaggio che il pilota copre 1-3 unità e non procede; il cap "max 3 attive" è imposto nel service `strutture` (unico punto) ed è un parametro **distinto** dalla soglia fiscale (AD-12)
**And** una Struttura con dati collegati non si cancella fisicamente ma si porta ad **`archiviata`** (esce dal conteggio attive e dal Regime fiscale; i Feed smettono di sincronizzare); audit/registro/storico restano append-only (AD-20)
**And** il flusso di aggiunta è guidato passo-passo con progress e tooltip sui termini normativi, sempre skippabile (UX-DR3)

### Story 1.5: Anagrafica Comune/Regione e configurazione normativa con degrado sicuro

As an Host,
I want associare ogni Struttura al suo Comune e alla sua Regione,
So that Tassa di soggiorno e ISTAT/ROSS1000 siano parametrizzati correttamente, e il sistema mi avvisi con onestà quando non è ancora configurato per me.

**Acceptance Criteria:**

**Given** il modulo `config_normativa` con `comune_config` e `regione_config` a validità temporale (`valido_dal/al`, AD-9)
**When** l'Host associa un Comune e una Regione a una Struttura
**Then** l'anagrafica base di Comuni/Regioni è seedata dai codici ISTAT e gli aggiornamenti di configurazione passano da endpoint interni auditati (chi/cosa/quando), mai da modifiche dirette al DB (AD-9)
**And** cambiare il Comune di una Struttura ricarica la configurazione della Tassa applicabile senza perdere lo storico dei versamenti già registrati (FR-2)
**And** un Comune/Regione non riconosciuto o non ancora configurato produce lo stato esplicito **`configurazione_non_disponibile`** con promemoria manuale — mai un calcolo con default inventati, con tono informativo ("non ancora configurato per il tuo Comune"), non un errore che implica colpa dell'Host (FR-2, AD-9, UX §5.1)
**And** aliquote, esenzioni, periodicità, termini e tracciati sono **dati di configurazione**: aggiornarli non richiede un rilascio di codice (NFR-4)

### Story 1.6: Segnalazione del Regime fiscale derivato dal numero di Strutture

As an Host,
I want che il sistema mi segnali il regime fiscale applicabile in base a quante Strutture ho,
So that io capisca l'impatto della soglia dei tre immobili **prima** di trovarmelo a fine anno — senza che il prodotto pretenda di fare il commercialista.

**Acceptance Criteria:**

**Given** il service `strutture` e i parametri fiscali in `config_normativa` (soglia, aliquote citate, testo informativo — mai costanti nel codice, AD-12)
**When** il numero di Strutture non archiviate dell'Host cambia
**Then** il Regime fiscale è **sempre derivato** da `count(Strutture non archiviate)` al momento della lettura, mai persistito come stato autonomo (AD-12)
**And** con 1-2 Strutture il sistema indica il regime di cedolare secca (informativo); alla transizione a 3 emette un evento che attiva un **pannello a schermo intero** ("Con 3 Strutture cambia il tuo regime fiscale": presunzione di imprenditorialità, Partita IVA, aliquote citate come informative) con CTA "Ho capito, continua" e "Parlane con un commercialista" (FR-17, UJ-4, UX-DR14)
**And** da quel momento un **pannello Regime fiscale persistente** resta accessibile con disclaimer visibile in ogni stato, non solo alla prima visualizzazione (UX-DR14)
**And** se l'Host scende di nuovo a 2 Strutture (archiviazione/eliminazione della 3ª), il pannello torna allo stato 1-2 senza notifiche residue fuorvianti (UJ-4 edge)
**And** il contenuto è **informativo con disclaimer**, mai un calcolo d'imposta (Non-Goal PRD §8); la profondità (solo avviso vs. riepilogo strutturato) resta **parametrica rispetto a [DECISIONE G2-C]**, non decisa qui

---

## Epic 2: Calendario unificato e anti double-booking

L'Host collega i Feed iCal, vede tutte le Prenotazioni in un'unica griglia e viene avvisato e guidato sui Conflitti — senza falsa sincronia. Governato da AD-3, AD-4, AD-5, AD-10, AD-13 (canali notifiche), AD-14, AD-17, AD-19, **AD-21** (anagrafica `ospite`: minimizzazione e retention per azzeramento). Realizza UJ-1 (parte calendario), UJ-2.

> **[DECISIONE DI PRODOTTO — Anagrafica `ospite`, 2026-07-26]** — decisione di Fahad su proposta di Murat (issue **MYL-40**), registrata in PRD **§14.2**.
>
> **Opzione B — anagrafica vera con contatti.** L'entità `ospite` (nome + email/telefono **quando disponibili**) è **materializzata in questo Epic**, non tenuta come campo denormalizzato sulla Prenotazione: l'Epic 3 (Alloggiati) e l'Epic 5 (Messaggi agli Ospiti) la richiedono come entità, e l'ERD la prevede già. Cinque vincoli **non negoziabili** accompagnano la scelta e valgono come acceptance criteria di ogni Story che la tocca:
>
> 1. **Proprietà e creazione.** `ospite` appartiene al modulo `calendario`, unico scrittore (AD-18), ed è **creata dalla Story 2.3**, che ne risponde negli AC. Nessuna Story può **mostrare** l'Ospite senza che un'altra ne dichiari la creazione.
> 2. **Minimizzazione** (GDPR by design, `project-context.md` §5, NFR-11). Si salva **solo** ciò che arriva dal Feed o che l'Host inserisce volontariamente. Campi contatto **nullable**, mai obbligatori, **mai inventati né dedotti**. **Nessun documento d'identità in questa fase**: quello è `ospite_documento` (Epic 3, AD-11), con requisiti propri.
> 3. **Retention** (NFR-12). Periodo esplicito legato al **ciclo della Prenotazione**, espresso come **parametro configurabile** (coerente con G2-D 30/90), mai hardcodato. Il valore iniziale è **provvisorio**, in attesa dell'esito di R-5. **Registrata nello spine come `AD-21`** il 2026-07-26 (issue MYL-46): la retention si esegue **azzerando i campi personali**, mai cancellando la riga `ospite` o la Prenotazione — AD-20 elenca ora tre cancellazioni distruttive ammesse, non due. **Decorrenza e valore del parametro vivono in AD-21 e in nessun altro punto**: questo documento non li duplica.
> 4. **Tenancy** (AD-2, AR-4). `ospite` è **tenant-owned**: `host_id` NOT NULL e guardia strutturale di tenancy come le altre entità. **Non** va nell'allowlist dei dati di riferimento.
> 5. **Gate legale** (R-5). I contatti degli Ospiti sono dati personali **di terzi**, non del cliente: **base giuridica** del trattamento contatti e **retention** sono punti espliciti del mandato di verifica (`docs/implementation-readiness.md` R-5, PRD §14.2). È materia **privacy, non fiscale**.
>
> **Collocazione della creazione — deviazione dichiarata dal candidato indicato.** Il candidato naturale era la **Story 2.1** (import dai Feed), ma la 2.1 è **già consegnata** (MYL-37) e ha deliberatamente **non** introdotto l'entità: i VEVENT di Airbnb/Booking non portano un'identità Ospite affidabile, quindi il campo `sommario` conserva il testo opaco del feed e nulla più. Creare `ospite` nella 2.1 produrrebbe una tabella **senza alcun percorso di scrittura**. La creazione va perciò alla **prima Story non ancora avviata che la richiede — la 2.3** — e la prima scrittura volontaria dell'Host alla **2.4**. Il vincolo 1 resta soddisfatto: la 2.3 crea e mostra nello stesso perimetro.

### Story 2.1: Collegamento di un Feed iCal e import on-demand

As an Host,
I want collegare a una Struttura l'URL del Feed iCal di Airbnb o Booking e vedere subito le prenotazioni importate,
So that abbia in HostPilot le prenotazioni che oggi tengo sparse sui portali, con la prova che il collegamento ha funzionato.

**Acceptance Criteria:**

**Given** il modulo `calendario` con `feed_ical`, `prenotazione`, `sync_run` (proprietario unico scrittore, AD-18)
**When** l'Host incolla un URL di Feed iCal valido
**Then** viene accodato subito un **job di sync prioritario** con progresso visibile ("Importazione in corso…" → "Importate N prenotazioni — ultimo aggiornamento HH:MM") (AD-4, AD-10, UJ-1)
**And** il parsing dei VEVENT normalizza e fa **upsert idempotente** con chiave naturale `(feed_id, ical_uid)`: rieseguire il sync non duplica né perde Prenotazioni (AD-4, NFR-1)
**And** l'import **non cancella mai** una Prenotazione: un evento scomparso dal feed porta la Prenotazione a stato `rimossa_dal_feed` (AD-4, AD-19)
**And** un URL non valido o irraggiungibile produce un **errore inline immediato** sul campo/Struttura, mai un fallimento silenzioso (FR-3)
**And** l'URL è trattato come **input non fidato** e il fetch rispetta la politica di uscita di rete: soli schemi `http`/`https`; l'**indirizzo risolto** via DNS è rifiutato se ricade su loopback, reti private, link-local o endpoint di metadati d'istanza; la validazione è ripetuta **dopo ogni redirect**; il rifiuto produce lo stesso errore inline dell'URL irraggiungibile, senza rivelare l'esito della risoluzione (NFR-17)
**And** il fetch ha **timeout** di connessione e lettura e un **cap sulla dimensione** della risposta, entrambi configurazione e non costanti di codice; il superamento chiude la connessione e scrive un `sync_run` fallito, senza saturare il worker (NFR-17, NFR-4)
**And** ogni run scrive un record `sync_run` (esito, timestamp) e le Prenotazioni importate sono associate alla Struttura corretta (AD-4)

### Story 2.2: Poller periodico di sincronizzazione durevole e resiliente

As an Host,
I want che HostPilot risincronizzi periodicamente i Feed da solo,
So that il calendario resti aggiornato senza che io debba fare nulla, e senza perdere prenotazioni se un portale è temporaneamente irraggiungibile.

**Acceptance Criteria:**

**Given** l'infrastruttura di job durevoli (AD-10)
**When** il poller esegue il ciclo di sync
**Then** ogni Feed è sincronizzato a intervallo configurabile (default proposto **G3-5**: 15 minuti, adattivo fino a 5 in prossimità di check-in) come job durevole, mai un timer solo in-memory (AD-10, NFR-1)
**And** l'uso di `ETag`/`If-Modified-Since` evita scaricamenti inutili e l'import è append-preserving (AD-4)
**And** un fallimento temporaneo dell'OTA lascia intatti i dati già importati e produce un errore visibile sulla Struttura, con **alert interno dopo N fallimenti consecutivi** (NFR-1, AR-10)
**And** ogni superficie che mostra dati da Feed espone il timestamp dell'ultimo sync riuscito ("dati aggiornati alle HH:MM") (NFR-2, UX-DR6)

### Story 2.3: Calendario unificato multi-Struttura

As an Host,
I want vedere in un'unica griglia le Prenotazioni di tutte le mie Strutture e di tutti i Canali,
So that capisca a colpo d'occhio la mia situazione senza aprire 5-6 schede di browser.

**Acceptance Criteria:**

**Given** Prenotazioni importate e/o manuali
**When** l'Host apre il Calendario
**Then** vede una griglia (mensile/settimanale) che aggrega le Prenotazioni di tutte le Strutture e Canali, con distinzione visiva per Canale (FR-4)
**And** ogni Prenotazione mostra Canale d'origine, Struttura, date e Ospite (FR-4)
**And** questa Story **crea l'anagrafica `ospite`** come tabella del modulo `calendario`, unico scrittore (AD-18), secondo l'invariante **AD-21**: `host_id` NOT NULL sotto la guardia strutturale di tenancy — **non** è un dato di riferimento (AD-2, AR-4) — con `nome` e i contatti (`email`, `telefono`) **tutti nullable** e **nessun** campo di documento d'identità (quello è `ospite_documento`, Epic 3, AD-11) `[DECISIONE MYL-40 → PRD §14.2; spine AD-21]`
**And** l'anagrafica si popola **solo** con ciò che il Feed fornisce esplicitamente o che l'Host inserisce volontariamente (Story 2.4): nessun campo dedotto o inferito — in particolare il `sommario` del VEVENT resta **testo opaco** della Prenotazione e non viene mai promosso a nome di Ospite (NFR-11)
**And** una Prenotazione **senza Ospite noto resta valida** e si presenta come "Ospite non indicato" — mai un placeholder che somigli a un nome, mai un errore; dove l'ERD ammette più Ospiti per Prenotazione la griglia mostra l'**Ospite principale** (l'unico noto, o quello indicato dall'Host) e l'eventuale conteggio degli altri
**And** i dati dell'Ospite **non compaiono** in log, eventi di dominio, payload `outbox`/`job` o notifiche — gli eventi portano solo identificatori (AD-16, AD-17, NFR-11) — e ogni altro modulo li legge **solo** via service di `calendario` (AD-18)
**And** l'accesso è limitato al solo Host proprietario (NFR-14) e nessun dato reale di Ospiti entra in fixture o test (NFR-16)
**And** la **retention** dei dati personali dell'Ospite segue **AD-21**, che ne è l'unica fonte per periodo e decorrenza: è un **parametro di configurazione** legato al ciclo della Prenotazione (mai un periodo hardcodato — valore iniziale **provvisorio** in attesa di R-5), e alla scadenza un **job durevole** e idempotente (AD-10) **azzera i campi personali** (`nome`, `email`, `telefono`) lasciando **intatte** la riga `ospite`, la Prenotazione e la sua storia — l'azzeramento non è **mai** una `DELETE` di riga, ed è una delle tre sole cancellazioni distruttive che AD-20 ammette (NFR-12, NFR-4, NFR-15)
**And** il selettore Struttura filtra tra vista aggregata e singola Struttura senza cambiare schermata (UX-DR1)
**And** è sempre visibile "dati aggiornati alle HH:MM" per i dati derivati da Feed (NFR-2, UX-DR6)
**And** i dati derivati di dominio (stati, urgenze) arrivano dall'API e il frontend li presenta, mai li ricalcola (AD-14)

### Story 2.4: Inserimento manuale di Prenotazioni

As an Host,
I want inserire una Prenotazione manuale (prenotazione diretta o blocco date),
So that il calendario rifletta anche ciò che non arriva dai portali e concorra all'anti double-booking.

**Acceptance Criteria:**

**Given** il Calendario unificato
**When** l'Host inserisce una Prenotazione manuale
**Then** la Prenotazione è creata in stato `attiva` e partecipa alla rilevazione dei Conflitti (FR-7, AD-19)
**And** una Prenotazione manuale che si sovrappone a una da Feed genera un Conflitto (FR-7 → FR-5)
**And** l'Host **può** — non deve — indicare l'Ospite: nome e, se li ha, email/telefono sono campi **facoltativi** dell'inserimento, scritti nell'anagrafica creata dalla Story 2.3 passando dal service di `calendario` (AD-18, AD-21); una Prenotazione manuale si salva anche **completamente senza Ospite**, e nessun campo contatto è mai obbligatorio o precompilato con un valore dedotto (NFR-11, `[DECISIONE MYL-40]`)
**And** una Prenotazione manuale non si cancella fisicamente: si porta a stato `cancellata` (AD-19), emettendo `prenotazione.cessata`

### Story 2.5: Rilevazione dei Conflitti

As an Host,
I want che il sistema rilevi automaticamente ogni sovrapposizione di date sulla stessa Struttura,
So that nessuna doppia prenotazione mi sfugga.

**Acceptance Criteria:**

**Given** l'insieme delle Prenotazioni in stato `attiva` di una Struttura
**When** termina un import o viene inserita una Prenotazione manuale
**Then** la rilevazione è una **funzione pura** rieseguita su quell'insieme; due Prenotazioni sovrapposte generano **esattamente un** Conflitto con stato `rilevato`, con identità stabile `(struttura_id, coppia di prenotazioni)` — mai due Conflitti aperti per la stessa coppia, mai Conflitti persi (FR-5, AD-3, AD-5)
**And** il Conflitto registra fonte e timestamp di sincronizzazione di ciascuna Prenotazione coinvolta (FR-5)
**And** se una delle due Prenotazioni esce da `attiva` (cancellata sull'OTA, `rimossa_dal_feed`, `cancellata` manuale), il Conflitto passa a **`decaduto`** — transizione di sistema tracciata, distinta da `gestito`, che alimenta la misura di SM-C1 (AD-5, AD-19) `[estensione Glossario da registrare: readiness R-2]`
**And** un Conflitto `rilevato` resta in evidenza in Dashboard finché non è gestito (FR-6)

### Story 2.6: Notifiche di Conflitto (in-app + email) — fondazione `notifiche`

As an Host,
I want essere avvisato appena emerge una possibile doppia prenotazione,
So that possa intervenire in tempo, perché questa è la funzione di fiducia del prodotto.

**Acceptance Criteria:**

**Given** il modulo `notifiche` (canali MVP: in-app + email) e l'infrastruttura di job durevoli (AD-10, AR-11)
**When** un Conflitto emerge alla prima sincronizzazione in cui è rilevato
**Then** parte una notifica (in-app + email) via **job durevole**, mai silenziosa ("Possibile doppia prenotazione — Bologna Centro, 15-17 agosto") (FR-5, NFR-3, AD-10)
**And** `notifiche` dipende solo in lettura da `identity` per risolvere destinatario e preferenze (spine); nessun modulo dipende sincronicamente da `notifiche` (solo via job/eventi)
**And** la consegna è at-least-once con handler idempotente (nessuna notifica persa per restart/crash; nessun doppione fastidioso per ritentativo) (AD-10)
**And** questa fondazione `notifiche` è riusata da Epic 3 (promemoria/escalation Adempimenti) ed Epic 5 (Messaggi Ospiti)

### Story 2.7: Finestra di riconciliazione del Conflitto

As an Host,
I want risolvere un Conflitto scegliendo quale Prenotazione tenere e ricevendo istruzioni per bloccare le date sull'altro Canale,
So that eviti la doppia prenotazione, sapendo che il sistema non scrive al posto mio sui portali.

**Acceptance Criteria:**

**Given** un Conflitto `rilevato`
**When** l'Host apre la Finestra di riconciliazione
**Then** vede le due Prenotazioni sovrapposte affiancate, ciascuna con Canale, Ospite (se noto — dall'anagrafica creata dalla 2.3; "Ospite non indicato" quando manca), date e **timestamp di sincronizzazione della fonte** ("Airbnb — sincronizzato alle 14:32", "Booking — sincronizzato alle 09:10") (FR-6, NFR-2, UX-DR6)
**And** sceglie quale Prenotazione tenere e riceve **istruzioni guidate passo-passo** per bloccare le date sull'altro Canale; il sistema **non esegue scritture automatiche sull'OTA** (FR-6 Out of Scope, Non-Goal §8)
**And** la transizione `rilevato → gestito` avviene **solo per azione esplicita dell'Host**; il Conflitto resta nello storico, mai cancellato (FR-6, AD-5)
**And** se la sovrapposizione **persiste** nei sync successivi oltre una finestra configurabile (default proposto **G3-5**: 24h) dopo `gestito`, si apre un **nuovo** Conflitto collegato al precedente — il sistema non si fida ciecamente della conferma umana (AD-5, UX UJ-2 edge)
**And** l'intero flusso è completabile da tastiera e ha equivalenti testuali per screen reader (UX-DR10)

### Story 2.8: Contributo alla Dashboard — riepilogo calendario e stato Conflitti

As an Host,
I want vedere in Dashboard un riepilogo del calendario e lo stato dei Conflitti,
So that capisca "sono a posto?" senza aprire ogni sezione.

**Acceptance Criteria:**

**Given** la Dashboard frame (Story 1.3) e i dati di calendario/Conflitti
**When** l'Host apre la Dashboard
**Then** vede un badge di stato Conflitti ("0 conflitti" quando pulito; conteggio e link quando ci sono Conflitti `rilevato`) con trattamento testo + icona, non solo colore (UX-DR2, UX-DR4)
**And** un Conflitto `rilevato` è evidenziato con severità alta finché non risolto (FR-6, UX §4.5)
**And** il riepilogo mostra "dati aggiornati alle HH:MM" coerente con il calendario (NFR-2, UX-DR6)

---

## Epic 3: Adempimenti italiani "in regola"

Un unico cruscotto per i quattro Adempimenti, con scadenze, promemoria affidabili, compilazione assistita e GDPR by design sui dati identità. Governato da AD-7, AD-8, AD-9, AD-10, AD-11, AD-16, AD-17. Realizza UJ-3. Ordine interno: motore → cruscotto → CIN (plugin più semplice) → privacy → Alloggiati → tassa → ISTAT → dashboard/osservabilità → gate legale di rilascio.

> **Prerequisito di rilascio (non di sviluppo), AR-12:** le feature di compliance con effetti verso terzi non vanno **messe in produzione per Host reali** prima della verifica legale delle fonti normative (PRD §12.1) e della conferma della retention (G2-D). Lo sviluppo test-first procede con parametri configurabili; il gate di rilascio è la Story 3.9.

### Story 3.1: Motore Adempimenti — entità unica, macchina a stati, contratto plugin

As an Host,
I want che tutti i miei Adempimenti siano gestiti con la stessa logica affidabile di stati e scadenze,
So that ogni obbligo sia tracciato allo stesso modo e nessuno sia chiuso senza che sia davvero fatto.

**Acceptance Criteria:**

**Given** il modulo `adempimenti` con l'entità unica `adempimento` (proprietario unico scrittore, AD-18)
**When** si implementa il motore
**Then** tutti i tipi usano gli stati `da_fare / in_sospeso / completato / non_applicabile` (enum Postgres) e lo stesso motore di scadenze/promemoria; la transizione a `non_applicabile` richiede una **motivazione registrata** (AD-7, UX §4.5)
**And** ogni tipo implementa il contratto `AdempimentoPlugin` (`trigger`, `calcola_scadenza`, `prepara`, `submit` opzionale, `evidenza`) e il **Livello di automazione per tipo è configurazione runtime** (FR-16, parametrico su [DECISIONE G2-A]), mai un branch di codice per tipo fuori dal plugin (AD-7)
**And** la transizione a **`completato` avviene SOLO** per (a) conferma esplicita dell'Host o (b) esito di trasmissione positivo registrato dall'adapter — nessun percorso marca `completato` allo scadere del tempo (AD-8, SM-C2)
**And** ogni transizione di stato e ogni trasmissione scrivono un record append-only in `evento_compliance` (chi/cosa/quando/esito) (AD-16, NFR-7)
**And** gli eventi/job usati dal motore sono dichiarati nel catalogo unico `core/events.py` (AD-17)

### Story 3.2: Cruscotto Adempimenti, scadenze, gerarchia di urgenza e promemoria

As an Host,
I want vedere in un unico posto tutti gli Adempimenti aperti ordinati per urgenza e ricevere promemoria affidabili,
So that non dimentichi mai una scadenza — che è la ragione per cui mi fido di HostPilot.

**Acceptance Criteria:**

**Given** il motore Adempimenti (Story 3.1) e la fondazione `notifiche` (Story 2.6)
**When** l'Host apre il Cruscotto Adempimenti
**Then** ogni Adempimento mostra stato, scadenza e Struttura, con badge testo + icona distinguibili anche senza colore (FR-15, UX-DR4)
**And** l'ordinamento segue una **gerarchia di urgenza a 3 livelli** — normale (> 48h) / urgente (6–48h) / critico-scaduto (< 6h o scaduto) più il livello dedicato < 2h per soggiorni < 24h — calcolata **lato server** in Europe/Rome con soglie configurabili ed esposta come campo `livello_urgenza` dell'API (il frontend la presenta, non la ricalcola) (UX-DR5, AD-14, AD-3)
**And** i promemoria sono generati con **anticipo configurabile** rispetto alla scadenza, come job durevoli, con escalation a frequenza crescente all'avvicinarsi del termine (FR-15, NFR-3, AD-10, UX UJ-3 edge)
**And** un Adempimento scaduto e non completato resta evidenziato con severità alta, mai auto-archiviato né mai marcato `completato` automaticamente (FR-15, AD-8, UX §4.5)
**And** il countdown/scadenza relativa ha un equivalente testuale per screen reader (UX-DR9)

### Story 3.3: Adempimento CIN — tracciamento ed esposizione

As an Host,
I want tracciare il CIN di ogni Struttura e sapere se soddisfo i requisiti di esposizione,
So that non rischi la sanzione per CIN mancante o non esposto.

**Acceptance Criteria:**

**Given** il motore Adempimenti (Story 3.1) e il campo CIN sulla Struttura (Story 1.4)
**When** una Struttura è priva di CIN
**Then** esiste un Adempimento CIN in stato `da_fare` in evidenza, mai un blocco dell'onboarding (FR-14, UJ-1)
**And** il sistema fornisce una **checklist dei requisiti di esposizione** del CIN (es. presenza negli annunci) che l'Host può marcare come soddisfatti (FR-14)
**And** l'emissione del codice presso la BDSR resta fuori scope: il prodotto **traccia e ricorda, non emette** (Non-Goal §8)
**And** il plugin CIN implementa il contratto `AdempimentoPlugin` senza dati sensibili né canale di invio (AD-7)

### Story 3.4: Dati identità Ospite — segregazione, cifratura e retention (GDPR)

As an Host,
I want che i documenti d'identità dei miei Ospiti siano trattati in modo sicuro e cancellati quando non servono più,
So that io sia in regola col GDPR e i miei Ospiti si fidino a darmi i loro dati.

**Acceptance Criteria:**

**Given** il modulo `privacy` con la tabella segregata `ospite_documento` (proprietario unico scrittore, AD-18)
**When** si trattano i dati del documento d'identità
**Then** vi vivono **solo** i campi richiesti dal tracciato Alloggiati Web (minimizzazione, NFR-11), cifrati **a campo** con AES-256-GCM ed envelope encryption (DEK per record, KEK nel secret manager, rotazione senza ri-cifratura di massa) (AD-11, NFR-13)
**And** un **job di retention durevole** elimina i dati documento **N giorni dopo `completato`** e comunque **non oltre M giorni dal check-out** anche se l'Adempimento non è mai stato completato; la purge **non chiude** l'Adempimento (resta aperto senza dati) (AD-11, NFR-12) — N/M sono configurazione ([DECISIONE G2-D]; default proposti **G3-3**: N=30, M=90, da confermare col legale)
**And** è **vietato** scrivere i campi documento in log, eventi, outbox o risposte API di default; la UI li ri-espone solo per **azione esplicita di audit** (AD-11, AD-16, UX-DR8)
**And** l'accesso è scopato all'Host proprietario (AD-2, NFR-14) e la cancellazione su richiesta dell'interessato usa la stessa procedura della purge, con evidenza (NFR-15, AD-20)
**And** nessun dato reale di Ospiti è usato nei fixture/test (NFR-16)

### Story 3.5: Adempimento Alloggiati Web — compilazione assistita

As an Host,
I want registrare il check-in e inviare la comunicazione Alloggiati Web con i dati precompilati,
So that adempia in tempo (24h / 6h) in un momento in cui sono sotto pressione, con l'ospite davanti.

**Acceptance Criteria:**

**Given** il motore Adempimenti (3.1), la privacy dei dati identità (3.4) e il modulo `calendario`
**When** l'Host registra il check-in di un Ospite (azione esplicita sulla Prenotazione, che emette `prenotazione.checkin_registrato`, AD-17)
**Then** si apre un Adempimento Alloggiati Web con **scadenza calcolata e visibile** dai termini configurati (24h standard, 6h per soggiorni < 24h) in Europe/Rome (FR-11, AD-3, AD-9) — termini **configurabili, non hardcoded**
**And** la compilazione assistita precompila i campi noti dalla Prenotazione; l'Host completa/verifica i campi **minimizzati** del documento (form senza campi extra, scopo dichiarato inline) (UX-DR8), e il modulo integra i dati Ospite via service di `calendario` (anagrafica) e `privacy` (documento), mai con UPDATE diretti (AD-18)
**And** l'MVP genera il **tracciato ministeriale (txt) + upload guidato** sul portale; l'Adempimento resta `in_sospeso` finché l'Host non conferma l'avvenuta comunicazione, poi passa a `completato` con timestamp (FR-11, AD-8)
**And** l'`evidenza` conserva solo prova **non sensibile** (timestamp, esito, hash ricevuta), che sopravvive alla purge dei dati (AD-11, NFR-7)
**And** l'**invio automatico** via `WS_ALLOGGIATI` (SOAP) è **fuori MVP**, previsto come fast-follow dietro `submit` senza ridisegno; se attivato, un errore di trasmissione lascia `in_sospeso` col motivo visibile, mai `completato` (AR-13, AD-8, SM-C2, UX-DR7)

### Story 3.6: Adempimento Tassa di soggiorno — calcolo e registro

As an Host,
I want calcolare la Tassa di soggiorno dovuta secondo le regole del mio Comune e tenerne il registro,
So that versi l'importo giusto alle scadenze giuste senza rifare i conti a mano.

**Acceptance Criteria:**

**Given** il motore Adempimenti (3.1) e `config_normativa` (Story 1.5)
**When** si calcola la Tassa per una Struttura
**Then** il calcolo usa la configurazione del Comune (aliquota, esenzioni, periodicità); **nessuna aliquota è hardcodata**; gli importi sono in **centesimi interi** (`importo_cent`), mai float (FR-12, AD-9, spine)
**And** il sistema tiene il registro incassi/versamenti (`movimento_tassa`, append-only) e produce il riepilogo periodico secondo la periodicità configurata, incluso il riepilogo utile alla dichiarazione annuale telematica (FR-12)
**And** le esenzioni configurabili (es. minori, durata massima) sono applicate al calcolo (FR-12)
**And** un Comune non ancora configurato produce lo stato `configurazione_non_disponibile` con promemoria manuale, non un importo errato (FR-12, AD-9)
**And** il registro modella la responsabilità di versamento dell'Host (host = responsabile d'imposta) — dettaglio confermato in fonte primaria nel reviewer gate dell'architettura, da validare col legale prima del rilascio (Story 3.9)

### Story 3.7: Adempimento ISTAT/ROSS1000 — rilevazione movimento turistico

As an Host,
I want compilare la rilevazione ISTAT/ROSS1000 secondo il tracciato della mia Regione ed essere ricordato delle scadenze,
So that rispetti l'obbligo statistico, anche quando non ho avuto ospiti nel periodo.

**Acceptance Criteria:**

**Given** il motore Adempimenti (3.1) e `config_normativa` (Story 1.5)
**When** matura il periodo di rilevazione
**Then** il sistema compila il prospetto (arrivi, presenze, provenienza Ospiti) secondo il **tracciato e la periodicità della Regione** (nessun tracciato unico hardcodato) (FR-13, AD-9)
**And** il promemoria è generato **anche in assenza di Prenotazioni** nel periodo (movimento zero) (FR-13)
**And** le Regioni supportate all'MVP restano **parametriche rispetto a [DECISIONE G2-B]** (perimetro iniziale), con degrado sicuro `configurazione_non_disponibile` altrove (FR-13, AD-9)
**And** eventuali adapter di invio per Regione sono rinviati post-MVP come plugin, senza ridisegno del motore (AD-7)

### Story 3.8: Contributo Dashboard Adempimenti e osservabilità delle metriche di compliance

As an Host,
I want vedere in Dashboard gli Adempimenti in scadenza,
So that "un solo posto" mi dica se sono a posto con gli obblighi.

**Acceptance Criteria:**

**Given** la Dashboard frame (1.3), il motore (3.1) e il cruscotto (3.2)
**When** l'Host apre la Dashboard
**Then** vede un riepilogo degli Adempimenti in scadenza ordinati per urgenza, con lo stesso vocabolario visivo del Cruscotto (UX-DR2, UX-DR5)
**And** le metriche di successo sono **misurabili dagli eventi di dominio** senza strumentazione separata: SM-2 (`completato` entro scadenza da `evento_compliance`), SM-C2 (strutturalmente 0 per AD-8), oltre a SM-1/SM-C1 dai Conflitti (AD-16, NFR-7)
**And** i log strutturati JSON (`request_id`, `host_id`) non contengono **mai** campi documento (AD-11, AD-16)

### Story 3.9: Gate di rilascio compliance — verifica legale e conferma retention

As a squad leader (John) e Product Owner (Fahad),
I want che le feature di compliance non vadano in produzione per Host reali senza verifica legale e retention confermata,
So that non promettiamo "in regola" su basi normative non primarie.

**Acceptance Criteria:**

**Given** le feature di compliance sviluppate test-first con parametri configurabili (Stories 3.5, 3.6, 3.7)
**When** si valuta il go-live per Host reali
**Then** esiste una **verifica legale/commercialista documentata** delle fonti normative rilevanti (termini Alloggiati, aliquote/soglie fiscali, responsabilità versamento tassa, retention) — PRD §12.1, §7 (AR-12)
**And** i parametri normativi in `config_normativa` (termini, retention N/M, soglia fiscale, aliquote) sono impostati ai valori confermati (chiude [DECISIONE G2-D]) senza rilascio di codice (AD-9, AD-11)
**And** finché questo gate non è soddisfatto, l'invio/effetto verso terzi resta disabilitato o in sola compilazione assistita con disclaimer, coerente col principio "assiste e ricorda, non certifica" (UX-DR7)
**And** questo gate **non blocca lo sviluppo** delle Stories precedenti né alcuna Story di altri Epic: è un criterio di **rilascio**, non di implementazione

---

## Epic 4: Motore di Regole di prezzo

L'Host configura Regole di prezzo, vede l'anteprima calcolata e spiegata, ed esporta i prezzi. Motore di calcolo consultabile, non channel manager. Governato da AD-6, AD-14. Realizza UJ-5.

### Story 4.1: Definizione delle Regole di prezzo

As an Host,
I want creare Regole di prezzo per stagione, weekend, last-minute e soggiorno minimo per ogni Struttura,
So that imposti i prezzi una volta invece di ricalcolare tutto a mano su Excel.

**Acceptance Criteria:**

**Given** il modulo `prezzi` con la tabella `regola_prezzo` (proprietario unico scrittore, AD-18)
**When** l'Host crea una Regola per una Struttura
**Then** può definire tipo (base, alta/bassa stagione, maggiorazione weekend, sconto last-minute, soggiorno minimo), intervallo/condizione e valore (FR-8)
**And** ogni Regola è visibile in un elenco con la sua condizione ed effetto in linguaggio naturale ("Alta stagione: 1 giu – 15 set, +30%") (FR-8, UJ-5)
**And** un nuovo tipo di Regola è una riga (`tipo`, condizione, valore), estensione del valutatore e non una migrazione del modello (AD-6)

### Story 4.2: Calcolo, precedenza e anteprima del prezzo spiegabile

As an Host,
I want vedere il prezzo calcolato per ogni data con la spiegazione di quale Regola l'ha determinato,
So that mi fidi del numero e capisca perché, anche quando più Regole si sovrappongono.

**Acceptance Criteria:**

**Given** le Regole vigenti di una Struttura
**When** il sistema calcola il prezzo di una data
**Then** il prezzo è **sempre ricalcolato** dalla funzione di valutazione pura (nessun prezzo materializzato come verità; cache solo come derivata invalidabile) (AD-6)
**And** la **precedenza deterministica** è definita in un solo punto — proposta `last-minute > weekend > stagione > prezzo base` con il **soggiorno minimo come vincolo ortogonale** — e resta **parametrica rispetto a [DECISIONE G3-2]** (da ratificare a G3) (AD-6, FR-8)
**And** ogni prezzo porta la **catena delle Regole applicate** ("€145 — Weekend + Alta stagione"): la Regola vincente è sempre resa esplicita in UI, qualunque sia la precedenza (UX-DR13, UJ-5 edge)
**And** l'arrotondamento è half-up al centesimo, definito una sola volta nel valutatore; anteprima, export e API mostrano sempre il valore del valutatore, mai un ricalcolo del frontend (AD-6, AD-14)
**And** l'anteprima è mostrata sul calendario per data/Struttura, con soggiorno minimo per data (FR-9); senza Regole definite il calendario mostra un prezzo base placeholder con invito a configurare, mai "N/D" senza spiegazione (UJ-5 edge)

### Story 4.3: Esportazione/consultazione dei prezzi

As an Host,
I want esportare i prezzi calcolati in un formato che posso riportare sui portali,
So that applichi i prezzi su Airbnb/Booking manualmente, dato che HostPilot non scrive per me.

**Acceptance Criteria:**

**Given** i prezzi calcolati (Story 4.2)
**When** l'Host esporta
**Then** ottiene un **CSV** per data/Struttura con prezzo, soggiorno minimo e Regola determinante (FR-10, AD-6) — formato esatto da rifinire in Fase 4 con Sally (PRD §13.4)
**And** il **push automatico verso Airbnb/Booking è fuori scope** (Feed iCal read-only; nessuna scrittura OTA) (FR-10 Out of Scope, Non-Goal §8)

### Story 4.4: Contributo Dashboard — riepilogo prezzi

As an Host,
I want un riepilogo prezzi in Dashboard,
So that "un solo posto" includa anche lo stato dei miei prezzi.

**Acceptance Criteria:**

**Given** la Dashboard frame (1.3) e i prezzi calcolati
**When** l'Host apre la Dashboard
**Then** vede un riepilogo sintetico dei prezzi applicati/prossimi per Struttura, coerente coi formati italiani (UX-DR2, UX-DR11)

---

## Epic 5: Operatività — pulizie e messaggi Ospiti

L'Host pianifica i Turni di pulizia e configura i Messaggi automatici agli Ospiti, senza mai marcare inviato ciò che non è partito. Governato da AD-10, AD-13, AD-19. Riusa la fondazione `notifiche` (Story 2.6).

### Story 5.1: Turni di pulizia legati ai check-out

As an Host,
I want che HostPilot mi generi i Turni di pulizia dai check-out e me li faccia segnare come completati,
So that coordini le pulizie senza rincorrere promemoria sparsi.

**Acceptance Criteria:**

**Given** il modulo `operativita` con `turno_pulizia` (proprietario unico scrittore, AD-18) e gli eventi del `calendario`
**When** una Prenotazione ha un check-out
**Then** un evento di dominio genera/suggerisce un `turno_pulizia` per quella Struttura/data (FR-18, AD-19)
**And** l'Host vede i Turni e può marcarli **completati** (FR-18)
**And** se la Prenotazione di origine **cessa** (`prenotazione.cessata`), i Turni futuri derivati sono **annullati**, mai lasciati orfani (AD-19)
**And** l'assegnazione a collaboratori esterni resta **fuori MVP**; il modello non la preclude (un campo assegnatario in v2) (PRD §9.2)

### Story 5.2: Messaggi automatici agli Ospiti

As an Host,
I want configurare messaggi automatici per pre-arrivo, check-in e check-out,
So that comunichi con gli Ospiti senza scrivere ogni volta a mano, e senza illudermi che un messaggio sia partito quando non lo è.

**Acceptance Criteria:**

**Given** il modulo `operativita` con `messaggio` e la fondazione `notifiche` (Story 2.6, canale email)
**When** si verifica un evento del ciclo di vita Prenotazione (pre-arrivo/check-in/check-out)
**Then** un job durevole genera il Messaggio dal template configurabile per evento/Struttura; il canale MVP è **email** (FR-19, AD-13, AD-10)
**And** se il contatto Ospite **manca** (i Feed spesso non lo forniscono), il Messaggio diventa un **task visibile "da inviare manualmente"** per l'Host — mai scartato in silenzio, mai marcato inviato (AD-13, UX-DR7)
**And** se la Prenotazione **cessa**, i Messaggi futuri derivati sono annullati (AD-19)

### Story 5.3: Contributo Dashboard — operatività

As an Host,
I want vedere in Dashboard i prossimi Turni di pulizia e i Messaggi da inviare manualmente,
So that "un solo posto" copra anche l'operatività quotidiana.

**Acceptance Criteria:**

**Given** la Dashboard frame (1.3), i Turni (5.1) e i Messaggi (5.2)
**When** l'Host apre la Dashboard
**Then** vede i prossimi Turni di pulizia e gli eventuali Messaggi "da inviare manualmente" in evidenza, con badge testo + icona (UX-DR2, UX-DR4, UX-DR7)

---

_Fine Epic Breakdown. Stato: draft, co-artefatto del gate umano **G3** (Architettura + Epics/Stories + Readiness insieme). Le Stories sono parametriche rispetto a [DECISIONE G2-A…E] e [G3-1…5]: la loro chiusura è attesa al gate. Nessuno scaffolding applicativo (Story 1.1) prima dell'approvazione di Fahad (`project-context.md` §6). Verifica di coerenza completa in `docs/implementation-readiness.md`._

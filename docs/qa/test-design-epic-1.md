---
title: 'Test Design — Epic 1 (Fondamenta e gestione Strutture)'
status: draft
phase: '4 · Implementation — gate di qualità (Murat, Test Architect)'
created: 2026-07-25
author: Murat — Master Test Architect
scope: 'Epic 1, Story 1.1 → 1.6'
inputDocuments:
  - docs/epics.md (Epic 1, Story 1.1–1.6, acceptance criteria Given/When/Then)
  - docs/architecture.md + docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-1…AD-20)
  - docs/prd.md (FR-1, FR-2, FR-17; NFR-8, NFR-9, NFR-14, NFR-16)
  - docs/ux-spec.md (UX-DR)
related:
  - docs/stories/story-1.1-scaffolding-monorepo-core-ci.md (consegnata, PR #9)
  - docs/stories/story-1.2-registrazione-auth-host.md (consegnata, PR #10)
---

# Test Design — Epic 1

Piano di test **essenziale e risk-based** per l'Epic 1. Recupera il kickoff di qualità
saltato: definisce *cosa* testare, a *quale livello*, con *quale priorità*, e traccia
ogni acceptance criteria (AC) di `epics.md` verso un invariante architetturale (AD-N).
Non è una suite: è il contratto di copertura contro cui misurare le Story 1.1→1.6 al gate.

> **Principio guida:** la profondità del test scala con il rischio (probabilità × impatto).
> Preferire sempre il livello più basso possibile (unit > integration > e2e). Le API sono
> cittadini di prima classe: gran parte di Epic 1 non ha ancora UI e va coperta al confine
> service/API. Nessun dato reale di Ospiti nei fixture (NFR-16).

---

## 1. Valutazione del rischio (Epic 1)

| ID | Area di rischio | Prob. | Impatto | Punteggio | AD/NFR | Livello test prioritario |
| --- | --- | :---: | :---: | :---: | --- | --- |
| R-A | **Isolamento tenant** — un Host legge/scrive dati di un altro (`host_id` da input) | Bassa | Critico | **Alto** | AD-2, NFR-14 | integration (API) + guardia strutturale |
| R-B | **Autenticazione** — sessione forgiabile, password recuperabile, enumerazione utenti | Media | Critico | **Alto** | AD-15 | integration (API) + unit (service) |
| R-C | **Perdita/duplicazione job & eventi** — consegna non atomica, at-least-once violato | Media | Alto | **Alto** | AD-1, AD-10 | integration (DB reale, concorrenza) |
| R-D | **Cap 3 Strutture & archiviazione** — 4ª attiva ammessa, cancellazione fisica di dati collegati | Media | Alto | **Alto** | AD-18, AD-20 | integration (service) |
| R-E | **Regime fiscale derivato** — valore persistito/stale, soglia hardcoded, transizione 2↔3 sbagliata | Media | Alto | **Alto** | AD-12 | unit (derivazione) + integration (evento) |
| R-F | **Degrado normativo non sicuro** — calcolo con default inventati invece di `configurazione_non_disponibile` | Media | Alto | **Alto** | AD-9 | integration (service) |
| R-G | **Contratto API divergente dal client TS** — drift OpenAPI ↔ client | Media | Medio | **Medio** | AD-14 | contract (CI `api-contract`) |
| R-H | **Semantica temporale** — intervalli/overlap errati, timestamp naive persistiti | Bassa | Alto | **Medio** | AD-3 | unit |
| R-I | **Migrazioni** — forward-only violato, schema divergente dai modelli | Bassa | Alto | **Medio** | AR-11 | integration (Alembic su PG reale) |
| R-J | **a11y / i18n** — badge solo-colore, formati non italiani, tastiera incompleta | Media | Medio | **Medio** | NFR-8, NFR-9, UX-DR4/11 | e2e (Story 1.3+) |

Le aree **Alto** sono P0 (obbligatorie al gate). Le **Medio** sono P1. Nessuna area di
Epic 1 è puramente cosmetica: anche i2n e a11y sono requisiti (NFR-8/9).

---

## 2. Strategia per livello (piramide)

- **Unit** — logica pura senza I/O: `date_range` (AD-3), `money` (centesimi interi),
  derivazione Regime fiscale (AD-12), validazione payload catalogo (AD-17), backoff dei job.
  Veloci, deterministici, la base larga della piramide.
- **Integration (service/repository + DB reale PostgreSQL 18)** — il cuore di Epic 1:
  auth, tenancy, outbox/job con concorrenza (`SKIP LOCKED`), cap Strutture, config
  normativa, migrazioni Alembic. Su DB **reale** (no SQLite): le proprietà testate
  (SKIP LOCKED, JSONB, vincoli, timezone) sono specifiche di Postgres.
- **Contract** — job CI `api-contract`: rigenera OpenAPI + client TS e fallisce sul `git diff`.
  È il guardiano di AD-14; va mantenuto verde ad ogni Story che tocca l'API.
- **e2e (Playwright, dalla Story 1.3 — prima UI reale)** — solo i percorsi critici e i
  requisiti che esistono *solo* in UI: navigazione 5 voci, formati it-IT, a11y (badge
  testo+icona, contrasto, tastiera), pannello Regime fiscale a schermo intero. Pochi,
  stabili: la flakiness è debito tecnico critico.
- **Strutturale (meta-test)** — la guardia `test_auth_convention.py` (ogni endpoint non
  pubblico dipende da `get_current_host`) è il modello da estendere: convenzioni imposte
  dai test, non dalle code review. Raccomandato un gemello per la tenancy (vedi §4, G-3).

---

## 3. Copertura per Story (AC → livello → priorità → stato)

Legenda stato: ✅ coperto nella consegna · ⚠️ coperto ma con gap (vedi §4) · ⛔ da consegnare.

### Story 1.1 — Scaffolding, `core`, CI (consegnata)

| AC (sintesi) | AD | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| `date_range` semiaperto `[in,out)`, overlap=intersezione, UTC | AD-3 | unit | P0 | ✅ |
| Catalogo eventi/job versionato, payload = soli identificatori scalari | AD-17 | unit | P0 | ✅ |
| Outbox: emit nella stessa tx, rollback annulla, consegna post-commit | AD-1 | integration | P0 | ✅ |
| Outbox/Job: claim concorrente `FOR UPDATE SKIP LOCKED` (2 sessioni) | AD-1/10 | integration | P0 | ✅ |
| Job: retry/backoff esponenziale, esaurimento → `failed`, idempotenza | AD-10 | integration | P0 | ⚠️ (G-1) |
| Worker: consegna outbox poi job durevoli scaduti | AD-1/10 | integration | P0 | ✅ |
| API `/api/v1`, errori RFC 9457 `problem+json` | AD-14 | integration | P0 | ✅ |
| OpenAPI ↔ client TS allineati | AD-14 | contract (CI) | P0 | ✅ |
| Convenzioni: UUIDv7 PK, centesimi interi, enum di stato | spine | unit | P1 | ✅ |
| Migrazioni Alembic forward-only su PG18 | AR-11 | integration | P1 | ✅ |

### Story 1.2 — Registrazione e auth Host (consegnata)

| AC (sintesi) | AD | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Password argon2id (mai in chiaro, hash `$argon2id$`) | AD-15 | integration | P0 | ✅ |
| Sessione server-side, cookie HttpOnly+Secure+SameSite=Lax | AD-15 | integration | P0 | ✅ |
| Token opaco, in DB solo hash SHA-256 | AD-15 | integration | P0 | ✅ |
| Login senza enumerazione utenti (email ignota ≡ password errata) | AD-15 | integration | P0 | ✅ |
| Logout server-side invalida la sessione (token riproposto → 401) | AD-15 | integration | P0 | ✅ |
| Sessione scaduta → 401; cookie contraffatto → 401 | AD-15 | integration | P0 | ✅ |
| `host_id` **solo** dalla sessione, mai da query/header client | AD-2 | integration | P0 | ✅ |
| Ogni endpoint non pubblico richiede sessione (guardia strutturale) | AD-2/15 | strutturale | P0 | ✅ |
| Registrazione email duplicata rifiutata (case-insensitive) | AD-18 | integration | P0 | ⚠️ (G-2) |
| Validazione 422 non riflette la password in chiaro | AD-15/NFR-6 | integration | P1 | ⛔ (G-4) |
| `host_id` NOT NULL su tabella di sessione | AD-2 | integration | P1 | ✅ |

### Story 1.3 — App shell, navigazione, i18n, Account (da consegnare)

| AC (sintesi) | Rif | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Navigazione 5 voci (tab mobile / sidebar desktop), Strutture in impostazioni | UX-DR1 | e2e | P0 | ⛔ |
| Selettore Struttura trasversale con default "Tutte le Strutture" | UX-DR1 | e2e | P0 | ⛔ |
| Dashboard frame con stato vuoto rassicurante | UX-DR2 | e2e | P1 | ⛔ |
| UI it-IT + formati italiani (gg/mm/aaaa, €, virgola) | NFR-9/UX-DR11 | e2e + unit(format) | P0 | ⛔ |
| Pannello Account / preferenze notifica | UX-DR15 | e2e + integration | P1 | ⛔ |
| Layout responsive mobile-first, densità 1–3 Strutture | UX-DR12 | e2e | P1 | ⛔ |
| a11y baseline WCAG 2.1 AA sui flussi critici | NFR-8 | e2e (axe) | P0 | ⛔ |

### Story 1.4 — Strutture con cap 3 (da consegnare)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Creazione richiede nome+Comune+Regione; CIN opzionale | FR-1 | integration | P0 | ⛔ |
| CIN assente → indicatore non bloccante "CIN mancante" | FR-1/UJ-1 | integration+e2e | P1 | ⛔ |
| 4ª Struttura **attiva** rifiutata; cap imposto nel service (unico punto) | FR-1/AD-12 | integration | P0 | ⛔ |
| Cap "3 attive" ≠ soglia fiscale (parametri distinti) | AD-12 | unit/integration | P0 | ⛔ |
| Struttura con dati collegati → `archiviata`, mai cancellata; audit append-only | AD-20 | integration | P0 | ⛔ |
| Struttura archiviata esce da conteggio attive e da Regime fiscale | AD-20/AD-12 | integration | P0 | ⛔ |
| `struttura.host_id` NOT NULL + scoping repository (tenancy) | AD-2 | integration | P0 | ⛔ |
| Flusso guidato passo-passo, skippabile | UX-DR3 | e2e | P2 | ⛔ |

### Story 1.5 — Comune/Regione + config normativa, degrado sicuro (da consegnare)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| `comune_config`/`regione_config` a validità temporale (`valido_dal/al`) | AD-9 | integration | P0 | ⛔ |
| Anagrafica seedata da codici ISTAT; update solo via endpoint interni auditati | AD-9 | integration | P0 | ⛔ |
| Cambio Comune ricarica config Tassa senza perdere storico versamenti | FR-2 | integration | P0 | ⛔ |
| Comune non configurato → stato `configurazione_non_disponibile`, mai default inventati | AD-9/FR-2 | integration | P0 | ⛔ |
| Tono informativo, non errore-colpa | UX §5.1 | e2e | P1 | ⛔ |
| Aliquote/periodicità/termini = dati, aggiornabili senza rilascio | NFR-4 | integration | P0 | ⛔ |

### Story 1.6 — Regime fiscale derivato (da consegnare)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Regime **sempre derivato** da `count(Strutture non archiviate)` alla lettura, mai persistito | AD-12 | unit + integration | P0 | ⛔ |
| Soglia e parametri fiscali in `config_normativa`, mai costanti nel codice | AD-12 | integration | P0 | ⛔ |
| 1–2 Strutture → cedolare (informativo); alla 3ª → evento + pannello schermo intero | FR-17/UX-DR14 | integration(evento)+e2e | P0 | ⛔ |
| Pannello Regime persistente con disclaimer sempre visibile | UX-DR14 | e2e | P1 | ⛔ |
| Ridiscesa a 2 (archiviazione 3ª) → stato 1–2, nessuna notifica residua | UJ-4 edge | integration | P0 | ⛔ |
| Contenuto informativo con disclaimer, mai calcolo d'imposta | Non-Goal | e2e | P1 | ⛔ |

---

## 4. Gap di copertura e raccomandazioni

Rilievi emersi dalla review retroattiva 1.1 e cross-review 1.2. Sono **proposte di
correzione** ad Amelia (le entità applicative restano di sua competenza); i test/fixture/CI
li porto io. Priorità indicata.

- **G-1 (P1, correttezza AD-1/AD-10) — Atomicità per-item degli handler.** In
  `deliver_pending` e `run_due_jobs` un handler che *scrive e poi solleva* lascia le sue
  mutazioni ORM parziali nella sessione: vengono committate dal worker insieme al
  bookkeeping di fallimento. Manca un SAVEPOINT per item. Con at-least-once + retry questo
  può produrre **effetti collaterali doppi** o stato parziale persistito. I test di
  fallimento esistenti usano handler che sollevano *senza scrivere*, quindi il percorso non
  è coperto. → Proposta: avvolgere ogni chiamata handler in `session.begin_nested()` con
  rollback del savepoint su eccezione. Test di regressione: handler *write-then-raise* →
  asserire che nessuno stato parziale sopravvive e che l'evento/job resta ritentabile.

- **G-2 (P1, robustezza) — Registrazione concorrente stessa email.** Il controllo
  `by_email` + insert non è atomico: due registrazioni concorrenti con la stessa email
  fanno passare entrambe il controllo, poi una viola il vincolo `uq_host_email` →
  `IntegrityError` non intercettato → **500** invece di **409**. → Proposta: intercettare
  `IntegrityError` sull'email e mappare a 409. Test: due insert in race → una 201, una 409,
  mai 500.

- **G-3 (P0, tenancy) — Guardia strutturale sullo scoping `host_id`.** La guardia auth
  (`test_auth_convention.py`) verifica che ogni endpoint abbia una sessione, ma **non** che
  ogni query su tabella tenant-owned passi dal repository filtrando `host_id`. Dalla Story
  1.4 (prima tabella con `host_id`) serve un meta-test gemello che fallisca se un modulo
  interroga una tabella tenant-owned senza filtro tenant. È il moltiplicatore di rischio più
  alto di tutto l'Epic (R-A). → Da introdurre con la Story 1.4.

- **G-4 (P1, igiene sicurezza NFR-6) — La 422 riflette la password.** Il gestore di
  `RequestValidationError` restituisce `exc.errors()`, che in Pydantic v2 include il campo
  `input`: su password troppo corta a `/auth/registrazione` o `/auth/login` la **password in
  chiaro viene rimandata** nel corpo `errors[].input` (e finisce in eventuali log del
  client/proxy). Stesso mittente → rischio basso, ma è igiene da chiudere. → Proposta:
  redigere `input` (e `url`) per i campi sensibili prima di serializzare. Test: 422 su
  password → il corpo NON contiene il valore inviato.

- **G-5 (P2, tech-debt) — Sessioni scadute mai raccolte + nessun rate-limit login.** Le
  sessioni scadute restano in tabella (crescita illimitata); il login non ha throttling/
  lockout (brute-force mitigato solo dal costo argon2id). → Proposta: purge come `job`
  durevole (AD-10) e rate-limit come follow-up NFR-sicurezza. Non blocca Epic 1.

---

## 5. Fixture & dati di test (vincoli)

- **Nessun dato reale di Ospiti** (NFR-16): email su dominio `example.com`, documenti
  d'identità mai nei fixture. Il pattern già in uso in 1.2 è la baseline.
- **DB reale in CI** (`HOSTPILOT_TEST_DB_REQUIRED=1`): il salto dei test DB è un errore in
  pipeline — una pipeline verde implica sempre che i test su Postgres sono girati. Mantenere.
- **Isolamento tra test**: TRUNCATE delle tabelle tra i test (già in `conftest.py`). Ogni
  nuova tabella tenant-owned va aggiunta a `TABELLE_DA_SVUOTARE`.
- **Determinismo temporale**: iniettare `now` nei test che dipendono dal tempo (già fatto
  per job/sessione); mai `sleep` per attendere scadenze.

---

## 6. Criteri di gate per le Story di Epic 1

Una Story è candidabile al merge umano quando:

1. **Tutti gli AC P0 della Story hanno un test verde** al livello indicato in §3.
2. **CI verde**: lint, typecheck, test (con DB reale), build, e job `api-contract` (se l'API
   cambia). Zero test flaky.
3. **Guardie strutturali verdi**: auth-convention (tutte le Story) e tenant-scoping (da 1.4).
4. **Nessun dato reale** nei fixture; segreti fuori dal repo.
5. I **gap P0/P1 aperti** che toccano la Story sono chiusi o esplicitamente accettati
   dall'umano con motivazione.

Il verdetto di gate (PASS / CONCERNS / FAIL / WAIVED) è una **raccomandazione**: la
decisione di rilascio resta all'umano (Fahad).

---

_Documento vivo: ad ogni Story consegnata la relativa tabella §3 passa da ⛔/⚠️ a ✅ e i gap
§4 chiusi vengono barrati. Aggiornamenti via PR._

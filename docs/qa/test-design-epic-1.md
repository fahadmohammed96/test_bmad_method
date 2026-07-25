---
title: 'Test Design e matrice di tracciabilità — Epic 1 (Fondamenta e gestione Strutture)'
status: 'chiuso — Epic 1 a debito zero (2026-07-25, vedi §7.6)'
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
  - docs/stories/story-1.3-app-shell-navigazione-account.md (consegnata, PR #13)
  - docs/stories/story-1.4-registrazione-strutture-cap3.md (consegnata, PR #14)
  - docs/stories/story-1.5-config-normativa.md (consegnata, PR #16)
  - docs/stories/story-1.6-regime-fiscale.md (consegnata, PR #19)
---

> **Come si legge questo documento.** §1–§6 sono il *piano* di test dell'Epic 1 (rischio,
> livelli, copertura per Story, criteri di gate). **§7 è la matrice di tracciabilità di
> chiusura**: se stai cercando la risposta a *«l'Epic 1 ha debito aperto?»*, vai a
> **§7.4** (registro dei finding), **§7.6** (dichiarazione di debito zero) e **§7.7**
> (rischi tracciati, che debito **non** sono).

# Test Design e matrice di tracciabilità — Epic 1

Piano di test **essenziale e risk-based** per l'Epic 1. Recupera il kickoff di qualità
saltato: definisce *cosa* testare, a *quale livello*, con *quale priorità*, e traccia
ogni acceptance criteria (AC) di `epics.md` verso un invariante architetturale (AD-N).
Non è una suite: è il contratto di copertura contro cui misurare le Story 1.1→1.6 al gate.
A Epic concluso è anche il documento di chiusura: la §7 dice se resta debito, e la risposta
oggi è **no** (§7.6).

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
| Job: retry/backoff esponenziale, esaurimento → `failed`, idempotenza | AD-10 | integration | P0 | ✅ (G-1 chiuso, PR #12) |
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
| Registrazione email duplicata rifiutata (case-insensitive) | AD-18 | integration | P0 | ✅ (G-2 chiuso, PR #12) |
| Validazione 422 non riflette la password in chiaro | AD-15/NFR-6 | integration | P1 | ✅ (G-4 chiuso, PR #12) |
| `host_id` NOT NULL su tabella di sessione | AD-2 | integration | P1 | ✅ |

### Story 1.3 — App shell, navigazione, i18n, Account (consegnata, PR #13)

| AC (sintesi) | Rif | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Navigazione 5 voci (tab mobile / sidebar desktop), Strutture in impostazioni | UX-DR1 | e2e | P0 | ✅ (PR #13, component) |
| Selettore Struttura trasversale con default "Tutte le Strutture" | UX-DR1 | e2e | P0 | ✅ (PR #13, component) |
| Dashboard frame con stato vuoto rassicurante | UX-DR2 | e2e | P1 | ✅ (PR #13) |
| UI it-IT + formati italiani (gg/mm/aaaa, €, virgola) | NFR-9/UX-DR11 | e2e + unit(format) | P0 | ✅ (PR #13) |
| Pannello Account / preferenze notifica | UX-DR15 | e2e + integration | P1 | ✅ (PR #13) |
| Layout responsive mobile-first, densità 1–3 Strutture | UX-DR12 | e2e | P1 | ✅ (PR #13) |
| a11y baseline WCAG 2.1 AA sui flussi critici | NFR-8 | e2e (axe) | P0 | ✅ (C1 chiuso in PR #14: axe in CI su 4 superfici) |

### Story 1.4 — Strutture con cap 3 (consegnata, PR #14)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Creazione richiede nome+Comune+Regione; CIN opzionale | FR-1 | integration | P0 | ✅ (PR #14) |
| CIN assente → indicatore non bloccante "CIN mancante" | FR-1/UJ-1 | integration+e2e | P1 | ✅ (PR #14, derivato server-side) |
| 4ª Struttura **attiva** rifiutata; cap imposto nel service (unico punto) | FR-1/AD-12 | integration | P0 | ✅ (PR #14) — vedi F-1 (atomicità) |
| Cap "3 attive" ≠ soglia fiscale (parametri distinti) | AD-12 | unit/integration | P0 | ✅ (PR #14, `max_strutture_attive`) |
| Struttura con dati collegati → `archiviata`, mai cancellata; audit append-only | AD-20 | integration | P0 | ✅ (PR #14, idempotente) |
| Struttura archiviata esce da conteggio attive e da Regime fiscale | AD-20/AD-12 | integration | P0 | ✅ (PR #14, conteggio solo `ATTIVA`) |
| `struttura.host_id` NOT NULL + scoping repository (tenancy) | AD-2 | integration | P0 | ✅ (PR #14, G-3 chiuso) |
| Flusso guidato passo-passo, skippabile | UX-DR3 | e2e | P2 | ✅ (PR #14, wizard 3 passi e2e) |

### Story 1.5 — Comune/Regione + config normativa, degrado sicuro (consegnata, PR #16)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| `comune_config`/`regione_config` a validità temporale (`valido_dal/al`) | AD-9 | integration | P0 | ✅ (PR #16; determinismo di pari data → F-2, chiuso in #18) |
| Anagrafica seedata da codici ISTAT; update solo via endpoint interni auditati | AD-9 | integration | P0 | ✅ (PR #16, token di servizio + `config_audit`) |
| Cambio Comune ricarica config Tassa senza perdere storico versamenti | FR-2 | integration | P0 | ✅ (PR #16, risoluzione alla lettura) |
| Comune non configurato → stato `configurazione_non_disponibile`, mai default inventati | AD-9/FR-2 | integration | P0 | ✅ (PR #16, `parametri: null` per area) |
| Tono informativo, non errore-colpa | UX §5.1 | e2e | P1 | ✅ (PR #16, test anti-parole-di-colpa) |
| Aliquote/periodicità/termini = dati, aggiornabili senza rilascio | NFR-4 | integration | P0 | ✅ (PR #16) |

### Story 1.6 — Regime fiscale derivato (consegnata, PR #19)

| AC (sintesi) | AD/FR | Livello | Prio | Stato |
| --- | --- | --- | :---: | :---: |
| Regime **sempre derivato** da `count(Strutture non archiviate)` alla lettura, mai persistito | AD-12 | unit + integration | P0 | ✅ (PR #19, test che vieta colonne `regime*`/`fiscal*`) |
| Soglia e parametri fiscali in `config_normativa`, mai costanti nel codice | AD-12 | integration | P0 | ✅ (PR #19, soglia abbassata → esito cambia) |
| 1–2 Strutture → cedolare (informativo); alla 3ª → evento + pannello schermo intero | FR-17/UX-DR14 | integration(evento)+e2e | P0 | ✅ (PR #19, evento solo alla transizione) |
| Pannello Regime persistente con disclaimer sempre visibile | UX-DR14 | e2e | P1 | ✅ (PR #19) |
| Ridiscesa a 2 (archiviazione 3ª) → stato 1–2, nessuna notifica residua | UJ-4 edge | integration | P0 | ✅ (PR #19, il rientro azzera la conferma di lettura) |
| Contenuto informativo con disclaimer, mai calcolo d'imposta | Non-Goal | e2e | P1 | ✅ (PR #19, test che vieta campi di importo) |

---

## 4. Gap di copertura e raccomandazioni

Rilievi emersi dalla review retroattiva 1.1 e cross-review 1.2. Sono **proposte di
correzione** ad Amelia (le entità applicative restano di sua competenza); i test/fixture/CI
li porto io. Priorità indicata.

**Stato: tutti chiusi.** G-1, G-2, G-4 dal fix-batch FIX-FORWARD (PR #12). G-3 e C1 dalla
Story 1.4 (PR #14). F-2 dal secondo fix-batch (PR #18). F-1 e F-3 dal terzo fix-batch
(PR #21). **G-5 — l'ultimo — dal quarto fix-batch (PR #23, mergiata il 2026-07-25).**
Nessun finding dell'Epic 1 resta aperto: il registro completo è in §7.4.

- **F-2 ✅ CHIUSO (PR #18) — (P1, correttezza AD-9/NFR-4) — Delibera ri-emessa con la stessa
  `valido_dal`.** Due periodi restavano aperti e la risoluzione dipendeva dall'ordine di
  Postgres (nessun tiebreaker, nessun UNIQUE). **Esito:** chiusura anche delle aperte di pari
  decorrenza (`valido_dal <=`) che si chiudono a `valido_dal - 1` — intervallo vuoto, mai
  vigente, resta nello storico — più tiebreaker `creato_il DESC` come difesa in profondità.
  Vale per Comune e Regione; 3 test nuovi. Verificato retroattivamente (PR mergiata prima del
  verdetto): il caso normale a date distinte non regredisce.

- **F-3 ✅ CHIUSO (PR #21) — (P2, robustezza) — `compare_digest` solleva `TypeError` su header non-ASCII.** Le
  intestazioni HTTP sono decodificate latin-1: un `X-Admin-Token` con un byte non-ASCII
  produce **500** invece di 403. Nessun leak né bypass. → Confrontare i byte (`.encode()`).

- **G-1 ✅ CHIUSO (PR #12) — (P1, correttezza AD-1/AD-10) — Atomicità per-item degli handler.** In
  `deliver_pending` e `run_due_jobs` un handler che *scrive e poi solleva* lascia le sue
  mutazioni ORM parziali nella sessione: vengono committate dal worker insieme al
  bookkeeping di fallimento. Manca un SAVEPOINT per item. Con at-least-once + retry questo
  può produrre **effetti collaterali doppi** o stato parziale persistito. I test di
  fallimento esistenti usano handler che sollevano *senza scrivere*, quindi il percorso non
  è coperto. → Proposta: avvolgere ogni chiamata handler in `session.begin_nested()` con
  rollback del savepoint su eccezione. Test di regressione: handler *write-then-raise* →
  asserire che nessuno stato parziale sopravvive e che l'evento/job resta ritentabile.
  **Esito:** SAVEPOINT per item in `outbox.py` e `jobs.py`, bookkeeping fuori dal savepoint;
  test *write-then-raise* su entrambi i percorsi (nessuna riga orfana, `attempts=1`, retry).

- **G-2 ✅ CHIUSO (PR #12) — (P1, robustezza) — Registrazione concorrente stessa email.** Il controllo
  `by_email` + insert non è atomico: due registrazioni concorrenti con la stessa email
  fanno passare entrambe il controllo, poi una viola il vincolo `uq_host_email` →
  `IntegrityError` non intercettato → **500** invece di **409**. → Proposta: intercettare
  `IntegrityError` sull'email e mappare a 409. Test: due insert in race → una 201, una 409,
  mai 500. **Esito:** `try/except IntegrityError` sul flush → rollback → 409 problem+json;
  test di gara con pre-check `by_email` accecato (decide il vincolo UNIQUE del DB).

- **G-3 ✅ CHIUSO (PR #14) — (P0, tenancy) — Guardia strutturale sullo scoping `host_id`.** La guardia auth
  (`test_auth_convention.py`) verifica che ogni endpoint abbia una sessione, ma **non** che
  ogni query su tabella tenant-owned passi dal repository filtrando `host_id`. Dalla Story
  1.4 (prima tabella con `host_id`) serve un meta-test gemello che fallisca se un modulo
  interroga una tabella tenant-owned senza filtro tenant. È il moltiplicatore di rischio più
  alto di tutto l'Epic (R-A). → Da introdurre con la Story 1.4.
  **Esito:** `tests/test_tenancy_convention.py` — (1) ogni tabella dati fuori allowlist ha
  `host_id` NOT NULL + FK verso `host`; (2) ogni metodo pubblico dei repository di dominio
  richiede `host_id` in firma; (3) test anti-svuotamento della guardia.

- **C1 ✅ CHIUSO (PR #14) — (P0, test-coverage) — a11y/e2e non automatizzati in CI.**
  Emerso dalla review di Story 1.3: la prima UI reale non aveva copertura a11y/e2e in CI.
  **Esito:** job CI `e2e` full-stack (Playwright avvia backend reale con migrazioni + frontend
  buildato), baseline **axe serious/critical = 0** su accesso/registrazione/dashboard/strutture,
  flusso registrazione→prima Struttura, su chromium + mobile.

- **F-1 ✅ CHIUSO (PR #21) — (P2, robustezza) — Il cap "3 attive" non è atomico (TOCTOU).** Emerso dalla review
  di Story 1.4. `conta_attive(host_id) >= 3` e l'insert non sono atomici né serializzati:
  due `POST /strutture` concorrenti dello stesso Host possono passare entrambi il controllo
  → 4 attive. Stessa classe di G-2, ma impatto minore (cap di prodotto morbido, nessuna
  violazione di tenancy o dati; il Regime fiscale della 1.6 deriva da `count`, quindi non si
  corrompe) e probabilità minore (tenant a utente singolo). → Proposta: serializzare per host
  (`SELECT … FOR UPDATE` sulla riga `host` o `pg_advisory_xact_lock`) + test di gara sul
  modello di G-2. Non blocca il pilota; decisione di dispatch all'umano.

- **G-4 ✅ CHIUSO (PR #12) — (P1, igiene sicurezza NFR-6) — La 422 riflette la password.** Il gestore di
  `RequestValidationError` restituisce `exc.errors()`, che in Pydantic v2 include il campo
  `input`: su password troppo corta a `/auth/registrazione` o `/auth/login` la **password in
  chiaro viene rimandata** nel corpo `errors[].input` (e finisce in eventuali log del
  client/proxy). Stesso mittente → rischio basso, ma è igiene da chiudere. → Proposta:
  redigere `input` (e `url`) per i campi sensibili prima di serializzare. Test: 422 su
  password → il corpo NON contiene il valore inviato. **Esito:** redatti `input`/`url`/`ctx`
  su **tutti** i campi (nessuna allow-list da mantenere), restano `loc`/`msg`/`type`; test:
  password assente dal body, 422 ancora utile al client.

- **G-5 ✅ CHIUSO (PR #23) — (P2, tech-debt) — Sessioni scadute mai raccolte + nessun
  rate-limit login.** Le sessioni scadute restavano in tabella (crescita illimitata); il
  login non aveva throttling/lockout (brute-force mitigato solo dal costo argon2id). →
  Proposta: purge come `job` durevole (AD-10) e rate-limit come follow-up NFR-sicurezza.
  **Esito:** (1) purge delle sessioni scadute come **job durevole periodico** sul kernel
  AD-10 — handler idempotente che si riprogramma a fine giro più bootstrap idempotente al
  riavvio del worker, nessun timer in memoria; ripulisce anche le tracce di login fuori
  finestra, così nemmeno quella tabella cresce senza limite. Nuovo entrypoint applicativo
  `python -m app.worker`, che registra gli handler di dominio e lascia `app.core.worker`
  generico (AD-1 preservato). (2) **Freno ai login ripetuti** su finestra temporale, mai
  lockout permanente: due limiti distinti — per account (Host preso di mira) e per origine
  (spraying su molti account) — applicati **prima** di verificare le credenziali e anche
  per email inesistenti, altrimenti la differenza di comportamento diventerebbe
  enumerazione degli account (regressione su AD-15). 429 `problem+json` con `Retry-After`;
  un accesso riuscito azzera il debito dell'account; soglie e finestra in configurazione
  (`login_max_tentativi_account`, `login_max_tentativi_origine`, `login_finestra_minuti`),
  mai hardcoded. La tabella `tentativo_login` non ha `host_id` — si scrive prima di sapere
  se l'account esiste — ed è in allowlist **esplicita e sorvegliata** dalla guardia di
  tenancy. Evidenza: `backend/tests/test_purge_sessioni.py` (7 test: eliminazione
  selettiva, idempotenza, riprogrammazione, bootstrap dopo riavvio, tipo a catalogo) e
  `backend/tests/test_rate_limit_login.py` (10 test: soglia, `Retry-After`, scadenza della
  finestra, azzeramento su login riuscito, **non-enumerazione**, spraying per origine,
  password mai registrata, interazione col purge).

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

## 7. Matrice di tracciabilità — chiusura Epic 1

Controllo di chiusura complessivo dell'Epic: ogni requisito coperto dall'Epic 1 risale a una
Story, a un livello di test e a un'evidenza eseguibile. Compilata da Murat al termine
dell'Epic; non sostituisce i verdetti pre-merge, li ricapitola.

**Scritta per chi non c'era.** Le sezioni che seguono rispondono in ordine a: cosa è stato
verificato (§7.1–§7.3), cosa era rotto e chi l'ha chiuso (§7.4), quanto è coperto Story per
Story (§7.5), se resta debito (§7.6), che cosa resta comunque da sorvegliare (§7.7).

### 7.1 Requisiti funzionali

| Req | Story | Livello di verifica | Evidenza (suite) | Stato |
| --- | --- | --- | --- | :---: |
| **FR-1** Registrazione Strutture, cap 3 | 1.4 | integration + e2e | `test_strutture.py`, `flusso-strutture.spec.ts` | ✅ |
| **FR-2** Anagrafica Comune/Regione, degrado sicuro | 1.5 | integration + e2e | `test_config_normativa.py` | ✅ |
| **FR-17** Segnalazione Regime fiscale | 1.6 | unit + integration + e2e | `test_regime_fiscale.py`, `regime-fiscale.spec.ts` | ✅ |
| **FR-20** Account / preferenze notifica (UX-DR15) | 1.3 | integration + component | `test_identity_account.py` | ✅ |

### 7.2 Invarianti architetturali (AD) esercitati nell'Epic 1

| AD | Invariante | Story | Presidio di test | Stato |
| --- | --- | --- | --- | :---: |
| AD-1 | Outbox transazionale, effetti asincroni | 1.1, 1.4, 1.6 | `test_outbox.py` + SAVEPOINT per item (G-1) | ✅ |
| AD-2 | Tenancy per `host_id` | 1.2, 1.4 | **guardia strutturale** `test_tenancy_convention.py` (G-3) | ✅ |
| AD-3 | Semantica temporale unica | 1.1 | `test_date_range.py` | ✅ |
| AD-9 | Parametri normativi = dati versionati | 1.5 | `test_config_normativa.py` (+ F-2) | ✅ |
| AD-10 | Scheduling durevole, no timer in-memory | 1.1 | `test_jobs.py` (SKIP LOCKED, backoff) | ✅ |
| AD-12 | Regime fiscale derivato, mai persistito | 1.6 | test che **vieta colonne** `regime*`/`fiscal*` | ✅ |
| AD-14 | Contratto API unico e tipizzato | 1.1→1.6 | job CI `api-contract` (OpenAPI ↔ client TS) | ✅ |
| AD-15 | Sessione server-side, argon2id | 1.2, 1.3 | **guardia strutturale** `test_auth_convention.py` | ✅ |
| AD-17 | Catalogo unico eventi/job, payload minimi | 1.1, 1.4, 1.6 | `test_events.py` + validazione payload | ✅ |
| AD-18 | Un solo modulo scrittore per entità | 1.2→1.6 | struttura a strati api/service/repository | ✅ |
| AD-20 | Archiviare, mai distruggere | 1.4 | `test_strutture.py` (archiviazione idempotente) | ✅ |

### 7.3 Requisiti non funzionali

| NFR | Presidio | Stato |
| --- | --- | :---: |
| **NFR-4** Configurabilità normativa senza rilascio | soglia/aliquote da `config_normativa`; test che abbassa la soglia e cambia l'esito | ✅ |
| **NFR-8** Accessibilità WCAG 2.1 AA | job CI e2e con **axe serious/critical = 0** su 4+ superfici (C1) | ✅ |
| **NFR-9** Localizzazione it-IT | `lib/formati.ts` centralizzato + copy per feature | ✅ |
| **NFR-14** Controllo accessi Host proprietario | guardia tenancy + test cross-tenant (404 su risorse altrui) | ✅ |
| **NFR-16** Nessun dato reale nei test | fixture su dominio `example.com`, codici ISTAT sintetici marcati | ✅ |

### 7.4 Registro dei finding dell'Epic 1 — stato finale

**Tutti e nove i finding numerati emersi nell'Epic 1 sono chiusi.** Nessuna riga è aperta,
nessuna è stata accettata come debito residuo, nessuna è stata chiusa ammorbidendo un test:
in ogni caso il test descriveva l'atteso e il codice si è adeguato.

| ID | Prio | Sintesi | Origine | Chiuso da | Evidenza di regressione |
| --- | :---: | --- | --- | :---: | --- |
| **G-1** | P1 | Handler outbox/job non atomici per item: un handler *write-then-raise* lasciava scritture parziali committate col bookkeeping di fallimento | review retroattiva 1.1 | ✅ **PR #12** | SAVEPOINT per item; test *write-then-raise* in `test_outbox.py`, `test_jobs.py` |
| **G-2** | P1 | Registrazione concorrente stessa email → `IntegrityError` non intercettato → 500 invece di 409 | cross-review 1.2 | ✅ **PR #12** | test di gara con pre-check accecato in `test_identity_auth.py` (una 201, una 409, mai 500) |
| **G-3** | P0 | Nessuna guardia strutturale sullo scoping `host_id` (solo quella auth) — moltiplicatore di rischio R-A | cross-review 1.2, da consegnare con 1.4 | ✅ **PR #14** | `test_tenancy_convention.py` (+ test anti-svuotamento della guardia stessa) |
| **G-4** | P1 | La 422 di validazione rifletteva la **password in chiaro** in `errors[].input` | cross-review 1.2 | ✅ **PR #12** | redazione di `input`/`url`/`ctx`; test che la password non compare nel body |
| **G-5** | P2 | Sessioni scadute mai raccolte (crescita illimitata) + nessun freno ai login ripetuti | cross-review 1.2 | ✅ **PR #23** | `test_purge_sessioni.py` (7 test), `test_rate_limit_login.py` (10 test) |
| **F-1** | P2 | Cap "3 Strutture attive" non atomico (TOCTOU): due `POST` concorrenti → 4 attive | review 1.4 | ✅ **PR #21** | `pg_advisory_xact_lock` per Host; test di gara a 8 thread con barrier |
| **F-2** | P1 | Delibera ri-emessa con la stessa `valido_dal`: due periodi aperti, risoluzione dipendente dall'ordine di Postgres | review 1.5 | ✅ **PR #18** | chiusura delle pari-decorrenza + tiebreaker `creato_il DESC`; 3 test in `test_config_normativa.py` |
| **F-3** | P2 | `compare_digest` su header non-ASCII → `TypeError` → 500 invece di 403 | review 1.5 | ✅ **PR #21** | confronto sui byte (`.encode()`) + test con header non-ASCII |
| **C1** | P0 | Prima UI reale senza copertura a11y/e2e in CI | review 1.3 | ✅ **PR #14** | job CI `e2e` full-stack + **axe serious/critical = 0** su 4 superfici |

**Lettura per priorità:** 2 P0 (G-3, C1), 4 P1 (G-1, G-2, G-4, F-2), 3 P2 (G-5, F-1, F-3) —
**9 su 9 chiusi entro l'Epic**. Ogni chiusura è passata da un verdetto esplicito prima del
merge umano, tranne F-2 e G-1/G-2/G-4, verificati **retroattivamente** (PR mergiate prima che
la regola «verdetto prima del merge» fosse in vigore): la verifica retroattiva è stata fatta
e documentata, non saltata.

### 7.5 Copertura Story per Story (1.1 → 1.6)

Sintesi delle tabelle di §3: ogni Story dell'Epic 1 è consegnata e ogni suo AC ha un test
verde al livello previsto dal test design. Nessun AC è coperto "per ispezione".

| Story | Consegnata da | AC tracciati (P0 / P1 / P2) | AC coperti | Livelli effettivi | Finding aperti sulla Story |
| --- | :---: | :---: | :---: | --- | :---: |
| **1.1** Scaffolding, `core`, CI | PR #9 | 10 (8 / 2 / 0) | 10/10 ✅ | unit + integration su PG reale + contract (CI) | nessuno (G-1 chiuso) |
| **1.2** Registrazione e auth Host | PR #10 | 11 (9 / 2 / 0) | 11/11 ✅ | integration (API) + guardia strutturale auth | nessuno (G-2, G-4, G-5 chiusi) |
| **1.3** App shell, i18n, Account | PR #13 | 7 (4 / 3 / 0) | 7/7 ✅ | component + e2e (axe) + integration | nessuno (C1 chiuso) |
| **1.4** Strutture con cap 3 | PR #14 | 8 (6 / 1 / 1) | 8/8 ✅ | integration + e2e + guardia strutturale tenancy | nessuno (F-1 chiuso) |
| **1.5** Comune/Regione, degrado sicuro | PR #16 | 6 (5 / 1 / 0) | 6/6 ✅ | integration + e2e | nessuno (F-2, F-3 chiusi) |
| **1.6** Regime fiscale derivato | PR #19 | 6 (4 / 2 / 0) | 6/6 ✅ | unit + integration (evento) + e2e | nessuno |
| **Totale Epic 1** | — | **48 (36 / 11 / 1)** | **48/48 ✅** | — | **0** |

I criteri di gate di §6 sono soddisfatti per tutte e sei le Story: AC P0 verdi al livello
indicato, CI verde (compreso `api-contract` quando l'API cambia), guardie strutturali verdi
(auth su tutte, tenancy da 1.4), nessun dato reale nei fixture, zero gap P0/P1 aperti.

### 7.6 Dichiarazione di chiusura — **Epic 1 a debito zero**

> **In data 2026-07-25 dichiaro l'Epic 1 (Story 1.1 → 1.6) chiuso a debito zero.**
> Non esiste alcun finding di qualità, correttezza o sicurezza aperto o accettato come
> debito residuo sull'Epic 1.
>
> — Murat, Master Test Architect

Su che cosa si fonda la dichiarazione (verificabile, non dichiarativo):

1. **Registro dei finding completo e chiuso** — 9 finding su 9 chiusi (§7.4), ciascuno con la
   PR che lo chiude e un test di regressione nominato. Nessuna chiusura per waiver.
2. **Copertura degli AC completa** — 48 AC su 48 coperti da test verdi al livello previsto
   (§7.5); tracciabilità requisito → Story → livello → suite in §7.1–§7.3.
3. **Verdetto dato su ogni PR** — ogni consegna e ogni fix-batch è passato dal verdetto del
   Test Architect prima del merge umano; le quattro PR mergiate prima che la regola entrasse
   in vigore (#12, #18) sono state verificate retroattivamente e l'esito è nel registro.
4. **CI verde su `main`** — sul commit di riferimento `61d7ac4` (che include `dec7680`, il
   merge della PR #23) i cinque check obbligatori sono `success`: `backend`, `frontend`,
   `e2e`, `api-contract`, **SonarCloud Code Analysis**.
5. **La pipeline non può essere verde a vuoto** — `HOSTPILOT_TEST_DB_REQUIRED=1` rende errore
   lo skip dei test su Postgres reale, e il job `api-contract` fallisce sul `git diff` se
   OpenAPI e client TS divergono dal codice: una CI verde implica che quei test sono girati
   davvero e che il contratto è allineato.
6. **Gli invarianti sono imposti dai test, non dalle review** — `test_auth_convention.py`
   (ogni endpoint non pubblico è protetto) e `test_tenancy_convention.py` (ogni tabella
   tenant-owned ha `host_id` NOT NULL + FK, ogni repository di dominio lo richiede in firma),
   entrambe con allowlist esplicite a loro volta sorvegliate da un test.

**Che cosa questa dichiarazione NON dice:** non dice che l'Epic 1 è privo di rischio, né che
è pronto per un traffico di produzione. Dice che il lavoro pianificato è completo e che
nulla di noto è stato lasciato indietro. I rischi noti e non chiusi — che debito **non**
sono — sono elencati qui sotto.

### 7.7 Rischi tracciati alla chiusura (non sono debito)

Debito zero ≠ rischio zero. Queste voci **non** sono finding aperti: nessuna viola un AC o
un invariante, nessuna ha un test rosso. Sono condizioni note, accettate consapevolmente,
con un momento preciso in cui vanno rivalutate. Elencarle è il modo di non farle diventare
debito per dimenticanza.

| ID | Rischio | Perché non è debito | Quando rivalutarlo |
| --- | --- | --- | :---: |
| **RT-1** | **Advisory `npm audit` transitivi.** 14 advisory *high* sul frontend, nessuno diretto: 11 nella toolchain di sviluppo (catena `eslint`/`minimatch`/`brace-expansion`, `@redocly/openapi-core`/`js-yaml`) e **3 nel runtime, tutti transitivi dentro `next` 16.2.11** (`postcss`, `sharp`). | Gli 11 di toolchain non finiscono nel bundle (`npm audit --omit=dev` ne conta 3). I 3 runtime non sono raggiungibili dalla superficie dell'Epic 1: `postcss` agisce a build-time su CSS del progetto, non su input utente; `sharp` serve l'ottimizzazione immagini di `next/image`, e in Epic 1 non esiste upload né sorgente immagine remota controllabile dall'utente. | **Al prossimo bump di `next`.** Nota operativa: `npm audit fix --force` qui propone `next@9.3.3` — un **downgrade major** — e va rifiutato; la risoluzione corretta è aspettare la patch upstream, non "seguire il consiglio del tool". |
| **RT-2** | **Il freno per origine usa `request.client.host`.** Dietro un reverse proxy tutte le richieste condividono un'unica origine. | Non è un bypass — l'`X-Forwarded-For` *non* è considerato, ed è la scelta sicura in assenza di una lista di proxy fidati. Il limite per account resta pienamente efficace e nessun AC dipende dal limite per origine. L'effetto possibile è un falso positivo collettivo, non un buco. | **Alla prima messa in esercizio dietro proxy/CDN**, insieme alla configurazione dei proxy fidati. |
| **RT-3** | **Namespace `1001` degli advisory lock.** Il cap Strutture usa `pg_advisory_xact_lock(1001, hashtext(host_id))`. | Oggi è l'unico advisory lock del progetto: nessuna collisione possibile. | **Al secondo advisory lock** introdotto nel codice: va usato un namespace diverso e la convenzione va scritta. |
| **RT-4** | **Copertura e2e volutamente stretta.** Pochi spec Playwright, scelti sui percorsi critici. | È una scelta di strategia (§2): la flakiness è debito tecnico critico, e la piramide vuole il minimo indispensabile al livello più alto. Gli invarianti stanno ai livelli sotto. | **Quando l'Epic 2 introduce il calendario/sync iCal**, superficie in cui il rischio di regressione è realmente end-to-end. |

Nessuna di queste voci blocca la chiusura dell'Epic 1 né richiede una decisione oggi.
Sono consegnate all'umano (Fahad) come informazione, non come richiesta.

---

_Documento chiuso per l'Epic 1 il 2026-07-25 (§7.6). Resta il riferimento di tracciabilità
per l'Epic: eventuali riaperture vanno fatte via PR, aggiungendo una riga a §7.4 con la
motivazione — non modificando la dichiarazione. Il modello §3/§4/§7 si replica per l'Epic 2
in un documento nuovo._

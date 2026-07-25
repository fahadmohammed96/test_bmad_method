---
title: 'Story 1.4 — Registrazione delle Strutture con cap di 3 unità'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: done
created: 2026-07-25
updated: 2026-07-25
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.4, AC completi)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-1, AD-2, AD-12, AD-18, AD-20)
  - docs/qa/test-design-epic-1.md (G-3 P0, condizione C1)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
depends_on: 'Story 1.3 (merge PR #13)'
---

# Story 1.4 — Registrazione delle Strutture con cap di 3 unità

## Story

As an Host,
I want registrare, modificare e archiviare le mie Strutture fino a un massimo di 3 attive,
So that gestisca i miei appartamenti in un unico posto senza superare lo scope del pilota.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.4) | Esito | Dove |
| --- | --- | --- |
| Modulo `strutture`, tabella `struttura`, proprietario unico scrittore (AD-18) | ✅ | `backend/app/strutture/` (models/repository/service/schemas/api); migrazione `0004`; eventi `struttura.creata`/`struttura.archiviata` a catalogo (AD-17) ed emessi via outbox nella stessa transazione (AD-1) |
| Creazione richiede nome, Comune, Regione; CIN opzionale (FR-1) | ✅ | `POST /api/v1/strutture` (422 senza campi obbligatori); l'anagrafica ISTAT di Comuni/Regioni arriva con la 1.5 (qui campi liberi) |
| CIN assente → indicatore non bloccante "CIN mancante" (UJ-1) | ✅ | campo derivato `cin_mancante` nell'API (AD-14); badge testo+icona in lista (UX-DR4); onboarding mai bloccato (test dedicato) |
| 4ª attiva rifiutata con messaggio "pilota 1-3"; cap nel service, unico punto, parametro distinto dalla soglia fiscale (AD-12) | ✅ | `service.crea_struttura` + `Settings.max_strutture_attive` (config applicativa); 409 problem+json `cap-strutture-attive`; la soglia fiscale vivrà in `config_normativa` (1.6) |
| Archiviare, mai distruggere (AD-20): esce dal conteggio attive, resta nello storico | ✅ | `POST /strutture/{id}/archivia`, idempotente; nessuna DELETE esposta; test "archiviare libera un posto" |
| Flusso guidato passo-passo con progress e tooltip normativi, sempre skippabile (UX-DR3) | ✅ | wizard `/strutture/nuova` (3 passi, "Passo X di 3", `<details>` su Comune/Regione e CIN, "Salta per ora e registra") |

## Debiti chiusi con questa story

- **G-3 (P0)** — guardia strutturale tenant-scoping: `tests/test_tenancy_convention.py` — (a) ogni tabella dati fuori allowlist ha `host_id` NOT NULL + FK verso host; (b) ogni metodo pubblico di ogni `*Repository` nei moduli di dominio (scoperti automaticamente, esclusi core/api/identity) DEVE avere `host_id` in firma. Una query non scopata fa fallire la CI.
- **C1** — e2e + a11y in CI: job `e2e` in `.github/workflows/ci.yml` — Playwright avvia **backend reale** (migrazioni + uvicorn su DB dedicato) e frontend buildato; suite: axe (impatti serious/critical = 0) su accesso/registrazione/dashboard/strutture, flusso completo registrazione→prima Struttura, smoke; progetti desktop + mobile (UX-DR12).

## Dev Agent Record

### Evidenza dei test (2026-07-25)

- Backend: `uv run pytest` → **108 passed** (15 nuovi: creazione/validazione/CIN/cap per host/archiviazione idempotente/outbox/tenancy cross-host 404 + guardia G-3). `ruff`/`mypy` puliti.
- Frontend: `npm test` → **18 passed** (6 nuovi: lista con badge e cap, wizard passo-passo con skip CIN, selettore popolato con le sole attive). `lint`/`typecheck`/`next build` puliti.
- E2E locale: `npm run test:e2e` → **8 passed** (chromium + mobile) con backend reale su PostgreSQL 18.
- Contratto rigenerato e committato (job `api-contract`).

### Note di completamento

- Comune/Regione come testo libero in questa story: la 1.5 porta l'anagrafica ISTAT e il collegamento a `config_normativa` senza migrazione distruttiva (si aggiungeranno colonne di riferimento).
- Cookie di sessione in e2e: `HOSTPILOT_SESSION_COOKIE_SECURE=false` SOLO nell'ambiente Playwright su http; ovunque resta true.
- Migrazione 0004: `create_table` crea da sé il tipo enum Postgres — niente `.create()` esplicito (il doppione fa fallire l'upgrade).
- shadcn/ui: valutato per il wizard; i componenti nativi + token bastano ancora (form lineari). Resta il seed ratificato, si attiva al primo bisogno reale (dialog/combobox della 1.5 è il nuovo candidato).

### Correzioni post-consegna (CI GitHub + SonarQube)

Segnalate da Fahad sulla PR #14, risolte sullo stesso branch:

**CI GitHub — 3 job rossi (`frontend`, `e2e`, `api-contract`)**: `npm ci` falliva con `EUSAGE` perché `package-lock.json` non era in sync col `package.json` dopo l'aggiunta di `@axe-core/playwright` (voci `@emnapi/*` mancanti/disallineate: dipendenze opzionali multipiattaforma risolte diversamente in locale). Lockfile **rigenerato da zero** e verificato con `npm ci` pulito.

**SonarQube — Quality Gate "C Security Rating on New Code"**: 6 vulnerabilità MAJOR, tutte nel nuovo job `e2e` del workflow. Mitigazioni (estese per coerenza a tutti i job):
- `githubactions:S7637` — `astral-sh/setup-uv` pinnata al **commit SHA** `d4b2f3b…` (il tag è mutabile); le action `actions/*` restano su tag come da prassi GitHub-owned.
- `githubactions:S8541` / `S8544` — `uv sync` → **`uv sync --locked --no-build --no-install-project`**: installa solo dal lockfile, senza costruire sdist di terze parti né il progetto locale. I comandi diventano `uv run --no-sync …` (nessun re-sync implicito). `scripts/export_openapi.py` ora aggiunge la dir backend a `sys.path`, così gira anche senza progetto installato.
- `githubactions:S6505` — `npm ci` → **`npm ci --ignore-scripts`** (niente lifecycle script di terze parti; i browser Playwright si installano in uno step esplicito).
- `githubactions:S6505` / `S8543` — `npx playwright install` → **`npm exec --no -- playwright install`**: usa la versione del lockfile, senza installazioni on-demand.

**Code smell risolti** (9): `response_model` ridondante sui 4 endpoint `strutture` (duplicava il return type; contratto OpenAPI **invariato**, verificato), `role="status"` → elemento nativo `<output>` (3), props marcate `Readonly` (2).

Verifica dopo le correzioni: backend **108 passed** + ruff/mypy puliti, contratto invariato; frontend **18 passed** + lint/typecheck; **e2e 8 passed** (chromium + mobile) con `npm ci --ignore-scripts` e `npm exec --no` — cioè esattamente i comandi della CI.

### Change log

- 2026-07-25 — Story creata, implementata test-first e consegnata in PR (branch `story/1.4-strutture`).
- 2026-07-25 — Correzioni CI/Sonar sullo stesso branch (lockfile, hardening supply-chain del workflow, code smell).

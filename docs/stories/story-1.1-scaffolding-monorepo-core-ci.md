---
title: 'Story 1.1 — Scaffolding del monorepo, `core` kernel e CI'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: done
created: 2026-07-24
updated: 2026-07-25
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.1, AC completi)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-1, AD-3, AD-10, AD-14, AD-17, Consistency, Stack)
  - docs/project-context.md (§4 regole di consegna, §6 stack, §7 regole)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
---

# Story 1.1 — Scaffolding del monorepo, `core` kernel e CI

## Story

As a squad di sviluppo (Amelia, Fase 4),
I want un monorepo applicativo inizializzato dai template di squadra con lo shared kernel `core` e la pipeline CI/migrazioni,
So that ogni Story successiva costruisca su fondamenta coerenti, con confini di modulo e contratto API già imposti dalla struttura.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.1) | Esito | Dove |
| --- | --- | --- |
| `backend/` (FastAPI, Python 3.14, SQLAlchemy 2, Alembic, Pydantic v2) e `frontend/` (Next.js 16.2 App Router, TS, Node 24) accanto a `docs/` | ✅ | `backend/pyproject.toml`, `frontend/package.json` (next 16.2.11, engines node ≥24) |
| Package `core` con `date_range` (semiaperto, Europe/Rome, UTC), catalogo `core/events.py`, tabella `outbox`, tabella `job` con `SELECT … FOR UPDATE SKIP LOCKED`, `db`, `config` | ✅ | `backend/app/core/{date_range,events,outbox,jobs,db,config}.py` |
| Worker processo dedicato: consegna outbox dopo il commit, esegue job con handler idempotenti | ✅ | `backend/app/core/worker.py` (`python -m app.core.worker`); test `tests/test_worker.py` |
| API sotto `/api/v1`, OpenAPI da FastAPI, frontend consuma SOLO il client TS generato; errori RFC 9457 problem+json | ✅ | `backend/app/main.py`, `backend/app/api/problems.py`, `backend/openapi.json`, `frontend/lib/api/{schema.d.ts,client.ts}` |
| CI GitHub Actions (lint/typecheck/test/build su ogni PR), Alembic forward-only, `.env.example` | ✅ | `.github/workflows/ci.yml`, `backend/alembic/` (downgrade vietato), `backend/.env.example`, `frontend/.env.example` |
| Test dedicati per `date_range`, catalogo eventi, convenzioni (UUIDv7, centesimi, enum); nessun dato reale nei fixture | ✅ | `backend/tests/test_{date_range,events,conventions}.py` |

## Task eseguiti (in ordine)

1. Toolchain: Python 3.14.6 (uv), Node 24, PostgreSQL 18 (Docker) per i test di integrazione.
2. Test-first: scritta la suite (`tests/`) — semantica AD-3, catalogo AD-17, outbox AD-1, job/SKIP LOCKED AD-10, contratto API AD-14, migrazioni forward-only — prima dell'implementazione (red), poi implementato il kernel (green), poi lint/format/typecheck (refactor).
3. Frontend inizializzato dal template `frontend-next` e portato a Next 16.2/Node 24; client generato via `openapi-typescript` + `openapi-fetch`; provider TanStack Query.
4. CI con 3 job: `backend` (ruff, mypy, pytest su PostgreSQL 18 reale, `HOSTPILOT_TEST_DB_REQUIRED=1`), `frontend` (eslint, tsc, vitest, next build), `api-contract` (rigenera contratto + client e fallisce se divergono dal committato).
5. Documenti: `project-context.md` §6/§7 aggiornati con lo stack ratificato (la sezione lo richiedeva a valle del G3), AGENTS.md per package, README.

## Dev Agent Record

### Evidenza dei test (2026-07-24)

- Backend: `uv run pytest` → **62 passed** (include outbox/job/migrazioni su PostgreSQL 18 reale; claim concorrente SKIP LOCKED verificato con due sessioni).
- Backend: `uv run ruff check .` / `uv run ruff format --check .` / `uv run mypy` → **puliti**.
- Frontend: `npm test` → **2 passed** (client generato chiama `/api/v1/health` tipizzato; render home). `npm run lint`, `npm run typecheck`, `npm run build` → **puliti**.

### Note di completamento

- **Deviazione minima dal template backend**: il template usa pip; adottato **uv** con `uv.lock` per garantire Python 3.14 riproducibile in CI e in locale (il template resta la base della struttura). Documentato in `backend/AGENTS.md`.
- Il catalogo `core/events.py` parte **vuoto ma funzionante** (macchina di validazione + registri di produzione): i tipi si dichiarano nella Story che li emette per la prima volta — evita di inventare payload per moduli non ancora esistenti (AD-17, YAGNI).
- shadcn/ui non ancora inizializzato: si attiva con la Story 1.3 (prima UI reale); Tailwind 4 e TanStack Query 5 sono già operativi.
- E2E Playwright: harness presente dal template (`frontend/e2e/`), non in CI PR; si attiva con la Story 1.3 quando esisterà UI da coprire.
- `npm audit`: restano 3 advisory high **transitive dentro Next 16.2.11** (postcss bundled, sharp) senza fix non-breaking upstream; nessuna esposizione runtime nostra (build-time). Da rivalutare al bump di Next.

### Change log

- 2026-07-24 — Story creata, implementata test-first e consegnata in PR (branch `story/1.1-scaffolding-core-ci`).
- 2026-07-25 — Mergiata su `main` con il verdetto del Test Architect; stato portato a **`done`** alla chiusura dell'Epic 1 a debito zero (azione **A7** della retrospettiva; evidenza in `docs/qa/test-design-epic-1.md` §7.5 copertura AC e §7.6 dichiarazione).

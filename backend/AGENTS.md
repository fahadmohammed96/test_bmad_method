# Progetto

Backend di **HostPilot** — monolite modulare a strati con eventi di dominio
(transactional outbox) + worker, stesso codebase (AD-1). Consumato dal
frontend Next.js via client TypeScript generato dall'OpenAPI (AD-14).
Contratto vincolante: `docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md`
(AD-1…AD-20 + Consistency Conventions).

# Stack

- Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- Database: PostgreSQL 18 (uuidv7 nativo); driver psycopg3
- Dipendenze: uv + pyproject.toml — installare con `uv sync --group dev`
- Test: pytest (+ TestClient per gli endpoint; PostgreSQL reale per outbox/job)
- Lint/format: ruff · Typecheck: mypy

# Comandi (verificati sul repo pulito)

- Installazione: `uv sync --group dev`
- DB di test locale: `docker run -d --name hostpilot-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=hostpilot_test -p 54329:5432 postgres:18`
- Test: `uv run pytest` — la suite deve passare prima di ogni PR (i test DB
  si saltano solo senza PostgreSQL; in CI sono obbligatori)
- Lint: `uv run ruff check .` e `uv run ruff format --check .`
- Typecheck: `uv run mypy`
- Avvio API: `uv run uvicorn app.main:app --reload` → http://localhost:8000
- Avvio worker: `uv run python -m app.worker` (entrypoint applicativo:
  registra gli handler dei moduli e fa il bootstrap dei job periodici,
  poi cede a `app.core.worker`, che resta il ciclo generico del kernel)
- Migrazioni: `uv run alembic upgrade head` (forward-only: downgrade vietato)
- Export contratto: `uv run python scripts/export_openapi.py` → `openapi.json`

# Struttura

- `app/core/` — shared kernel (AD-1): `date_range` (AD-3), `events.py`
  catalogo unico (AD-17), `outbox` (AD-1), `jobs` + claim SKIP LOCKED (AD-10),
  `worker`, `db`, `config`, `money`. Nessuno stato di dominio.
- `app/api/` — plumbing HTTP: health, errori RFC 9457 problem+json (AD-14)
- `app/<modulo>/` — moduli di dominio (`identity`, `strutture`, …) con strati
  `api / service / repository`; nascono con le Story che li richiedono
- `alembic/` — migrazioni forward-only (AR-11)
- `tests/` — specchia la struttura del codice

# Convenzioni di codice (spine Consistency)

- Sostantivi del Glossario PRD in italiano VERBATIM in codice/DB/API
  (`struttura`, `prenotazione`, `adempimento`…); vocabolario tecnico in inglese
- PK `UUIDv7` (`app.core.db.new_uuid7`); mai chiavi naturali esterne come PK
- Date calendario: `DATE` Europe/Rome; istanti: `timestamptz` UTC;
  importi: centesimi interi (`_cent`), mai float
- Un modulo non importa mai `repository`/tabelle di un altro modulo (AD-1);
  ogni tabella tenant-owned porta `host_id` NOT NULL (AD-2)
- Eventi/job SOLO dichiarati nel catalogo `app/core/events.py` (AD-17)
- Errori API: RFC 9457 `application/problem+json`, mai stacktrace al client
- Ogni endpoint NON pubblico dichiara `CurrentHost` (`app.identity.deps`)
  oppure, per gli endpoint `/interno`, `AdminToken`
  (`app.config_normativa.deps`): `host_id` si risolve dalla sessione, mai
  da input client (AD-15); la convenzione è imposta da
  `tests/test_auth_convention.py`
- Ogni tabella di dominio porta `host_id` NOT NULL e i repository lo
  richiedono in ogni metodo (`tests/test_tenancy_convention.py`). Le
  tabelle di RIFERIMENTO condivise (anagrafica ISTAT e `config_normativa`)
  sono nell'allowlist esplicita di quel test: non sono di un Host
- Parametri normativi (aliquote, esenzioni, periodicità, tracciati) sono
  DATI a validità temporale: si aggiornano via `PUT /api/v1/interno/...`
  con audit chi/cosa/quando, mai con costanti nel codice (AD-9, NFR-4)

# Dati e migrazioni

- Migrazioni Alembic **forward-only** (AR-11): `downgrade()` solleva errore
- Modifiche distruttive vietate salvo AD-20 (purge retention GDPR)
- Ogni evento outbox si scrive NELLA STESSA transazione della modifica di stato

# Test

- Test-first (red → green → refactor); nessun dato reale di Ospiti nei
  fixture (NFR-16)
- Unit per la logica pura; integrazione su PostgreSQL reale per outbox, job
  (SKIP LOCKED) e migrazioni — vedi `tests/conftest.py`

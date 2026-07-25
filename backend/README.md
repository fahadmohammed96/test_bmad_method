# HostPilot — API

Backend FastAPI del gestionale HostPilot: monolite modulare + worker
outbox/job. Le convenzioni operative sono in **[AGENTS.md](./AGENTS.md)**;
il contratto architetturale è lo spine in `../docs/architecture/`.

## Avvio rapido

```bash
uv sync --group dev
cp .env.example .env
uv run uvicorn app.main:app --reload    # http://localhost:8000/api/v1/docs
uv run python -m app.core.worker        # worker outbox/job (processo separato)
```

## Comandi

| Comando                                   | Cosa fa                       |
| ----------------------------------------- | ----------------------------- |
| `uv run uvicorn app.main:app --reload`    | Server di sviluppo            |
| `uv run python -m app.core.worker`        | Worker outbox/job             |
| `uv run pytest`                           | Suite di test                 |
| `uv run ruff check .` / `format --check .`| Lint / format                 |
| `uv run mypy`                             | Typecheck                     |
| `uv run alembic upgrade head`             | Migrazioni (forward-only)     |
| `uv run python scripts/export_openapi.py` | Esporta `openapi.json`        |

Test di integrazione: serve PostgreSQL 18 —
`docker run -d --name hostpilot-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=hostpilot_test -p 54329:5432 postgres:18`

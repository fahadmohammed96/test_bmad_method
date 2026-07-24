# Memorie — Amelia — Senior Software Engineer (Fase 4 Implementation)

_Fatti durevoli e decisioni apprese durante il progetto HostPilot. Un fatto per voce, con data. Aggiornare via PR. Non duplicare `docs/project-context.md`._

<!-- Esempio:
- 2026-07-24 — <fatto appreso e perché conta>.
-->

- 2026-07-24 — Story 1.1 consegnata: monorepo `backend/`+`frontend/`, kernel `core`, CI. Il backend usa **uv** (non pip come il template): `uv sync --group dev`, `uv run pytest`. Test DB su PostgreSQL 18 reale via `HOSTPILOT_TEST_DATABASE_URL` (locale: Docker porta 54329); in CI `HOSTPILOT_TEST_DB_REQUIRED=1` impedisce skip silenziosi.
- 2026-07-24 — Contratto API: `backend/openapi.json` e `frontend/lib/api/schema.d.ts` sono **committati** e la CI (`api-contract`) fallisce se divergono dal codice. Dopo ogni modifica agli endpoint: `uv run python scripts/export_openapi.py` + `npm run generate:api`.
- 2026-07-24 — Catalogo `core/events.py`: registrare i tipi evento/job nella Story che li emette per la prima volta (catalogo di produzione parte vuoto; i test usano istanze `Catalog()` locali).
- 2026-07-24 — `eslint-config-next` 16 è flat-native: si importa da `eslint-config-next/core-web-vitals` e `/typescript`, senza FlatCompat (il template Next 15 va adattato).
- 2026-07-24 — shadcn/ui non ancora inizializzato (previsto con la Story 1.3, prima UI reale); e2e Playwright presente ma fuori dalla CI PR fino alla 1.3.

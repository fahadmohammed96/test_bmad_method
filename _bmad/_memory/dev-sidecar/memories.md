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
- 2026-07-24 — Story 1.2: FastAPI 0.139 include i router in modo **lazy** (`_IncludedRouter`): per ispezionare le route usare `route.effective_route_contexts()` (vedi `tests/test_auth_convention.py`). Il TestClient va creato con `base_url="https://testserver"` o il cookie Secure non viene mai rinviato.
- 2026-07-24 — Auth: ogni endpoint nuovo NON pubblico deve dichiarare `CurrentHost` (da `app.identity.deps`) — la guardia `test_auth_convention.py` fallisce altrimenti e va aggiornata la allowlist SOLO per endpoint davvero pubblici. `host_id` sempre dalla sessione.
- 2026-07-25 — Regola FIX-FORWARD attivata da Fahad: preparare un fix-batch è autonomo (branch `fix/<epic>-<batch>`, PR separata, verdetto di Murat), accettare (merge) è umano. Scope dei batch RIGIDO: solo i finding elencati.
- 2026-07-25 — Pattern per handler outbox/job: l'invocazione è dentro `session.begin_nested()` (SAVEPOINT per item, G-1) — un handler che scrive e poi solleva non lascia scritture parziali. I nuovi handler restano idempotenti E le loro scritture devono passare dalla sessione ricevuta, mai da sessioni proprie.
- 2026-07-25 — Debiti registrati da Murat per story future: G-3 (guardia strutturale tenant-scoping `host_id`) va consegnata CON la Story 1.4; G-5 (purge sessioni scadute come job + rate-limit login) resta proposta P2.
- 2026-07-25 — Story 1.3: `get_settings()` è lru_cache-ata e `app.main` la chiama a import-time (CORS) — nei test l'URL del DB va impostato PRIMA di ogni import di `app.*`: il conftest lo fa a modulo-import + `cache_clear()` nella fixture. Non rimuovere quelle righe.
- 2026-07-25 — Frontend: vitest senza `globals: true` → l'auto-cleanup di Testing Library non si attiva; è agganciato in `vitest.setup.ts` (afterEach(cleanup)). CLDR it-IT: separatore migliaia solo da 5 cifre ("1234,56 €"). shadcn/ui ancora NON inizializzato: attivarlo alla prima story con form complessi (1.4), è il seed ratificato G3-1.
- 2026-07-25 — Regola di gate aggiornata da Murat: dalla Story 1.3 il suo verdetto PRECEDE il merge umano — consegnare sempre con menzione a lui e non aspettarsi merge prima del verdetto.

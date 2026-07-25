---
title: 'Story 1.2 — Registrazione e autenticazione dell''Host'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: in_review
created: 2026-07-24
updated: 2026-07-24
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.2, AC completi)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-2, AD-15, AD-18, AR-6)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
depends_on: 'Story 1.1 (merge PR #9)'
---

# Story 1.2 — Registrazione e autenticazione dell'Host

## Story

As an Host,
I want registrarmi con email e password e accedere in modo sicuro,
So that i miei dati e quelli delle mie Strutture siano protetti e accessibili solo a me.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.2) | Esito | Dove |
| --- | --- | --- |
| Modulo `identity` e tabella `host` | ✅ | `backend/app/identity/` (models, repository, service, api, deps); migrazione `0002` |
| Password con argon2id + sessione server-side con cookie HttpOnly Secure SameSite=Lax (AD-15) | ✅ | `service.py` (argon2-cffi, profilo argon2id), cookie in `api.py`; token opaco, in DB solo hash SHA-256 |
| Ogni endpoint (salvo login/registrazione/health) richiede sessione valida e risolve `host_id` dalla sessione, mai da input client (AD-2, AD-15) | ✅ | `deps.get_current_host` + **guardia strutturale** `tests/test_auth_convention.py` che cammina tutte le route dell'app: un endpoint futuro senza auth fa fallire la CI |
| Tabelle tenant-owned con `host_id` NOT NULL e query solo via repository col filtro `host_id` (AD-2, NFR-14) | ✅ (fondazione) | `sessione.host_id` NOT NULL + FK; pattern repository in `identity/repository.py`; la prima tabella di dominio tenant-owned arriva con la Story 1.4 e ha già la guardia |
| TLS su tutti gli ambienti, segreti nel secret manager (AR-6) | ✅ (contratto) | cookie `Secure` sempre attivo (`HOSTPILOT_SESSION_COOKIE_SECURE`, override documentato SOLO per dev http); nessun segreto nel repo, `.env.example` aggiornato |

## Endpoint introdotti (`/api/v1`)

- `POST /auth/registrazione` → 201 + cookie di sessione; 409 problem+json su email già registrata (case-insensitive); 422 su email non valida / password < 8.
- `POST /auth/login` → 200 + cookie; 401 problem+json identico per email sconosciuta e password errata (nessuna enumerazione utenti, con pareggio dei tempi via hash fittizio).
- `POST /auth/logout` → 204; elimina la sessione server-side e cancella il cookie.
- `GET /hosts/me` → 200 profilo dell'Host autenticato (dimostra la risoluzione di `host_id` dalla sessione).

## Dev Agent Record

### Evidenza dei test (2026-07-24)

- `uv run pytest` → **81 passed** (19 nuovi: registrazione, login, sessioni scadute/contraffatte, logout server-side, anti-impersonificazione via query/header, guardia strutturale auth su tutte le route).
- `uv run ruff check .` / `format --check .` / `uv run mypy` → puliti.
- Frontend: contratto rigenerato (`openapi.json` + `lib/api/schema.d.ts`); `npm run typecheck` e `npm test` → puliti.

### Note di completamento

- FastAPI 0.139 usa l'include **lazy** dei router (`_IncludedRouter`): la guardia strutturale appiattisce le route via `effective_route_contexts()` (fallback su `APIRoute` per compatibilità).
- Il cookie è `Secure` anche nei test: il TestClient usa `base_url` https, altrimenti il jar non lo invierebbe.
- Rate limiting sul login e verifica email: **fuori scope** di questa Story (non negli AC); da valutare come hardening post-MVP.
- Preferenze di notifica dell'Host (UX-DR15): arrivano con la Story 1.3 (pannello Account), su questa fondazione.

### Change log

- 2026-07-24 — Story creata, implementata test-first e consegnata in PR (branch `story/1.2-registrazione-auth-host`).

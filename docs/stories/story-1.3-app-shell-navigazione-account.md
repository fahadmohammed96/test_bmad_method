---
title: 'Story 1.3 — App shell, navigazione, Dashboard frame, i18n e pannello Account'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: done
created: 2026-07-25
updated: 2026-07-25
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.3, AC completi)
  - docs/ux-spec.md (UX-DR1, UX-DR2, UX-DR11, UX-DR12, UX-DR15)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-14, AD-15, AD-18, Consistency)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
depends_on: 'Story 1.2 (merge PR #10) + fix-batch (merge PR #12)'
---

# Story 1.3 — App shell, navigazione, Dashboard frame, i18n e pannello Account

## Story

As an Host,
I want un'app in italiano con una navigazione chiara e un pannello dove gestire account e preferenze di notifica,
So that trovi "un solo posto dove guardare" e sappia sempre dove sono le mie cose.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.3) | Esito | Dove |
| --- | --- | --- |
| Navigazione primaria a 5 voci (Dashboard, Calendario, Prezzi, Adempimenti, Operatività), tab bar mobile / sidebar desktop; Strutture da impostazioni/account (UX-DR1) | ✅ | `frontend/components/AppNav.tsx` (un componente, layout responsive; `aria-current` sulla voce attiva); Strutture è sezione del pannello Account, non voce di nav |
| Selettore Struttura trasversale con "Tutte le Strutture" default (UX-DR1) | ✅ | `frontend/components/SelettoreStruttura.tsx` nell'header dell'app shell; popolato dalle Strutture reali con la Story 1.4 |
| Dashboard frame con stato vuoto rassicurante (UX-DR2) | ✅ | `frontend/app/(app)/dashboard/page.tsx`: stato vuoto + 3 sezioni segnaposto (calendario/adempimenti/prezzi) che gli Epic riempiranno |
| UI in italiano, formati italiani, stringhe in moduli copy per feature (UX-DR11, NFR-9) | ✅ | `frontend/lib/copy/{nav,dashboard,account,auth,app}.ts`; `frontend/lib/formati.ts` (unico punto: date gg/mm/aaaa, € con virgola, importi SOLO in centesimi interi) |
| Pannello Account / preferenze di notifica (email, password, canale preferito) su infrastruttura `identity` (UX-DR15) | ✅ | `frontend/app/(app)/account/page.tsx` + backend: `canale_notifica_preferito` su `host` (migrazione `0003`), `PATCH /api/v1/hosts/me/preferenze`, `POST /api/v1/hosts/me/password` (ruota la password e invalida le ALTRE sessioni), logout |
| Layout responsive mobile-first, densità 1-3 Strutture (UX-DR12) | ✅ | tab bar fissa in basso su mobile / sidebar su desktop; layout a card fluide; nessun componente dipende dal numero di Strutture |

## Aggiunte tecniche a supporto

- **Accesso/Registrazione UI** (`app/(auth)/accesso`, `app/(auth)/registrazione`): senza, "l'Host autenticato entra nell'app" non è esercitabile; consumano SOLO gli hook sul client generato (AD-14).
- **Guard di shell** (`app/(app)/layout.tsx`): `useMe()` → 401 ⇒ redirect ad `/accesso`; home `/` smista autenticato/anonimo.
- **CORS** sul backend (origin esplicita `HOSTPILOT_FRONTEND_ORIGIN` + credentials, mai wildcard): il frontend su :3000 invia il cookie di sessione all'API su :8000.
- Errori di dominio nuovi: `403 urn:hostpilot:problem:invalid-current-password`.

## Dev Agent Record

### Evidenza dei test (2026-07-25)

- Backend: `uv run pytest` → **93 passed** (12 nuovi: preferenze default/aggiornamento/validazione, cambio password con rotazione credenziali e invalidazione delle altre sessioni, preflight CORS). `ruff` + `mypy` puliti.
- Frontend: `npm test` → **12 passed** (formati it-IT, nav 5 voci + aria-current, selettore default, dashboard empty-state, pannello Account + mutazione canale, smistamento home). `lint`, `typecheck`, `next build` puliti.
- Contratto rigenerato: `backend/openapi.json` + `frontend/lib/api/schema.d.ts` allineati (job CI `api-contract`).

### Note di completamento

- **Fixture DB dei test**: `get_settings()` è cachata e `app.main` ora la invoca a import-time (CORS) — il conftest imposta `HOSTPILOT_DATABASE_URL` al modulo-import e fa `cache_clear()` prima delle migrazioni, altrimenti la suite completa puntava al DB di default.
- **shadcn/ui**: NON ancora inizializzato — il seed ratificato resta; si attiva alla prima Story con componenti complessi (form multi-step della 1.4 è il candidato). I componenti attuali sono Tailwind semplici sui token di `globals.css`. Registrato in `frontend/AGENTS.md`.
- **E2E**: smoke Playwright aggiornato (home → /accesso senza sessione). Non ancora in CI PR: proposta di attivazione post-merge quando esiste un flusso E2E con backend orchestrato (candidata Story 1.4 con QA).
- Nota CLDR it-IT: il separatore delle migliaia compare solo da 5 cifre (es. `1234,56 €`, `12.345,67 €`) — test allineato al comportamento ICU.
- `Sessione`/logout: il cambio password invalida tutte le sessioni TRANNE la corrente (scelta di sicurezza standard, testata).

### Change log

- 2026-07-25 — Story creata, implementata test-first e consegnata in PR (branch `story/1.3-app-shell`).

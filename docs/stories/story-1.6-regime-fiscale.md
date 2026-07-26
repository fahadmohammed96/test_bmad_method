---
title: 'Story 1.6 — Segnalazione del Regime fiscale derivato dal numero di Strutture'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: done
created: 2026-07-25
updated: 2026-07-25
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.6, AC completi)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-12, AD-9, AD-17, AD-18)
  - docs/qa/test-design-epic-1.md (§3 Story 1.6)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
depends_on: 'Story 1.5 (PR #16) + fix-batch F-2 (PR #18)'
---

# Story 1.6 — Segnalazione del Regime fiscale derivato

## Story

As an Host,
I want che il sistema mi segnali il regime fiscale applicabile in base a quante Strutture ho,
So that io capisca l'impatto della soglia dei tre immobili **prima** di trovarmelo a fine anno — senza che il prodotto pretenda di fare il commercialista.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.6) | Esito | Dove |
| --- | --- | --- |
| Regime **sempre derivato** da `count(Strutture non archiviate)` alla lettura, mai persistito (AD-12) | ✅ | `backend/app/strutture/regime_fiscale.py`: funzione pura sul conteggio. Test che **vieta colonne** `regime*`/`fiscal*` su `struttura` e `host`: non può esistere uno stato che diverge dal conteggio |
| Soglia, aliquote citate e testo informativo in `config_normativa`, **mai costanti nel codice** (AD-12, NFR-4) | ✅ | `parametro_fiscale` a validità temporale (migrazione `0006`), aggiornabile da `PUT /api/v1/interno/parametri-fiscali` con audit chi/cosa/quando. Test: abbassare la soglia a 2 cambia l'esito **senza rilascio** |
| 1-2 Strutture → cedolare secca (informativo); alla 3ª → evento + pannello a schermo intero (FR-17, UX-DR14) | ✅ | eventi `regime_fiscale.soglia_superata` / `.rientrato` a catalogo (AD-17), emessi via outbox **solo alla transizione**; pannello modale nella shell con CTA "Ho capito, continua" e "Parlane con un commercialista" |
| Pannello Regime **persistente** con disclaimer sempre visibile (UX-DR14) | ✅ | `PannelloRegimeFiscale` nella pagina Strutture: presente in **ogni** stato (sotto soglia, oltre soglia, configurazione assente) col disclaimer in fondo |
| Ridiscesa a 2 → stato 1-2, **nessuna notifica residua** (UJ-4 edge) | ✅ | archiviare la 3ª emette `regime_fiscale.rientrato`, azzera la conferma di lettura e riporta il pannello allo stato informativo; e2e verifica che il modale non ricompaia |
| Contenuto **informativo con disclaimer**, mai un calcolo d'imposta (Non-Goal PRD §8) | ✅ | nessun campo di importo nella risposta — test che vieta `imposta*`/`dovuto_cent`/`totale_cent`; disclaimer presente in ogni stato |

## Scelte di progetto da segnalare in review

- **Il Regime non è uno stato, è una funzione.** Non esiste nessuna colonna "regime": la lettura calcola sempre da `count(non archiviate)` e dai parametri vigenti. L'unico stato persistito è la **conferma di lettura** del pannello (`regime_lettura`, tenant-owned con `host_id` NOT NULL) — che non è il Regime.
- **Degrado sicuro anche qui**: senza parametri fiscali configurati non si inventa una soglia né un regime; si dichiara `configurazione_non_disponibile` e non si emette alcun evento di transizione (coerente con AD-9 e con la Story 1.5).
- **Il rientro azzera la conferma di lettura.** Prima versione: la conferma era legata al *conteggio*; l'ho cambiata dopo che il test di ridiscesa+risalita ha mostrato il buco (3 → archivio → nuova 3ª non ripresentava il pannello). Ora il rientro sotto soglia cancella la conferma, così una nuova risalita ripropone l'informativa — e sotto soglia non resta mai nulla in sospeso.
- **Soglia fiscale ≠ cap di prodotto**: test dedicato che abbassa la soglia normativa a 2 e verifica che il cap `max_strutture_attive` resti 3 (AD-12).

## Dev Agent Record

### Evidenza dei test (2026-07-25)

- Backend: `uv run --no-sync pytest` → **159 passed** su PostgreSQL 18 (21 nuovi: derivazione, archiviazione, tenancy, parametri come dati, audit, validità temporale, eventi di transizione, pannello, disclaimer, assenza di calcoli d'imposta); `ruff` + `mypy` puliti.
- Frontend: `npm test` → **29 passed** (6 nuovi: pannello persistente nei 3 stati, modale di transizione con CTA e disclaimer, assenza sotto soglia); `lint`/`typecheck`/`build` puliti.
- E2E: `npm run test:e2e` → **10 passed** (chromium + mobile), nuovo scenario completo 1→2→3 Strutture con modale, conferma, ridiscesa; axe serious/critical = 0.
- Contratto OpenAPI + client TS rigenerati.

### Note di completamento

- **Bug trovato dall'e2e**: dopo l'archiviazione il pannello persistente restava a "3 Strutture attive" — le mutazioni sulle Strutture invalidavano solo la cache `strutture`, non `regime-fiscale`. Corretto centralizzando l'invalidazione (`invalidaStruttureERegime`): il Regime dipende dal conteggio, quindi ogni mutazione lo invalida. È esattamente il tipo di difetto che i soli test di componente non vedono.
- L'archiviazione chiede conferma con `window.confirm`: in Playwright va accettata esplicitamente (`page.once("dialog", …)`), altrimenti viene rifiutata di default e il test fallisce in modo fuorviante.
- Il token di servizio e2e è impostato solo nell'ambiente Playwright: i parametri fiscali dei test si caricano dagli endpoint interni, coerentemente col principio "sono dati, non costanti".

### Change log

- 2026-07-25 — Story creata, implementata test-first e consegnata in PR (branch `story/1.6-regime-fiscale`). **Chiude l'Epic 1.**
- 2026-07-25 — Mergiata su `main` con il verdetto del Test Architect; stato portato a **`done`** alla chiusura dell'Epic 1 a debito zero (azione **A7** della retrospettiva; evidenza in `docs/qa/test-design-epic-1.md` §7.5 copertura AC e §7.6 dichiarazione).

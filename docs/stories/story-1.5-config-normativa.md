---
title: 'Story 1.5 — Anagrafica Comune/Regione e configurazione normativa con degrado sicuro'
epic: 'Epic 1: Fondamenta della piattaforma e gestione delle Strutture'
status: done
created: 2026-07-25
updated: 2026-07-25
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 1.5, AC completi)
  - docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-9, AD-18, NFR-4)
  - docs/qa/test-design-epic-1.md (§3 Story 1.5)
issue: 'MYL-28 — PILOTA HostPilot — Fase 4 Implementation (Epic 1)'
depends_on: 'Story 1.4 (merge PR #14)'
---

# Story 1.5 — Anagrafica Comune/Regione e configurazione normativa con degrado sicuro

## Story

As an Host,
I want associare ogni Struttura al suo Comune e alla sua Regione,
So that Tassa di soggiorno e ISTAT/ROSS1000 siano parametrizzati correttamente, e il sistema mi avvisi con onestà quando non è ancora configurato per me.

## Acceptance Criteria → esito

| AC (epics.md, Story 1.5) | Esito | Dove |
| --- | --- | --- |
| Modulo `config_normativa` con `comune_config`/`regione_config` a validità temporale (`valido_dal/al`, AD-9) | ✅ | `backend/app/config_normativa/` (models, repository, service, api); migrazione `0005`; risoluzione per data con test su due periodi di delibera |
| Anagrafica seedata dai codici ISTAT; update di configurazione solo da endpoint interni auditati (chi/cosa/quando), mai modifiche dirette al DB | ✅ | 20 Regioni seedate nella migrazione (codici ISTAT stabili); Comuni importati dal file ufficiale ISTAT (`app.config_normativa.importa_comuni`, upsert idempotente); `PUT /api/v1/interno/{comuni,regioni}/{codice}/configurazione` protetti da token di servizio, ogni scrittura in `config_audit` |
| Cambiare il Comune ricarica la configurazione applicabile senza perdere lo storico dei versamenti (FR-2) | ✅ | il legame Struttura→Comune è un riferimento, la configurazione si risolve alla lettura da `(comune, data)`: **mai copiata sulla Struttura**. Test dedicato che verifica l'assenza di colonne `tassa*`/`aliquota*` su `struttura` e la sopravvivenza delle config del Comune precedente |
| Comune/Regione non riconosciuto o non configurato → stato esplicito `configurazione_non_disponibile` + promemoria manuale, tono informativo (FR-2, AD-9, UX §5.1) | ✅ | stato **per area** (Tassa / ISTAT) con 4 motivi distinti; `parametri: null` sempre — mai un default inventato; copy verificata da un test che vieta parole di colpa ("errore", "non valido", "sbagliat…") |
| Aliquote, esenzioni, periodicità, termini e tracciati sono DATI: aggiornarli non richiede un rilascio (NFR-4) | ✅ | nuova delibera = nuova riga con `valido_dal`; il periodo precedente viene **chiuso**, non sovrascritto (append-only sulla validità) |

## Scelte di progetto da segnalare in review

- **Nessun codice ISTAT inventato nel repository.** Le 20 Regioni hanno codici stabili e sono seedate; gli ~8.000 Comuni si importano dal file ufficiale ISTAT con un comando dedicato (operazione dati, non un rilascio). Il perimetro iniziale dei Comuni da configurare resta la decisione di prodotto **G2-B**: il sistema degrada in sicurezza per qualunque Comune non presente o non configurato, quindi la decisione non blocca questa Story.
- **Stato per area, non complessivo.** L'AC chiede lo stato esplicito per Comune *e* Regione: la risposta espone `tassa_soggiorno` e `istat` con stato, motivo, messaggio, `promemoria_manuale` e `parametri` propri. Un Comune configurato e una Regione no restano leggibili separatamente.
- **Guardie strutturali estese, non indebolite.** Anagrafica e configurazione sono dati di riferimento condivisi: sono in un'**allowlist esplicita** di `test_tenancy_convention.py`, con un test aggiuntivo che verifica che quelle tabelle non acquisiscano mai un legame con `host` (se accadesse, l'esenzione decadrebbe). `test_auth_convention.py` ora accetta due protettori — sessione Host **o** token interno — e verifica che gli endpoint `/interno` non usino mai la sessione Host.
- **Comune/Regione restano scrivibili a mano** nel form: un luogo non ancora in anagrafica non blocca la registrazione (UJ-1), semplicemente non porta il codice ISTAT e la configurazione degrada.

## Dev Agent Record

### Evidenza dei test (2026-07-25)

- Backend: `uv run --no-sync pytest` → **131 passed** su PostgreSQL 18 (23 nuovi: anagrafica, validità temporale, degrado sicuro per 4 motivi, tono del copy, cambio Comune, audit, NFR-4, tenancy 404); `ruff` + `mypy` puliti.
- Frontend: `npm test` → **23 passed** (5 nuovi: `CampiLuogo` con codice ISTAT dai suggerimenti e fallback a mano, `PannelloConfigurazione` con parametri in formato italiano e degrado senza importi); `lint`/`typecheck` puliti.
- E2E: `npm run test:e2e` → **8 passed** (chromium + mobile), esteso allo stato di configurazione visibile all'Host; axe serious/critical = 0.
- Contratto OpenAPI + client TS rigenerati (job `api-contract`).

### Note di completamento

- `datalist` fuori dalla `<label>` e `htmlFor`/`id` espliciti: dentro la label i suggerimenti finivano nel testo accessibile del campo (rotture a11y e test).
- Migrazione 0005: l'enum `periodicita` è creato una volta con `comune_config` e riusato in `regione_config` con `create_type=False`.
- Il token degli endpoint interni si confronta con `secrets.compare_digest`; se non configurato, gli endpoint sono **chiusi di default** (nessun accesso implicito).

### Change log

- 2026-07-25 — Story creata, implementata test-first e consegnata in PR (branch `story/1.5-config-normativa`).

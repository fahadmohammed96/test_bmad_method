# HostPilot

Gestionale in abbonamento per **host privati di affitti brevi** (1–3 appartamenti su Airbnb/Booking).
Progetto pilota di collaudo della **BMAD Squad** (metodo BMad v6, modulo BMM) con **gate umani** e **consegne via PR**.

## Nucleo funzionale (da confermare/dettagliare nelle fasi BMAD)

1. **Calendario unificato** multi-struttura con sincronizzazione iCal (Airbnb/Booking) e prevenzione double-booking.
2. **Motore regole di prezzo**: stagionalità, weekend, last-minute, soggiorni minimi.
3. **Adempimenti italiani**: comunicazione alloggiati (Questura), tassa di soggiorno, ISTAT.
4. **Operatività**: turni di pulizia, messaggi automatici agli ospiti.

Mercato: host privati italiani oggi su fogli Excel. Riutilizzabilità futura: property manager multi-unità.

## Come lavora la squad

Il metodo è guidato dai **documenti**: ogni fase produce l'artefatto che dà contesto alla successiva.

| Fase | Owner | Artefatto |
|------|-------|-----------|
| 1 · Analysis | Mary — Business Analyst | Project Brief / PRFAQ + ricerca normativa |
| 2 · Planning | John — Product Manager + Sally — UX Designer | PRD + UX Spec |
| 3 · Solutioning | Winston — System Architect | Architettura + Epics/Stories |
| 4 · Implementation | Amelia — Senior Software Engineer | Story implementate |
| Trasversale | Paige — Technical Writer | Documentazione |
| Test (modulo TEA) | Murat — Master Test Architect | Strategia di test risk-based |

**Regole invarianti**: consegne sempre via PR verso `main`, **mai push diretto**; il **merge è sempre umano**; nessuna fase inizia senza l'artefatto approvato della fase precedente.

Le regole complete e vincolanti per gli agenti sono in [`docs/project-context.md`](docs/project-context.md) — la **costituzione del progetto**.

## Struttura del repo

```
docs/                     Artefatti BMAD (brief, PRD, UX spec, architettura, epics/stories)
  project-context.md      Costituzione del progetto (regole per gli agenti)
_bmad/                    Configurazione BMAD e memoria sidecar degli agenti
  bmm/config.yaml         Config del modulo BMM
  _memory/<ruolo>-sidecar/ Memoria persistente per agente (memories, instructions, knowledge)
```

## Stato

Fase 0 — Bootstrap. Lo **stack tecnologico non è ancora deciso**: la scelta spetta a Winston in Fase 3 (Solutioning).

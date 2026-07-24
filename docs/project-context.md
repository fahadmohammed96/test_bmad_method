---
project_name: 'HostPilot'
user_name: 'Fahad'
date: '2026-07-24'
sections_completed: ['product', 'method_and_gates', 'roster_and_scope', 'delivery_rules', 'domain_constraints', 'technology_stack']
existing_patterns_found: 0
bmad_module: 'bmm'
bmad_version: 'v6'
status: 'bootstrap (Fase 0) — stack e architettura TBD in Fase 3'
---

# Project Context for AI Agents — HostPilot

_Costituzione del progetto. Contiene le regole critiche e non ovvie che ogni agente della BMAD Squad DEVE seguire. Ottimizzato per l'efficienza di contesto: leggere per intero all'avvio di ogni run. In caso di conflitto tra questo file e un'istruzione runtime, prevale questo file; se un'istruzione dell'Agent Identity confligge, prevale l'Agent Identity._

---

## 1. Prodotto

- **HostPilot**: gestionale in abbonamento per **host privati di affitti brevi** con 1–3 appartamenti su Airbnb/Booking.
- **Utente target**: host privato italiano, non tecnico, oggi su fogli Excel. Ottica futura: property manager multi-unità (non è lo scope del pilota).
- **Nucleo funzionale previsto** (da confermare/dettagliare nelle fasi BMAD, non è un impegno di scope):
  1. Calendario unificato multi-struttura, sync iCal (Airbnb/Booking), anti double-booking.
  2. Motore regole di prezzo: stagionalità, weekend, last-minute, soggiorni minimi.
  3. Adempimenti italiani: comunicazione alloggiati (Questura), tassa di soggiorno, ISTAT.
  4. Operatività: turni di pulizia, messaggi automatici agli ospiti.
- **Natura del progetto**: pilota di collaudo della **BMAD Squad**. Il valore per l'utente viene prima; la fattibilità tecnica è un vincolo, non il punto di partenza.

## 2. Metodo BMad v6 e gate umani (REGOLA VINCOLANTE)

- Il metodo è **guidato dai documenti**: ogni fase produce l'artefatto che dà contesto alla successiva. Non si apre il lavoro di una fase se l'artefatto della fase precedente non è **approvato dall'umano**.
- Sequenza delle fasi:
  1. **Analysis** (Mary) → Project Brief / PRFAQ + ricerca normativa.
  2. **Planning** (John + Sally) → PRD + UX Spec.
  3. **Solutioning** (Winston) → Architettura + Epics/Stories, con implementation-readiness.
  4. **Implementation** (Amelia) → story test-first, code review, sprint.
  - **Paige** (documentazione) è trasversale; **Murat** (modulo TEA) porta la strategia di test risk-based.
- **I gate di fase sono UMANI.** Si presenta l'artefatto completo all'umano (Fahad) e si **FERMA** fino ad approvazione esplicita. Sequenza dei gate: **G0** bootstrap → **G1** brief → **G2** PRD+UX → **G3** architettura+epics → poi implementazione.
- **Mai colmare una lacuna decisionale con una scelta propria.** Di fronte a un bivio di prodotto/priorità: proporre opzioni con trade-off e un consiglio, e chiedere all'umano. Priorità e decisioni di prodotto sono dell'umano.

## 3. Roster e confini di scope

| Agente | Ruolo | Fase | Sidecar |
|--------|-------|------|---------|
| Mary | Business Analyst | 1 · Analysis | `_bmad/_memory/analyst-sidecar/` |
| John | Product Manager (**leader squad**) | 2 · Planning | `_bmad/_memory/pm-sidecar/` |
| Sally | UX Designer | 2 · Planning | `_bmad/_memory/ux-sidecar/` |
| Winston | System Architect | 3 · Solutioning | `_bmad/_memory/architect-sidecar/` |
| Amelia | Senior Software Engineer | 4 · Implementation | `_bmad/_memory/dev-sidecar/` |
| Paige | Technical Writer | Trasversale | `_bmad/_memory/tech-writer-sidecar/` |
| Murat | Master Test Architect | Modulo TEA | `_bmad/_memory/test-architect-sidecar/` |

- Ogni agente resta nel **proprio scope**: un task che lo supera diventa un'issue separata o una segnalazione all'umano, mai un allargamento dell'assegnazione.
- **Un solo agente alla volta** sulla stessa issue.
- **Handoff** (responsabilità del leader): a consegna avvenuta, riassegnare l'issue all'agente della fase successiva; se è già assegnata a lui, la riassegnazione è un no-op → **menzionare @l'agente** nel commento (la menzione è il trigger). Un'issue ferma senza un task attivo dell'assegnatario è una catena interrotta: riattivarla e segnalare l'anomalia all'umano.
- Task non coperto dal roster → segnalarlo all'umano, non forzare l'assegnazione.

## 4. Regole di consegna (REGOLA VINCOLANTE)

- **Consegne SEMPRE via Pull Request verso `main`. MAI push diretto su `main`.**
- **Il merge è SEMPRE dell'umano.** Nessuna issue è chiusa/`done` prima del merge. La CI verde e le branch protection sono il gate di merge di GitHub, non il criterio di accettazione dell'agente.
- **Artefatti in `docs/`** (default): brief, PRD, UX spec, architettura, epics/stories. `docs/project-context.md` è la costituzione — curarne coerenza e aggiornamento **via PR**.
- **A PR aperta**, riferire il link nell'issue prima di ogni handoff. Nessun handoff senza il riferimento alla PR.
- **Lingua**: comunicazione con l'umano e **documenti di output in italiano**. Codice, identificatori e commenti tecnici in inglese quando è la convenzione dello stack scelto.
- **Modifiche richieste** in review → tornano al Developer autore. Oltre due giri sullo stesso punto: fermarsi e segnalare all'umano (il problema è nell'issue o nel contesto).

## 5. Vincoli di dominio (Italia — attenzione alta)

Questi punti richiedono **ricerca normativa accurata in Fase Analysis** e non vanno dati per scontati in implementazione:

- **Comunicazione alloggiati / Questura**: portale *Alloggiati Web* della Polizia di Stato. Termine di comunicazione degli ospiti entro le tempistiche di legge; gestione documenti d'identità con vincoli privacy (GDPR) e minimizzazione/retention dei dati personali.
- **Tassa di soggiorno**: **regolamento comunale**, quindi importi, esenzioni e periodicità di versamento variano per Comune. Non hardcodare aliquote: modellare per configurazione.
- **ISTAT**: rilevazione del movimento turistico (spesso via portale regionale, es. sistemi tipo *Ross1000*). La periodicità e i tracciati dipendono dalla Regione.
- **iCal sync**: i feed Airbnb/Booking sono **read-only e non in tempo reale** (latenza di aggiornamento). L'anti double-booking deve prevedere finestre di conflitto e riconciliazione, non assumere sincronia istantanea.
- **Dati personali degli ospiti** = categoria sensibile: applicare GDPR by design (base giuridica, minimizzazione, retention, cifratura at-rest per i documenti).

> Nota: i dettagli normativi sopra sono da **verificare e datare** in Fase 1; qui servono solo a segnalare le aree di rischio agli agenti.

## 6. Technology Stack & Versions

- **Non ancora deciso.** La scelta dello stack e dell'architettura spetta a **Winston in Fase 3 (Solutioning)** e passa dal gate umano G3.
- Template di stack disponibili nella libreria del team (repo `test-multica`: `frontend-next`, `backend-fastapi`) come **candidati**, non come decisione presa.
- Finché lo stack non è approvato: **non** creare scaffolding applicativo, lockfile o scelte di framework. Questa sezione va aggiornata (via PR) quando l'architettura è approvata, con versioni esatte e vincoli di compatibilità.

## 7. Critical Implementation Rules

- Nessuna regola di codice applicabile al bootstrap (repo senza stack). Da popolare in Fase 3/4 con: convenzioni di naming, struttura moduli, error handling, pattern di test (test-first per Amelia), coverage attese.
- **Segreti**: mai committare `.env` o credenziali; usare `.env.example`. Nessun dato reale di ospiti nei fixture/test.
- **Memoria sidecar**: ogni agente legge la propria `_bmad/_memory/<ruolo>-sidecar/` all'avvio e la aggiorna **via PR** quando impara qualcosa di importante (vedi `_bmad/_memory/README.md`).

---
title: 'Story 2.1 — Collegamento di un Feed iCal e import on-demand'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-07-26
updated: 2026-07-26
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 2.1, AC completi)
  - 'ramo docs/nfr17-politica-uscita-rete (NFR-17 + i due AC SSRF, PR non ancora aperta)'
  - 'PR #32 — docs/qa/test-design-epic-2.md (contratto di copertura, ramo qa/epic2-test-design)'
  - 'PR #34 — invariante di uscita di rete nello spine (AD-4 esteso)'
  - docs/retrospettive/epic-1.md (azioni A2, A3, A9)
issue: 'MYL-37 — Story 2.1'
depends_on: 'Story 1.4 (modulo strutture), kernel core AD-10/AD-17 (Story 1.1)'
---

# Story 2.1 — Collegamento di un Feed iCal e import on-demand

## Story

As an Host,
I want collegare a una Struttura l'URL del Feed iCal di Airbnb o Booking e vedere subito le prenotazioni importate,
So that abbia in HostPilot le prenotazioni che oggi tengo sparse sui portali, con la prova che il collegamento ha funzionato.

## Nota sugli input non ancora su `main`

Tre input di questa Story vivono su rami non mergiati (PR #32, PR #34,
`docs/nfr17-politica-uscita-rete`), per decisione di Fahad del 26/07: lo
sviluppo riprende senza attendere i merge documentali, il gate vero — verdetto
di Murat + merge umano del codice — resta intatto. Se al merge dei documenti
qualcosa cambia, **questo ramo si adegua**.

L'ancora normativa dell'SSRF è **NFR-17**, non NFR-6: quest'ultimo nel PRD §7
è la sicurezza dei dati personali e non c'entra con l'uscita di rete. La
citazione sbagliata presente nel test design non è stata propagata.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.1
(13 righe tracciate, di cui 9 P0).

| # | AC (test design §3) | Livello | Esito | Dove |
| :---: | --- | --- | :---: | --- |
| 1 | URL valido ⇒ job di sync **prioritario** subito, con progresso visibile | I + Cmp | ✅ | `jobs.accoda_sync_immediato` accoda con `due_at = adesso`: il worker lo prende al primo giro, mentre ogni ciclo periodico ha `due_at` nel futuro. Test che lo dimostra **contro** il purge periodico già in coda. Progresso: `stato_sync` derivato dall'API + `FeedIcalStruttura` |
| 2 | ⚡ **Upsert idempotente su `(feed_id, ical_uid)`** | I (gara A3-1) | ✅ | `PrenotazioneRepository.upsert_dal_feed`: **una sola istruzione** `ON CONFLICT` sul UNIQUE del DB, nessun pre-check da accecare. `tests/test_calendario_gara.py` — 8 thread, barrier fra i client, visto rosso |
| 3 | L'import **non cancella mai**: evento scomparso ⇒ `rimossa_dal_feed` | I + S (GS-6) | ✅ | `marca_rimosse_dal_feed` è una UPDATE, mai una DELETE. Guardia `tests/test_append_preserving_convention.py` |
| 4 | † **«Scomparso» ≠ «non ricevuto»** | U + I | ✅ | `ical.analizza_feed` rifiuta corpo troncato/vuoto/non chiuso; il service transiziona **solo** dopo parse completo. 8 forme di risposta bugiarda, tutte con dati intatti. Visto rosso: l'implementazione ingenua marca `rimossa_dal_feed` **2 su 2** prenotazioni vive |
| 5 | URL non valido o irraggiungibile ⇒ errore inline, mai fallimento silenzioso | U + I | ✅ | Formato ⇒ 422 sincrono (`url-feed-non-valido`); raggiungibilità ⇒ `stato_sync: fallito` + categoria, entro il primo run. Vedi §4.2-1 sotto |
| 6 | † **URL come input non fidato** (NFR-17) | U + I | ✅ | `uscita_rete.py`: 45 test unit sulla matrice degli indirizzi; `trasporto.py` rivaluta la politica **a ogni hop**, cap di dimensione in streaming, timeout di connessione e lettura da configurazione |
| 7 | Ogni run scrive un `sync_run` (esito, timestamp), anche quando fallisce | I | ✅ | `esegui_sync` non solleva mai su errore di feed o di rete: registra. Nessun `commit` nel percorso del job (il SAVEPOINT per item di G-1 lo annullerebbe) |
| 8 | † Prenotazioni sulla **Struttura corretta**, ogni tabella con `host_id` NOT NULL + FK | I + S | ✅ | Test cross-tenant su feed, prenotazioni e run; `test_tenancy_convention.py` arruola `calendario` da sé |
| 9 | † **Normalizzazione VEVENT → `DateRange`** (tabella §5.3) | U | ✅ | `normalizzazione.py` + `tests/test_ical.py`: 42 test su tipo di data, TZID/DST, DURATION, folding/CRLF/BOM/non-ASCII, UID, STATUS/RRULE/EXDATE |
| 10 | † **Chiave naturale = la coppia**: stesso `ical_uid` su Feed diversi ⇒ due Prenotazioni | I | ✅ | Test con due Feed sullo stesso corpo: due righe distinte. Un UNIQUE sul solo `ical_uid` passerebbe l'AC 2 e romperebbe qui |
| 11 | † Tipo di job a catalogo, payload di soli identificatori scalari | U + S (GS-5) | ✅ | `feed_ical.sync_richiesto` in `core/events.py`, payload `(feed_id, host_id)`. La 2.1 **non emette eventi di dominio**: nessun consumatore esiste ancora, e inventarne uno sarebbe anticipare la 2.5 |
| 12 | † **Un solo modulo scrittore** delle tabelle del calendario | S (GS-3) | ⚠️ parziale | GS-3 è assegnata alla Story **2.6** dal test design. Qui l'invariante è rispettato per costruzione (`calendario` legge `strutture` solo dal suo *service*, mai dal repository) e la guardia GS-6 già vieta a chiunque di cancellare quelle tabelle. La guardia sul grafo delle dipendenze resta alla 2.6 |
| 13 | † **Nessuna chiamata di rete reale** nella suite | S (GS-1) | ✅ | `tests/conftest.py::isolamento_di_rete` (autouse) + `tests/test_isolamento_rete.py` che dimostra che la guardia morde |

### AC di NFR-17 (accolti da Fahad, valgono come AC della Story)

| AC | Esito | Dove |
| --- | :---: | --- |
| Soli schemi `http`/`https` | ✅ | `SCHEMI_AMMESSI`; `file`, `gopher`, `ftp`, `javascript`, `data`, `webcal` rifiutati a unit e via API (422) |
| Indirizzo **risolto** rifiutato su loopback / private / link-local / metadati d'istanza | ✅ | denylist su `ipaddress` + reti aggiuntive (CGNAT, `192.0.0.0/24`, metadati Alibaba, NAT64) e srotolamento degli IPv4-mapped. **Tutti** gli indirizzi risolti devono passare: un round-robin con un indirizzo interno non è un bypass |
| Validazione ripetuta **dopo ogni redirect** | ✅ | il client HTTP non segue i redirect; li segue il trasporto un hop alla volta. Test: un `Location:` verso `169.254.169.254` è rifiutato e **il secondo hop non parte** |
| Il rifiuto dà lo stesso errore dell'URL irraggiungibile, **senza rivelare l'esito della risoluzione** | ✅ | `DestinazioneNonAmmessaError` → `UrlNonRaggiungibileError` → categoria `url_non_raggiungibile`, identica a una connessione fallita |
| Validatore testato a unit | ✅ | `tests/test_uscita_rete.py` |
| **Timeout** (connessione e lettura) e **cap di dimensione**, entrambi configurazione (NFR-4) | ✅ | `HOSTPILOT_FEED_*` in `.env.example`; test che cambiando l'impostazione cambia la politica. Cap applicato in streaming **e** sul `Content-Length` dichiarato: un feed che si dichiara da 2 GB non merita il primo byte |
| Il superamento chiude la connessione e scrive un `sync_run` fallito, senza saturare il worker | ✅ | categorie `timeout` / `risposta_troppo_grande`, corpo mai accumulato oltre il tetto |

## Scelte di progetto da segnalare in review

- **`rimossa_dal_feed` solo dopo un parse completo e validato** (E2-G3). Il
  parser è severo per scelta: un corpo non chiuso da `END:VCALENDAR`, o con un
  VEVENT non chiuso, è un **errore**, non «un evento in meno». Ne segue una
  decisione che vale la pena guardare: un calendario **valido ma senza eventi**
  produce un `sync_run` fallito (`feed_senza_eventi`) e **nessuna**
  transizione. Il costo dei due errori non è simmetrico — trattarlo come
  «tutto scomparso» svuoterebbe il calendario e farebbe `decadere` i Conflitti;
  trattarlo come run fallito costa un errore visibile su un Feed che davvero
  non ha prenotazioni. Il test design chiede esplicitamente il secondo (§5.3,
  riga «Trasporto»).
- **Gli uid presenti nel feed includono gli eventi malformati.** Sottigliezza
  della stessa famiglia: un VEVENT con `UID` ma senza `DTEND` è *nel* feed,
  solo non si normalizza. Escluderlo dagli uid presenti marcherebbe
  `rimossa_dal_feed` una Prenotazione viva su un trasporto perfetto. Ha un test
  dedicato e l'ho visto rosso.
- **Un 304 in questa Story è un esito HTTP inatteso.** La 2.1 non manda header
  condizionali, quindi un 304 non è previsto: si registra come run fallito e
  **non tocca nulla**. La 2.2, che introduce `ETag`/`If-Modified-Since`, lo
  tratterà come run *riuscito* con dati intatti. Entrambe le versioni
  rispettano l'invariante che conta (nessuna transizione), che è il punto.
- **Il progresso non lo simula il client.** `stato_sync` è derivato dall'API
  (`mai_sincronizzato` / `in_corso` / `riuscito` / `fallito`) leggendo la
  traccia append-only dei `sync_run` e la coda dei job. Non esiste una colonna
  «ultimo sync riuscito»: un timestamp duplicato è un timestamp che prima o poi
  avanza su un run fallito, ed è precisamente la falsa sincronia che NFR-2
  vieta. Un test di componente verifica che su un run fallito l'orario mostrato
  **non** avanzi.
- **`mai_sincronizzato` esiste come stato dichiarato.** È il caso in cui la
  falsa sincronia fa il danno maggiore, e nessun AC lo copriva (§4.2-3): il
  prodotto dice «non so» invece di tacere in modo ambiguo, coerentemente con il
  `configurazione_non_disponibile` dell'Epic 1.
- **L'URL torna al client redatto.** Se l'Host incolla credenziali nell'URL,
  `https://***@host/path` è ciò che vede — in API e nei log. Test dedicati su
  entrambe le superfici.
- **Nessuna entità `ospite` in questa Story.** Il VEVENT non porta un'identità
  Ospite affidabile (gli export OTA mettono in `SUMMARY` testo opaco tipo
  «Reserved»), e l'anagrafica Ospite è parcheggiata per Fahad (MYL-40). Il
  `SUMMARY` si conserva come testo opaco (`prenotazione.sommario`) perché
  all'Host serve per riconoscere la Prenotazione — non è un'anagrafica.
- **`RRULE` non si espande nell'MVP**, ma non in silenzio: l'evento entra come
  singola occorrenza e il `sync_run` conta
  `eventi_ricorrenti_non_espansi`, che l'API espone e la UI mostra. Un evento
  ricorrente ignorato senza dirlo sarebbe una Prenotazione persa (NFR-1).
- **La priorità del job non ha toccato `core`.** «Prioritario» qui significa
  «già scaduto»: aggiungere una colonna `priority` alla tabella `job` sarebbe
  un cambio del kernel per il bisogno di un solo dominio. Se la 2.2 mostrerà
  che serve davvero (equità della coda, E2-G6), è una decisione architetturale
  da portare a Winston, non da prendere qui.
- **Limite noto e dichiarato: DNS rebinding.** La politica valida gli indirizzi
  risolti, non la socket effettiva; un DNS che cambia risposta fra validazione
  e connessione non è coperto. Chiuderlo richiede il **pinning** dell'indirizzo
  nel trasporto (riscrittura dell'host + `Host` header + SNI). Non è richiesto
  dagli AC di NFR-17 e non l'ho implementato: lo segnalo perché resti tracciato.

## Voci di §4.2 che toccano questa Story

Il test design le manda a John: sono decisioni di prodotto, non le decido io
(criterio di gate 11).

- **§4.2-1 — «errore inline immediato» per un URL irraggiungibile.** Implementata
  la *proposta* del test design: validazione sincrona del formato (422 inline)
  separata dall'esito di raggiungibilità (stato d'errore sul Feed entro il primo
  run). Se John decide diversamente, cambia l'API, non l'invariante.
- **§4.2-2 — il feed che «torna».** **Non deciso da me.** Una Prenotazione
  `rimossa_dal_feed` che ricompare **non** torna `attiva`: nessuna
  risurrezione silenziosa, e in particolare nessun Conflitto che riappare da
  sé. Il fatto non si perde: il `sync_run` conta
  `prenotazioni_ricomparse`. L'AC relativo resta **non chiudibile** finché
  John non decide.
- **§4.2-3 — cosa mostra una superficie che non ha mai avuto un sync riuscito.**
  Implementato lo stato esplicito `mai_sincronizzato` (proposta del test
  design). Riguarda la 2.2, ma la superficie nasce qui.
- **§4.2-13 — ciclo di vita del `feed_ical`** (URL modificato, Feed scollegato):
  **non implementato**, come da indicazione («va deciso prima che qualcuno lo
  implementi per intuizione»). Non esiste endpoint di modifica o scollegamento.

## Finding del test design chiusi qui

| Finding | Esito | Test di regressione |
| --- | :---: | --- |
| **E2-G1** (P0) — nessun isolamento di rete nella suite | chiuso | `tests/conftest.py::isolamento_di_rete` + `tests/test_isolamento_rete.py` (7 test) |
| **E2-G2** (P0) — SSRF sull'URL del Feed (NFR-17) | chiuso | `tests/test_uscita_rete.py` (45) + `TestPoliticaDiUscitaDiRete` (8) |
| **E2-G3** (P0) — «scomparso» ≠ «non ricevuto» | chiuso | `TestScomparsoNonERicevuto` (10, di cui 8 parametrizzati) |
| **E2-G4** (P1) — `TABELLE_DA_SVUOTARE` scritta a mano | chiuso | `tests/test_isolamento_dati.py` (4) |
| **E2-G7** (P0) — «non cancella mai» difeso solo da test di percorso | chiuso | `tests/test_append_preserving_convention.py` (6) |
| **E2-G5** (P1) — l'ambiente e2e non avvia il worker | **deciso**: opzione (a) del test design, la raccomandata — gli AC che dipendono da un job si coprono in **integration**, nessun e2e nuovo in questa Story (elenco chiuso §2.5 rispettato) | `tests/test_calendario_api.py::TestLettura` copre il percorso completo API → job → import → lettura |
| **A2** (retrospettiva) — `permissions:` assente in `ci.yml` | chiuso | blocco `permissions: contents: read` a livello di workflow, con la motivazione scritta in testa al file |

**Aperti e fuori dal perimetro di questa Story:** E2-G6 (equità della coda,
P2 — da valutare con la 2.2), E2-G8 (guardia GS-7, assegnata alla 2.3),
GS-3 e GS-4 (assegnate alla 2.6 e alla 2.7).

## Dev Agent Record

### Evidenza dei test (2026-07-26)

Comandi eseguiti, output reale:

- **Backend** — `uv run pytest -q` → **343 passed** su PostgreSQL 18 reale
  (165 nuovi: 45 uscita di rete, 42 parser/normalizzatore, 46 sync di
  integrazione, 13 API, 2 di gara, 7 isolamento di rete, 4 isolamento dati,
  6 append-preserving).
- `uv run ruff check .` → *All checks passed*; `ruff format --check` → 93 file
  già formattati; `uv run mypy` → *Success: no issues found in 50 source files*.
- **Frontend** — `npm test` → **39 passed** (10 nuovi su `FeedIcalStruttura`);
  `npm run lint`, `npm run typecheck`, `npm run build` puliti.
- **E2E** — `npm run test:e2e` → **10 passed** (chromium + mobile), nessuno
  spec nuovo; la baseline axe serious/critical = 0 copre la pagina di dettaglio
  Struttura, dove il pannello dei Feed è stato innestato.
- **Contratto** — `scripts/export_openapi.py` + `npm run generate:api`
  rieseguiti e committati.

### Prova del rosso (criterio di gate 4)

Tre esperimenti, ciascuno ripristinato subito dopo:

1. **A3-1, test di gara.** Rimosso `sa.UniqueConstraint("feed_id","ical_uid")`
   dalla migrazione 0008 **e** sostituito l'upsert con un check-then-write
   equivalente (`SELECT` poi `INSERT`). Esito:
   `assert esiti.count("importata") == 1` → `AssertionError: assert 8 == 1`,
   con tutte e otto le righe duplicate nel DB.
2. **E2-G3, corpo bugiardo.** Trattato il `FeedNonValidoError` come «feed
   vuoto» (l'implementazione ingenua). Esito:
   `assert run.prenotazioni_rimosse_dal_feed == 0` → `assert 2 == 0`: **due
   prenotazioni vive su due** marcate `rimossa_dal_feed` da una risposta
   troncata. È R2-C riprodotto.
3. **Uid presenti.** Costruito `uid_presenti` dai soli eventi normalizzati.
   Esito: `assert run.prenotazioni_rimosse_dal_feed == 0` → `assert 1 == 0`.

Nel caso 2 le asserzioni del test sono state riordinate perché l'invariante di
**dato** venga verificato prima della contabilità: se cade il primo è una
doppia prenotazione ospitata, se cade il secondo è un'etichetta.

### Note di completamento

- **La rete si stub-a al trasporto.** `tests/server_feed.py` è un
  `ThreadingHTTPServer` su 127.0.0.1 che sa rispondere con redirect,
  `Content-Length` bugiardo, chiusura anticipata e silenzio. Nessun mock del
  client dentro il service: `ETag`, redirect, timeout e cap *sono* il
  comportamento sotto test.
- **La guardia di isolamento di rete deriva da `BaseException`.** Non è
  pedanteria: `valida_destinazione` converte `OSError` in «destinazione non
  ammessa» e il client converte gli errori di rete in «URL non
  raggiungibile». Se la guardia derivasse da `Exception` verrebbe assorbita da
  entrambi, e un test senza risolutore iniettato passerebbe per il motivo
  sbagliato. Ci sono due test che verificano esattamente questo.
- **Due guardie esistenti leggevano i metadati troppo presto.**
  `Base.metadata.tables` contiene solo le tabelle dei moduli importati:
  `test_tenancy_convention.py` sarebbe stato **cieco** alle tre tabelle nuove a
  seconda dell'ordine dei test, perché `calendario` non era raggiungibile da
  `app.main` prima di questa Story. Aggiunto `tests/modello.py::carica_modelli()`
  e usato da tutte le guardie sul modello. È la stessa classe di difetti che le
  guardie combattono — le assenze — applicata alle guardie.
- **`get_settings()` è lru_cache-ata e i test si sporcavano fra loro.** Un test
  che cambiava una variabile d'ambiente lasciava il valore in cache anche dopo
  il ripristino di `monkeypatch`, e il test successivo vedeva
  un'impostazione che non aveva chiesto. Fixture `autouse` che svuota la cache
  dopo ogni test.
- **Sul `xmax = 0`**: distingue la riga appena inserita da quella aggiornata
  nel `RETURNING` dell'upsert. Senza, il conteggio «importate» sarebbe una
  stima, e l'AC 2 si verificherebbe su un numero inventato.
- Il corpus di fixture iCal ha un README che dichiara il proprio limite: è
  modellato su RFC 5545 e sulla forma documentata degli export, **non**
  catturato da feed reali (punto A11, che resta aperto).

### Change log

- 2026-07-26 — Story creata, implementata test-first e consegnata in PR
  (branch `story/2.1-feed-ical-import`). Prima Story dell'Epic 2, primo codice
  di rete in uscita del progetto.

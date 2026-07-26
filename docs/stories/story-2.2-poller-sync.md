---
title: 'Story 2.2 — Poller periodico di sincronizzazione durevole e resiliente'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-07-26
updated: 2026-07-26
review: 'in attesa del verdetto di Murat (cross-review pre-merge)'
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 2.2, AC completi)
  - 'docs/qa/test-design-epic-2.md §3 (12 AC tracciati), §2.4 (gare A3-2/A3-3), §6 (gate)'
  - docs/retrospettive/epic-1.md (azioni A2, A3, A10, A11)
  - 'docs/qa/test-design-epic-1.md §7.7 (RT-3, namespace degli advisory lock)'
  - 'ramo docs/nfr17-politica-uscita-rete (NFR-17: testo non ancora su main)'
issue: 'MYL-45 — Story 2.2'
depends_on: 'Story 2.1 (modulo calendario, trasporto, uscita di rete) — fix-batch su main con PR #37'
---

# Story 2.2 — Poller periodico di sincronizzazione durevole e resiliente

## Story
As an Host,
I want che HostPilot risincronizzi periodicamente i Feed da solo,
So that il calendario resti aggiornato senza che io debba fare nulla, e senza
perdere prenotazioni se un portale è temporaneamente irraggiungibile.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.2
(12 righe tracciate, di cui 7 P0).

| # | AC (test design §3) | Livello | Esito | Dove |
| :---: | --- | --- | :---: | --- |
| 1 | Ogni Feed sincronizzato a **intervallo configurabile** come job durevole, mai un timer in-memory | I | ✅ | `calendario.jobs`: `TIPO_JOB_SYNC_PERIODICO` a catalogo, `_riprogramma` scrive in `job`. `TestUnCicloDurevolePerFeed` (7 test) — «configurabile» provato cambiando `HOSTPILOT_FEED_SYNC_INTERVALLO_MINUTI` e osservando il `due_at` |
| 2 | ⚡ † Bootstrap e riprogrammazione **idempotenti**, anche dopo riavvio e sotto concorrenza | I (gara A3-3) | ✅ | `assicura_sync_periodico` + `bootstrap_sync_periodico`; `TestBootstrapIdempotente` (6 test) e `test_calendario_gara_poller.py::TestBootstrapDelCicloSottoConcorrenza`. Rosso visto |
| 3 | ⚡ † Claim concorrente: un solo worker esegue il sync di un dato Feed | I (gara A3-2) | ✅ | `test_calendario_gara_poller.py::TestClaimDelPollerSottoConcorrenza`. Rosso visto |
| 4 | `ETag` / `If-Modified-Since` evitano scaricamenti inutili | I | ✅ | `trasporto.Validatori` + colonne `feed_ical.etag/last_modified`; `TestRichiestaCondizionale` e `TestValidatoriMemorizzati` (9 test) — asserzioni sulle intestazioni **realmente arrivate al server** |
| 5 | † Un **304** non tocca alcuna Prenotazione, non marca nulla `rimossa_dal_feed`, e il `sync_run` è riuscito | I | ✅ | Ritorno anticipato in `service.esegui_sync`: nessun percorso da lì a `_riconcilia`. `TestTrecentoQuattro` (6 test) + `TestUn304NonSollecitato` (2) |
| 6 | Un fallimento temporaneo lascia **intatti** i dati già importati | I | ✅ | `TestUnFallimentoNonErodeIDati` — quattro giri falliti di fila su tre forme di guasto, poi ripresa senza perdite |
| 7 | Il fallimento produce un **errore visibile sulla Struttura** | I + Cmp | ✅ | `categoria_errore` + `fallimenti_consecutivi` in `FeedIcalOutput`; `test_calendario_api.py` e `FeedIcalStruttura.test.tsx` (3 test nuovi: quando, quante volte, e la distinzione fra intoppo e guasto) |
| 8 | **Alert interno dopo N fallimenti consecutivi**, N configurabile | I | ⚠️ implementato, AC **non chiudibile** (§4.2-9) | `service._valuta_alert_fallimenti`: log strutturato all'attraversamento della soglia. `TestFallimentiConsecutiviEAlert` (7 test). Vedi «Voci di §4.2» |
| 9 | Ogni superficie con dati da Feed espone l'**ultimo sync riuscito**; su un run fallito non avanza | I + **S** (GS-7) + E | ✅ I e S · ❌ E non implementabile | `PrenotazioniDelFeedOutput` (envelope nuovo) + `tests/test_superfici_feed_convention.py` (GS-7, 7 test). Il livello **E** richiede due superfici che oggi non esistono: vedi «Scelte di progetto» |
| 10 | Intervallo **adattivo** fino a 5' in prossimità di un check-in | U | ⚠️ implementato, AC **non chiudibile** (§4.2-8) | `calendario/intervallo.py`, funzione pura; `tests/test_intervallo_sync.py` (14 test, confini e cambio d'ora inclusi) |
| 11 | † Un Feed **mai** sincronizzato espone uno stato esplicito, mai un orario inventato | I + Cmp | ✅ | `TestVeritaTemporaleSottoIlPoller`, `test_le_prenotazioni_di_un_feed_MAI_sincronizzato_dicono_non_so`, e il ramo `maiAggiornato` di `FeedIcalStruttura` (il trattino `—` è stato tolto) |
| 12 | † Backoff e `max_attempts`: un Feed rotto **non blocca** gli altri; l'esaurimento è visibile | I | ✅ | `TestUnFeedRottoNonBloccaGliAltri` (2 test): quattro giri con due Feed in coda, e l'esaurimento che lascia `failed` + `last_error` |

### Lavoro di igiene agganciato alla Story (accolto dal supervisore)

| # | Esito | Dove |
| --- | :---: | --- |
| **MYL-44** — `alembic check` in CI | ✅ | Passo `Schema allineato ai modelli` nel job `backend`. **Ha richiesto di chiudere prima la deriva preesistente** (5 voci): vedi «Scelte di progetto» |
| **MYL-49** — guardia sulla base della PR | ✅ | Job `base-della-pr`; A2 applicata (nessun `${{ }}` di input non fidato dentro `run:`, nessun checkout, nessun permesso in più) |
| **RT-3** — namespace degli advisory lock | ✅ chiuso | `app/core/lock.py` + `tests/test_lock_convention.py` (8 test) |

## Scelte di progetto da segnalare in review

- **Un `304` si accetta solo se glielo abbiamo chiesto.** È la scelta più
  importante del file, e diverge da come la Story 2.1 aveva previsto questo
  passaggio. La 2.1 scrive: «la 2.2 tratterà il 304 come run *riuscito* con
  dati intatti». Qui vale **solo per un 304 in risposta a una richiesta
  condizionale**: se non abbiamo mandato validatori, un 304 resta
  `esito_http_inatteso`. La ragione è asimmetrica — se non abbiamo mandato
  nulla non c'è niente che il portale possa aver confrontato, quindi quel 304
  non afferma «è tutto uguale»; accettarlo congelerebbe il Feed **per sempre**,
  con esito riuscito e quindi senza che nessuna superficie lo segnali.
  Conseguenza pratica: il caso `(RispostaPreparata(stato=304), ESITO_HTTP_INATTESO)`
  già pinnato in `test_calendario_sync.py` **resta verde e invariato**, e
  accanto c'è il caso nuovo del 304 sollecitato.

- **I validatori si scrivono DOPO la riconciliazione, mai dopo un run fallito.**
  Un `ETag` memorizzato su un corpo che non è entrato nel database farebbe
  rispondere 304 a un feed che non abbiamo mai importato: il Feed resterebbe
  vuoto dichiarandosi aggiornato. E si **sostituiscono**, non si fondono: una
  200 senza `ETag` azzera quello vecchio (`test_una_risposta_senza_validatori_azzera_quelli_vecchi`).

- **`fallimenti_consecutivi` è DERIVATO, non un contatore sul Feed.** Stessa
  scelta e stessa ragione di `ultimo_sync_riuscito_il`: un contatore mantenuto
  ha due punti di scrittura — l'incremento e **l'azzeramento al primo
  successo** — e il test design nota che il secondo è quello che si dimentica.
  Un contatore che non si azzera fa suonare l'alert per sempre su un Feed
  guarito, e un alert che suona sempre è un alert spento. Derivandolo,
  l'azzeramento non è codice che qualcuno deve ricordarsi di scrivere.

- **Un 304 FA avanzare «dati aggiornati alle HH:MM».** Scelta esplicita e nel
  verso giusto di NFR-2: con un 304 abbiamo davvero verificato col portale che
  i dati che mostriamo sono correnti. Non farlo avanzare farebbe invecchiare
  l'etichetta su un Feed sano finché l'Host non conclude che è rotto.

- **`GET /feed-ical/{id}/prenotazioni` ora ritorna un envelope, non una lista.**
  È un cambio di contratto, e lo segnalo perché è tale. UX-DR6 chiede
  l'etichetta su **ogni** superficie con dati da Feed, e una lista nuda non ha
  un posto dove metterla: il consumatore dovrebbe procurarsi il timestamp da
  una seconda chiamata e correlarlo a mano — due letture che possono divergere
  e nessuna che dica quale vale. La rotta oggi non è consumata da alcun hook o
  componente, quindi il costo del cambio è zero e non tornerà a zero più tardi.

- **GS-7 l'ho implementata qui, non nella 2.3.** §2.6 la assegna alla 2.3 e
  §3 la mette fra i livelli dell'AC 9 di **questa** Story: ho seguito la
  tabella degli AC, che è il contratto di copertura. Se preferisci il
  contrario, la guardia è un file solo e si sposta; ma anticiparla costa poco e
  significa che la griglia del calendario nasce già dentro il cancello.

- **Il livello E dell'AC 9 non è implementabile in questa Story, e non l'ho
  finto.** Il test design lo motiva con «due superfici che non divergono dopo
  una mutazione»: oggi la superficie è **una** — `FeedIcalStruttura` sulla
  pagina di dettaglio della Struttura — e `app/(app)/calendario/page.tsx` è
  ancora un segnaposto. Uno spec e2e su una sola superficie non può vedere il
  difetto che quel livello esiste per vedere. Passa alla 2.3 insieme alla
  griglia. §2.5 vieta comunque l'e2e sul **ciclo** del poller, che infatti è
  tutto in integration.

- **Il ciclo periodico parte al collegamento, non al riavvio del worker.**
  `collega_feed` accoda l'import on-demand **e** il ciclo; il bootstrap
  all'avvio è la rete di sicurezza per i cicli persi. Affidare il primo giro al
  bootstrap significherebbe che un Feed collegato oggi comincia a
  risincronizzarsi al prossimo rilascio.

- **Un lock consultivo, non un UNIQUE, per il bootstrap.** Il vincolo non è
  esprimibile come unicità di una riga: `job` è una coda generica del kernel e
  la condizione è «nessuna riga di questo tipo per questo feed in stato pending
  o running» — un predicato su un sottoinsieme. Un UNIQUE parziale su
  `(job_type, payload->>'feed_id')` legherebbe `core` alla forma del payload di
  un dominio (AD-1). Il lock è **per Feed**, e c'è un test che lo dimostra
  (`test_feed_DIVERSI_non_si_aspettano_a_vicenda`): un lock su chiave costante
  darebbe la stessa post-condizione e passerebbe, poi con centinaia di Feed il
  bootstrap diventerebbe una fila indiana e nessun test lo direbbe.

- **`bootstrap_sync_periodico` non è scopata per Host, e vive in `jobs.py`.**
  All'avvio del worker non esiste un Host «corrente», e scoparla
  significherebbe non sincronizzare i Feed di tutti gli altri. Vive fuori dal
  repository perché lì la guardia di tenancy (G-3) impone `host_id` su ogni
  metodo: l'eccezione è dichiarata dove si vede, invece di indebolire la regola
  per tutti. È la forma già usata da `identity/jobs.py::purge_sessioni_scadute`.

- **La deriva di `alembic check` andava chiusa prima di accendere il cancello**
  (lo diceva già la nota della 2.1 su MYL-44). Cinque voci, di cui **due erano
  deriva dei MODELLI** e non dello schema: gli indici parziali `ix_job_due` e
  `ix_outbox_pending` esistevano nel database dalla migrazione 0001 e non erano
  dichiarati — `alembic check` proponeva di **cancellarli**. Dichiarati in
  `app/core/jobs.py` e `app/core/outbox.py`, nessuna modifica al database. La
  terza è `regime_lettura.host_id`: il modello (`unique=True, index=True`) rende
  un indice unico, lo schema aveva UNIQUE constraint **più** un indice non unico
  ridondante; la migrazione 0009 lascia cadere l'indice ridondante (`drop_index`
  non è distruttivo ai sensi di AD-20 — non cancella righe, e il vincolo
  mantiene il proprio indice sulla stessa colonna).

- **Helper dei test estratti in `tests/calendario.py`, fixture `contesto` in
  `conftest.py`.** Non è un refactor opportunistico: importare la fixture da un
  file di test la rende una ridefinizione (F811) a ogni funzione che la chiede
  come parametro, e con tre file che ne hanno bisogno la CI sarebbe rossa. Le
  fixture si condividono dal conftest, gli helper puri da un modulo.

## Voci di §4.2 che toccano questa Story

Sono decisioni di prodotto: non le decido io (criterio di gate 11).

- **§4.2-8 — «adattivo fino a 5' in prossimità di check-in» non è
  quantificato.** Ho implementato la *proposta del test design*: tre parametri
  di configurazione (`feed_sync_intervallo_minuti`,
  `feed_sync_intervallo_minimo_minuti`, `feed_sync_finestra_prossimita_ore`) e
  una funzione pura che li rispetta. I test provano che la funzione **obbedisce
  ai parametri**, non che 24 ore siano la finestra giusta. **L'AC 10 resta non
  chiudibile** finché John/Fahad non fissano la soglia. Nota di dettaglio già
  decisa in codice e da confermare: la regola è a **gradino**, non a rampa, e
  «in prossimità» guarda il primo check-in **attivo** della Struttura.

- **§4.2-9 — «alert interno dopo N fallimenti consecutivi» non ha né N né un
  artefatto osservabile.** Ho implementato la proposta minima del test design:
  contatore derivato + soglia configurabile (`feed_sync_fallimenti_per_alert`,
  default 3) + log strutturato all'attraversamento. È verificabile — c'è un
  test che lo cattura con `caplog` — ma il canale di alert vero è NFR-7, cioè
  Epic 3. **L'AC 8 resta tracciato come non chiudibile.** Scelta di dettaglio da
  confermare: l'alert scatta **all'attraversamento**, non a ogni fallimento
  successivo, perché un portale giù per un giorno produrrebbe 96 righe identiche.

- **§4.2-3 — cosa mostra una superficie mai sincronizzata.** Coperto
  dall'implementazione (`mai_sincronizzato` dalla 2.1, più il ramo
  `maiAggiornato` per il Feed fallito che non ha mai avuto un successo), ma
  l'interpretazione resta la proposta del test design, non una decisione.

## A10 e A11 della retrospettiva

- **A10 — osservabilità del poller.** Implementato lo **scenario A in forma
  minima**, come indicato nell'issue: `ultimo_sync_riuscito_il` (esisteva già) e
  `fallimenti_consecutivi` (nuovo) come campi API. Metriche, dashboard e storico
  di compliance restano NFR-7 → Epic 3. Costo pagato: un giro di contratto
  (OpenAPI + client TS rigenerati e committati).
- **A11 — nessuno ha mai visto l'app girare fuori dalla CI.** Non l'ho fatto:
  la raccomandazione dice «prima di dichiarare fatta la 2.2, far girare almeno
  un feed reale in un ambiente vero», e ambiente e decisione sono di Fahad.
  **Lo segnalo perché non resti implicito**: nessun test di questa Story ha mai
  parlato con Airbnb o Booking — per NFR-16 e per la guardia GS-1, che vieta
  qualunque uscita di rete non-loopback nella suite.

## Finding e debiti chiusi qui

| Voce | Esito | Test di regressione |
| --- | :---: | --- |
| **RT-3** (Epic 1 §7.7) — namespace degli advisory lock da rivalutare al secondo lock | chiuso | `tests/test_lock_convention.py` (8 test): namespace distinti, SQL del lock in un solo modulo, nessuna dichiarazione fuori posto, più due sentinelle |
| **MYL-44** — deriva di `alembic check` | chiuso | passo di CI + `tests/test_migrations.py` esistente |
| **R2-C / E2-G3, variante 304** | chiuso | `tests/test_calendario_condizionale.py` (20 test) |

**Aperti e fuori dal perimetro:** E2-G6 (equità della coda, P2 — l'ho
guardato: `TestUnFeedRottoNonBloccaGliAltri` mostra che un Feed rotto non
blocca la coda, ma **non** misura l'equità fra tenant con K job di sync in
coda; resta aperto e resta P2), GS-3 (2.6), GS-4 (2.7), E2-G8.

## Dev Agent Record

### Evidenza dei test (2026-07-26)

Comandi eseguiti, output reale.

- **Backend** — `uv run pytest -q` → **499 passed** in 114s su PostgreSQL 18
  reale (**87 nuovi** rispetto ai 412 su `main`: 20 condizionale, 33 poller,
  14 intervallo, 3 gara, 8 lock, 7 GS-7, più 2 API).
- `uv run ruff check .` → *All checks passed!* · `uv run ruff format --check .`
  → *106 files already formatted* · `uv run mypy` → *Success: no issues found
  in 53 source files*.
- **`alembic check`** → *No new upgrade operations detected.* (su database
  ricostruito da zero con `alembic upgrade head`). Prima di questa PR lo stesso
  comando riportava 5 operazioni.
- **Frontend** — `npm test` → **48 passed** (14 file; 9 erano 39 su `main`,
  +9 su `FeedIcalStruttura`) · `npm run lint`, `npm run typecheck`,
  `npm run build` puliti.
- **E2E** — `npm run test:e2e` → **10 passed** (chromium + mobile), nessuno
  spec nuovo, come impone §2.5.
- **Contratto** — `scripts/export_openapi.py` + `npm run generate:api`
  rieseguiti e committati.

### Prova del rosso (criterio di gate 4)

Due esperimenti, ciascuno ripristinato subito dopo.

1. **A3-2 — claim del poller.** Rimosso `skip_locked=True` da
   `app/core/jobs.py::claim_due` (`.with_for_update(skip_locked=True)` →
   `.with_for_update()`). Esito: `threading.BrokenBarrierError` —
   i sette contendenti restano appesi sul lock di riga e non raggiungono mai la
   seconda barriera entro i 10 secondi. È esattamente la proprietà che l'AC
   nomina («gli altri sette non ottengono nulla **e non bloccano**») e che un
   test sul solo conteggio non avrebbe visto: senza `SKIP LOCKED` il conteggio
   resterebbe 1, perché in READ COMMITTED chi aspetta poi rivaluta il `WHERE` e
   scarta la riga già presa. La disposizione con le transazioni tenute aperte
   fino a che tutti e otto hanno tentato è ciò che rende le due implementazioni
   distinguibili.

2. **A3-3 — bootstrap del ciclo periodico.** Rimossa la riga
   `blocca_per_id(db, NAMESPACE_SYNC_PERIODICO, feed.id)` da
   `assicura_sync_periodico`. Esito:
   `assert len(cicli) == 1` → **`AssertionError: assert 8 == 1`** — otto cicli
   periodici in coda per lo stesso Feed. Il difetto è reale e sarebbe stato
   silenzioso: otto volte le richieste a quel portale, per sempre, senza alcun
   errore.

Un terzo esperimento **non riuscito**, e lo riporto perché è informazione:
la prima stesura di `tests/test_calendario_poller.py` aveva un caso
parametrizzato **verde per la ragione sbagliata**. L'handler usa
`client_di_produzione()`, che legge la politica di uscita di rete dalla
configurazione: senza il loopback ammesso, ogni fetch verso il server di test
veniva rifiutato *a monte*, e il rifiuto produce `url_non_raggiungibile` —
proprio uno degli esiti che il caso voleva osservare. L'ho scoperto perché gli
altri casi della stessa parametrizzazione fallivano. Rimedio: fixture
`rete_verso_il_loopback` **autouse** su tutto il file, con il perché scritto
nella docstring.

### Note di completamento

- **Il rischio che questa Story doveva chiudere per primo è chiuso, e la
  chiusura è strutturale.** In `esegui_sync` il ramo del 304 fa un **ritorno
  anticipato**: non esiste alcun percorso da lì a `_riconcilia`. Non è una
  guardia che qualcuno può indebolire — è l'assenza di un cammino.
- **Il 304 nei test non si prepara a mano.** `ServerFeed` confronta davvero
  l'`If-None-Match` che il client gli manda e risponde 304 da sé. Un 304
  preparato a tavolino avrebbe provato che il codice sa *leggere* un 304, non
  che sappia *chiedere* in modo condizionale — e la differenza fra le due cose
  è l'AC 4 per intero.
- **Il ciclo periodico si riprogramma anche quando il sync fallisce.** È il
  punto di NFR-1: `esegui_sync` non solleva sugli errori di rete (li registra),
  quindi l'handler arriva alla riprogrammazione in entrambi i casi. L'unica
  uscita senza riprogrammazione è il Feed che non esiste più.
- **`ParametriIntervallo` valida alla costruzione.** Un
  `feed_sync_intervallo_minuti = 0` letto dall'ambiente riaccoderebbe il job già
  scaduto e il poller consumerebbe la coda di **tutti** gli Host. Un parametro
  di configurazione sbagliato deve fermare l'avvio, non degradare in un difetto
  di regime che nessuno collega alla causa.
- **L'intervallo adattivo confronta ISTANTI, non date.** Il check-in è una data
  Europe/Rome (AD-3): il confronto usa l'inizio di quel giorno nel fuso locale.
  Sottrarre date perderebbe l'ora, e attraverso il cambio d'ora perderebbe
  proprio i sessanta minuti che la regola esiste per proteggere — c'è un test
  sul 26 ottobre 2026 che lo pinna.
- **La guardia MYL-49 non fa checkout.** Le serve solo il payload dell'evento,
  e un job che non clona il repository non può eseguirne il codice. Il corpo
  della PR passa da `env:` e non da `${{ }}` dentro `run:`: è l'unico campo di
  questa pipeline che un estraneo può scrivere, e l'interpolazione avviene prima
  che la shell veda lo script. Ho verificato la logica su sei casi, iniezione
  compresa (`$(touch /tmp/pwned)` nel corpo: nessun file creato).
- **`sed` POSIX e non `grep -P` nella guardia**: il PCRE di grep si rifiuta di
  girare in un locale non UTF-8 e la guardia diverrebbe rossa per la ragione
  sbagliata. I corpi delle PR di GitHub arrivano con CRLF, quindi `tr -d '\r'`.
- **Il trattino `—` è stato tolto dalla UI.** Nel ramo «riuscito» un timestamp
  assente veniva reso come `—`, che si legge come un valore. Ora si dice che
  non si sa.
- **I permessi della CI sono passati a default-deny** dopo il primo giro di
  Sonar (`githubactions:S8264`, unico finding, Security Rating C sul nuovo
  codice). `permissions: contents: read` a livello di workflow lo dava anche
  ai job che non toccano il repository: ora il workflow è `permissions: {}` e
  i quattro job che fanno `actions/checkout` se lo concedono al proprio
  livello, mentre `base-della-pr` dichiara `{}` esplicito. Il finding era
  corretto e la postura di A2 ne esce più stretta, non più larga.

### Change log

- 2026-07-26 — Story creata, implementata test-first e consegnata in PR
  (branch `story/2.2-poller-sync`, base `main`). Secondo advisory lock del
  progetto: RT-3 scade e la convenzione dei namespace è scritta e sorvegliata.
  Prima PR con `alembic check` e con la guardia sulla base della PR attivi.

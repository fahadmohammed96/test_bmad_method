---
title: 'Story 2.4 — Inserimento manuale di Prenotazioni'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-07-30
updated: 2026-07-30
review: 'fix-forward del P1 di Murat (AC 6, testimone che non cadeva) applicato — in attesa del secondo verdetto'
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 2.4, AC completi)
  - 'docs/qa/test-design-epic-2.md §3 Story 2.4 (9 AC tracciati, 5 P0), §2.4 (gare A3), §2.5 (elenco chiuso e2e), §3 Story 2.3 AC 6 e AC 8 (residui)'
  - 'docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-3, AD-14, AD-17, AD-18, AD-19, AD-20, AD-21)'
  - 'docs/prd.md §4 Glossario (Canale), §14.2 (DECISIONE MYL-40)'
issue: 'MYL-61 — Story 2.4'
depends_on: 'Story 2.3 (anagrafica ospite, griglia, etichetta di freschezza) — su main'
---

# Story 2.4 — Inserimento manuale di Prenotazioni

## Story
As an Host,
I want inserire una Prenotazione manuale (prenotazione diretta o blocco date),
So that il calendario rifletta anche ciò che non arriva dai portali e concorra
all'anti double-booking.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.4 (9 righe
tracciate, 5 P0). I test backend citati senza percorso stanno in
`backend/tests/test_prenotazione_manuale.py`.

| # | AC (test design) | Livello | Esito | Dove |
| :---: | --- | :---: | :---: | --- |
| 1 | Creata in stato **`attiva`** e **partecipa** alla rilevazione dei Conflitti | I | ✅ (la partecipazione come **precondizione**, vedi AC 2) | `TestCreazione::test_una_manuale_nasce_attiva_e_senza_feed`, `TestApiCreazione::test_creare_una_manuale_risponde_201`, `TestPartecipaAllaRilevazione` (2 test) |
| 2 | Una manuale sovrapposta a una da Feed **genera un Conflitto** | I | ❌ **non coperto — è la Story 2.5** | Dichiarato, non taciuto: vedi «Voci aperte» |
| 3 | **Non si cancella fisicamente**: transizione a `cancellata` + `prenotazione.cessata` | I + **S** (GS-6) | ✅ | `TestCancellazione` (5 test), `TestApiCancellazione` (4 test), `test_gara_cancellazione_prenotazione.py`. GS-6 **non allargata**: `test_append_preserving_convention.py` è invariata |
| 4 | † `prenotazione.cessata` a catalogo con payload di soli identificatori | U | ✅ | `TestEventoACatalogo` (2 test): il payload è esattamente `{prenotazione_id, host_id, struttura_id}` e aggiungere `ospite` solleva |
| 5 | † Il UNIQUE `(feed_id, ical_uid)` non impedisce l'inserimento né collassa più manuali | I | ✅ | `TestVincoloUniqueConNull` (2 test): cinque righe `(NULL, NULL)` convivono su Postgres reale; il CHECK nuovo chiude la forma **mista** |
| 6 | † `DateRange` (`check_out > check_in`), adiacenza **non** è sovrapposizione, 422 `problem+json` mai 500 | U + I | ✅ | U: `test_l_intervallo_di_una_manuale_e_quello_di_ad_3`; adiacenza esaustiva in `test_date_range.py::TestOverlapSemiOpen` + `TestConfineDellIntervallo`; HTTP: `TestApiCreazione::test_un_intervallo_vuoto_e_un_422_problem_json_mai_un_500` (2 casi: zero notti **e** date invertite) |
| 7 | † Tenancy: si crea **solo** su Strutture del proprio Host | I | ✅ | `TestTenancy` (2 test, con «zero righe scritte»), `TestApiCreazione::test_una_struttura_di_un_altro_host_e_404`, `::test_senza_sessione_si_ottiene_401`, `TestApiCancellazione::test_una_prenotazione_di_un_altro_host_e_404` |
| 8 | † Una Struttura **`archiviata`** non accetta nuove Prenotazioni **e i suoi Feed smettono di sincronizzare** | I | ⚠️ **prima metà coperta, seconda metà aperta** | `TestStrutturaArchiviata` (2 test) + `TestApiCreazione::test_una_struttura_archiviata_e_422`. La seconda metà: vedi «Voci aperte» |
| 9 | † Il **blocco date** (manuale senza Ospite) è ammesso e partecipa ai Conflitti | I | ✅ | `TestCreazione::test_il_blocco_date_si_salva_completamente_senza_ospite`, `TestOspiteFacoltativoDavvero` (3 test), `TestApiCreazione::test_un_form_che_manda_i_campi_dell_ospite_VUOTI_non_crea_un_ospite`. La manuale di `TestPartecipaAllaRilevazione` **è** un blocco date |

### Gli AC di `epics.md` non tracciati nel test design

| # | AC | Esito | Dove |
| :---: | --- | :---: | --- |
| E1 | L'Host **può** — non deve — indicare l'Ospite: nome, email, telefono **facoltativi**, mai obbligatori, mai precompilati con un valore dedotto | ✅ | `TestApiCreazione::test_nessun_campo_dell_ospite_e_obbligatorio_nel_contratto` (asserito sull'OpenAPI: `OspiteInput.required == []`); `components/FormPrenotazioneManuale.test.tsx` → `l'Ospite è facoltativo DAVVERO` (3 test), fra cui «la nota NON diventa il nome dell'Ospite» |
| E2 | L'Ospite si scrive passando dal **service di `calendario`** (AD-18, AD-21) | ✅ | `service.crea_prenotazione_manuale` usa `OspiteRepository` del proprio modulo; nessun altro modulo importato |
| E3 | Una manuale cancellata entra nel ciclo di **retention** di AD-21 come le altre | ✅ | `TestLaRetentionRaggiungeAncheLeManuali` (2 test): la cancellata è selezionata da `filtro_scadute`, l'attiva e futura no. Nessun codice nuovo — l'AC era «non costruire una scorciatoia», e la decorrenza la scrive `marca_cancellata` |
| E4 | Il `sommario` resta **testo opaco**, mai un suggerimento di nome (NFR-11, MYL-40) | ✅ | `TestCreazione::test_il_sommario_resta_il_testo_che_l_host_ha_scritto`; sul form il campo nota e il campo nome sono separati e nessuno inizializza l'altro |

## I due residui QA della Story 2.3, chiusi qui

### AC 6 — «una mutazione della sorgente aggiorna sia la griglia sia l'etichetta» (P0)

Chiuso alla **terza** stesura, e le due che non hanno tenuto valgono più della
conclusione: entrambe erano verdi, ed entrambe restavano verdi con il difetto in
pagina.

**Prima stesura — l'etichetta asserita per assenza.** Le due asserzioni erano
`potrebbe essere incompleta` visibile e `Dati aggiornati alle` assente: **vere
anche prima** della mutazione. Cancellando `onSuccess` il test restava verde
sulla metà «etichetta». Causa: in questo ambiente `ultimo_sync_riuscito_il` è
`null` per tutta la suite (nessun worker, nessun import concluso), quindi la
stringa `HH:MM` non si renderizza mai e qualunque asserzione scritta lì è vera a
etichetta ferma.

**Seconda stesura — il polling consegnava l'aggiornamento al posto della
mutazione.** Trovata da Murat in cross-review (PR #52), riprodotta e confermata.
`useCalendario` accende `refetchInterval: 3000` quando `stato_sync ===
"in_corso"`, ed è esattamente lo stato di questo ambiente: `collega_feed` accoda
il job, nessun worker lo drena, `sync_in_coda` resta vero. Con il timeout di
`expect` a 5000ms e il poll a 3000ms, **qualunque** asserzione post-mutazione
viene soddisfatta entro la finestra di retry, con o senza invalidazione:

| # | codice | esito |
| :---: | --- | :---: |
| 1 | seconda stesura intatta | ✅ verde (4.4s) |
| 2 | seconda stesura, `onSuccess` rimosso da **entrambi** gli hook | ✅ **verde (10.1s)** ← il difetto |

I secondi in più sono la firma: non era l'invalidazione a consegnare
l'aggiornamento, era l'attesa del poll. E c'è un'ironia strutturale che vale
ricordare: il Feed si collega **deliberatamente** perché l'etichetta abbia
qualcosa da dire, ed è quel collegamento ad accendere il polling che maschera il
meccanismo che si voleva osservare. Il test si era tolto il testimone da sé.

La prova del rosso che avevo usato — congelare la freschezza al primo render —
era valida per **quel** difetto (rompe la sorgente dati dell'etichetta, e nessun
refetch la salva), ma non per il meccanismo che l'AC 6 nomina. L'AC 6 parla di
**coerenza fra cache**: la mutazione che la prova è cancellare `onSuccess`, ed è
la stessa che avevo usato per scoprire la debolezza della prima stesura. Non
l'ho rieseguita dopo la correzione. È la lezione di questa Story.

**Terza stesura — l'intercettazione spostata all'inizio, e tre campi invece di
uno.** L'unica differenza sostanziale è `stato_sync: "riuscito"`, che riporta
`refetchInterval` a `false`: da lì l'unica sorgente di refetch è la mutazione.
`feed_mai_sincronizzati: 0` segue per coerenza — un payload «riuscito» con Feed
mai sincronizzati affermerebbe due cose opposte. Installata dal primo `goto`, la
pagina rende il ramo `HH:MM` da subito, e ne segue un guadagno: l'asserzione
NFR-2 dell'atto 1 passa da «`Dati aggiornati alle` è assente» a «l'etichetta è
**ancora** alle 14:35 dopo l'inserimento» — asserisce che una manuale non fa
*avanzare* la freschezza dei portali, invece di asserire un'assenza che c'era
comunque.

I due atti sono ora (`frontend/e2e/calendario.spec.ts`, `una mutazione della
sorgente muove la griglia e l'etichetta, senza reload`):

1. l'inserimento muove la **griglia** e non muove l'**etichetta** (NFR-2);
2. l'orario della sorgente avanza, e la cancellazione muove **entrambe**.

**Prova del rosso — quella giusta**, misurata su `chromium`:

| # | codice | esito |
| :---: | --- | :---: |
| 4 | terza stesura intatta | ✅ verde (5.2s / mobile 4.7s) |
| 5 | `onSuccess` rimosso dalla **cancellazione** | ❌ rosso su `Cancellata` (9.5s) |
| 6 | `onSuccess` rimosso dalla **creazione** | ❌ rosso su `Ospite Inventato` (8.3s) |

La proprietà che questo test deve conservare, ed è scritta nel suo docstring:
**diventa rosso se si toglie `onSuccess` da uno dei due hook**, con il polling
nello stato in cui l'ambiente lo mette davvero. Chi lo modifica rimisuri quello,
non che sia verde.

Oggi griglia ed etichetta vengono dalla **stessa** query (una sola chiave
invalidata), quindi divergere è strutturalmente impossibile: l'asserzione
sull'etichetta è ciò che diventa rossa il giorno in cui le si separa senza
invalidare entrambe — la classe di difetto della Story 1.6.

Resta **fuori portata in questo ambiente** un import che si conclude davvero: il
`webServer` avvia l'API ma non il worker, e la politica di uscita di rete
rifiuta il loopback (NFR-17). Non è il perimetro della Story: è l'ambiente. Ciò
che l'AC 6 chiede — che una mutazione della sorgente aggiorni griglia **e**
etichetta — è però asserito, e cade quando il meccanismo non c'è.

### AC 8 — axe sui chip su dati veri

Chiuso. `violazioniGravi(page)` gira **tre** volte nel test nuovo su dati
persistiti dal server: a form aperto (superficie nuova), dopo l'inserimento con
il chip `Inserita a mano` in pagina, e dopo la cancellazione con il chip
`Cancellata`. Nessuno spec nuovo, `axe-utils.ts` invariato (vincolo A4).

Serviva davvero: la 2.4 introduce un **tono nuovo** per il badge `manuale`
(`components/BadgeCanale.tsx`), e il payload intercettato preesistente contiene
solo `airbnb`/`booking`/`altro` — non avrebbe mai visto quel tono. E-2F4 era un
`color-contrast serious` su quello stesso componente.

## Scelte di progetto da segnalare in review

**`manuale` è un valore nuovo di `canale_feed`, non un riuso di `altro`.** Il
Glossario (PRD §4) definisce il Canale come «la fonte OTA di una Prenotazione:
Airbnb, Booking.com, o inserimento manuale»: il valore mancava perché nessun
percorso scriveva Prenotazioni senza Feed. Riusare `altro` renderebbe una
Prenotazione scritta dall'Host indistinguibile in griglia da una di un terzo
portale — l'opposto della distinzione per Canale che FR-4 chiede, sul confronto
che all'Host interessa più di tutti.

**Il CHECK `(feed_id IS NULL) = (ical_uid IS NULL)`.** La forma **mista** — un
`feed_id` senza `ical_uid` — sfuggirebbe al UNIQUE `(feed_id, ical_uid)`, perché
in Postgres i `NULL` sono distinti fra loro dentro un indice: lo stesso Feed
potrebbe produrre righe duplicate e l'upsert idempotente non se ne accorgerebbe.
È lo stesso vincolo, chiuso dal lato che l'unicità non copre.

**`ALTER TYPE … ADD VALUE` senza usare il valore nella stessa migrazione.**
Postgres ammette `ADD VALUE` dentro una transazione ma vieta di *usare* il
valore prima del commit, e `env.py` esegue l'intero `upgrade` in una sola
transazione. È la ragione per cui il CHECK non nomina `'manuale'` (vedi «Voci
aperte»).

**`POST /cancellazione`, non `DELETE`.** Il verbo dell'API dichiara cosa succede
al dato: qui non si cancella nulla, si registra un fatto, la riga resta con la
sua storia e continua a comparire in griglia con la sua etichetta. Un `DELETE`
inviterebbe il prossimo a implementarlo davvero — la quarta cancellazione
distruttiva che AD-20 non ammette.

**L'idempotenza della cancellazione è nella `UPDATE`, non in un `if`.** La
condizione sullo stato sta dentro l'istruzione (`WHERE stato = 'attiva'`) e
l'evento si emette solo se ha toccato una riga. Con l'`if` fuori, otto
contendenti producono **cinque** `prenotazione.cessata` invece di uno — misurato,
`test_gara_cancellazione_prenotazione.py` — e nessuna delle due conseguenze dà
errore: `cessata_il` riscritta rimanda in avanti la scadenza di un dato
personale (AD-21), e nella 2.5 lo stesso Conflitto decadrebbe più volte.

**Tre campi vuoti non sono un Ospite.** Una riga `ospite` con `nome`, `email` e
`telefono` a `NULL` sarebbe indistinguibile da un'anagrafica azzerata dalla
retention: l'evidenza `anonimizzato_il` esiste proprio per separare «non ha mai
avuto contatti» da «i contatti sono stati cancellati». La normalizzazione della
stringa vuota sta nello **schema d'ingresso** perché un form HTML invia sempre i
suoi campi, e li invia vuoti — e su `email` la stringa vuota non passerebbe
nemmeno la validazione di formato, trasformando un campo facoltativo in un 422.

**`leggi_struttura_attiva` vive in `strutture`, non in `calendario`.** Lo stato
della Struttura è di quel modulo: `calendario` che leggesse `StatoStruttura`
importerebbe il modello di un altro dominio (AD-1), e «posso ancora scriverci?»
smetterebbe di avere una sola risposta il giorno in cui gli stati diventano tre.
Come effetto, `collega_feed` ora rifiuta una Struttura archiviata: collegarle un
Feed la riporterebbe a sincronizzare.

**GS-7: tre schemi nuovi in `SUPERFICI_ESENTI`.** `OspiteInput` e
`PrenotazioneManualeInput` sono input. `PrenotazioneManualeOutput` è la voce che
vale una riga di review: una manuale non deriva da alcun Feed — l'Host l'ha
appena scritta — e mostrarle accanto l'orario dell'ultimo sync di un portale
sarebbe una verità temporale presa in prestito da un'altra sorgente. Il
timestamp per l'intera vista lo porta `CalendarioOutput`, ed è lì che la domanda
ha senso. È la guardia che funziona come progettata: **forza** a classificare
ogni schema nuovo.

**Il default del fixture `crea_prenotazione` passa da `altro` a `manuale`.**
Cambio che tocca i dati prodotti da ogni test preesistente che usa l'helper:
nessuno asserisce sul vecchio default, la suite è verde. La ragione è di
correttezza — l'helper scrive righe senza `feed_id`, e «senza Feed» con Canale
`altro` è una forma che il prodotto non sa produrre.

## Voci aperte, dichiarate invece che taciute

### AC 2 — il Conflitto non è generato qui: è la Story 2.5

**Non coperto, per costruzione.** Su `main` non esiste nessuna entità
`conflitto`, e la rilevazione è la Story 2.5. Quello che la 2.4 fa è rendere la
Prenotazione manuale **indistinguibile da una da Feed** agli occhi di quella
rilevazione: stesso stato `attiva`, stessa struttura dati, stesso percorso di
lettura. `TestPartecipaAllaRilevazione` asserisce esattamente la precondizione —
la manuale e la da Feed sovrapposte tornano nello **stesso** insieme di `attiva`
della Struttura, letto dal percorso di produzione, con intervalli che si
intersecano — e che una manuale cancellata **esce** da quell'insieme.

Il «genera un Conflitto» si realizza quando atterra la 2.5, senza che questa
Story vada riaperta. Nota per la 2.5: la **creazione** non emette alcun evento
di dominio, quindi non c'è oggi un aggancio a cui sottoscriversi per rieseguire
la rilevazione dopo un inserimento manuale.

### AC 8, seconda metà — i Feed di una Struttura archiviata continuano a sincronizzare

**Aperto.** La prima metà è chiusa (nessuna Prenotazione nuova, e nessun Feed
nuovo collegabile). Sui Feed **già collegati** la sincronizzazione continua:
`FeedIcalRepository.dell_host` non filtra sullo stato della Struttura, ed
`esegui_sync` non lo legge.

Non è un'omissione da correggere in due righe, e la ragione è che quello stesso
metodo è il perimetro da cui il Calendario deriva «dati aggiornati alle HH:MM»:
la freschezza aggregata è quella del **Feed più vecchio** dell'Host. Fermare il
Feed di una Struttura archiviata senza togliere quel Feed dal perimetro della
freschezza congelerebbe l'etichetta dell'**intero** calendario su un orario che
non avanza più — la falsa sincronia che NFR-2 vieta, prodotta dal rimedio.

Chiuderlo bene richiede quindi di decidere **se una Struttura archiviata esce
anche dal perimetro di freschezza del calendario** (e se le sue Prenotazioni
passate restano in griglia, e con quale etichetta). Nessun AC lo dice, ed è una
decisione di prodotto: segnalata a John, con `DECISIONE-UMANA: sì`.

### La biconditional «senza Feed ⇔ Canale manuale» non è imposta dal database

Una riga con `canale = 'airbnb'` e `feed_id NULL` resta **rappresentabile**: il
CHECK non nomina il Canale, per il vincolo di transazione di `ADD VALUE`
descritto sopra. In produzione è inarrivabile — l'unico scrittore senza Feed è
`crea_manuale`, che fissa `MANUALE` — e «è una manuale» si decide da
`feed_id IS NULL`, non dal Canale, quindi nessun percorso attuale sbaglia.
Chiuderlo costa una migrazione **separata** (il valore va nominato dopo il
commit di `0013`). Non l'ho fatto: nessun AC lo chiede e non è debito di questa
Story da smaltire di iniziativa. Lo lascio a registro.

## Dev Agent Record

### Cosa è stato scritto

Backend:
- `app/calendario/models.py` — `CanaleFeed.MANUALE`; CHECK
  `ck_prenotazione_feed_e_uid_insieme`
- `app/calendario/schemas.py` — `OspiteInput`, `PrenotazioneManualeInput`,
  `PrenotazioneManualeOutput`; `TestoFacoltativo`/`EmailFacoltativa`
  (normalizzazione della stringa vuota); `FeedIcalInput` rifiuta il Canale
  `manuale`
- `app/calendario/repository.py` — `crea_manuale`, `marca_cancellata`
  (`UPDATE` condizionata allo stato)
- `app/calendario/service.py` — `DatiPrenotazioneManuale`,
  `crea_prenotazione_manuale`, `cancella_prenotazione`,
  `_ospite_da_registrare`, `EVENTO_PRENOTAZIONE_CESSATA`; `collega_feed` legge
  la Struttura **attiva**
- `app/calendario/api.py` — `POST /calendario/prenotazioni`,
  `POST /calendario/prenotazioni/{id}/cancellazione`
- `app/core/events.py` — `prenotazione.cessata` a catalogo, payload di soli
  identificatori
- `app/strutture/service.py` — `leggi_struttura_attiva`,
  `StrutturaArchiviataError`
- `alembic/versions/20260730_0013_prenotazione_manuale.py` — additiva

Frontend:
- `components/FormPrenotazioneManuale.tsx` — l'inserimento; Ospite in una
  sezione facoltativa, nessun campo obbligatorio, nessun default dedotto
- `components/AzioneCancellaPrenotazione.tsx` — conferma esplicita, dice cosa
  succede al dato
- `components/BadgeCanale.tsx`, `components/CalendarioGriglia.tsx`,
  `app/(app)/calendario/page.tsx`, `lib/copy/calendario.ts`
- `lib/api/hooks.ts` — `useCreaPrenotazioneManuale`, `useCancellaPrenotazione`,
  `invalidaCalendario`

### Evidenza dei test (output reale)

Backend — suite completa, PostgreSQL 18 reale:

```
$ HOSTPILOT_TEST_DB_REQUIRED=1 uv run pytest -q
706 passed, 1 warning in 123.48s (0:02:03)
```

I test della Story:

```
$ uv run pytest tests/test_prenotazione_manuale.py tests/test_gara_cancellazione_prenotazione.py -q
48 passed, 1 warning in 4.96s
```

Lint, format, typecheck e schema:

```
$ uv run ruff check .            → All checks passed!
$ uv run ruff format --check .   → 123 files already formatted
$ uv run mypy                    → Success: no issues found in 56 source files
$ uv run alembic upgrade head && uv run alembic check
                                 → No new upgrade operations detected.
```

Frontend:

```
$ npm run lint       → (nessun errore)
$ npm run typecheck  → (nessun errore)
$ npm test
 Test Files  20 passed (20)
      Tests  168 passed (168)
$ npm run build      → build completata, 13 route
```

Contratto API (job `api-contract`):

```
$ uv run python scripts/export_openapi.py && npm run generate:api
$ git diff --exit-code -- backend/openapi.json frontend/lib/api/schema.d.ts
API-CONTRACT: ALIGNED
```

E2E + axe, `chromium` e `mobile`:

```
$ npm run test:e2e
  ok  6 [chromium] › calendario.spec.ts › una mutazione della sorgente muove la griglia e l'etichetta, senza reload
  ok 16 [mobile]   › calendario.spec.ts › una mutazione della sorgente muove la griglia e l'etichetta, senza reload
  20 passed (1.0m)
```

### Prova del rosso

**La gara sulla cancellazione (A3).** Con la condizione sullo stato in un `if`
fuori dalla `UPDATE`, otto contendenti in barriera producono **cinque**
`prenotazione.cessata` invece di uno. Con la condizione dentro l'istruzione, uno.

**L'anello di invalidazione (AC 6 della 2.3).** Togliendo `onSuccess` da uno dei
due hook di mutazione in `lib/api/hooks.ts`:

```
$ # onSuccess rimosso dalla CANCELLAZIONE
  x  1 [chromium] › calendario.spec.ts:381 › una mutazione della sorgente muove
       la griglia e l'etichetta, senza reload (9.5s)
    Error: expect(locator).toBeVisible() failed
    Locator: getByRole('table').getByText('Cancellata')
  1 failed

$ # onSuccess rimosso dalla CREAZIONE
  x  1 [chromium] › calendario.spec.ts:381 › una mutazione della sorgente muove
       la griglia e l'etichetta, senza reload (8.3s)
    Error: expect(locator).toBeVisible() failed
    Locator: getByRole('table').getByText('Ospite Inventato')
  1 failed
```

Ripristinati entrambi, verde in 5.2s. Prima del rimedio la stessa mutazione —
`onSuccess` rimosso da **entrambi** — lasciava il test **verde** in 10.1s: era il
poll da 3s a consegnare l'aggiornamento, non l'invalidazione.

### Note di consegna

Due task consecutivi su questa Story sono morti per `API Error: 529 Overloaded`
prima di poter pushare. Il lavoro del primo **non era perso**: il commit
`a04f77e` esisteva nel workspace locale e non su GitHub. Primo atto di questo
task: pusharlo. La disciplina chiesta da Fahad — ramo su GitHub prima del codice
vero — è ora la prima cosa che faccio.

### Change log

| Data | Cosa | Perché |
| --- | --- | --- |
| 2026-07-30 | `a04f77e` — inserimento manuale, cancellazione come transizione, migrazione `0013`, form e chip | Story 2.4 |
| 2026-07-30 | `77a828c` — l'atto 2 dell'e2e (l'etichetta segue la sorgente); log della creazione sotto NFR-11; 422 sulle date invertite a livello HTTP; `PrenotazioneManualeOutput` sotto la guardia AD-14 | Quattro asserzioni che mancavano, una delle quali lasciava senza testimone la metà P0 dell'AC 6 della Story 2.3 |
| 2026-07-30 | fix-forward P1 — l'intercettazione della freschezza spostata all'inizio del test, con `stato_sync: "riuscito"` che spegne il `refetchInterval` da 3s | Finding di Murat in cross-review della PR #52, riprodotto: il testimone dell'AC 6 restava **verde** cancellando l'invalidazione della cache, perché il poll consegnava l'aggiornamento al posto della mutazione. Ora cade su entrambi gli hook |

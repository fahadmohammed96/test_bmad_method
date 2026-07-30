---
title: 'Story 2.3 — Calendario unificato multi-Struttura (crea l''anagrafica Ospite)'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-07-27
updated: 2026-07-27
review: 'fix epic2-2.3-p2 (E2-F2) applicato — in attesa del terzo verdetto di Murat'
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - docs/epics.md (Story 2.3, AC completi + decisione MYL-40 in testa all'Epic 2)
  - 'docs/qa/test-design-epic-2.md §3 (12 AC tracciati, 5 P0), §2.5 (elenco chiuso e2e), §4.2-12/13, §6 (gate)'
  - 'docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-21, AD-20, AD-18, AD-14, AD-3)'
  - docs/architecture.md §7 (retention dell''anagrafica Ospite)
  - docs/retrospettive/epic-1.md (azioni A4, A8)
issue: 'MYL-52 — Story 2.3'
depends_on: 'Story 2.1 e 2.2 (modulo calendario, sync_run, poller) — su main'
---

# Story 2.3 — Calendario unificato multi-Struttura

## Story
As an Host,
I want vedere in un'unica griglia le Prenotazioni di tutte le mie Strutture e
di tutti i Canali,
So that capisca a colpo d'occhio la mia situazione senza aprire 5-6 schede di
browser.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.3
(12 righe tracciate, di cui 5 P0). Gli AC dell'anagrafica Ospite non hanno una
riga nel test design — quel documento è del 2026-07-25 e la decisione MYL-40 è
del 26 — e il livello lo dichiaro qui.

| # | AC (test design §3) | Livello | Esito | Dove |
| :---: | --- | --- | :---: | --- |
| 1 | Griglia mensile/settimanale che aggrega **tutte** le Strutture e i Canali, distinzione per Canale **testo + icona** | Cmp + E (axe) | ✅ | `components/CalendarioGriglia.tsx` + `BadgeCanale.tsx`; `CalendarioGriglia.test.tsx` (15 test). Entrambe le viste sono MVP — vedi §4.2-13 sotto |
| 2 | Ogni Prenotazione mostra **Canale, Struttura, date e Ospite** | I (API) + Cmp | ✅ | `VoceCalendarioOutput`; `test_calendario_griglia.py::TestCosaMostraOgniPrenotazione` (6 test) e `CalendarioGriglia.test.tsx` |
| 3 | Il selettore Struttura filtra aggregata ↔ singola **senza cambiare schermata** | Cmp | ✅ | `components/SelezioneStruttura.tsx` (context) + `app/(app)/calendario/page.tsx`; `app/__tests__/calendario.test.tsx` (2 test) + e2e |
| 4 | **«dati aggiornati alle HH:MM»** sempre visibile, etichetta persistente | Cmp + **S** (GS-7) + E | ✅ | `CalendarioOutput` classificato superficie da Feed in `test_superfici_feed_convention.py`; `calendario.test.tsx` (5 test) + `e2e/calendario.spec.ts` |
| 5 | I derivati di dominio arrivano dall'API, il frontend li **presenta** | **C** + **S** | ✅ | Job CI `api-contract` (contratto rigenerato) + guardia nuova `lib/calendario/griglia.guardia.test.ts` (16 test): niente accessor di data locale nella griglia, niente orologio sulla superficie, i derivati esistono nel contratto |
| 6 | † **Coerenza fra cache correlate**: una mutazione aggiorna griglia **e** etichetta | **E** (unico testimone) | ⚠️ metà coperta, metà **non esercitabile** | `e2e/calendario.spec.ts` (3 test × 2 progetti). La metà «sync concluso» non è esercitabile qui: vedi «Voci aperte» |
| 7 | † **Tenancy**: mai le Prenotazioni di un altro Host (404/vuoto) | I | ✅ | `test_calendario_griglia.py::TestTenancy` (2 test) + `TestApi::test_la_struttura_di_un_altro_host_e_un_404` e `test_senza_sessione_e_401` |
| 8 | † a11y **axe serious/critical = 0** sulla nuova superficie | **E** (axe) | ✅ | `e2e/calendario.spec.ts`, 5 chiamate a `violazioniGravi` su chromium e mobile. **Ha trovato un difetto vero**: vedi «Difetti trovati dai test» |
| 9 | Layout responsive, densità 1-3 Strutture senza degrado | Cmp | ✅ | `CalendarioGriglia.test.tsx::densità e sovrapposizioni` (3 test) + baseline mobile nell'e2e |
| 10 | † Formati italiani (gg/mm/aaaa) dal modulo `lib/formati.ts` | U + Cmp | ✅ | `formatGiornoIt` in `lib/formati.ts` (4 casi unit, cambio d'ora incluso) usato dalla griglia; asserito in `CalendarioGriglia.test.tsx` |
| 11 | † **Mappatura intervallo → celle**, mese e ora legale inclusi | U | ✅ | `lib/calendario/griglia.ts` (funzioni pure) — `griglia.test.ts`, 28 test |
| 12 | † Trattamento in griglia di `cancellata` / `rimossa_dal_feed` | Cmp | ✅ | Restano visibili con etichetta propria; `CalendarioGriglia.test.tsx::Prenotazioni non più attive` (3 test) + `test_calendario_griglia.py::TestPrenotazioniNonAttive` |

### AC dell'anagrafica Ospite (decisione MYL-40 / AD-21) — livello dichiarato qui

| # | AC (`epics.md`, Story 2.3) | Livello | Esito | Dove |
| :---: | --- | --- | :---: | --- |
| O1 | La Story **crea** `ospite` nel modulo `calendario`, unico scrittore (AD-18) | I + **S** | ✅ | `app/calendario/models.py::Ospite`, migrazione `0010`; scrittura solo da `service.registra_ospite` |
| O2 | `host_id` NOT NULL sotto la guardia strutturale, **non** dato di riferimento | **S** | ✅ | G-3 arruola la tabella da sé; `test_calendario_ospite.py::test_e_tenant_owned_come_le_altre_entita` verifica che non sia finita in nessuna allowlist |
| O3 | `nome`, `email`, `telefono` **tutti nullable**; **nessun** campo documento | **S** | ✅ | `test_calendario_ospite.py::TestLaFormaDellaTabella` (4 test, con sentinella) |
| O4 | Si popola solo da ciò che il Feed dà o l'Host inserisce: **il `sommario` non diventa mai un nome** | I | ✅ | `TestNienteValoriDedotti` (3 test): dopo un sync completo `ospite` è **vuota** e il `sommario` resta sulla Prenotazione |
| O5 | Una Prenotazione **senza Ospite resta valida** → «Ospite non indicato», mai un segnaposto che somigli a un nome; con più Ospiti si mostra il **principale** e il conteggio degli altri | I + Cmp | ✅ | `service._principale` + `TestCosaMostraOgniPrenotazione`; `CalendarioGriglia.test.tsx` (il `sommario` non compare al posto del nome) |
| O6 | I dati dell'Ospite **non** in log, eventi, payload `outbox`/`job`, notifiche | U + I | ✅ | `catalog.register_job(..., payload_keys=())` + `test_retention_ospite.py::test_il_log_non_porta_dati_personali` (asserito sui `record`, non su `caplog.text`) |
| O7 | Accesso al solo Host proprietario; **nessun dato reale di Ospiti** in test | I + ispezione | ✅ | `TestProprietaEAccesso` (3 test); tutti i nomi sono inventati e gli indirizzi `example.com` |
| O8 | **Retention**: parametro di configurazione, mai hardcodato; job durevole **idempotente** che **azzera i campi** lasciando riga, Prenotazione e storia | U + I + **S** | ✅ | `app/calendario/retention.py` (regola pura, 10 test unit) + `jobs.azzera_anagrafiche_scadute` (13 test) + `ospite` in `TABELLE_PROTETTE` di GS-6 |

## Scelte di progetto da segnalare in review

- **`prenotazione.cessata_il` è una colonna nuova, e serve ad AD-21.** La
  decorrenza della retention è «il `check_out`, **o l'uscita dallo stato
  `attiva` se precedente**». La seconda metà non è calcolabile da ciò che
  c'era: `aggiornata_il` avanza a ogni sync anche senza cambio di stato,
  quindi userebbe una data che si muove. Senza la colonna, i contatti di una
  Prenotazione cancellata sei mesi prima dell'arrivo resterebbero fino a sei
  mesi più il periodo — cioè la metà «se precedente» dell'invariante sarebbe
  scritta e non applicata. `cessata_il` si scrive nella transizione a
  `rimossa_dal_feed` e nell'upsert quando il feed dà l'evento cancellato, si
  **conserva** se c'era già (`COALESCE`: riscriverla a ogni sync rimanderebbe
  la scadenza in avanti per sempre) e torna `NULL` se la Prenotazione torna
  `attiva`. Le righe preesistenti restano a `NULL`: per loro decide il
  `check_out`, che è un dato vero — inventare una decorrenza sarebbe peggio
  che non averla.

- **La regola di retention esiste due volte, ed è dichiarato.** Il job non può
  filtrare in Python (leggerebbe l'intera tabella a ogni giro), quindi accanto
  alla funzione pura `scaduta` c'è il predicato SQL `filtro_scadute`. Stanno
  nello stesso file a poche righe di distanza e
  `test_la_regola_e_il_filtro_concordano` le confronta su una tabella di casi
  al confine — cambiare una senza l'altra è rosso subito, non un difetto che
  si scopre novanta giorni dopo su dati che non tornano. `LimiteRetention`
  porta con sé i due valori già convertiti (istante e giorno romano), così la
  conversione di fuso resta in Python dov'è testata.

- **`ultimo_sync_riuscito_il` aggregato è il MINIMO, non il massimo.** Con due
  portali, uno sincronizzato due minuti fa e uno fermo da tre giorni, il
  massimo direbbe all'Host che il calendario è aggiornato a due minuti fa: è
  aritmeticamente vero e falso come affermazione sui dati che sta guardando.
  E diventa `None` appena un Feed del perimetro non ha mai importato: un
  orario che descrive metà dei dati non descrive la vista. I tre conteggi
  (`feed_collegati`, `feed_mai_sincronizzati`, `feed_in_errore`) esistono
  perché «nessun Feed», «un Feed muto» e «un Feed rotto» arrivano altrimenti
  alla superficie con lo stesso aspetto — timestamp assente — e sono
  affermazioni diverse.

- **Griglia ed etichetta sono UNA sola query, non due.** È la risposta di
  disegno al rischio R2-M: due cache distinte sullo stesso derivato possono
  divergere, e l'etichetta ferma su un orario vecchio è la falsa sincronia di
  NFR-2. Con una voce sola di cache la divergenza non è improbabile: è
  impossibile. L'e2e ammesso resta comunque, perché l'invalidazione dalle
  mutazioni di un'altra superficie non è coperta da questa scelta.

- **Con più Ospiti e nessuno indicato non se ne elegge uno d'ufficio.** Il
  primo inserito non è «il principale»: è il primo, e presentarlo come tale
  sarebbe un'identità dedotta — la stessa cosa che l'invariante vieta di fare
  col `sommario`. In quel caso la griglia dice «Ospite non indicato» e mostra
  quanti sono. Un indice UNIQUE **parziale** su `(prenotazione_id) WHERE
  principale` impone dal database che l'Ospite indicato sia al più uno: con
  due righe marcate la griglia sceglierebbe a caso, e la scelta cambierebbe
  fra due letture identiche.

- **Corsie invece di sovrapposizioni disegnate.** Due Prenotazioni che si
  toccano sulla stessa Struttura aprono una riga in più, non si sovrappongono
  graficamente: nasconderne una significherebbe nascondere proprio il fatto
  che il prodotto esiste per far notare (FR-5). Il turnover dello stesso
  giorno — `check_out` di una uguale al `check_in` dell'altra — **non** apre
  una corsia: le notti sono disgiunte (AD-3).

- **A8 non è stata sciolta e non l'ho forzata.** Nessuna libreria di
  componenti introdotta: la griglia usa Tailwind e i token già in
  `globals.css`, come le 2.1/2.2. Il livello presentazionale è separabile —
  periodo, corsie e collocazione stanno tutti in `lib/calendario/griglia.ts`,
  che non conosce React: se la decisione arriva dopo, il costo è riscrivere i
  componenti, non il calendario.

- **Il selettore Struttura ora ha uno stato condiviso.** Viveva in `useState`
  dentro `SelettoreStruttura`, cioè cambiava solo se stesso. Un context
  minimo (`ProviderSelezioneStruttura`) è ciò che rende vero «filtra senza
  cambiare schermata». Non è uno store globale ed è un solo valore — la
  motivazione richiesta dallo spine è questa riga.

## Voci di §4.2 toccate da questa Story

- **§4.2-12 — Prenotazioni non `attiva` nella griglia.** Decisione applicata:
  **restano visibili**, con etichetta propria («Cancellata», «Non più nel
  portale») e tratto attenuato. AD-19 dice che non partecipano ai Conflitti,
  non che spariscono, e farle sparire senza traccia contraddirebbe
  «archiviare, mai distruggere» agli occhi dell'Host, che quella prenotazione
  l'ha vista ieri. La voce resta aperta per John: se la decisione di prodotto
  fosse diversa, cambia il componente, non l'API — lo `stato` viaggia già.

- **§4.2-13 — «mensile/settimanale»: due viste o una scelta.** Applicata:
  **entrambe**. Con il periodo ridotto a una funzione pura da una data di
  riferimento (`periodoDelMese` / `periodoDellaSettimana`), la seconda vista
  costa un parametro invece di una superficie: chiudere l'ambiguità facendole
  entrambe è più economico che sceglierne una al posto di qualcun altro.

- **Non toccato: MYL-47** (retention del `sommario`). L'AC è applicato come
  scritto — `sommario` opaco, mai promosso a nome — e la sua retention non è
  anticipata: il job di AD-21 non lo tocca, e c'è un test che lo pinna.

## Difetti trovati dai test durante la Story

**L'e2e di a11y ha morso davvero (AC 8).** Sul progetto `mobile` axe ha
segnalato `scrollable-region-focusable` con impatto **serious**: il
contenitore `overflow-x-auto` della griglia si scorreva solo col mouse o col
dito. Su schermo stretto un Host che naviga da tastiera vedeva la prima metà
del mese e non aveva modo di arrivare alla seconda. Chiuso con `role="region"`
+ `tabIndex={0}` + `aria-label` (UX-DR10, NFR-8). È esattamente la classe che
il test design assegna a `E`: axe misura l'albero accessibile **renderizzato**,
e nessun livello sotto lo vede.

**Una clausola che sembrava giusta era un difetto (trovato per mutazione).**
La selezione del job di retention aveva `anonimizzato_il IS NULL`, che sembra
la condizione naturale per «non rifarlo due volte». Provando a rimuoverla,
**nessun test è diventato rosso**: dopo l'azzeramento i tre campi sono `NULL`,
quindi l'idempotenza viene dall'altro filtro. La clausola non era ridondante e
basta — era dannosa: dalla Story 2.4 l'Host può reinserire un contatto su
un'anagrafica già azzerata, e con quel filtro **quel dato non sarebbe scaduto
mai più**. Rimossa, e coperta da
`test_un_contatto_reinserito_DOPO_l_azzeramento_scade_di_nuovo`. La domanda
giusta è «c'è qualcosa da azzerare?», non «l'ho già fatto una volta?».

## Voci aperte, dichiarate invece che taciute

- **AC 6, metà «sync concluso» — non esercitabile in questo ambiente.**
  L'e2e ammesso copre la coerenza fra griglia ed etichetta su: (a) una
  mutazione avvenuta su un'altra superficie con navigazione lato client
  (collegamento di un Feed), (b) il cambio del selettore Struttura, che
  muove insieme perimetro dei dati e perimetro della freschezza. La metà
  «sync concluso» **non è raggiungibile qui**: il `webServer` di Playwright
  avvia l'API ma non il worker, e la politica di uscita di rete rifiuta il
  loopback (NFR-17), quindi nessun import può concludersi. La prima
  Prenotazione scrivibile dall'Host arriva con la 2.4. Lo dichiaro invece di
  farlo passare per coperto: il completamento naturale è la 2.4, quando esiste
  una mutazione che produce dati.

  **Chiuso dalla Story 2.4** (`docs/stories/story-2.4-inserimento-manuale-prenotazioni.md`,
  sezione «I due residui QA della Story 2.3»): l'e2e esercita una mutazione
  reale della sorgente e asserisce che l'etichetta porta il valore **nuovo**,
  con prova del rosso. Resta fuori portata soltanto un import che si conclude
  davvero — nessun worker, e il loopback rifiutato da NFR-17: è l'ambiente, non
  il perimetro di una Story, e non si chiude aspettando la prossima.

- **E2-G8 (residuo di GS-7 fuori dal modulo `calendario`)** resta **aperto**.
  Questa Story aggiunge una superficie da Feed **dentro** `app/calendario/
  schemas.py`, quindi GS-7 la arruola da sé e la classificazione è stata
  aggiornata; ma la guardia continua a non vedere una superficie scritta in un
  altro modulo, che è il caso per cui E2-G8 esiste. Il primo modulo che
  mostrerà dati da Feed fuori da `calendario` è la Dashboard (2.8).

- **Il conteggio «altri Ospiti» non ha ancora un percorso di scrittura via
  API.** L'anagrafica si scrive solo dal service, che è la porta corretta
  (AD-18); l'endpoint arriva con la 2.4, che è la Story in cui l'Host scrive
  per la prima volta un Ospite. La tabella non nasce senza scrittore — nasce
  con lo scrittore di modulo e senza quello di rete.

  **Aperto ancora dopo la 2.4**, ristretto: `POST /calendario/prenotazioni`
  scrive **un** Ospite, quello che l'Host indica, marcato `principale`. Il
  conteggio «altri Ospiti» resta senza percorso di scrittura via API.

## Dev Agent Record

### Cosa è stato scritto

**Backend**

- `app/calendario/models.py` — `Ospite` (anagrafica AD-21, indice UNIQUE
  parziale sul principale) e `Prenotazione.cessata_il`.
- `app/calendario/retention.py` — **nuovo**: `limite_retention`, `scaduta`,
  `filtro_scadute`. Regola pura + la sua traduzione SQL, accanto.
- `app/calendario/jobs.py` — `ospite.azzera_scaduti` a catalogo con payload
  vuoto, handler idempotente, bootstrap del ciclo.
- `app/calendario/repository.py` — `OspiteRepository`,
  `PrenotazioneRepository.nel_periodo` / `by_id`,
  `FeedIcalRepository.dell_host`, `cessata_il` nell'upsert e nella
  transizione.
- `app/calendario/service.py` — `registra_ospite`,
  `ospiti_della_prenotazione`, `calendario`, `_stato_aggregato`.
- `app/calendario/schemas.py` + `api.py` — `GET /api/v1/calendario`.
- `app/core/config.py`, `.env.example` — `ospite_retention_giorni` (90,
  **provvisorio** in attesa di R-5) e `ospite_retention_intervallo_minuti`.
- `alembic/versions/20260727_0010_anagrafica_ospite.py`.

**Frontend**

- `lib/calendario/griglia.ts` — **nuovo**, funzioni pure (periodo, corsie,
  collocazione, segmenti).
- `lib/calendario/oggi.ts` — **nuovo**, l'unico punto che legge l'orologio.
- `lib/formati.ts` — `formatGiornoIt`.
- `components/CalendarioGriglia.tsx`, `components/BadgeCanale.tsx`,
  `components/SelezioneStruttura.tsx` — **nuovi**.
- `app/(app)/calendario/page.tsx` — dalla pagina segnaposto alla griglia.
- `lib/api/hooks.ts` — `useCalendario`; invalidazione di `["calendario"]`
  dalle mutazioni su Strutture e Feed.

### Evidenza dei test (output reale)

Backend — `uv run pytest -q` con `HOSTPILOT_TEST_DB_REQUIRED=1`:

```
586 passed, 1 warning in 113.58s (0:01:53)
```

(erano **522** su `main`: **+64**, di cui 23 `test_retention_ospite.py`,
14 `test_calendario_ospite.py`, 26 `test_calendario_griglia.py`, più una riga
nelle due guardie estese.)

`uv run ruff check .` → `All checks passed!` · `uv run mypy` →
`Success: no issues found in 54 source files` · `uv run alembic check` →
`No new upgrade operations detected.`

Frontend — `npm test`:

```
 Test Files  18 passed (18)
      Tests  121 passed (121)
```

(erano **48**: **+73**, di cui 28 `griglia.test.ts`, 16
`griglia.guardia.test.ts`, 15 `CalendarioGriglia.test.tsx`, 13
`app/__tests__/calendario.test.tsx`, 1 `formati.test.ts`.)

`npm run typecheck`, `npm run lint`, `npm run build` → puliti.

E2E — `npx playwright test` (chromium **e** mobile, backend reale):

```
  ok  3 [chromium] › e2e\calendario.spec.ts:57:5 › la griglia e l'etichetta del timestamp si muovono insieme (2.6s)
  ok  4 [chromium] › e2e\calendario.spec.ts:110:5 › il selettore Struttura filtra griglia ed etichetta senza cambiare schermata (2.7s)
  ok  5 [chromium] › e2e\calendario.spec.ts:140:5 › la vista settimanale e la navigazione fra periodi restano accessibili (2.9s)
  ...
  16 passed (54.2s)
```

### Prova del rosso

I test di regola pura e di API sono stati visti rossi durante la scrittura.
Per le proprietà che un test funzionale può affermare senza dimostrare, la
prova è la **mutazione**:

| Proprietà | Mutazione | Esito |
| --- | --- | --- |
| Freschezza aggregata = il Feed più vecchio | `min(orari)` → `max(orari)` | `test_l_orario_mostrato_e_quello_del_feed_PIU_VECCHIO` rosso |
| Intervallo semiaperto nel perimetro del periodo | `check_out > da` → `>= da` | `test_una_prenotazione_che_finisce_il_primo_giorno_visibile_e_fuori` rosso |
| Idempotenza del job di retention | rimossa `anonimizzato_il IS NULL` | **verde** → la clausola non era necessaria **ed era dannosa**: rimossa e sostituita da un test sul caso che rompeva (vedi «Difetti trovati») |
| Guardia sugli accessor di data locale | sorgente finto con `.getDate()` | sentinella rossa |
| Guardia sui campi documento in `ospite` | nomi finti (`numero_documento`, …) | sentinella rossa |

## Fix-batch `epic2-2.3-p1` — i cinque P1 della cross-review

Cross-review di Murat sulla PR #42: **BOCCIA**, cinque P1 dispacciati come
un solo batch a scope rigido. I P2 (E2-F6…E2-F18) restano fuori: vanno a
Fahad. Ogni fix porta il nome del test che lo pinna.

| ID | Fix | Test di regressione |
| :--- | --- | --- |
| **E2-F1** | La retention non si spegne più da sola: l'errore si registra invece di sollevarsi, e la riprogrammazione avviene **sempre**. Più `Field(gt=0)` sui due parametri | `TestIlCicloNonSiSpegneDaSolo` (5 test) e `TestIParametriDiConfigurazione` (4) |
| **E2-F2** | `queryClient.clear()` al logout: la cache non sopravvive all'uscita | `uscita-e-cache.test.tsx::E2-F2` (2 test) |
| **E2-F3** | `ProviderSelezioneStruttura` spostato dal root layout a `(app)/layout.tsx`: uscire smonta il provider | `uscita-e-cache.test.tsx::E2-F3` (2 test) |
| **E2-F4** | L'attenuazione di una Prenotazione non attiva sta su bordo e sfondo, **mai sul testo**; e la baseline axe adesso vede i chip | `CalendarioGriglia.test.tsx::l'attenuazione NON passa dall'opacità sul testo` + `e2e/calendario.spec.ts::la griglia CON Prenotazioni non ha violazioni a11y gravi` |
| **E2-F5** | Il divieto di accessor locali si applica a tutta la superficie, non al solo modulo delle date | `griglia.guardia.test.ts` (26 test, sentinelle sulla funzione) |

### Deviazione dichiarata sul rimedio di E2-F1

Il finding è esatto e il modo di guasto è quello descritto. **Il rimedio
proposto — `try/finally` attorno al corpo — non lo chiude**, e la ragione sta
nel kernel: l'handler gira dentro `session.begin_nested()` (SAVEPOINT per
item, G-1), quindi una riprogrammazione scritta in un `finally` viene
annullata dal rollback del savepoint insieme all'eccezione che l'ha
provocata. In più, se a fallire è la `UPDATE` stessa, la transazione resta
abortita e l'`INSERT` della riprogrammazione fallisce a sua volta — il
rimedio morirebbe dello stesso errore da cui deve proteggere.

Implementato invece un savepoint **interno** attorno alla sola `UPDATE`, con
l'errore registrato e non sollevato: è la stessa forma per cui il poller
regge (`esegui_sync` registra gli errori di rete invece di sollevarli).

**Verificato, non argomentato.** Applicando la variante `try/finally`
letterale, tutti e cinque i test della classe diventano rossi — compreso
`test_il_worker_non_manda_il_job_a_failed_per_un_guasto_dell_azzeramento`,
che passa dal percorso reale (`run_due_jobs`) e non dall'handler chiamato a
mano.

### La coppia E2-F4, e perché era la più importante

L'osservazione dietro il finding vale più del finding: *l'a11y ha morso su
una superficie senza dati, quindi ha dimostrato di funzionare proprio dove
non poteva trovare granché*. La limitazione dell'ambiente e2e era dichiarata
per l'AC 6 e non per l'AC 8, e quella conseguenza mancava.

Chiuso su due livelli, perché nessuno dei due basta da solo:

- **componente** — jsdom non calcola il contrasto, quindi axe lì non lo
  vedrebbe: la proprietà verificabile è che l'attenuazione non passi
  dall'opacità sul contenitore del testo, e c'è un test che la nomina;
- **e2e** — un test dedicato **intercetta la risposta dell'API** e fa
  renderizzare i chip in un browser vero con il CSS vero. Le Prenotazioni non
  si possono creare (nessun worker), ma il DOM e i colori sì. Le voci si
  costruiscono dal `da` realmente richiesto: fissarle su un mese scelto a
  mano le farebbe cadere fuori dal periodo aperto e il test resterebbe verde
  misurando di nuovo una griglia vuota.

**Rosso visto, con il numero esatto:** con `opacity-70` rimesso, axe riporta
`color-contrast` `serious`, *«insufficient color contrast of 2.67 …
Expected contrast ratio of 4.5:1»* — il valore che la review aveva calcolato
a mano (2.66).

### AC 8: la voce aperta che mancava

Accolta l'aggiunta chiesta in review. La baseline axe dell'AC 8 ora audita
anche il contenuto della griglia, ma su un payload **intercettato**: ciò che
resta non esercitato end-to-end è la catena API → griglia con dati veri, per
la stessa ragione dell'AC 6 (nessun worker, loopback rifiutato da NFR-17).
Si chiude con la Story 2.4, quando esiste una scrittura che produce
Prenotazioni.

## Fix `epic2-2.3-p2` — E2-F2, la strada della scadenza

Secondo verdetto di Murat: quattro P1 chiusi, **E2-F2 chiusa a metà**. Il
finding era stato scritto — e quindi chiuso — sul solo `useLogout`. Ma il
logout non è l'unico modo in cui una sessione finisce, e su tutti gli altri
nessun `onSuccess` parte.

**Lo scenario che restava aperto, e non richiede nessun logout:** la sessione
di Host A muore da sé (cookie scaduto, `purge_sessioni_scadute`, riavvio del
backend — oppure un «Esci» la cui risposta si perde *dopo* che il server
l'ha processata). `useMe` prende un 401, la shell fa `router.replace`, che è
navigazione lato client: **la cache resta intatta**. Host B accede nella
stessa scheda, `useLogin` scriveva solo `["me"]`, e al primo paint di
`/calendario` la chiave è byte-identica → TanStack serve le Prenotazioni di
A, `ospite_principale` compreso. NFR-14, dati personali di terzi.

**Il presidio si sposta dalle uscite all'ingresso.** I modi di finire una
sessione non sono enumerabili; le porte per entrare sono due. `entra`
(`lib/api/hooks.ts`) svuota e **poi** scrive, ed è l'unico punto che
`useLogin` e `useRegistrazione` attraversano — stessa scelta di E2-F3: vero
per costruzione invece che «ricordarsi di azzerare».

`useLogout` continua a svuotare: quando la strada del bottone c'è, non ha
senso tenere dati personali in memoria un istante più del necessario. Ma il
commento che dichiarava di chiudere il buco «per intero» è stato corretto:
era più forte del codice, ed è la cosa che la review ha ripreso.

| Test | Cosa pinna |
| :--- | --- |
| `useLogin \| useRegistrazione non lascia entrare l'Host nuovo sui dati del precedente` | Le due porte, con la cache di A popolata e `["me"]` già a `null` per il 401 |
| `la garanzia non passa dal logout: quella strada non viene percorsa` | Asserisce che `/api/v1/auth/logout` **non** compare fra le chiamate: se qualcuno «richiudesse» il buco di nuovo sull'uscita, gli altri test cadrebbero e questo no |
| `lo svuotamento precede la scrittura di `me`, non la annulla` | L'ordine — l'unico modo di sbagliare questo rimedio |

**Rosso visto, due mutazioni:**

- `clear()` rimosso dall'ingresso (il difetto originale): `3 failed | 5 passed`.
- ordine invertito, `clear()` dopo la scrittura: `4 failed | 4 passed` — cade
  anche `["me"]`, cioè la shell resterebbe su «Caricamento…».

E2-F19…E2-F22 **non toccati**: sono a registro e vanno a Fahad con gli altri
P2, come chiesto.

### Change log

- 2026-07-27 — Story creata, implementata test-first e consegnata in PR
  (branch `story/2.3-calendario-unificato`, base `main`). Prima superficie
  complessa del prodotto e prima tabella con dati personali di terzi:
  `ospite` entra in `TABELLE_PROTETTE` di GS-6 e la sua retention è un
  parametro, non una costante. A8 non forzata: nessuna libreria di componenti
  introdotta.
- 2026-07-27 — Cross-review di Murat sulla PR #42: **BOCCIA**, cinque P1.
  Fix-batch `epic2-2.3-p1` sullo stesso branch: ciclo di retention che non si
  spegne (con savepoint interno, non `try/finally`), cache e selezione
  Struttura che non sopravvivono al logout, attenuazione che non passa
  dall'opacità sul testo, baseline axe estesa ai chip, guardia AD-14 puntata
  su tutta la superficie. Rosso visto su tutti e cinque. Backend
  586 → **595** test, frontend 121 → **136**, e2e 16 → **18**.
- 2026-07-27 — Secondo verdetto di Murat: quattro P1 chiusi, E2-F2 chiusa a
  metà. Fix `epic2-2.3-p2`, una voce sola: il presidio della cache si sposta
  dalle uscite all'**ingresso** (`entra`, attraversato da `useLogin` e
  `useRegistrazione`), così la sessione può finire in qualunque modo senza
  lasciare dati dell'Host precedente alla portata del successivo. Test dalla
  strada della **scadenza**, non del bottone. Frontend 136 → **140**.

---
title: 'Story 2.5 — Rilevazione dei Conflitti'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-08-12
updated: 2026-08-12
review: 'verdetto BOCCIA del 12/08 — batch F1, F2, F3 + F5 applicato fix-forward sulla stessa PR #62, in attesa del secondo verdetto'
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - 'docs/epics.md (Story 2.5) + i quattro AC che arrivano con la PR #60 (MYL-69, §4.2-4/5/6), scritti per intero nell''issue MYL-83'
  - 'docs/qa/test-design-epic-2.md §3 Story 2.5 (12 AC tracciati, 9 P0), §2.4 (gara A3-4), §2.5 (elenco chiuso e2e), §4.2-4/5/6'
  - 'docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-1, AD-2, AD-3, AD-5, AD-10, AD-14, AD-16, AD-17, AD-18, AD-19, AD-20, AD-21)'
issue: 'MYL-83 — Story 2.5'
depends_on: 'Story 2.4 (Prenotazioni manuali, `prenotazione.cessata`) — su main'
---

# Story 2.5 — Rilevazione dei Conflitti

## Story
As an Host,
I want che il sistema rilevi automaticamente ogni sovrapposizione di date sulla
stessa Struttura,
So that nessuna doppia prenotazione mi sfugga.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.5 (12 righe
tracciate, 9 P0). I percorsi dei test sono relativi a `backend/`.

| # | AC (test design) | Livello | Esito | Dove |
| :---: | --- | :---: | :---: | --- |
| 1 | La rilevazione è una **funzione pura** dell'insieme `attiva`, rieseguita dopo ogni import e ogni inserimento manuale | U | ✅ | `tests/test_conflitti_rilevazione.py` (21 test, 0,09 s, **nessun import di `Session`/`Engine`/modello**). I **due** inneschi hanno ciascuno il suo test: manuale → `::test_due_manuali_sovrapposte_aprono_un_conflitto`; **import** → `::test_e_l_IMPORT_a_rilevare_quando_arriva_la_seconda` (aggiunto col batch, F2) |
| 2 | ⚡ Due sovrapposte ⇒ **esattamente un** Conflitto `rilevato`, identità stabile, mai due aperti per la stessa coppia | U + I (**gara A3-4**) | ✅ | `TestAperturaDelConflitto::test_due_manuali_sovrapposte_aprono_un_conflitto`, `::test_rieseguire_la_rilevazione_non_apre_un_secondo_conflitto`, `tests/test_calendario_gara_conflitti.py` (8 contendenti) |
| 3 | † Coppia **canonicalizzata**, vincolo UNIQUE **parziale nel DB** | U + I | ✅ | U: `TestIdentitaDellaCoppia` (3 test); I: `TestIdentitaImpostaDalDatabase` (3 test) — il secondo prova che la coppia scambiata **non è rappresentabile** (CHECK), che è ciò che rende efficace l'indice |
| 4 | † Sovrapposizione = intersezione non vuota di intervalli **semiaperti**; il turnover dello stesso giorno **non** è un Conflitto | U | ✅ | `TestConfineDellIntervalloSemiaperto` — 10 casi al confine × 2 ordini + turnover + notte singola; sul percorso reale `TestAperturaDelConflitto::test_il_turnover_dello_stesso_giorno_non_apre_niente` |
| 5 | Il Conflitto **espone fonte e timestamp di sincronizzazione** di ciascuna Prenotazione, derivati alla lettura (AC riformulato il 12/08 con MYL-90) | I | ✅ (**derivato alla lettura**, vedi «Scelte di progetto» 1) | `TestFonteEtimestamp` (3 test), `TestApiDeiConflitti::test_i_conflitti_dell_host_con_i_due_lati` |
| 6 | Una Prenotazione che esce da `attiva` porta il Conflitto a **`decaduto`** — transizione tracciata, distinta da `gestito`, mai una cancellazione | I + **S** (GS-6) | ✅ | `tests/test_conflitti_decadimento.py::TestLeTreStradeArrivanoAlloStessoEsito` (3 test, una per strada), `TestLeDueMetaDellaCoppia` (F3: la Prenotazione che esce è il **`max`**), `TestEventoInRitardo` (F1: **e solo se è fuori da `attiva` adesso**), `TestTracciaturaEmisura`; GS-6 **irrigidita**: `conflitto` è ora in `TABELLE_PROTETTE` |
| 7 | `decaduto` alimenta SM-C1 ed è distinguibile da `gestito` **negli eventi di dominio** | I | ✅ | `TestTracciaturaEmisura::test_il_decadimento_e_interrogabile_dagli_eventi_di_dominio` — due tipi distinti a catalogo, payload di soli identificatori |
| 8 | Un Conflitto `rilevato` resta **in evidenza** finché non è gestito, senza auto-nascondimento a tempo | I (API) + E (2.8) | ✅ per la parte API + guardia strutturale; **E è della 2.8** | `tests/test_conflitti_niente_auto_chiusura.py` (11 test: 4 sentinelle della guardia, 3 anzianità, comportamento) |
| 9 | † Tre sovrapposte a due a due ⇒ **tre** Conflitti | U | ✅ | `TestUnitaDiRilevazione` (2 test: mutue e catena), I: `::test_tre_sovrapposte_a_due_a_due_aprono_tre_conflitti` |
| 10 | † Rilevazione **scopata alla Struttura** | U + I | ✅ | U: `TestPerimetroDellaStruttura` (2 test); I: `::test_prenotazioni_di_strutture_diverse_non_si_incontrano_mai` |
| 11 | † Un import **fallito o parziale** non produce falsi `decaduto` | I | ✅ | `TestImportFallito::test_un_import_fallito_non_spegne_un_conflitto` — e per costruzione: la rilevazione **non chiude niente** (vedi «Scelte di progetto» 3) |
| 12 | † `decaduto` e gli stati Prenotazione **registrati nel Glossario** (readiness R-2) | ispezione | ⏸️ **non mio**: owner John | Dichiarato, non taciuto — il test design lo elenca fra i due soli AC coperti per ispezione |

### AC di `epics.md` deliberatamente **non** implementati qui

- **«L'Host riceve una notifica alla prima sincronizzazione in cui il Conflitto
  emerge»** (FR-5). Il modulo `notifiche` **non esiste**: è la Story 2.6. Il test
  design lo dichiara scoperto fino ad allora, e lo dichiaro anch'io invece di
  darlo per buono. Ciò che questa Story lascia pronto è il **fatto** su cui la
  2.6 si aggancerà: `conflitto.rilevato`, emesso una volta sola per coppia
  (provato dalla gara A3-4, che conta gli eventi e non solo le righe).
- **`rilevato → gestito`, la Finestra di riconciliazione e la riapertura oltre
  la finestra** sono la Story 2.7. Qui non c'è nessun percorso che scriva
  `gestito` — ed è imposto, non promesso: `tests/test_conflitti_niente_auto_chiusura.py`.
- **Badge e conteggio in Dashboard** sono la 2.8. Di quell'AC questa Story fa la
  parte API (`GET /api/v1/conflitti`) e l'invariante di **assenza di
  comportamento**.

## Scelte di progetto da segnalare in review

### 1. Fonte e timestamp sono DERIVATI alla lettura, non copiati sul Conflitto

L'AC dice «il Conflitto **registra** fonte e timestamp di sincronizzazione di
ciascuna Prenotazione coinvolta», e la lettura letterale sarebbe due colonne
sulla riga `conflitto`, scritte al momento della rilevazione. Non l'ho fatto, e
la ragione non è economia di codice: **un timestamp copiato è una fotografia che
invecchia.** Un Conflitto resta aperto per giorni; le due colonne continuerebbero
a dichiarare la freschezza dell'istante in cui è stato rilevato, mentre l'Host le
guarda oggi per decidere quale prenotazione tenere. È la falsa sincronia di
NFR-2 nel punto in cui costa di più, ed è la stessa ragione per cui questo
progetto non ha una colonna «ultimo sync riuscito» sul Feed ma la deriva dalla
traccia append-only dei `sync_run`.

Il dato che l'AC chiede c'è, ed è quello vero: `service.conflitti_rilevati`
ritorna per ciascun lato `canale`, `aggiornata_il` e `sincronizzata`. **Se questa
lettura non regge, si corregge una riga di documento adesso, non del codice
dopo** — ma il test dell'AC 5 non cambierebbe di una virgola, perché asserisce il
valore mostrato, non dove è memorizzato.

> **Ratificato il 2026-08-12 (MYL-90): opzione A — l'implementazione resta, il
> documento è stato corretto.** Fahad ha ratificato la raccomandazione, che
> Amelia e Murat avevano dato in modo indipendente. La parola «registra»
> dell'AC è stata sostituita in `docs/epics.md` §Story 2.5, e con essa i due
> riassunti che la ricopiavano (`docs/prd.md` FR-5, `docs/architecture.md`
> §3.2) più la riga 5 del test design: fonte e timestamp sono **derivati alla
> lettura** e sempre correnti. Immutata la ratifica §4.2-6 (Prenotazione
> manuale: fonte «Manuale», timestamp = data di inserimento, con etichetta che
> dichiara che non è un dato sincronizzato). Il terzo caso deciso qui — Feed
> mai sincronizzato con successo, timestamp assente — è ora **registrato**
> nell'AC come comportamento consegnato; la sua resa in UI resta il punto
> aperto §4.2-3, di Fahad.

### 2. §4.2-6: la falsa simmetria si evita con un flag, non con un'etichetta

Una Prenotazione manuale un sync non ce l'ha: `canale = manuale`,
`aggiornata_il` = data di **inserimento**, `sincronizzata = false`. Il testo
(«sincronizzato alle 14:32» / «inserita a mano il …») è del client, perché il
copy italiano è già centralizzato lì e AD-14 vuole che il server dia il
**derivato**, non la frase. Il flag è il derivato: senza, le due colonne
affiancate della Finestra di riconciliazione mostrerebbero due orari dall'aria
identica che significano cose diverse.

Terzo caso, che l'AC non nomina e che ho dovuto decidere: una Prenotazione da un
Feed **mai sincronizzato con successo**. `aggiornata_il` è `None` —
«non lo so» — invece di un orario preso in prestito da qualche altra parte.

### 3. La rilevazione APRE e basta: il decadimento ha una sola causa

`rivaluta_conflitti` non chiude nulla. Il decadimento è governato **solo**
dall'uscita di una Prenotazione dallo stato `attiva`, che arriva come evento.
Non è un'omissione: è ciò che rende vero l'AC 11 **per costruzione**. Se la
rilevazione facesse decadere i Conflitti «non più visti», qualunque futura
regressione sull'insieme letto — non solo l'import fallito, che oggi esce molto
prima — trasformerebbe un errore di trasporto in una doppia prenotazione non
segnalata, con esito riuscito e quindi in silenzio.

Il costo di questa scelta è dichiarato sotto, in «Voci aperte»: una
sovrapposizione che cessa **senza** che nessuna delle due Prenotazioni esca da
`attiva` (il portale sposta le date) oggi non fa decadere niente.

**E la simmetrica, chiusa col batch (F1).** Il decadimento non si fida
dell'evento: la `UPDATE` chiede anche che la Prenotazione sia fuori da `attiva`
**adesso**. La consegna è asincrona e il percorso di ritorno esiste — una
`cancellata` che il portale ritira torna `attiva`, perché la clausola che
blocca il ritorno nell'upsert protegge solo `rimossa_dal_feed` — quindi un
evento in ritardo racconta un fatto che era vero quando è stato scritto e non
lo è più quando lo si consuma. Non è idempotenza: è **staleness**, e sono due
proprietà diverse che si difendono in due punti diversi della stessa `WHERE`.

### 4. Il vincolo di identità è due cose, e separarle lo annullerebbe

L'indice UNIQUE parziale su `(struttura_id, prenotazione_min_id,
prenotazione_max_id) WHERE stato = 'rilevato'` è quello prescritto da A3-4. Da
solo **non basta**: con le due colonne libere di essere scambiate, `(A,B)` e
`(B,A)` sono righe diverse per l'indice e il vincolo non morde — cioè
l'invariante è violabile senza violare la lettera dell'AC (§4.2-4). Perciò
accanto c'è un `CHECK (prenotazione_min_id < prenotazione_max_id)`: la
canonicalizzazione non è rispettata dal codice che oggi scrive, è
**irrappresentabile** altrimenti.

### 5. L'apertura è UNA istruzione, e ne fa due cose

`INSERT … SELECT … WHERE NOT EXISTS (… stato = 'gestito') ON CONFLICT … DO
NOTHING RETURNING id`. Il `DO NOTHING` impone l'invariante di AD-5 sotto
concorrenza; il `WHERE NOT EXISTS` impedisce alla rilevazione di **riaprire da
sé** un Conflitto che l'Host ha già gestito. Oggi il secondo è irraggiungibile —
nessun percorso scrive `gestito` — ma senza di esso la 2.7 troverebbe la propria
regola («riapri solo oltre la finestra configurabile, collegato al precedente»)
già scavalcata dal primo sync successivo.

### 6. La rilevazione dopo un inserimento manuale è una chiamata diretta

Non un evento nuovo. Entrambi i percorsi di scrittura vivono dentro `calendario`,
che ne è l'unico scrittore (AD-18). L'asimmetria con il punto 7 è deliberata: le
**uscite** passano per l'evento perché sono tre e una avviene in un worker di
sfondo; l'**ingresso** è un percorso solo, nello stesso modulo. Quello che non
esiste è una seconda funzione di rilevazione: `rivaluta_conflitti` è chiamata da
`esegui_sync` e da `crea_prenotazione_manuale`, e non ce n'è un'altra.

### 7. MYL-69 opzione A: tre strade, un evento, e come si riconosce la transizione

| strada | dove | come si riconosce che è appena uscita da `attiva` |
| --- | --- | --- |
| cancellazione manuale | `service.cancella_prenotazione` | `rowcount` della `UPDATE … WHERE stato = 'attiva'` (già così dalla 2.4) |
| scompare dal feed | `repository.marca_rimosse_dal_feed` | `RETURNING id, struttura_id` sulla `UPDATE` di massa: serve sapere **quali** righe, non quante |
| `STATUS:CANCELLED` | percorso di upsert | `cessata_il == adesso` nel `RETURNING` |

La terza merita una riga in più. In un `ON CONFLICT DO UPDATE` il `RETURNING` di
Postgres vede la riga **nuova**, mai quella vecchia: «è `cancellata`» si legge,
«**era** `attiva` e ora è `cancellata`» no — e la prima è vera anche al decimo
sync consecutivo su una prenotazione annullata da settimane. L'informazione
mancante era però già scritta lì accanto: `_cessata_il_dopo_upsert` conserva con
un `COALESCE` la decorrenza di una riga già cessata (serve alla retention di
AD-21), quindi `cessata_il` torna uguale ad `adesso` **solo** se è questa
esecuzione ad aver fatto la transizione. Stesso dato, domanda gemella.

**Residuo dichiarato.** L'inferenza ha un buco storico: una riga già `cancellata`
con `cessata_il` a `NULL` — possibile solo per le righe scritte **prima** della
migrazione 0010, che ha aggiunto la colonna lasciandole a `NULL` — riemetterebbe
l'evento una volta. La conseguenza è nulla: l'handler è idempotente, il secondo
decadimento tocca zero righe e non emette niente. Lo scrivo perché è l'unico caso
in cui la regola «una volta sola» non è imposta ma dedotta.

### 8. Due eventi di Conflitto a catalogo, e non uno

`conflitto.rilevato` e `conflitto.decaduto`, payload `(conflitto_id, host_id,
struttura_id)`. AD-16 vuole che le metriche si misurino dagli **eventi di
dominio** senza strumentazione separata, e SM-C1 distingue i Conflitti che l'Host
ha davvero risolto da quelli che si sono spenti da soli. Con un solo evento
«conflitto cambiato» quella distinzione andrebbe cercata rileggendo lo stato
corrente, che al momento della misura è già l'ultimo e non dice come ci si è
arrivati.

### 9. `PrenotazioneRepository.della_struttura` (E2-F23) è stato **adottato**, non rimosso

La 2.5 aveva bisogno esattamente di quell'insieme, in una forma leggermente
diversa: solo le `attiva`, con ordine stabile. Il metodo è diventato
`attive_della_struttura`, è chiamato dal percorso di produzione ed è coperto. I
10 mutanti `no tests` dello spike MYL-72 erano i suoi.

## Voci aperte, dichiarate invece che taciute

### A — La sovrapposizione che cessa senza che nessuno esca da `attiva`

**Per John, in linguaggio non tecnico.** Oggi l'avviso di doppia prenotazione si
spegne quando una delle due prenotazioni sparisce, viene annullata o cancellata.
Non si spegne se il portale **sposta le date** di una delle due in modo che non
si accavallino più: entrambe restano valide, quindi per il sistema l'avviso è
ancora aperto. L'Host lo vedrebbe acceso su due prenotazioni che ormai
convivono, e non avrebbe modo di chiuderlo finché la 2.7 non gli darà il
bottone.

Non l'ho implementato perché **gli AC dicono un'altra cosa**: sia `epics.md`
(«se una delle due Prenotazioni esce da `attiva`») sia AD-5 («quando la
sovrapposizione cessa — *una Prenotazione esce dallo stato `attiva`*») definiscono
il decadimento **esattamente** come l'uscita da `attiva`. Aggiungere «e anche
quando le date non si toccano più» è un cambiamento di regola, non un
completamento: aprirebbe la porta a una rilevazione che **chiude** Conflitti, che
è la forma di difetto contro cui è scritto l'AC 11. Ha la stessa forma delle voci
di §4.2: un confine non esplorato, non un errore di scrittura. **Decidilo tu:**
se vale, apri l'issue e la implemento con il suo test di non-regressione su AC 11.

### B — §4.2-7 (riapertura dopo `gestito` per due manuali) resta aperta

Non la tocco: è materia della 2.7. Ho però lasciato il posto pronto — la
rilevazione non riapre un Conflitto `gestito` (punto 5), quindi la 2.7 può
scegliere la sua regola senza trovarla già scavalcata.

### C — L'e2e non si allarga

L'elenco chiuso di §2.5 non ammette un e2e per la rilevazione dei Conflitti
(«qualunque asserzione di regola di dominio già coperta al livello sotto»), e la
superficie che li mostrerà è della 2.7/2.8. Nessuno spec nuovo, nessuna
estensione dei baseline: non c'è ancora niente da guardare nel browser.

### D — I P2 del verdetto, non nel batch

Murat li ha esclusi dal batch e non li ho toccati: la decisione è di Fahad.
Li registro qui perché non si perdano fra un commento e l'altro.

- **F4 — il decadimento cancella la memoria del `gestito`.** Portando a
  `decaduto` anche un Conflitto `gestito`, la guardia anti-riapertura di `apri`
  (`WHERE NOT EXISTS … stato = 'gestito'`) non vede più niente, e la rilevazione
  successiva aprirebbe un `rilevato` nuovo senza la finestra configurabile e
  senza il collegamento al precedente che la 2.7 AC 5 richiede. **Latente oggi**
  (nessun percorso scrive `gestito`), trappola certa per chi implementa la 2.7.
- **F6 — la guardia anti-riapertura non ha test**, perché nessun test della
  suite può scrivere `gestito` senza violare l'invariante di AC 8. Arriva con la
  2.7, insieme al percorso che la rende esercitabile.
- **F7 — ordine di merge**: la PR #60 porta negli AC i quattro requisiti che
  questa PR implementa ed è **ancora aperta**. Mergiare la #62 prima
  lascerebbe su `main` il codice senza il contratto che lo giustifica.
- **F8 — la guardia AST riconosce `StatoConflitto` per nome**: un
  `import … as SC` o una `UPDATE` in SQL testuale le passerebbero sotto. È un
  limite dichiarato del suo dominio, non un difetto.

## Dev Agent Record

### Cosa è stato scritto

**Produzione**

| File | Cosa |
| --- | --- |
| `app/calendario/conflitti.py` (nuovo) | La regola pura: `PrenotazioneAttiva`, `CoppiaSovrapposta`, `coppie_sovrapposte` |
| `app/calendario/models.py` | `StatoConflitto`, `Conflitto` + indice UNIQUE parziale e due CHECK |
| `app/calendario/repository.py` | `ConflittoRepository` (`apri`, `decadi_per_prenotazione`, `rilevati`, `by_id`); `attive_della_struttura` (ex `della_struttura`); `marca_rimosse_dal_feed` ritorna QUALI; `upsert_dal_feed` ritorna `EsitoUpsert` |
| `app/calendario/service.py` | `rivaluta_conflitti`, `decadi_conflitti_della_prenotazione`, `conflitti_rilevati`, `_emetti_cessate`; i due inneschi (import, inserimento manuale) |
| `app/calendario/sottoscrizioni.py` (nuovo) | Il primo sottoscrittore di `outbox` del progetto |
| `app/calendario/schemas.py`, `api.py`, `app/main.py` | `GET /api/v1/conflitti` |
| `app/core/events.py` | `conflitto.rilevato`, `conflitto.decaduto`, e il commento di `prenotazione.cessata` riscritto: ora il nome dice il vero |
| `app/worker.py` | Import di registrazione del sottoscrittore |
| `alembic/versions/20260812_0015_conflitto.py` (nuovo) | Migrazione 0015, additiva |

**Test** — 5 file nuovi (`test_conflitti_rilevazione.py`, `test_conflitti.py`,
`test_conflitti_decadimento.py`, `test_conflitti_niente_auto_chiusura.py`,
`test_calendario_gara_conflitti.py`), 3 guardie estese (GS-2 `conftest.py`, GS-6
`test_append_preserving_convention.py`, GS-7 `test_superfici_feed_convention.py`),
2 test di `test_calendario_sync.py` aggiornati alla nuova firma di
`marca_rimosse_dal_feed`.

**Nessuna guardia è stata allargata.** GS-6 è stata **irrigidita** (`conflitto`
fra le tabelle protette, `Conflitto` fra i modelli protetti); GS-7 ha una
superficie sorvegliata in più e due esenzioni motivate.

### Evidenza dei test (output reale)

Suite completa, PostgreSQL 18 reale, `HOSTPILOT_TEST_DB_REQUIRED=1`:

```
824 passed, 1 warning in 161.75s (0:02:41)
```

Perimetro della Story più le guardie strutturali che tocca:

```
$ uv run pytest tests/test_conflitti_rilevazione.py tests/test_conflitti.py \
    tests/test_conflitti_decadimento.py tests/test_conflitti_niente_auto_chiusura.py \
    tests/test_calendario_gara_conflitti.py tests/test_append_preserving_convention.py \
    tests/test_superfici_feed_convention.py tests/test_isolamento_dati.py \
    tests/test_tenancy_convention.py tests/test_auth_convention.py tests/test_migrations.py -q
101 passed, 1 warning in 10.42s
```

La funzione pura, senza database (AC 1 — se il test avesse avuto bisogno di una
`Session`, la purezza sarebbe già stata violata):

```
$ uv run pytest tests/test_conflitti_rilevazione.py -q
21 passed, 1 warning in 0.09s
```

Gara A3-4, tre esecuzioni consecutive:

```
1 passed, 1 warning in 1.02s
1 passed, 1 warning in 1.15s
1 passed, 1 warning in 1.19s
```

Qualità: `ruff check` e `ruff format --check` puliti, `mypy` `Success: no issues
found in 58 source files`, `alembic check` `No new upgrade operations detected`
(una sola head), `openapi.json` e `frontend/lib/api/schema.d.ts` rigenerati e
committati, frontend `168 passed (20 files)` + `eslint` pulito.

### Prova del rosso

**A3-4 con il rimedio rimosso.** Sostituito il percorso atomico di `apri` con il
check-then-write ingenuo («esiste già?» poi «inserisci»), a parità di indice:

```
>       assert [esito for esito in esiti if esito.startswith("errore")] == []
E       AssertionError: assert ['errore:Inte...tegrityError'] == []
E         Left contains 4 more items, first extra item: 'errore:IntegrityError'
1 failed, 1 warning in 1.11s
```

**Cinque contendenti su otto** hanno superato il pre-check e sono finiti contro
il vincolo: la finestra critica c'è, e senza l'istruzione unica sarebbe un
`IntegrityError` dentro un job di sync — cioè un import fallito per un Conflitto
che il sistema aveva rilevato correttamente. Con l'indice **rimosso** l'esito è
diverso e altrettanto istruttivo: Postgres rifiuta l'`ON CONFLICT` stesso
(`there is no unique or exclusion constraint matching the ON CONFLICT
specification`), quindi il codice non può nemmeno girare senza il vincolo che lo
governa.

**Otto mutazioni, una per invariante.** Ogni riga è: mutazione applicata sul
codice committato, test del perimetro eseguiti, `git checkout --` per
ripristinare.

| # | Mutazione | Esito |
| :---: | --- | --- |
| M1 | Canonicalizzazione rimossa (coppia in ordine d'arrivo) | 2 failed |
| M2 | Perimetro della Struttura ignorato | 2 failed |
| M3 | Confine semiaperto → inclusivo (il turnover diventa Conflitto) | 4 failed |
| M4 | Filtro `attiva` rimosso dalla lettura | 1 failed |
| M5 | Strada 3 muta (`STATUS:CANCELLED` non emette) | 2 failed |
| M6 | Strada 2 muta (scomparsa dal feed non emette) | 2 failed |
| M7 | Emissione a **ogni** sync invece che alla transizione | 1 failed |
| M8 | Idempotenza persa (decadimento non condizionato allo stato) | 1 failed |

### Le stesure che non hanno tenuto

Sono la parte utile del documento, come nella 2.4.

**1. `rowcount` su un `INSERT … SELECT` — il difetto che i test hanno preso per
me.** La prima versione di `apri` decideva «ho inserito?» dal `rowcount`. Due
test sono diventati rossi subito: `rivaluta_conflitti` dichiarava di aver aperto
un Conflitto a **ogni** esecuzione. Il motivo non è il database — il vincolo
faceva perfettamente il suo lavoro, nessuna riga doppia è mai esistita — ma
SQLAlchemy, che su un `INSERT … SELECT` non garantisce il conteggio e restituisce
**`-1`**: un valore **vero** in un `if`. Il difetto sarebbe stato invisibile allo
stato persistito e visibile solo a valle: un `conflitto.rilevato` di troppo a
ogni sync, cioè — nella 2.6 — una notifica ripetuta all'Host per lo stesso fatto,
sulla funzione di fiducia del prodotto. Ora la domanda «ho inserito?» ha per
risposta la riga stessa (`RETURNING`).

**2. La guardia anti-auto-chiusura era verde per la ragione sbagliata.** La prima
versione cercava le scritture di `StatoConflitto.GESTITO` fra gli argomenti
**nominati** (`stato=…`) e le assegnazioni — cioè le forme che sapevo
immaginare — e non vedeva la scrittura **posizionale**
`literal(StatoConflitto.RILEVATO, tipo)`, che è quella che il repository fa
davvero. Se ne è accorto il suo stesso test di completezza
(`test_la_guardia_trova_qualcosa_da_controllare`), che pretende di trovare
scritti **tutti** gli stati ammessi: si aspettava `{RILEVATO, DECADUTO}` e ha
trovato `{DECADUTO}`. La riscrittura è default-deny — **ogni** uso di
`StatoConflitto.X` è una scrittura tranne quelli dentro un confronto — perché
leggere è il caso enumerabile e scrivere no. Le sentinelle sono ora quattro,
compresa la forma posizionale.

**3. Il contatore `rimosse_dal_feed` stava per cambiare significato.** Nel primo
passaggio ho fatto confluire le uscite delle strade 2 e 3 in una lista sola e ho
scritto `rimosse_dal_feed=len(cessate)` nel `sync_run`: il contatore avrebbe
iniziato a includere anche le prenotazioni **annullate dal portale**, che non sono
«scomparse dal feed». Nessun test lo avrebbe visto — i due numeri coincidono in
quasi ogni scenario — e la colonna avrebbe smesso di significare ciò che il suo
nome dice, su una tabella append-only che nessuno riscrive. Le due liste sono
tornate separate: il `sync_run` conta le scomparse, l'evento le racconta tutte.

### Batch di correzione dopo il verdetto BOCCIA del 12/08

Murat ha riprodotto la suite (824 passed) e poi ha mutato il codice: **8
mutazioni, 6 catturate, 2 sopravvissute**. Le due sopravvissute sono la parte
che conta, perché nessuna di esse era visibile leggendo i test.

Applicato **fix-forward sulla stessa PR #62**, non su un ramo separato: la PR
non è mergiata, quindi un secondo ramo dipenderebbe da codice che non esiste su
`main` e Murat rivedrebbe due diff per una Story sola.

| # | Finding | Cosa era | Cosa è ora |
| :---: | --- | --- | --- |
| **F1** | *correttezza* — un evento consegnato in ritardo spegne un Conflitto vivo | L'handler faceva decadere senza chiedere se la Prenotazione fosse ancora fuori da `attiva` **adesso** | `~ancora_attiva` dentro la `UPDATE` di `decadi_per_prenotazione` |
| **F2** | *copertura* — l'AC 1 «quando termina un import» senza test | Ogni allestimento creava la manuale **dopo** il sync: il Conflitto lo apriva sempre il percorso manuale | `TestAperturaDelConflitto::test_e_l_IMPORT_a_rilevare_quando_arriva_la_seconda` |
| **F3** | *copertura* — il lato `max` della coppia mai esercitato | `uuidv7` è monotono ⇒ la Prenotazione creata per prima è **sempre** il `min`, e tutte e tre le strade cancellavano quella | `TestLeDueMetaDellaCoppia`, che fa uscire la **seconda** e asserisce esplicitamente il lato |
| **F5** | *codice morto* — `ConflittoRepository.by_id` senza chiamanti | E2-F23 riaperto nella stessa PR che lo chiude | rimosso |

**F1 riprodotto prima di essere corretto** (regola del 27/07). Il rosso, sul
codice consegnato:

```
AssertionError: un evento consegnato in ritardo ha spento un Conflitto fra due
Prenotazioni ancora `attiva` e ancora sovrapposte (stato: StatoConflitto.DECADUTO)
```

L'allestimento è il percorso reale, non una forzatura: il portale annulla
(evento scritto, **non ancora consegnato** — è la finestra in cui vive il
difetto), poi ritira l'annullamento e la Prenotazione torna `attiva`. Il
secondo test della classe guarda ciò che resta a valle anche dopo che la
rilevazione successiva ha risanato lo stato: `outbox` è append-only, e un
`conflitto.decaduto` di troppo nella 2.6 è una seconda notifica per lo stesso
fatto.

**Le tre mutazioni, dopo il batch** — perimetro Conflitti + sync, 146 test:

| Mutazione | Prima | Ora |
| --- | :---: | --- |
| Decadimento cercato solo nella colonna `min` (M3 di Murat) | sopravvissuta | **1 failed** — `TestLeDueMetaDellaCoppia::test_decade_anche_quando_la_prenotazione_e_il_lato_max` |
| Rilevazione tolta da `esegui_sync` (M5 di Murat) | sopravvissuta | **1 failed** — `TestAperturaDelConflitto::test_e_l_IMPORT_a_rilevare_quando_arriva_la_seconda` |
| Condizione «ancora attiva» rimossa dal decadimento (il rimedio di F1) | — | **2 failed** — entrambi i test di `TestEventoInRitardo` |

**Un test esistente è stato corretto, non adattato.**
`test_un_conflitto_decaduto_non_impedisce_di_riaprirne_uno` faceva decadere un
Conflitto fra due Prenotazioni **ancora `attiva`**: uno stato che il prodotto
non produce, e che dopo F1 non è più raggiungibile. L'allestimento ora esegue
la transizione prima del decadimento. Se avessi allentato il rimedio per farlo
passare, avrei riaperto F1 dalla porta di servizio.

Suite completa dopo il batch: **828 passed** (824 + 4 test nuovi).

### Note di consegna

- CI e Sonar verdi prima della richiesta di verdetto (regola del 25/07): la PR è
  aperta e la catena è **CI + Sonar verdi → verdetto di Murat → merge di Fahad**.
- L'issue non è `done` prima del merge su `main`.
- Migrazione **0015**, una sola head, `alembic check` verde: la guardia di
  `tests/test_migrations.py` gira nella suite.
- Nessun dato reale di Ospiti in fixture o test (NFR-16); nessuna modifica a
  `.github/workflows/ci.yml`.

### Change log

| Data | Cosa |
| --- | --- |
| 2026-08-12 | Prima stesura completa: funzione pura, tabella `conflitto` + migrazione 0015, apertura atomica, decadimento per evento con le tre strade di MYL-69, `GET /api/v1/conflitti`, gara A3-4, guardia anti-auto-chiusura, GS-2/GS-6/GS-7 aggiornate. Consegnata per il verdetto di Murat. |
| 2026-08-12 | **Verdetto BOCCIA** (2 mutazioni sopravvissute su 8). Batch fix-forward sulla stessa PR: **F1** staleness del decadimento (riprodotto rosso, poi corretto dentro la `UPDATE`), **F2** test dell'innesco «import», **F3** test del lato `max` della coppia, **F5** rimozione di `by_id` senza chiamanti. F4, F6, F7, F8 restano a Fahad. 828 test verdi. |

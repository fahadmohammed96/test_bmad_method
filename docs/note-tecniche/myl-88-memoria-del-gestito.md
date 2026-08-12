---
title: 'MYL-88 — La conferma dell''Host sopravvive al decadimento del Conflitto'
tipo: 'nota tecnica (F4 del verdetto sulla PR #62, instradato come lavoro proprio)'
epic: 'Epic 2: Calendario unificato e anti double-booking'
created: 2026-08-12
updated: 2026-08-12
status: in_review
owner: 'Amelia — Senior Software Engineer (Fase 4)'
decisione: 'Fahad — opzione A, 12/08: si paga una colonna adesso invece di una migrazione di dati dopo'
sources:
  - 'Verdetto di Murat sulla PR #62, finding F4 (sezione «Finding P2 — non nel batch») e terzo punto «Per Fahad», thread MYL-83'
  - 'docs/stories/story-2.5-rilevazione-conflitti.md §«Voci aperte» D'
  - 'docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-5, AD-19, AD-20)'
issue: 'MYL-88'
depends_on: 'Story 2.5 (PR #62, su `main` dal 12/08 — `179f3ae`)'
---

## Il difetto, in una frase

Quando il Conflitto decade, sparisce anche la traccia che l'Host lo avesse già
gestito — e la guardia che impedisce alla rilevazione di riaprirlo non trova più
niente da proteggere.

## Perché era latente e perché non poteva restare tale

Nessun percorso di codice scrive oggi lo stato `gestito`: la transizione arriva
con la Story 2.7, e `tests/test_conflitti_niente_auto_chiusura.py` impone che
resti così. Su `main` il difetto non era quindi osservabile — ma la sua vittima
è determinata: chi implementa la 2.7 trova una guardia anti-riapertura che
*sembra* funzionare, la usa come fondamento della finestra configurabile
dell'AC 5, e scopre a valle che la finestra si scavalca da sé al primo
annullamento ritirato da un portale.

Il costo della correzione è asimmetrico nel tempo, ed è il criterio con cui
Fahad ha scelto l'opzione A: **oggi** è una colonna vuota su righe che non hanno
niente da ricordare; **dopo la 2.7** sarebbe la stessa colonna più la
ricostruzione di decisioni che nessuna tabella conserva più. La seconda non è
una migrazione più lunga: è un dato che non esiste.

## La distinzione che regge tutto il lavoro

Uno stato non può essere insieme `decaduto` e `gestito`. «È decaduto **ed era
stato gestito**» è invece un'informazione perfettamente rappresentabile — su
un'altra colonna.

| | cos'è | chi la scrive | quando cambia |
| --- | --- | --- | --- |
| `stato` | cos'è il Conflitto **adesso** | rilevazione (`rilevato`), sistema (`decaduto`), Host via 2.7 (`gestito`) | a ogni transizione |
| `gestito_il` | che una **decisione c'è stata**, e quando | solo la 2.7 | una volta, mai più |

`decaduto` e `gestito` restano due transizioni distinte e tracciate: SM-C1
misura «quanti Conflitti l'Host ha davvero risolto» separandole, e confonderle
non romperebbe nulla oggi.

## Cosa è stato scritto

| File | Cosa |
| --- | --- |
| `backend/app/calendario/models.py` | `Conflitto.gestito_il` (nullable) + CHECK `ck_conflitto_gestito_ha_istante` |
| `backend/app/calendario/repository.py` | la guardia anti-riapertura di `apri` legge `gestito_il IS NOT NULL` invece dello stato corrente; `decadi_per_prenotazione` non tocca `gestito_il` |
| `backend/alembic/versions/20260812_0016_conflitto_memoria_del_gestito.py` | migrazione 0016, additiva, senza backfill |
| `backend/tests/test_conflitti_memoria_del_gestito.py` (nuovo) | 4 test — chiude **F4** e con lui **F6** |

### Il CHECK è un'implicazione, non un'equivalenza

La 0015 aveva scritto `(stato = 'decaduto') = (decaduto_il IS NOT NULL)`, e la
simmetria è corretta lì. Qui no:

```sql
stato <> 'gestito' OR gestito_il IS NOT NULL
```

`gestito` senza il suo istante è una decisione senza il quando — cioè la
finestra della 2.7 senza il punto da cui si misura, e va vietato. L'inverso
invece è **esattamente lo stato che questa colonna esiste per rendere
rappresentabile**: un `=` scritto per simmetria vieterebbe il caso che si vuole
ottenere. È l'errore più facile da commettere copiando la riga sopra.

### Perché la guardia legge `gestito_il` e non anche lo stato

`stato = 'gestito' OR gestito_il IS NOT NULL` sarebbe ridondante: sotto il CHECK
il primo disgiunto è implicato dal secondo. Una ridondanza del genere nasconde
quale invariante regge davvero — e alla prima modifica qualcuno toglie quello
sbagliato.

## Cosa **non** è stato fatto

- **La Story 2.7 non è implementata.** Nessuna finestra configurabile, nessun
  collegamento al Conflitto precedente, nessuna superficie di gestione, nessun
  percorso applicativo che scriva `gestito`. Questo lavoro lascia il dato, non
  la stanza.
- **`gestito_il` non è esposta in API.** `ConflittoOutput` è invariato:
  `openapi.json` e il client TypeScript non cambiano di una riga (verificato
  rigenerando: diff vuoto). La superficie è della 2.7, e un campo pubblicato
  prima del percorso che lo riempie è un contratto che promette un dato sempre
  nullo.
- **Nessuna guardia è stata allargata.** GS-6 (`test_append_preserving_convention.py`)
  passa invariata: aggiungere una colonna non è una cancellazione. L'invariante
  di AC 8 (`test_conflitti_niente_auto_chiusura.py`) passa invariato: la
  scrittura di `gestito` di questo lavoro sta in un **helper di test**, e la
  guardia AST ispeziona `app/`. Il suo
  `test_la_guardia_trova_qualcosa_da_controllare` continua a trovare
  `{RILEVATO, DECADUTO}` scritti in `repository.py` — la modifica di `apri` ha
  tolto una **lettura**, che quella guardia non conta di proposito.

## F6 si chiude qui, e non per cortesia

F6 diceva che la guardia anti-riapertura non aveva alcun test, perché nessun
test della suite scriveva mai `gestito`. Non era una svista: era
un'impossibilità: scriverlo da `app/` avrebbe violato AC 8.

La via d'uscita è che a scriverlo sia l'**allestimento**, non la produzione.
`_gestito_dall_host` in `tests/test_conflitti_memoria_del_gestito.py` fa oggi ciò
che il service della 2.7 farà domani, e i test che ci poggiano sopra non
cambieranno quando quel service arriverà.

## Dev Agent Record

### TDD verificabile — i due SHA (regola del 12/08)

| | SHA | Cosa |
| --- | --- | --- |
| rosso | `8a2abb5430a204e6420db23f0da222ad1110df9f` | i due test di comportamento, senza alcuna modifica alla produzione |
| verde | `9440437b64b6803b4f5cba09e08a5807744ccd39` | colonna, CHECK, migrazione, guardia |

Il rosso è un **fallimento di asserzione sul comportamento**, non un
`ImportError` né un 404 su una rotta che non esiste:

```
$ uv run pytest tests/test_conflitti_memoria_del_gestito.py -q

E       AssertionError: la rilevazione ha riaperto una coppia che l'Host aveva già
        gestito: la guardia anti-riapertura ha perso la memoria della decisione
        quando il Conflitto è decaduto, e la 2.7 troverebbe una finestra di
        riconciliazione scavalcata prima di esistere
E       assert [<StatoConflitto.RILEVATO: 'rilevato'>] == [<StatoConflitto.DECADUTO: 'decaduto'>]
E         Left contains one more item: <StatoConflitto.RILEVATO: 'rilevato'>

E       AssertionError: assert 2 == 1
E        +  where 2 = _eventi(<Session>, 'conflitto.rilevato')

2 failed, 1 warning in 2.76s
```

**Dichiarato invece che taciuto — due scostamenti dall'ordine puro:**

1. Fra il rosso e il verde l'**allestimento** ha guadagnato una riga:
   `_gestito_dall_host` scrive anche `gestito_il`, perché il CHECK introdotto
   col verde lo richiede. Le **asserzioni** dei due test sono identiche nei due
   commit: il diff fra gli SHA lo mostra.
2. I due test di `TestIlDatoCheLaStoria27Trovera` sono nati **col verde**, non
   prima. Riguardano il dato e il vincolo che nascono con la colonna: prima
   della colonna il loro rosso sarebbe stato un `AttributeError`, cioè il
   segnaposto che la regola del 12/08 esclude esplicitamente dal valere come
   prova. Sono coperti dalle mutazioni qui sotto, che è la verifica che
   restava disponibile.

### Evidenza dei test (output reale)

Suite backend completa, PostgreSQL 18 reale, `HOSTPILOT_TEST_DB_REQUIRED=1`:

```
832 passed, 1 warning in 175.34s (0:02:55)
```

Il perimetro dei Conflitti e le guardie strutturali che tocca:

```
$ uv run pytest tests/test_conflitti_memoria_del_gestito.py tests/test_conflitti.py \
    tests/test_conflitti_decadimento.py tests/test_conflitti_niente_auto_chiusura.py \
    tests/test_calendario_gara_conflitti.py tests/test_append_preserving_convention.py \
    tests/test_migrations.py -q
66 passed, 1 warning in 16.28s
```

Qualità: `ruff check .` **All checks passed**, `ruff format --check .` *137
files already formatted*, `mypy` *Success: no issues found in 58 source files*,
`alembic check` **No new upgrade operations detected**, `alembic heads` → **0016
(head)**, una sola. `openapi.json` rigenerato: nessuna differenza di contenuto.

### La tenuta verificata con la mutazione, non con la conclusione

Ogni riga è: mutazione applicata sul codice **committato**, test eseguiti,
`git checkout --` per ripristinare.

| # | Mutazione | Esito |
| :---: | --- | --- |
| 1 | La guardia di `apri` torna a leggere lo stato corrente (`Conflitto.stato == StatoConflitto.GESTITO`) — cioè il codice di `main` | **3 fallimenti**: i due di comportamento più `test_il_decadimento_non_azzera_l_istante_della_decisione` (che trova due righe dove ne aspetta una) |
| 2 | `decadi_per_prenotazione` azzera la memoria mentre decade (`.values(…, gestito_il=None)`) | **3 fallimenti**, gli stessi: la colonna senza la regola «non si azzera mai» non serve a niente, e il test lo dimostra invece di prometterlo |
| 3 | Il CHECK `ck_conflitto_gestito_ha_istante` rimosso dal modello **e** dalla migrazione | **1 fallimento**: `test_un_gestito_senza_il_suo_istante_non_e_rappresentabile` — il vincolo è portante, non decorativo |

La mutazione 1 è quella che il verdetto chiedeva: rimossa la memoria appena
introdotta, cadono esattamente i test scritti per lei, e nient'altro nella suite
si muove. È anche la prova che il difetto era reale su `main` e non un'ipotesi.

### Note di consegna

- Base `main`, PR aperta da me, **merge di Fahad**.
- La guardia GS-6 non è stata allargata né toccata.
- Nessun percorso di `app/` scrive `gestito`: l'invariante di AC 8 regge
  invariato, ed è la ragione per cui la migrazione non ha backfill.
- La 2.5 resta il posto dove F4 era stato registrato: `docs/stories/story-2.5-rilevazione-conflitti.md`
  §«Voci aperte» D ora rimanda qui.

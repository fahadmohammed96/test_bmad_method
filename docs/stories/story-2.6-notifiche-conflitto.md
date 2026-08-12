---
title: 'Story 2.6 — Notifiche di Conflitto (in-app + email), fondazione `notifiche`'
epic: 'Epic 2: Calendario unificato e anti double-booking'
status: in_review
created: 2026-08-12
updated: 2026-08-12
owner: 'Amelia — Senior Software Engineer (Fase 4)'
sources:
  - 'docs/epics.md (Story 2.6) + l''eccezione di precedenza dell''issue MYL-92 sul trigger della notifica (§4.2-10, in arrivo con la PR #63)'
  - 'docs/qa/test-design-epic-2.md §3 Story 2.6 (11 AC, 7 P0), §2.4 (gara A3-5), §2.6 (guardia GS-3)'
  - 'docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-1, AD-2, AD-8, AD-10, AD-13, AD-16, AD-17, AD-18, AD-20, AD-21)'
issue: 'MYL-92 — Story 2.6'
depends_on: 'Story 2.5 (rilevazione dei Conflitti, evento `conflitto.rilevato`) — su main'
---

# Story 2.6 — Notifiche di Conflitto (in-app + email)

## Story
As an Host,
I want essere avvisato appena emerge una possibile doppia prenotazione,
So that possa intervenire in tempo, perché questa è la funzione di fiducia del
prodotto.

## Il residuo della 2.5 che questa Story chiude

Il test design dichiarava scoperto, alla 2.5, il *testable consequence* di
FR-5: «l'Host riceve una notifica alla prima sincronizzazione in cui il
Conflitto emerge». Amelia lo aveva dichiarato scoperto invece di darlo per
buono. **È chiuso qui**, e la prova è
`tests/test_notifiche_consegna.py::TestLaNotificaParte::test_la_rilevazione_apre_una_notifica_e_accoda_un_job_per_canale`
più `::TestAllaPrimaRilevazione` (2 test): dalla rilevazione del Conflitto
nasce una notifica, una sola, e le rilevazioni successive non ne aprono altre.

**Il trigger è la prima RILEVAZIONE, non la sincronizzazione** (eccezione di
precedenza dell'issue, §4.2-10 in arrivo con la PR #63). Nel codice questo non
è un'interpretazione: il sottoscrittore ascolta `conflitto.rilevato`, che la
2.5 emette da entrambi gli inneschi — import e inserimento manuale — quindi un
Conflitto nato da una Prenotazione manuale notifica come tutti gli altri. Non
esiste in tutto il modulo una riga che nomini un `sync`.

## Acceptance Criteria → esito

Riferimento di copertura: `docs/qa/test-design-epic-2.md` §3, Story 2.6 (11
righe, 7 P0). I percorsi dei test sono relativi a `backend/`.

| # | AC (test design) | Livello | Esito | Dove |
| :---: | --- | :---: | :---: | --- |
| 1 | Alla prima rilevazione parte una notifica (in-app + email) via **job durevole**, mai silenziosa | I | ✅ | `tests/test_notifiche_consegna.py::TestLaNotificaParte` (4 test): la notifica nasce, i due canali hanno ciascuno il suo job, **niente parte dentro la transazione che rileva**, e la consegna in-app scrive il messaggio sulla riga |
| 2 | ⚡ La notifica parte alla **prima** rilevazione, non a ogni sync | I (**gara A3-5**) | ✅ | `::TestAllaPrimaRilevazione` (2 test: seconda rilevazione, stesso evento riconsegnato) + `tests/test_notifiche_gara.py::test_otto_richieste_in_gara_aprono_una_sola_notifica` (8 contendenti) |
| 3 | ⚡ Consegna **at-least-once** con **handler idempotente**: nessuna persa, nessun doppione | I (**gara A3-5**) | ✅ | `::TestIdempotenzaDellaConsegna` (2 test) + `tests/test_notifiche_gara.py::test_otto_consegne_in_gara_mandano_una_sola_email` |
| 4 | `notifiche` dipende **solo in lettura** da `identity`; **nessun modulo dipende sincronicamente** da `notifiche` | **S** (GS-3) | ✅ | `tests/test_grafo_moduli.py` — 8 regole + 12 sentinelle. `::test_notifiche_dipende_solo_da_identity`, `::test_nessun_modulo_di_dominio_importa_notifiche`, `::test_solo_la_radice_di_composizione_conosce_notifiche` (insieme ESATTO) |
| 5 | Le **preferenze di notifica** dell'Host (Story 1.3, FR-20) sono rispettate | I | ✅ | `tests/test_notifiche_preferenze.py` (7 test, con la guardia sull'allineamento dei due vocabolari) + `tests/test_notifiche_consegna.py::TestPreferenzeIgnorate` sul percorso intero. **Vedi «Scelte di progetto» 2**: l'in-app si scrive sempre, la preferenza governa i canali in uscita |
| 6 | † Il payload non trasporta dati dell'Ospite: soli identificatori; il testo si compone **alla consegna** leggendo lo stato corrente | U + I | ✅ | `::TestSoliIdentificatori` (3 test). Il secondo cambia il nome della Struttura **fra la richiesta e la consegna** e pretende il nome di adesso: è la prova che il testo non è stato congelato. Il terzo registra un Ospite con nome inventato e lo cerca in `outbox`, in `job`, nelle righe e nel messaggio |
| 7 | Un fallimento del canale lascia il job **ritentabile**, mai marcato «inviata» | I | ✅ | `::TestUnCanaleCheFallisce` (4 test): consegna `in_attesa`, job `pending` con `attempts=1`, `due_at` nel futuro, `last_error` scritto — e il canale rotto **non trascina** quello che funziona |
| 8 | † L'esaurimento dei tentativi produce uno stato **visibile** (`failed` osservabile) | I | ✅ | `::test_esauriti_i_tentativi_il_job_resta_visibile_come_failed` — dopo `max_attempts` il job è `FAILED` con il motivo, e la consegna è ancora `in_attesa`. **Vedi «Scelte di progetto» 5** su dove vive la visibilità |
| 9 | † Il testo contiene Struttura e intervallo date in formato it-IT | U | ✅ | `tests/test_notifiche_testo.py` (22 test, nessun database, nessun orologio): l'esempio dell'Epic, notte singola, confine del `check_out`, cambio di mese, cambio d'anno, zero-padding, intervallo vuoto rifiutato, purezza |
| 10 | † **Nessun invio reale** nei test: canale email iniettato, guardia di rete attiva (GS-1) | **S** | ✅ | `tests/test_isolamento_notifiche.py` (8 test). Due difese **indipendenti**, entrambe viste mordere: la fixture `isolamento_canale_email` e — su un canale SMTP vero installato apposta — `TentativoDiUscitaDiRete` |
| 11 | «Questa fondazione è riusata da Epic 3 ed Epic 5» | **ispezione** + S (GS-3) | ⏸️ **dichiarato coperto per ispezione**, come previsto | La parte verificabile oggi è AC 4 e la copre GS-3. Vedi «Voci aperte» A: lo scrivo invece di lasciarlo passare |

## Scelte di progetto da segnalare in review

### 1. `app/cablaggio.py`: dove vive un collegamento che nessuno dei due lati può dichiarare

Lo spine disegna `calendario -. job .-> notifiche` **tratteggiata** e chiude con
«nessun modulo dipende in modo sincrono da `notifiche`»; l'unica freccia piena
che entra in `notifiche` è `notifiche → identity`. Ne segue un vincolo che non
è di stile:

- il collegamento **non può stare in `calendario`**, perché sarebbe un import
  di `notifiche`;
- **non può stare in `notifiche`**, perché il testo della notifica ha bisogno
  della Struttura e delle date di un Conflitto, cioè di `calendario`. Un
  modulo che li legge è un modulo legato al calendario, ed è esattamente la
  condizione che renderebbe falso AC 11.

La forma scelta è **porta e adattatore**, con l'adattatore alla radice di
composizione. `notifiche` dichiara il contratto (`registro.py`: dato un
`host_id` e un riferimento, restituisci un `Messaggio`) e conosce solo una
stringa; `app/cablaggio.py` — un modulo alla radice di `app/`, non un modulo di
dominio — implementa il compositore e sottoscrive `conflitto.rilevato`.
L'Epic 3 e l'Epic 5 registreranno il loro compositore allo stesso modo, e
`notifiche` non cambierà.

`cablaggio.py` è deliberatamente un **modulo** e non un pacchetto: tre guardie
del progetto (`registro_modelli`, `test_tenancy_convention`, GS-3) scoprono i
moduli di dominio con `pkgutil.iter_modules(..., ispkg=True)`, e un pacchetto
`app/cablaggio/` sarebbe entrato in tutte e tre come dominio.

### 2. AC 5: l'in-app si scrive sempre, la preferenza governa ciò che ESCE

`host.canale_notifica_preferito` è **uno** (FR-20: «il canale preferito tra
quelli disponibili»), mentre l'AC 1 dice «in-app + email». Le due righe si
conciliano in un modo solo che non sia ignorare una delle due:

- la **notifica in-app si scrive sempre**. Non è un modo di raggiungere
  l'Host: è la traccia del fatto dentro il prodotto — quella su cui la
  Dashboard della 2.8 costruirà il badge, e quella che rende verificabile
  «mai silenziosa». Sopprimerla renderebbe l'app cieca su un Conflitto per cui
  ha appena mandato un'email;
- i canali **in uscita** (oggi solo email) partono solo se sono il canale
  preferito.

Osservabile: con preferenza `in_app` **nessuna email parte**, e il test lo
verifica anche indirettamente — la guardia del conftest solleva se qualcuno
tocca il canale email, quindi quel test passa proprio perché nessuno lo tocca.

**È un'assunzione di prodotto e la dichiaro** (`DECISIONE-UMANA: sì`): se Fahad
legge la preferenza come esclusiva («ho scelto email, l'in-app non la voglio»),
cambia una riga in `canali_da_servire` e cade un test.

### 3. I due check-then-write, e dove sono finiti

| Domanda | Dove viveva | Dove vive ora |
| --- | --- | --- |
| «È già stata notificata?» → «notifica» | Un `SELECT` seguito da un `INSERT` | `uq_notifica_per_riferimento` su `(host_id, tipo, riferimento_id)` + `INSERT … ON CONFLICT DO NOTHING RETURNING` |
| «È ancora da inviare?» → «invia» | Un `if` sullo stato seguito dall'invio | La condizione dentro la `UPDATE`, decisione sul `RETURNING`, **invio dopo la marcatura** |

La terza forma di `main` — l'indice UNIQUE parziale della 2.5 — non serviva
qui: il riferimento **è** il Conflitto, che è già unico, quindi il UNIQUE è
pieno. Nessuna forma nuova, quindi niente da aggiungere a
`tests/test_lock_convention.py` (nessun advisory lock introdotto).

**L'ordine marca-poi-invia è la parte che conta.** Invertirlo passa i test
sequenziali e cade solo in gara: otto esecuzioni manderebbero otto email e ne
registrerebbero una. Il costo dell'ordine giusto è che una marcatura esiste per
un istante prima dell'esito reale — e non sopravvive: se il canale fallisce,
l'eccezione risale e il SAVEPOINT del kernel (G-1) la annulla. Nessuno stato di
successo **committato** senza un esito (AD-8).

### 4. Un job per canale, non uno per notifica

Con un job solo, l'email che fallisce farebbe annullare dal SAVEPOINT anche la
consegna in-app già marcata, e il ritentativo rifarebbe entrambe: un canale
rotto trascinerebbe con sé quello che funziona, e l'Host resterebbe cieco su un
Conflitto per un guasto del relay di posta. Ogni job possiede **un solo effetto
esterno**. Test: `::test_il_canale_rotto_non_trascina_quello_che_funziona`.

### 5. AC 8: dove vive la visibilità del fallimento

`failed` è il letterale di `JobStatus`, e il job è la riga visibile: dopo
`max_attempts` resta `failed` con `last_error`, e la consegna resta
`in_attesa` — mai «inviata». Non ho aggiunto uno stato `fallita` sulla
consegna, e la ragione è misurabile: l'handler gira dentro il SAVEPOINT del
kernel, quindi **qualunque cosa scrivesse prima di sollevare verrebbe
annullata** (è la lezione del fix-batch 2.3-P1). Uno stato «fallita» sulla riga
sarebbe scrivibile solo non sollevando — cioè rinunciando al ritentativo, che è
AC 7. Le due metà non stanno insieme, e ho scelto quella che gli AC chiedono
entrambe: ritentabile fino alla fine, poi visibile nel job.

`job.last_error` non porta il destinatario né il testo: è una colonna che
nessuno ripulisce (AD-16, NFR-11), e c'è il test che lo pretende.

### 6. Il canale email esiste, e senza SMTP configurato **fallisce invece di fingere**

`CanaleEmailSmtp` prende la connessione come parametro — è ciò che permette di
provarne la composizione senza una socket — e `canale_email_di_produzione()`
ritorna `CanaleEmailNonConfigurato` quando `HOSTPILOT_SMTP_HOST` è vuoto, che
solleva. Un default inventato (`localhost:25`) produrrebbe notifiche
dichiarate inviate e mai partite: il difetto di NFR-3 nella sua forma peggiore,
perché silenziosa. **La scelta del relay e delle credenziali è di Fahad**: il
codice è pronto, la configurazione no.

### 7. `notifiche` non riusa l'enum di `identity`, e l'allineamento è sorvegliato

La preferenza è una colonna di `host` e il suo tipo vive in `identity`;
riusarlo qui legherebbe lo schema di due moduli e violerebbe GS-3. `notifiche`
ha il suo `CanaleConsegna`, e `test_notifiche_preferenze.py` pretende che i due
vocabolari restino la stessa lista: se `identity` aggiungesse `web_push` (è nel
Deferred dello spine), un Host che lo scegliesse resterebbe senza notifiche in
uscita **in silenzio**.

### 8. Nessun endpoint HTTP in questa Story

Il contratto API non cambia (`openapi.json` invariato, nessuna riga nuova in
`test_auth_convention.py`). La superficie che mostra le notifiche in-app è
della 2.8 (Dashboard), e un endpoint senza consumatori è un pezzo di contratto
pubblico che nasce non esercitato — è E2-F23 sul lato API. La consegna in-app
scrive `oggetto` e `corpo` sulla riga: quando la superficie arriverà, il dato
c'è già.

### 9. `ConflittoRepository.by_id` torna, con il percorso che lo usa

La 2.5 lo aveva rimosso perché non aveva chiamanti (E2-F23). Il chiamante è
arrivato: il testo si compone dall'identificatore del Conflitto. Stessa regola,
esito opposto.

## Voci aperte, dichiarate invece che taciute

### A — AC 11 è coperto **per ispezione**, ed è il secondo e ultimo dell'Epic

«Questa fondazione è riusata da Epic 3 ed Epic 5» è un'affermazione su codice
**futuro**: nessun test dentro l'Epic 2 può verificarla. Ciò che si può provare
oggi è che l'interfaccia non conosce il dominio chiamante, e lo prova GS-3
(AC 4). Non lo do per coperto: lo scrivo.

Per ispezione, la superficie che l'Epic 3 e l'Epic 5 dovranno usare è:
`notifiche.service.richiedi(db, host_id, tipo=…, riferimento_id=…)` più un
compositore registrato in `app/cablaggio.py`. Nessun'altra parola di dominio
attraversa il confine.

### B — Il grafo dello spine è indietro rispetto al codice: **3 archi + 2 violazioni**

Costruendo GS-3 ho misurato il grafo reale contro il diagramma di
`ARCHITECTURE-SPINE.md`. Non coincidono, ed è un finding che **non ho
chiuso**, perché correggerlo è materia di architettura, non di questa Story.

**Archi che il codice ha e il diagramma non disegna** (legittimi, il diagramma
è incompleto):

- `strutture → config_normativa` — regge AD-12 (parametri fiscali);
- `calendario → identity` e `config_normativa → identity` — reggono
  `CurrentHost`, cioè l'autenticazione, che attraversa tutto per costruzione;
- `calendario → config_normativa` — l'endpoint `/interno` importa `AdminToken`.

**Violazioni vere della regola «nessun modulo importa `models` o `repository`
di un altro»**, presenti su `main` prima di questa Story:

- `app/strutture/service.py` → `app.config_normativa.repository`;
- `app/strutture/regime_fiscale.py` → `app.config_normativa.models`.

Sono in `ECCEZIONI_STORICHE`, elencate una per una e **a loro volta
sorvegliate**: un test pretende che l'insieme sia esattamente quello, quindi
non può crescere in silenzio né restare a nominare un import che non c'è più.
La guardia nasce verde e morde su tutto il resto. **Segnalato a John**: la
forma corretta è un metodo sul `service` di `config_normativa`, e la decisione
su quando pagarlo non è mia.

### C — Un Conflitto può restare aperto su date che non si sovrappongono più

Il portale può spostare le date di un evento già importato, e nessuna
transizione fa decadere il Conflitto per questo: il decadimento ha una sola
causa, l'uscita da `attiva` (AD-5, AD-19). Il compositore, che rilegge lo stato
corrente, si ferma con `ConflittoSenzaSovrapposizioneError` invece di inventare
un intervallo — scrivere all'Host notti che nessuno ha prenotato due volte è un
allarme più largo del fatto. Il job resta ritentabile e poi `failed` con il
motivo, che è visibile.

È la voce A della Story 2.5 («la sovrapposizione che cessa senza che nessuno
esca da `attiva`») vista dal lato della notifica. Resta aperta: la decisione su
cosa debba succedere al Conflitto è di prodotto, e la 2.7 è il suo posto.

### D — L'e2e non si allarga

A4, elenco chiuso: la 2.6 non ha superficie e non apre spec. Nessun file in
`frontend/e2e/` è toccato.

### E — I P2 e le `[PROPOSTA]` aperte non sono stati toccati

Come da istruzione: sono decisioni di Fahad da affrontare in un giro unico a
fine Epic.

## Dev Agent Record

### Cosa è stato scritto

**Modulo nuovo `backend/app/notifiche/`** (8 file):

| File | Cosa |
| --- | --- |
| `models.py` | `Notifica` (identità `(host_id, tipo, riferimento_id)` UNIQUE), `NotificaConsegna` (una riga per canale, CHECK `inviata ⇔ inviata_il`), `CanaleConsegna`, `StatoConsegna` |
| `registro.py` | La **porta**: `Messaggio`, `Compositore`, `CompositoriNotifica` — e il catalogo dei tipi di notifica |
| `repository.py` | `apri` (`ON CONFLICT DO NOTHING RETURNING`), `marca_inviata` (condizione dentro la `UPDATE`) |
| `service.py` | `richiedi`, `consegna`, `canali_da_servire` |
| `jobs.py` | `notifica.consegna_richiesta` a catalogo, payload `(consegna_id, host_id)`, handler |
| `canali.py` | `CanaleInApp`, `CanaleEmailSmtp` (connessione iniettabile), `CanaleEmailNonConfigurato`, `RegistroCanali` |
| `testo.py` | `intervallo_it` e i dodici mesi: funzione pura, nessun orologio |
| `__init__.py` | Il perché del modulo e i suoi due soli vicini ammessi |

**Radice di composizione**: `backend/app/cablaggio.py` (compositore del testo +
sottoscrittore di `conflitto.rilevato`), importato da `app/worker.py`.

**Toccati**: `app/identity/service.py` (`destinatario_notifiche`, un valore e
non la riga `host`), `app/calendario/service.py` (`riepilogo_conflitto`,
`ConflittoSenzaSovrapposizioneError`), `app/calendario/repository.py`
(`ConflittoRepository.by_id`), `app/core/config.py` + `.env.example` (4
parametri SMTP), `app/worker.py`, `tests/conftest.py`
(`TABELLE_DA_SVUOTARE` + la guardia sul canale email).

**Migrazione** `20260812_0016_notifiche.py` — additiva: due tipi, due tabelle,
i loro indici. `alembic check`: *No new upgrade operations detected*.
`alembic heads`: **0016 (head)**, una sola.

**Test nuovi** (6 file, 78 test): `test_notifiche_testo.py` (22),
`test_notifiche_consegna.py` (22), `test_notifiche_preferenze.py` (7),
`test_notifiche_gara.py` (2, 8 contendenti ciascuno),
`test_isolamento_notifiche.py` (8), `test_grafo_moduli.py` (17, di cui 12
sentinelle).

### Evidenza dei test (output reale)

Suite intera, PostgreSQL 18 reale:

```
910 passed, 1 warning in 174.99s (0:02:54)
Required test coverage of 93.0% reached. Total coverage: 96.91%
```

Copertura dei file nuovi (`--cov --cov-report=term-missing`):

```
app\cablaggio.py                23      0      2      0   100%
app\notifiche\canali.py         57      0      6      0   100%
app\notifiche\jobs.py           18      0      0      0   100%
app\notifiche\models.py         33      0      0      0   100%
app\notifiche\registro.py       23      0      0      0   100%
app\notifiche\repository.py     30      0      0      0   100%
app\notifiche\service.py        47      0     14      0   100%
app\notifiche\testo.py          15      0      8      0   100%
```

`ruff check` e `ruff format --check`: puliti. `mypy`: *Success: no issues found
in 67 source files*.

### Prova del rosso (regola del 12/08)

Due commit, in quest'ordine, sulla stessa PR:

| | SHA | Cosa |
| --- | --- | --- |
| **rosso** | `3d3ca46` | i test + la prima stesura: unicità controllata dal codice, marcatura in Python, intervallo formattato col `repr` delle date |
| **verde** | `5a34209` | i due vincoli nel database, l'ordine marca-poi-invia, il formato it-IT |

Esito del rosso: **27 fallimenti su 51, tutti asserzioni sul comportamento**
(nessun `ImportError`, nessun 404 su una rotta inesistente). I due che contano:

```
E  AssertionError: più di un contendente dichiara di aver aperto la notifica:
   ['aperta', 'aperta', 'aperta', 'aperta', 'aperta', 'aperta', 'aperta', 'aperta']
E  assert 8 == 1

E  AssertionError: più di un contendente dichiara di aver consegnato:
   ['inviata', 'inviata', 'gia_inviata', 'inviata', 'inviata', 'gia_inviata',
    'gia_inviata', 'inviata']
E  assert 5 == 1
```

Otto notifiche per lo stesso Conflitto, e cinque email allo stesso Host per lo
stesso fatto: la gara A3-5 ha visto la gara.

**Eccezioni dichiarate** (dichiarate valgono, taciute no):

- **AC 7 e AC 8 non hanno avuto un rosso proprio.** Il ritentativo e la
  visibilità del fallimento sono proprietà del kernel — il SAVEPOINT per item
  di `run_due_jobs` e il backoff di `_handle_failure` — che esistono dalla
  Story 1.1. I test li verificano e sono passati alla prima esecuzione: non ho
  scritto codice per farli passare, e dichiararli test-first sarebbe falso. La
  parte scritta da me è la *forma* dell'handler che li rende veri (sollevare
  invece di ingoiare), e quella è coperta dal rosso della gara.
- **GS-3 non ha un rosso di percorso**: è una guardia contro un'assenza e
  nasce verde su codice corretto. La sua prova di morsura sono le 12
  sentinelle, che le fanno esaminare sorgenti costruiti e pretendono che li
  segnali — la stessa forma di `test_lock_convention.py`.

### Verifica per mutazione (dopo il commit verde)

Il rosso su codice nuovo è poco informativo; la copertura vera si misura
rompendo un invariante alla volta. Sei mutazioni, in
`f5e6342` le tre correzioni che ne sono uscite:

| Mutazione | Chi cade |
| --- | --- |
| condizione sullo stato tolta dalla `UPDATE` di `marca_inviata` | gara della consegna |
| invio **prima** della marcatura | gara della consegna |
| preferenza ignorata (sempre entrambi i canali) | 2 test (unit + percorso) |
| import del cablaggio tolto da `app/worker.py` | 13 test |
| handler dei job tolto da `app/worker.py` | **nessuno** — è registrato transitivamente da `cablaggio → notifiche.service → notifiche.jobs`, e la guardia in processo fresco lo verifica comunque. L'import esplicito resta perché la radice di composizione dichiara le sue registrazioni |
| `if` di scorciatoia sullo stato in `service.consegna` | **nessuno** — vedi sotto |

### Le stesure che non hanno tenuto

**1. La guardia sulla registrazione era verde con l'import rimosso.** Il test
importava lui stesso `app.cablaggio` per prendere il riferimento all'handler,
e quell'import registrava: stava verificando che *qualcuno* avesse importato il
modulo, non che lo facesse il worker. Togliendo la riga da `app/worker.py`
restava verde. Ora gira in **processo fresco** importando solo l'entrypoint e
guardando il `__module__` degli handler registrati — la stessa forma di
`test_registro_modelli.py`. È la lezione della 2.5 applicata male la prima
volta.

**2. L'`if` di scorciatoia sembrava ridondante, e non lo è.** Rimuovendolo non
cadeva nessun test, il che di solito significa «togliere». Guardando *perché*
non cadeva: senza, una consegna già avvenuta ricompone il testo, e comporre un
fatto che nel frattempo si è mosso può fallire — un Conflitto le cui date non
si sovrappongono più non ha un intervallo da scrivere. Il ritentativo di un job
**già consegnato** diventerebbe un job `failed`: un allarme su una notifica che
l'Host ha ricevuto. Aggiunto
`::test_una_consegna_gia_avvenuta_non_ricompone_un_fatto_che_si_e_mosso`, che
ora cade sulla mutazione. Non tutto ciò che nessun test difende è da buttare:
a volte manca il test.

**3. Tre metodi senza chiamanti.** Passando `apri` a `ON CONFLICT`,
`per_riferimento` è rimasto senza chiamanti; `della_notifica` e
`registro.tipi()` non ne avevano mai avuti. Rimossi (E2-F23): un metodo arriva
con il percorso che lo usa.

**4. Il riscaldamento della seconda gara passa dall'in-app.** Riscaldare
sull'email avrebbe contato otto invii di riscaldamento e reso illeggibile il
numero che conta. È la stessa istruzione sulla stessa tabella, ma senza
effetti esterni.

**5. Il test di tenancy costruito male.** La prima stesura aggiungeva una
consegna «intrusa» a una notifica che aveva già entrambi i canali: cadeva sul
UNIQUE `(notifica_id, canale)` invece che sull'invariante che voleva provare.
Riscritto su una notifica fresca.

### Note di consegna

- CI e SonarCloud: da verificare sulla PR prima di chiedere il verdetto.
- Nessun dato reale di Ospiti nei fixture (NFR-16): il nome usato per provare
  che l'anagrafica non attraversa `outbox`, `job` e i messaggi è
  letteralmente «Mario Rossi Inventato».
- `.github/workflows/ci.yml` non è stato toccato (A2).
- Nessuna libreria di componenti introdotta: la Story non ha superficie (A8
  resta non deciso, e si ripresenta con la 2.7).

### Change log

| Data | Cosa |
| --- | --- |
| 2026-08-12 | `3d3ca46` test rossi (prima stesura con i check-then-write nel codice) |
| 2026-08-12 | `5a34209` verde: vincoli nel database, ordine marca-poi-invia, formato it-IT |
| 2026-08-12 | `f5e6342` correzioni trovate mutando: guardia in processo fresco, test sull'`if` di scorciatoia, rimozione dei metodi senza chiamanti |

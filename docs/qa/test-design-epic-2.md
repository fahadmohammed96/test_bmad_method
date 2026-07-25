---
title: 'Test Design — Epic 2 (Calendario unificato e anti double-booking)'
status: 'aperto — piano di test dell''Epic 2, scritto PRIMA del codice della Story 2.1 (azione A1)'
phase: '4 · Implementation — gate di qualità (Murat, Test Architect)'
created: 2026-07-25
author: Murat — Master Test Architect
scope: 'Epic 2, Story 2.1 → 2.8'
inputDocuments:
  - docs/epics.md (Epic 2, Story 2.1–2.8, acceptance criteria Given/When/Then)
  - docs/architecture.md §3 + ARCHITECTURE-SPINE.md (AD-3, AD-4, AD-5, AD-10, AD-13, AD-14, AD-17, AD-18, AD-19, AD-20)
  - docs/prd.md (FR-3…FR-7; NFR-1, NFR-2, NFR-3, NFR-8, NFR-9, NFR-14, NFR-16)
  - docs/ux-spec.md (UJ-1, UJ-2; UX-DR1, DR4, DR6, DR10, DR11, DR12)
  - docs/qa/test-design-epic-1.md (modello §1–§7; rischi tracciati §7.7)
  - docs/retrospettive/epic-1.md (azioni A1, A3, A4, A9; lezioni §5)
  - _bmad/_memory/test-architect-sidecar/memories.md + knowledge/test-architect/lezioni.md (libreria di squadra)
related:
  - docs/qa/test-design-epic-1.md (chiuso a debito zero, §7.6)
---

> **Come si legge questo documento.** §1–§3 sono il *piano*: rischi, strategia per livello,
> copertura AC per Story con **livello, priorità e il perché di quel livello**. §4 è ciò che
> **non decido io**: ambiguità e AC non testabili come scritti, che tornano a John. §5–§8 sono
> i presidi nuovi (guardie strutturali, concorrenza, e2e, fixture). §9 sono i criteri di gate.
> §10 è lo scheletro della matrice di tracciabilità, che si compila a Epic concluso — oggi è
> vuota di proposito. §11 riprende i rischi tracciati dell'Epic 1 che scadono qui.

# Test Design — Epic 2

Piano di test **risk-based** dell'Epic 2, scritto prima della prima riga di codice. È
l'azione **A1** della retrospettiva dell'Epic 1, e non è una precauzione teorica: cinque
finding su nove dell'Epic 1 vengono dalle due Story consegnate quando questo documento non
esisteva (retrospettiva §3.1).

Non è una suite: è il **contratto di copertura** contro cui misuro le Story 2.1→2.8 al gate.
Documento nuovo, stesso scheletro dell'Epic 1 — che è chiuso e non si estende.

> **Principio guida invariato:** la profondità scala con il rischio; si preferisce sempre il
> livello più basso possibile (unit > integration > component > e2e); le API sono cittadini
> di prima classe; la flakiness è debito tecnico critico; nessun dato reale di Ospiti nei
> fixture (NFR-16).

**Che cosa cambia rispetto all'Epic 1, in una riga.** L'Epic 1 non aveva input esterni: tutti
i suoi input li generavamo noi. L'Epic 2 importa testo scritto da terzi, su rete, in modo
periodico e concorrente, e ne deriva la funzione di fiducia del prodotto (nessun double-booking
sfuggito). Le quattro classi di cecità della CI verde diagnosticate nell'Epic 1 — interleaving,
input fuori alfabeto, assenze, colla fra livelli mockati — **sono tutte e quattro presenti in
questo Epic contemporaneamente**, e per la prima volta insieme. Il piano è costruito attorno
a questo fatto.

### Convenzione degli ID (precisazione rispetto all'Epic 1)

Nell'Epic 1 rischi e finding erano `R-x` / `G-n` / `F-n` / `C-n`, univoci **dentro** l'Epic.
Da qui in avanti prefisso con l'Epic: rischi **`R2-x`**, finding **`E2-Gn`** (gap da test
design o review retroattiva), **`E2-Fn`** (cross-review su Story consegnata), **`E2-Cn`**
(copertura/CI). Motivo: «G-2» ha già un significato preciso nelle conversazioni di squadra e
riusare la sigla in un altro Epic rende ambigua ogni citazione futura. I rischi tracciati
dell'Epic 1 restano `RT-n`, unici per progetto (§11).

---

## 1. Valutazione del rischio (Epic 2)

| ID | Area di rischio | Prob. | Impatto | Punteggio | AD/NFR | Livello test prioritario |
| --- | --- | :---: | :---: | :---: | --- | --- |
| **R2-A** | **Parsing iCal eterogeneo** — Airbnb e Booking scrivono VEVENT diversi (all-day vs datetime con TZID, `DTEND` esclusivo, righe folded, escaping, non-ASCII): date sbagliate ⇒ Conflitto perso o inventato | Alta | Critico | **Critico** | AD-3, AD-4 | unit su corpus di fixture |
| **R2-B** | **Feed vuoto/304/troncato letto come "eventi scomparsi"** ⇒ intero calendario marcato `rimossa_dal_feed` | Media | Critico | **Critico** | AD-4 | integration (HTTP reale locale) |
| **R2-C** | **Conflitti duplicati o persi** — identità `(struttura, coppia)` non canonica o non serializzata | Alta | Critico | **Critico** | AD-5 | integration + **gara** (A3) |
| **R2-D** | **Import non idempotente** — check-then-write su `(feed_id, ical_uid)`: duplicazione o 500 sotto concorrenza | Alta | Alto | **Alto** | AD-4, NFR-1 | integration + **gara** (A3) |
| **R2-E** | **Claim del poller** — stesso Feed sincronizzato due volte insieme, o tick perso al riavvio | Media | Alto | **Alto** | AD-10 | integration + **gara** (A3) |
| **R2-F** | **Falsa sincronia (NFR-2)** — "dati aggiornati alle HH:MM" derivato dall'ultimo *tentativo* invece che dall'ultimo *successo*, o assente su una superficie nuova | Alta | Alto | **Alto** | AD-4, NFR-2, UX-DR6 | integration + **guardia strutturale SG-4** |
| **R2-G** | **Import distruttivo** — un DELETE o un CASCADE che cancella Prenotazioni/Conflitti invece di transizionarli | Media | Critico | **Alto** | AD-4, AD-19, AD-20 | **guardia strutturale SG-3** |
| **R2-H** | **URL non fidato dell'utente** — il server fa fetch di un indirizzo scelto dall'Host: SSRF verso loopback/link-local/metadata, schemi non http(s), redirect, risposta senza limite di dimensione | Media | Critico | **Alto** | AD-4, NFR-6 | unit (validatore) + integration |
| **R2-I** | **Notifica di Conflitto persa o doppia** — la funzione di fiducia del prodotto (NFR-3, severità alta nel PRD) | Media | Critico | **Alto** | AD-10, AD-13 | integration (crash/restart, idempotenza) |
| **R2-J** | **Valori derivati con cache propria** — griglia calendario (2.3) e badge Dashboard (2.8) restano fermi sul dato vecchio dopo una mutazione | Alta | Medio | **Alto** | AD-14 | **e2e mirato** (A4, §7) |
| **R2-K** | **Riapertura post-`gestito`** — non riapre (falso negativo, SM-1) o riapre subito (rumore, SM-C1); finestra hardcoded | Media | Alto | **Alto** | AD-5 | integration |
| **R2-L** | **Semantica temporale** — intervallo semiaperto `[in, out)` sbagliato di un giorno: check-out e check-in adiacenti letti come sovrapposizione | Media | Alto | **Alto** | AD-3 | unit |
| **R2-M** | **a11y del flusso critico** — griglia calendario e Finestra di riconciliazione da tastiera (UX-DR10), distinzione Canale solo-colore (UX-DR4) | Media | Medio | **Medio** | NFR-8, UX-DR4/10 | e2e (axe) + component |
| **R2-N** | **Tenancy sulle nuove entità** — `feed_ical`, `prenotazione`, `ospite`, `conflitto`, `sync_run`, `notifica` | Bassa | Critico | **Medio** | AD-2, NFR-14 | guardia esistente `test_tenancy_convention.py` |
| **R2-O** | **Dati personali dai Feed** — nomi Ospite in log, payload di eventi/job, fixture committate | Media | Alto | **Medio** | AD-11, AD-17, NFR-16 | integration + revisione fixture |
| **R2-P** | **Drift del contratto API** e frontend che ricalcola derivati di dominio | Media | Medio | **Medio** | AD-14 | contract (CI `api-contract`) |

Le aree **Critico/Alto** sono **P0** (obbligatorie al gate). Le **Medio** sono **P1**.
Nessuna area è cosmetica: a11y e i18n restano requisiti (NFR-8/9), non rifiniture.

**Perché R2-A, R2-B e R2-C sono "Critico" e non solo "Alto".** Sono i tre punti in cui un
difetto produce **silenziosamente** l'esatto opposto della promessa del prodotto: un Conflitto
che non viene rilevato non fa rumore, non rompe una pipeline e non genera un ticket — arriva
all'Host sotto forma di due ospiti sulla stessa porta. Il PRD lo dice con SM-1; qui si traduce
in profondità di test.

---

## 2. Strategia per livello (piramide dell'Epic 2)

- **Unit** — il livello che cresce di più in questo Epic, e deve. Ci vive: il **parser iCal**
  su corpus di fixture (una variante di formato = un file, non un ambiente), la
  **normalizzazione temporale** verso `core/date_range` (AD-3), la **funzione pura di
  rilevazione Conflitti** (AD-5 la dichiara pura: se lo è davvero, l'intera matrice di
  sovrapposizione costa millisecondi), il **validatore dell'URL** del feed, il rendering del
  testo delle notifiche. Se un comportamento è deterministico su input testuale, sta qui —
  portarlo più in alto è solo più lento e meno esaustivo.
- **Integration (service/repository + PostgreSQL 18 reale)** — resta il cuore: idempotenza
  dell'upsert (serve il vincolo UNIQUE vero e `ON CONFLICT` veri), transizioni di stato,
  `sync_run`, job durevoli, notifiche at-least-once, tenancy. Su DB **reale**, mai SQLite.
- **Integration con confine HTTP vero (novità dell'Epic 2)** — la rete esterna si stub-a a
  livello di **trasporto** (server HTTP locale nel test), **non** mockando il client dentro il
  service. Motivo, che è la lezione §3.3 dell'Epic 1 applicata prima invece che dopo: `ETag`,
  `If-Modified-Since`, 304, redirect, timeout, dimensione della risposta **sono** il
  comportamento sotto test; un mock a livello di service li cancella dal mondo e il test
  misura il mock. Vale in particolare per R2-B, che vive esattamente lì.
- **Concorrenza (obbligatoria, A3)** — ogni percorso check-then-write nasce con un test di
  gara a **8 thread + `threading.Barrier` fra i client** (mai dentro il codice sotto test).
  Dettaglio in §6. Non è una raccomandazione: è un criterio di gate.
- **Component (Vitest/RTL)** — presentazione della griglia, badge, selettore Struttura,
  etichette di stato. Dove gli hook sono mockati, il test è cieco alla cache **per
  costruzione**: quello che finisce qui non conta come copertura del difetto di §7.
- **e2e (Playwright, full-stack)** — **solo** dove il difetto vive nella colla, con il difetto
  **nominato** (A4). Quattro spec nuovi, elencati e giustificati uno per uno in §7. Ogni spec
  senza un difetto nominabile va riscritto più in basso.
- **Contract (CI `api-contract`)** — invariato e non negoziabile: l'Epic 2 aggiunge molta
  superficie API, è il momento in cui il drift costa di più.
- **Strutturale (meta-test)** — la difesa più economica che abbiamo (§2.1 e §3.2 della
  retrospettiva: la classe "assenze" è quella dove sono finiti entrambi i P0 dell'Epic 1).
  Due guardie esistono; l'Epic 2 ne propone **tre nuove** (§5).

**Cosa NON aggiungiamo alla pipeline:** altri e2e oltre i quattro di §7, e nessuna fase nuova.
Il criterio resta quello della retrospettiva: aggiungere test che costano *unità*, non fasi che
costano *pipeline*.

---

## 3. Copertura per Story (AC → livello → priorità → perché)

Legenda stato: ⛔ da consegnare · ✅ coperto · ⚠️ coperto con gap (→ §4 o registro finding).
Ogni riga ha un **ID stabile** (`AC 2.n-x`) da citare nei nomi dei test e nella matrice §10.
Le righe marcate **→ §4-n** dipendono da una decisione di prodotto ancora aperta: il test si
scrive quando la decisione c'è, e la riga resta ⚠️ fino ad allora.

### Story 2.1 — Collegamento di un Feed iCal e import on-demand ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.1-a | Collegare un URL valido accoda **subito** un job di sync prioritario | AD-4, AD-10 | integration | P0 | L'accodamento è un fatto di stato in DB (riga `job`, priorità/`due_at`): osservabile senza UI. A unit il job non esiste; a e2e se ne vedrebbe solo l'effetto. |
| 2.1-b | Progresso visibile: "Importazione in corso…" → "Importate N prenotazioni — ultimo aggiornamento HH:MM" | UJ-1, UX §5.1 | component + integration | P1 | Il testo è presentazione (component); la **verità** dello stato è un campo API (AD-14) e va verificata a integration. Nessuna colla nuova: non merita un e2e proprio. |
| 2.1-c | Parsing VEVENT: all-day vs datetime con TZID, `DTEND` esclusivo, normalizzazione a date locali Europe/Rome | AD-3, AD-4 | **unit** (corpus) | P0 | Funzione pura su testo: livello più basso possibile e il solo dove moltiplicare le varianti è economico (una variante = un file). A integration la matrice dei formati diventa impraticabile. |
| 2.1-d | Confini testuali: non-ASCII, riga folded CRLF, BOM, campo mancante, `UID` duplicato nello stesso feed, VEVENT malformato ⇒ errore diagnosticabile, **mai** eccezione non gestita | AD-4 | **unit** (table-driven) | P0 | Lezione F-3 dell'Epic 1: i difetti che sopravvivono a una CI verde sono gli input **fuori dall'alfabeto immaginato**. Costa righe, non pipeline. |
| 2.1-e | Upsert idempotente su `(feed_id, ical_uid)`: rieseguire lo stesso sync non duplica né perde | AD-4, NFR-1 | integration | P0 | Serve il vincolo UNIQUE reale e il vero `ON CONFLICT`: un test in memoria passerebbe anche **senza** vincolo, che è precisamente il difetto. |
| 2.1-f | **RACE-1** — due sync concorrenti dello stesso feed con lo stesso `ical_uid` ⇒ una sola Prenotazione, mai 500 | AD-4 | **integration concorrente** | P0 | A3. G-2 e F-1 dell'Epic 1 sono lo stesso difetto trovato due volte: check-then-write senza serializzazione. Con 2 thread spesso non si riproduce (§6). |
| 2.1-g | Stesso `ical_uid` su **feed diversi** resta due Prenotazioni distinte | AD-4 | integration | P1 | Confine della chiave naturale: un UNIQUE sul solo `ical_uid` passerebbe 2.1-e e romperebbe qui. È il test che distingue la chiave giusta da quella che sembra giusta. |
| 2.1-h | Evento scomparso dal feed ⇒ `rimossa_dal_feed`; l'import non cancella **mai** | AD-4, AD-19 | integration + **SG-3** | P0 | Il comportamento è integration, ma l'**invariante** ("nessun DELETE") è un'assenza: la vede solo una guardia strutturale (§5). |
| 2.1-i | Risposta **304 / vuota / troncata / in errore** ⇒ **nessuna** Prenotazione marcata `rimossa_dal_feed` | AD-4, NFR-1 | integration (HTTP locale) | P0 | È l'**interazione fra due AC** (ETag e append-preserving) e il difetto peggiore dell'Epic: un 304 letto come "feed senza eventi" cancella logicamente l'intero calendario. Nessun test del singolo AC lo vede. R2-B. |
| 2.1-j | Prenotazione ri-comparsa dopo `rimossa_dal_feed` | AD-4, AD-19 | integration | P1 | **→ §4-2.** Le OTA omettono eventi temporaneamente (architettura §3.1): è il caso normale, non l'eccezione, e la transizione di ritorno non è specificata. |
| 2.1-k | URL non valido nel formato ⇒ errore **inline sincrono** sul campo, `problem+json` | FR-3 | integration | P0 | Validazione sincrona: risposta HTTP osservabile. **→ §4-1** per la parte "irraggiungibile", che sincrona non è. |
| 2.1-l | URL irraggiungibile / timeout / TLS non valido / redirect / 404 / risposta oltre la soglia ⇒ errore visibile sulla Struttura, mai fallimento silenzioso, mai 500 | FR-3, NFR-1 | integration (HTTP locale) | P0 | Ognuno di questi è un comportamento del **trasporto**: mockando il client si testerebbe l'immaginazione di chi scrive il mock. |
| 2.1-m | URL verso loopback / rete privata / link-local (169.254.169.254) / schema non `http(s)` ⇒ **rifiutato** | NFR-6 | unit (validatore) + integration | P0 | Prima superficie SSRF del progetto: l'URL è input **non fidato** e il fetch parte dal server. La regola della libreria di squadra sugli input non fidati vale qui, e "lo incolla un Host fidato" non regge (l'Host non è fidato per definizione di multi-tenant). |
| 2.1-n | Ogni run scrive `sync_run` (esito, timestamp) — **anche** quando fallisce | AD-4, AD-20 | integration | P0 | `sync_run` è append-only e alimenta NFR-2: un run fallito che non lascia traccia rende indistinguibile "non sincronizzo da 3 giorni" da "non ci sono novità" (retrospettiva A10). |
| 2.1-o | Prenotazioni associate alla Struttura corretta; accesso cross-tenant ⇒ 404 | AD-2, NFR-14 | integration + guardia tenancy | P0 | R2-N. Il comportamento si testa, la **convenzione** la impone la guardia già esistente. |
| 2.1-p | Solo il modulo `calendario` scrive `feed_ical`/`prenotazione`/`sync_run`/`ospite` | AD-18 | strutturale | P1 | Classe "assenze": un import sbagliato da un altro modulo non fallisce, tace. |

**16 AC — P0: 12 · P1: 4 · P2: 0.**

### Story 2.2 — Poller periodico durevole e resiliente ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.2-a | Sync come **job durevole**; nessun timer in-memory; il riavvio del worker non perde il tick (bootstrap idempotente + riprogrammazione a fine giro) | AD-10, NFR-1 | integration | P0 | Il kernel AD-10 è già coperto dall'Epic 1: qui si prova **l'aggancio del dominio**, sul modello già validato di `test_purge_sessioni.py`. Il riavvio si simula, non si aspetta. |
| 2.2-b | Intervallo configurabile, mai costante nel codice: cambiare il parametro cambia il `due_at` | AD-10, NFR-4 | integration | P0 | Modello del test della soglia fiscale (1.6): si abbassa il parametro e l'esito deve cambiare. È l'unico test che distingue "configurabile" da "configurabile sulla carta". |
| 2.2-c | Intervallo **adattivo** in prossimità di check-in | G3-5 | integration | P1 | **→ §4-8.** "In prossimità" non è quantificato: come scritto l'AC non è testabile. |
| 2.2-d | **RACE-2** — 8 worker sullo stesso Feed dovuto ⇒ un solo sync in esecuzione, nessun doppio fetch, nessun tick perso | AD-10 | **integration concorrente** | P0 | A3. `SKIP LOCKED` è coperto a livello kernel, ma il claim *per feed* è codice nuovo: è un check-then-write. |
| 2.2-e | `ETag`/`If-Modified-Since` inviati sulla richiesta successiva; 304 evita il re-parse | AD-4 | integration (HTTP locale) | P0 | La correttezza sta negli header **realmente inviati**: solo un server vero li può osservare. |
| 2.2-f | 200 con ETag cambiato ⇒ re-import append-preserving, nessuna duplicazione | AD-4 | integration | P0 | Combina 2.2-e e 2.1-e: è il percorso di regime, quello che gira mille volte al giorno. |
| 2.2-g | Fallimento temporaneo dell'OTA lascia **intatti** i dati già importati | NFR-1 | integration | P0 | Il dato preesistente è stato in DB: solo a integration si osserva che è ancora lì e immutato. |
| 2.2-h | Errore visibile sulla Struttura; il contatore di fallimenti consecutivi si azzera al primo successo | FR-3, AR-10 | integration | P0 | Contatore persistito: è stato, non presentazione. L'azzeramento è la metà dimenticata di ogni contatore. |
| 2.2-i | Alert interno dopo **N** fallimenti consecutivi | AR-10, NFR-7 | integration | P1 | **→ §4-9.** N non è definito e "alert interno" non ha destinatario né artefatto osservabile nell'MVP (NFR-7 è mappato sull'Epic 3): come scritto non è verificabile. |
| 2.2-j | Ogni superficie espone il timestamp dell'ultimo sync **riuscito** (non dell'ultimo tentativo) | NFR-2, UX-DR6 | integration + **SG-4** | P0 | R2-F. Un sync fallito che aggiorna l'etichetta è **falsa sincronia**: NFR-2 invertito. Il comportamento è integration; la copertura di *tutte* le superfici, comprese quelle scritte fra sei mesi, è una guardia (§5). |
| 2.2-k | Feed **mai** sincronizzato con successo ⇒ stato esplicito, mai un orario inventato o un vuoto ambiguo | NFR-2 | integration + component | P0 | **→ §4-3.** Stessa filosofia del `configurazione_non_disponibile` dell'Epic 1: il sistema dice "non so" invece di dare un numero sbagliato. |
| 2.2-l | I Feed di una Struttura `archiviata` smettono di sincronizzare | AD-20 | integration | P1 | Invariante dell'Epic 1 che l'Epic 2 può rompere per omissione: la Struttura archiviata è già coperta, il suo Feed no. |

**12 AC — P0: 9 · P1: 3 · P2: 0.**

### Story 2.3 — Calendario unificato multi-Struttura ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.3-a | Griglia aggrega Strutture e Canali; distinzione per Canale **testo + icona, mai solo colore** | FR-4, UX-DR4, NFR-8 | component + e2e (axe) | P0 | La conformità del singolo badge è verificabile isolata (component); axe sulla **pagina composta** sta in E2E-4, dove il contrasto reale esiste. |
| 2.3-b | Ogni Prenotazione mostra Canale, Struttura, date, Ospite | FR-4 | component | P1 | Presentazione pura di un payload API: nessuna logica, nessun I/O. |
| 2.3-c | Il selettore Struttura filtra aggregata ↔ singola senza cambiare schermata | UX-DR1 | component | P1 | Il pattern è già coperto dalla 1.3: qui cambia solo la sorgente dati, non il comportamento. |
| 2.3-d | I derivati di dominio arrivano dall'API; il frontend **non li ricalcola** | AD-14 | integration + component | P0 | Metà server (i campi ci sono nella risposta), metà client (il componente li **presenta** invece di derivarli). Il rischio è che il frontend reimplementi la sovrapposizione con la timezone del browser: sarebbe AD-3 violato in silenzio. |
| 2.3-e | "Dati aggiornati alle HH:MM" **sempre visibile**, etichetta persistente e non un tooltip | NFR-2, UX-DR6 | component + e2e | P0 | "Persistente e non nascosta" è un requisito di presentazione: si verifica dove il DOM esiste. |
| 2.3-f | Densità 1 e 3 Strutture senza degrado; stato vuoto rassicurante ("è normale per un nuovo collegamento") | UX-DR12, UJ-1 edge | component | P1 | Due varianti di dato, zero infrastruttura: component è il livello più economico che le distingue. |
| 2.3-g | Trattamento in griglia delle Prenotazioni `cancellata` / `rimossa_dal_feed` | AD-19 | component | P1 | **→ §4-12.** AD-19 dice che non partecipano ai Conflitti; **non** dice se e come si vedono. Farle sparire senza traccia contraddirebbe "archiviare, mai distruggere" all'occhio dell'Host. |
| 2.3-h | **E2E-1** — un import che cambia le Prenotazioni aggiorna la griglia | AD-14, A4 | **e2e** | P0 | §7: difetto di invalidazione cache fra due risorse. I test di componente mockano gli hook, quindi **la cache non esiste nel loro mondo**: sono ciechi per costruzione (lezione 1.6). |
| 2.3-i | Una Prenotazione `[check_in, check_out)` occupa le notti giuste, incluso attraversamento di mese e cambio ora legale | AD-3 | **unit** | P0 | Off-by-one di presentazione: funzione pura da intervallo a celle. R2-L. Un e2e qui costerebbe cento volte tanto e coprirebbe un caso solo. |

**9 AC — P0: 5 · P1: 4 · P2: 0.**

### Story 2.4 — Inserimento manuale di Prenotazioni ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.4-a | Creata in stato `attiva`; partecipa alla rilevazione dei Conflitti | FR-7, AD-19 | integration | P0 | Il "partecipa" è un effetto attraverso due moduli: si osserva solo con stato persistito. |
| 2.4-b | Manuale sovrapposta a una da Feed ⇒ Conflitto | FR-7 → FR-5 | integration | P0 | È il ponte fra le due sorgenti: il caso che nessun test del solo import e nessun test del solo inserimento manuale copre. |
| 2.4-c | Validazione: `check_out > check_in`; **check-out e check-in adiacenti non sono sovrapposizione** | AD-3 | **unit** | P0 | R2-L. È il difetto più probabile dell'intero Epic e costa un unit test: l'intervallo semiaperto esiste apposta e va provato al confine, non nel mezzo. |
| 2.4-d | Non si cancella fisicamente: `cancellata` + evento `prenotazione.cessata` | AD-19 | integration + **SG-3** | P0 | Comportamento a integration, invariante "nessun delete" alla guardia. |
| 2.4-e | `prenotazione.cessata` dichiarato nel catalogo con payload di **soli identificatori** | AD-17 | unit (`test_events.py`) | P1 | Il catalogo è già sorvegliato dall'Epic 1: aggiungere la riga costa nulla e impedisce lo snapshot di stato nel payload (che con i dati Ospite sarebbe anche R2-O). |
| 2.4-f | Inserimento su Struttura di un altro Host ⇒ 404 | AD-2, NFR-14 | integration | P0 | Tenancy: sempre esercitata sul percorso di scrittura nuovo, non solo dedotta dalla guardia. |
| 2.4-g | Il "blocco date" (senza Ospite) è ammesso e partecipa ai Conflitti | FR-7 | integration | P1 | Variante di dominio esplicita nella Story: senza Ospite, molti percorsi che assumono l'anagrafica saltano. |

**7 AC — P0: 5 · P1: 2 · P2: 0.**

### Story 2.5 — Rilevazione dei Conflitti ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.5-a | La rilevazione è una **funzione pura**: stesso insieme ⇒ stesso risultato, nessun I/O | AD-5 | **unit** | P0 | L'architettura la dichiara pura: se lo è, l'intera matrice di sovrapposizione costa millisecondi ed è esaustiva. Se il test non riesce a chiamarla senza DB, la purezza è già violata — ed è un finding, non un problema di test. |
| 2.5-b | Matrice: disgiunte / adiacenti / parziali / inclusa / identiche / singola notte | AD-3, AD-5 | **unit** | P0 | Combinatoria pura. Il posto giusto per essere esaustivi invece che rappresentativi. |
| 2.5-c | Solo `attiva` partecipa (`cancellata` e `rimossa_dal_feed` no) | AD-19 | unit + integration | P0 | La regola è unit; che il **chiamante** passi davvero solo le `attiva` è integration. Sono due difetti diversi. |
| 2.5-d | Due sovrapposte ⇒ **esattamente un** Conflitto `rilevato`; rieseguire non ne crea un secondo | FR-5, AD-5 | integration | P0 | L'idempotenza della rilevazione ripetuta è la proprietà che l'AC promette ("mai due aperti per la stessa coppia") e va provata sul percorso reale, non sulla funzione pura. |
| 2.5-e | Identità stabile con coppia **non ordinata**, imposta da un vincolo UNIQUE su forma canonica | AD-5 | integration | P0 | **→ §4-4.** È il punto esatto in cui nasce "due Conflitti per la stessa coppia": se la canonicalizzazione sta solo nel codice applicativo, la gara la aggira. |
| 2.5-f | **RACE-3** — 8 rilevazioni concorrenti sulla stessa coppia ⇒ un solo Conflitto aperto, mai 500 | AD-5 | **integration concorrente** | P0 | A3, ed è la terza occorrenza del medesimo difetto di famiglia in questo progetto. §6. |
| 2.5-g | Tre Prenotazioni sovrapposte a due a due ⇒ tre Conflitti (uno per coppia) | AD-5 | integration | P1 | **→ §4-5.** L'AC parla solo di "due Prenotazioni": che l'unità sia la coppia e non il gruppo è deducibile ma non scritto. |
| 2.5-h | Il Conflitto registra fonte e timestamp di sync di **ciascuna** Prenotazione coinvolta | FR-5, NFR-2 | integration | P0 | **→ §4-6** per la Prenotazione manuale, che un timestamp di sync non ce l'ha. È il dato che la Finestra di riconciliazione mostra (2.7-a): se è sbagliato qui, è sbagliato là. |
| 2.5-i | Una Prenotazione esce da `attiva` ⇒ Conflitto `decaduto`, tracciato, **distinto** da `gestito` | AD-5, AD-19 | integration | P0 | La distinzione fra i due stati è ciò che rende misurabile SM-C1: confonderli non rompe nulla oggi e rende inutilizzabile la metrica domani. |
| 2.5-j | `decaduto` non torna indietro da solo; se la sovrapposizione ricompare nasce un Conflitto **nuovo** | AD-5 | integration | P1 | Coerente con la riapertura post-`gestito` (2.7-e): la stessa filosofia applicata all'altra transizione. |
| 2.5-k | I `decaduto` mai `gestito` sono contabili da query, senza strumentazione separata (SM-C1) | AD-16 | integration | P2 | Se la metrica non è interrogabile ora, lo si scopre nell'Epic 3 quando serve. Costo oggi: una query in un test. |
| 2.5-l | Un Conflitto `rilevato` resta in evidenza finché non è gestito (nessun auto-nascondimento a tempo) | FR-6 | integration | P0 | Gemello di AD-8 ("nessun percorso di codice chiude da solo"): l'invariante è un'assenza di comportamento, e va asserita esplicitamente. |

**12 AC — P0: 9 · P1: 2 · P2: 1.**

### Story 2.6 — Notifiche di Conflitto (fondazione `notifiche`) ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.6-a | Notifica in-app + email via **job durevole** alla prima rilevazione; mai silenziosa | FR-5, NFR-3, AD-10 | integration | P0 | NFR-3 ha severità alta nel PRD. Il job è una riga in tabella: osservabile, deterministico, senza attese. |
| 2.6-b | Il testo contiene Struttura e intervallo date in formato it-IT ("Bologna Centro, 15-17 agosto") | NFR-9, UX-DR11 | **unit** | P1 | Il copy è funzione pura del dato; i formati italiani sono già centralizzati dalla 1.3. |
| 2.6-c | Handler **idempotente**: la riesecuzione at-least-once non produce una seconda email | AD-10 | integration | P0 | "At-least-once + idempotenza" è una coppia: testare solo la consegna lascia scoperto il doppione, che è il modo in cui una notifica utile diventa rumore. |
| 2.6-d | Crash/restart fra claim e invio ⇒ la notifica parte comunque | NFR-3, AD-10 | integration | P0 | È **la** promessa di NFR-3. Si simula terminando la transazione a metà, non spegnendo processi. |
| 2.6-e | Errore SMTP ⇒ retry con backoff; esaurimento ⇒ `failed` visibile, mai "inviata" ottimistica | AD-10, UX-DR7 | integration | P0 | Stessa famiglia di AD-8: nessuno stato di successo senza un esito reale. |
| 2.6-f | `notifiche` dipende solo in lettura da `identity`; **nessun** modulo dipende sincronicamente da `notifiche` | spine (grafo moduli) | **strutturale** | P0 | Classe "assenze": un import sbagliato non fallisce, tace, e si scopre quando l'Epic 3 prova a riusare il modulo. Una guardia sul grafo degli import costa millisecondi. |
| 2.6-g | Le preferenze di notifica dell'Host (1.3) sono rispettate | UX-DR15 | integration | P1 | Il pannello esiste dall'Epic 1 senza consumatori: questa è la prima Story in cui può essere ignorato in silenzio. |
| 2.6-h | La notifica parte **anche** per un Conflitto nato da inserimento manuale | FR-5, FR-7 | integration | P1 | **→ §4-10.** L'AC nomina solo la sincronizzazione: preso alla lettera, un Conflitto manuale non notifica. |
| 2.6-i | Nessun dato identità Ospite nel payload di eventi/job né nei log | AD-11, AD-17, NFR-16 | integration + unit (catalogo) | P0 | R2-O. I Feed portano nomi reali di persone: è la prima volta nel progetto che dati personali di terzi attraversano outbox e log. |
| 2.6-j | «Questa fondazione è riusata da Epic 3 ed Epic 5» | epics.md | **per ispezione** + SG | P2 | **Unico AC dell'Epic 2 che dichiaro non verificabile con un test dentro l'Epic 2**: è un'affermazione su codice futuro. Ciò che è verificabile oggi — l'interfaccia non conosce il dominio chiamante — lo copre 2.6-f. Lo scrivo invece di lasciarlo passare come coperto (nell'Epic 1 non è successo mai: teniamo il record e questa è l'unica eccezione). |

**10 AC — P0: 6 · P1: 3 · P2: 1.**

### Story 2.7 — Finestra di riconciliazione ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.7-a | Vista affiancata con Canale, Ospite, date e **timestamp di sync della fonte** per ciascuna | FR-6, NFR-2, UX-DR6 | integration + component | P0 | Il dato è server (2.5-h), la presentazione affiancata è client. Il valore di prodotto sta nel dichiarare il ritardo del feed, non nel layout. |
| 2.7-b | Nessuna scrittura automatica verso l'OTA | FR-6 Out of Scope | **SG-5** + integration | P0 | È un invariante negativo ("il sistema non fa mai X") su tutta la superficie del codice: solo una guardia strutturale lo impone. Un test funzionale può solo dire che *quel* percorso non lo fa. |
| 2.7-c | `rilevato → gestito` **solo** per azione esplicita dell'Host | FR-6, AD-5 | integration + strutturale | P0 | Gemello di AD-8. La lezione dell'Epic 1 è che gli invarianti "nessun percorso di codice fa X" si impongono, non si promettono. |
| 2.7-d | Il Conflitto `gestito` resta nello storico, mai cancellato | AD-5, AD-20 | integration + **SG-3** | P0 | Stesso presidio di 2.1-h/2.4-d: una sola guardia copre tre AC di tre Story diverse. |
| 2.7-e | Sovrapposizione persistente oltre la finestra dopo `gestito` ⇒ **nuovo** Conflitto collegato al precedente | AD-5, UJ-2 edge | integration | P0 | R2-K, e la ragione per cui il prodotto non si fida ciecamente della conferma umana. Il collegamento al precedente è ciò che distingue una riapertura da un duplicato. |
| 2.7-f | Finestra **configurabile**: cambiare il parametro cambia l'esito | G3-5, NFR-4 | integration | P0 | Modello del test 1.6 sulla soglia fiscale. Senza questo, "configurabile" è una parola nel documento. |
| 2.7-g | La riapertura **non** avviene prima della finestra | AD-5, SM-C1 | integration | P1 | La metà dimenticata di 2.7-e: riaprire subito è rumore, e il rumore è la counter-metrica del prodotto. |
| 2.7-h | Il trigger della riapertura esiste anche senza sync (Conflitto fra Prenotazioni manuali) | AD-5 | integration | P1 | **→ §4-7.** L'AC lega la riapertura ai "sync successivi": due manuali non ne hanno mai uno e la riapertura non scatterebbe mai. |
| 2.7-i | **RACE-4** — `gestito` dell'Host concorrente con `decaduto` da sync ⇒ stato finale deterministico, nessuna transizione persa | AD-5, AD-19 | **integration concorrente** | P1 | Non è un check-then-write classico, ma è una gara reale fra un'azione umana e il poller — e le due transizioni hanno significati opposti per SM-C1. |
| 2.7-j | Flusso completabile da tastiera + equivalenti testuali per screen reader | UX-DR10, NFR-8 | **e2e (E2E-4)** | P0 | Su un flusso modale l'ordine del focus, la trappola del focus e il **ritorno** del focus alla chiusura esistono solo nella pagina composta: un component test con il modale isolato è cieco a tutti e tre. |

**10 AC — P0: 7 · P1: 3 · P2: 0.**

### Story 2.8 — Contributo alla Dashboard ⛔

| ID | AC (sintesi) | Rif | Livello | Prio | Perché a questo livello |
| --- | --- | --- | --- | :---: | --- |
| 2.8-a | Badge "0 conflitti" / conteggio + link, con trattamento **testo + icona** | UX-DR2, UX-DR4 | component + e2e (axe) | P0 | Requisito di presentazione con una regola oggettiva (non solo colore): component lo verifica isolato, axe lo verifica in pagina. |
| 2.8-b | Il conteggio conta i `rilevato` (non `gestito`, non `decaduto`) ed è coerente col selettore Struttura | FR-6, UX-DR1 | integration | P0 | **→ §4-11.** Il conteggio è un derivato di dominio: sta all'API (AD-14). Se lo calcola il frontend, diverge dal calendario — che è esattamente 2.8-d. |
| 2.8-c | Un Conflitto `rilevato` resta a severità alta finché non è risolto | FR-6, UX §4.5 | component + integration | P0 | Il livello di severità è server-side per AD-14 (come `livello_urgenza`); la sua resa è component. |
| 2.8-d | "Dati aggiornati alle HH:MM" **coerente col calendario** | NFR-2, UX-DR6 | integration + **E2E-2** | P0 | Due superfici, un derivato, due query: è la definizione del difetto che solo l'e2e vede (§7). A livello API si verifica che la fonte del valore sia **una sola**. |
| 2.8-e | Stato vuoto rassicurante quando non ci sono Prenotazioni | UJ-1 edge, UX-DR2 | component | P1 | Variante di dato senza infrastruttura. |

**5 AC — P0: 4 · P1: 1 · P2: 0.**

### Riepilogo di copertura pianificata

| Story | AC tracciati | P0 | P1 | P2 | Livelli previsti |
| --- | :---: | :---: | :---: | :---: | --- |
| 2.1 Feed iCal + import on-demand | 16 | 12 | 4 | 0 | unit (corpus) + integration (DB e HTTP reali) + concorrenza + strutturale |
| 2.2 Poller durevole | 12 | 9 | 3 | 0 | integration (HTTP locale) + concorrenza + strutturale |
| 2.3 Calendario unificato | 9 | 5 | 4 | 0 | unit + integration + component + e2e |
| 2.4 Prenotazioni manuali | 7 | 5 | 2 | 0 | unit + integration |
| 2.5 Rilevazione Conflitti | 12 | 9 | 2 | 1 | unit (funzione pura) + integration + concorrenza |
| 2.6 Notifiche | 10 | 6 | 3 | 1 | unit + integration + strutturale (+1 per ispezione) |
| 2.7 Riconciliazione | 10 | 7 | 3 | 0 | integration + concorrenza + component + e2e (a11y) |
| 2.8 Dashboard | 5 | 4 | 1 | 0 | integration + component + e2e |
| **Totale Epic 2** | **81** | **57** | **22** | **2** | — |

Per confronto: l'Epic 1 ne aveva 48. L'aumento non è zelo — è la superficie: input esterni,
concorrenza in tre punti e due valori derivati con cache propria, tutti nello stesso Epic.

---

## 4. Ambiguità e AC non testabili come scritti — **per John, non per me**

Il mio confine: **non progetto il prodotto**. Qui elenco ciò che leggendo gli AC non riesco a
tradurre in un test senza inventare una decisione. Ogni voce ha una proposta, che è un
*suggerimento*, non una correzione applicata: `docs/epics.md` lo aggiorna John.

**Bloccanti per la Story 2.1** (vanno decise prima che Amelia scriva il codice):

1. **"Errore inline immediato" per un URL irraggiungibile (AC 2.1, 4ª clausola).**
   L'AC chiede un errore *immediato* su un fatto — l'irraggiungibilità — che si scopre
   **dentro un job asincrono** accodato dalla clausola precedente. Le due clausole della stessa
   Story si contraddicono nel tempo. Proposta: separare *validazione sincrona del formato*
   (errore inline sul campo, 422) da *esito di raggiungibilità* (stato di errore sulla Struttura
   entro il primo run, con testo esplicito). Senza questa distinzione non so cosa asserire in
   2.1-k/2.1-l.
2. **Comportamento del feed che "torna".** L'architettura dice che le OTA a volte
   omettono eventi temporaneamente (è la ragione stessa dell'append-preserving). Nessun AC dice
   cosa succede quando l'evento **ricompare**: la Prenotazione `rimossa_dal_feed` torna `attiva`
   (e quindi torna a generare Conflitti), oppure resta ferma? Le due scelte hanno conseguenze
   opposte su SM-1. Proposta: transizione di ritorno `rimossa_dal_feed → attiva` tracciata,
   con nuova valutazione dei Conflitti. Riguarda anche 2.2-k e il punto 3 qui sotto.
3. **Che cosa mostra una superficie che non ha MAI avuto un sync riuscito** (feed appena
   collegato, o sempre fallito). È il caso in cui la falsa sincronia fa il danno maggiore, e
   nessun AC lo copre. Proposta: stato esplicito ("mai sincronizzato" / "ultimo tentativo
   fallito alle HH:MM"), coerente con il `configurazione_non_disponibile` dell'Epic 1.

**Bloccanti per la Story 2.5** (la parte più delicata dell'Epic):

4. **La coppia del Conflitto è ordinata o no?** L'AC dice identità `(struttura_id, coppia
   di prenotazioni)` e "mai due Conflitti aperti per la stessa coppia". Se `(A,B)` e `(B,A)`
   sono due chiavi diverse, l'invariante è violabile senza violare la lettera dell'AC — ed è
   esattamente il modo in cui questi difetti nascono. Proposta: dichiarare la coppia **non
   ordinata**, canonicalizzata `(min, max)`, con vincolo UNIQUE nel DB (non solo nel codice:
   sotto concorrenza il codice perde, RACE-3).
5. **Tre Prenotazioni sovrapposte a due a due: tre Conflitti o uno?** L'AC parla solo
   di "due Prenotazioni sovrapposte". La coppia come unità è deducibile, non scritta. Impatta
   il conteggio del badge (2.8-b) e la misura di SM-1. Proposta: unità = coppia, tre Conflitti.
6. **Timestamp di sync per una Prenotazione manuale.** L'AC 2.5 chiede fonte e timestamp
   di sync "di ciascuna Prenotazione coinvolta", ma una Prenotazione manuale non ha un sync.
   La Finestra di riconciliazione (2.7-a) deve mostrare *qualcosa*. Proposta: Canale = "Manuale"
   e data di inserimento, con etichetta che dice che non è un dato sincronizzato — la falsa
   simmetria fra le due colonne sarebbe peggio dell'asimmetria.
7. **Il trigger della riapertura post-`gestito` non esiste per i Conflitti fra
   Prenotazioni manuali.** L'AC 2.7 lega la ri-verifica ai "sync successivi": due Prenotazioni
   manuali non ne avranno mai uno, quindi quel Conflitto non si riaprirà mai. Proposta: il
   trigger è la **rivalutazione della Struttura** (che avviene dopo ogni import *e* ogni
   inserimento manuale, come già dice AD-5), più un job durevole schedulato allo scadere della
   finestra — altrimenti la riapertura dipende dal fatto che passi di lì un altro evento.

**Decidibili durante l'Epic** (non bloccano il dispatch della 2.1):

8. **"Adattivo fino a 5 minuti in prossimità di check-in" (2.2)** non è quantificato:
   quante ore prima? Rispetto al check-in di quale Prenotazione? Proposta: due parametri di
   configurazione (`sync_intervallo_minuti`, `sync_intervallo_prossimita_minuti`,
   `sync_finestra_prossimita_ore`) e un AC riscritto in termini di parametri.
9. **"Alert interno dopo N fallimenti consecutivi" (2.2)** non ha né N né un artefatto
   osservabile: NFR-7 (osservabilità) è mappato sull'Epic 3, quindi oggi non c'è un canale di
   alert da verificare. È il punto **A10** della retrospettiva, ancora aperto. Proposta minima
   e verificabile subito: contatore `fallimenti_consecutivi` sul Feed + soglia configurabile +
   log strutturato con `host_id`/`feed_id` all'attraversamento della soglia. Se resta come
   scritto, l'AC 2.2-i non è verificabile e lo dichiaro tale al gate.
10. **La notifica per un Conflitto nato da inserimento manuale (2.6).** L'AC nomina solo
    "la prima sincronizzazione in cui è rilevato". Preso alla lettera, un Conflitto manuale non
    notifica — e FR-5 avrebbe un buco. Proposta: il trigger è la **prima rilevazione**, quale
    che sia l'origine.
11. **Il badge Conflitti e il selettore Struttura (2.8).** Il conteggio è globale o
    filtrato dal selettore trasversale (UX-DR1)? E include i `gestito` riaperti? Proposta:
    coerente con il selettore, conta i soli `rilevato` (un Conflitto riaperto **è** un
    `rilevato` nuovo, quindi rientra naturalmente).
12. **Prenotazioni non `attiva` nella griglia (2.3).** AD-19 dice che non partecipano ai
    Conflitti, non dice se si vedono. Farle sparire senza traccia contraddirebbe "archiviare,
    mai distruggere" agli occhi dell'Host, che ha visto quella prenotazione ieri.
13. **Ciclo di vita del `feed_ical` — nessun AC lo copre.** Cosa succede se l'Host
    cambia l'URL di un Feed collegato, o lo scollega? Le Prenotazioni importate restano (AD-20
    direbbe di sì), ma `(feed_id, ical_uid)` cambia significato. Non blocca la 2.1; va deciso
    prima che qualcuno lo implementi per intuizione.

**Nota di metodo.** Sette di questi tredici punti (1, 2, 3, 6, 7, 10, 12) hanno la stessa forma:
gli AC descrivono correttamente il **caso normale** e lasciano implicito il **ritorno dal caso
degradato** — il feed che torna, il sync mai riuscito, il Conflitto fra due Prenotazioni manuali,
la Prenotazione che esce da `attiva` ma resta sotto gli occhi dell'Host. Gli altri sei sono
parametri non quantificati (8, 9) o unità di misura non dichiarate (4, 5, 11, 13). Nessuno dei
tredici è un errore di scrittura: sono confini non esplorati. Trovarli adesso costa un giro di
documento; trovarli dopo costa un fix-batch — è precisamente il conto dell'Epic 1 (§3.6 della
retrospettiva: quattro batch reattivi contro uno pianificato).

---

## 5. Guardie strutturali — due esistenti, tre nuove

Sono la difesa più economica del progetto (girano in millisecondi) e coprono la classe
"assenze", dove sono finiti entrambi i P0 dell'Epic 1. Ogni allowlist è **esplicita e a sua
volta sorvegliata** da un test che la fa decadere se cambia la premessa (regola della libreria
di squadra).

**Esistenti — da estendere, non riscrivere:**

- `test_auth_convention.py` — ogni endpoint non pubblico richiede sessione. Copre i nuovi
  endpoint `calendario` per costruzione.
- `test_tenancy_convention.py` — `host_id` NOT NULL + FK su ogni tabella dati; repository di
  dominio con `host_id` in firma. Le sei nuove tabelle (`feed_ical`, `sync_run`, `prenotazione`,
  `ospite`, `conflitto`, `notifica`) ci ricadono automaticamente. **Criterio di gate: nell'Epic 2
  l'allowlist della guardia non cresce.** Se una nuova tabella chiede l'esenzione, serve la
  motivazione scritta e un test che faccia decadere l'esenzione.

**Nuove, proposte con questo test design:**

- **SG-3 — `test_append_preserving_convention.py` (P0, AD-4/AD-19/AD-20).** Nessun modulo di
  dominio esegue `DELETE`/`session.delete()` su `prenotazione`, `conflitto`, `sync_run`,
  `feed_ical`, `ospite`; nessuna FK verso queste tabelle dichiara `ondelete="CASCADE"`.
  Copre in un colpo 2.1-h, 2.4-d e 2.7-d, e soprattutto copre le Story che non ho ancora letto:
  è la guardia che il punto 4 dell'incarico chiede ("l'import non cancella mai è un invariante
  di dato, non un dettaglio di UI"). Modello: `test_tenancy_convention.py`.
- **SG-4 — `test_verita_temporale_convention.py` (P0, NFR-2/AD-4).** Ogni schema di risposta API
  che espone dati derivati da Feed (Prenotazione, Conflitto, griglia calendario, riepilogo
  Dashboard) porta il campo dell'**ultimo sync riuscito**. Cammina gli schemi e fallisce quando
  qualcuno aggiunge una superficie nuova senza il campo — che è il modo realistico in cui NFR-2
  si perde: non per errore, per aggiunta. È la richiesta esplicita del punto 5 dell'incarico.
- **SG-5 — `test_nessuna_scrittura_ota.py` (P0, AD-5 / FR-6 Out of Scope).** L'unico client HTTP
  in uscita è quello del Feed e usa **solo GET**; nessun modulo effettua richieste non-GET verso
  host esterni. Trasforma "il sistema non scrive mai verso le OTA" da promessa architetturale a
  invariante imposto. Copre 2.7-b su tutta la superficie, non solo sul percorso testato.
- **SG-6 (estensione di `test_conventions.py`, P0)** — il grafo delle dipendenze fra moduli:
  `notifiche` non importa moduli di dominio; nessun modulo importa `notifiche` in modo sincrono.
  Copre 2.6-f, ed è l'unico modo di verificare oggi la parte verificabile di 2.6-j.

**Costo stimato complessivo:** quattro file di test, nessuna dipendenza nuova, tempo di CI
trascurabile. **Valore:** coprono 9 AC di 5 Story diverse e, soprattutto, coprono il codice che
verrà scritto dopo di loro.

---

## 6. Concorrenza — il capitolato dei test di gara (azione A3, obbligatoria)

Nell'Epic 1 lo stesso difetto check-then-write è stato trovato **due volte** (G-2 alla Story
1.2, F-1 alla Story 1.4). La seconda volta è la prova che una regola non scritta non vale.
Qui è scritta.

**Il pattern, non negoziabile:**

- **8 thread** (non 2: con due contendenti l'interleaving spesso non si presenta e il test passa
  a vuoto — lezione della libreria di squadra);
- **`threading.Barrier` fra i client**, **mai** dentro il codice sotto test: se la correzione è
  basata su lock, un barrier interno manda il test in deadlock invece che in rosso, mascherando
  l'esito;
- **il test deve essere visto rosso prima**: si accieca il pre-check applicativo (come in
  `test_identity_auth.py` per G-2) e si verifica che senza la difesa il difetto si riproduce.
  Un test di gara verde che non ha mai visto la gara è peggio di nessun test, perché chiude la
  questione per tutti quelli che verranno dopo;
- l'esito atteso non è "nessun errore": è **la proprietà di dominio** (una sola riga, un solo
  Conflitto) **e** l'assenza di 500 (un `IntegrityError` non intercettato è un difetto, non una
  difesa).

| ID | Percorso | Story | Proprietà da preservare | Prio |
| --- | --- | --- | --- | :---: |
| **RACE-1** | Upsert `(feed_id, ical_uid)` | 2.1 | Una sola Prenotazione per chiave naturale; il perdente aggiorna, non duplica né esplode | P0 |
| **RACE-2** | Claim del Feed da parte del poller | 2.2 | Un solo sync in esecuzione per Feed; nessun doppio fetch; nessun tick perso | P0 |
| **RACE-3** | Creazione del Conflitto per una coppia | 2.5 | **Esattamente un** Conflitto aperto per `(struttura, coppia canonica)` | P0 |
| **RACE-4** | `gestito` (umano) vs `decaduto` (sync) sullo stesso Conflitto | 2.7 | Stato finale deterministico, entrambe le transizioni tracciate, nessuna persa | P1 |

**Nota su RT-3 — il momento di rivalutazione è arrivato.** Il rischio tracciato RT-3 dell'Epic 1
diceva: *«il namespace `1001` degli advisory lock va rivisto al secondo advisory lock introdotto
nel codice»*. RACE-2 e RACE-3 sono con ogni probabilità quel secondo e terzo uso. **Richiesta ad
Amelia:** se la difesa scelta è `pg_advisory_xact_lock`, il namespace va assegnato esplicitamente
(non `1001`) e la convenzione va **scritta** — un commento in un solo punto e una costante
condivisa, non tre numeri sparsi. Se la difesa è invece un vincolo UNIQUE + `ON CONFLICT`
(preferibile dove possibile: il DB serializza meglio di noi), RT-3 resta dov'è e lo si dice.

---

## 7. e2e — quattro spec, ognuno con il suo difetto nominato (azione A4)

**Regola di ammissione** (retrospettiva §3.3, già in libreria di squadra): *un e2e si giustifica
nominando la classe di difetti di cui è l'unico testimone. Se non sai nominarla, quel test va
scritto più in basso.* Applicata a priori, non a posteriori.

| ID | Spec | Difetto che **solo** questo livello vede | Perché i livelli sotto sono ciechi |
| --- | --- | --- | --- |
| **E2E-1** | `e2e/calendario-sync.spec.ts` | Un import che cambia le Prenotazioni non aggiorna la griglia: la mutazione invalida la cache `prenotazioni` ma non quella `calendario` (query separata sullo stesso derivato) | Nei test di componente gli hook sono mockati: **la cache non esiste nel loro mondo**. È letteralmente il difetto della Story 1.6, su una superficie nuova. |
| **E2E-2** | `e2e/conflitto-dashboard.spec.ts` | Risolvere un Conflitto aggiorna il pannello Conflitti ma **non** il badge in Dashboard; oppure "dati aggiornati alle HH:MM" diverge fra le due superfici | Due superfici, due query, un solo derivato. L'integration prova che l'API dà il valore giusto; il component prova che ciascuna superficie lo mostra. Nessuno dei due prova che **restano d'accordo dopo una mutazione**. |
| **E2E-3** | `e2e/feed-collegamento.spec.ts` | Il percorso UJ-1 completo (collega feed → job → progresso → griglia popolata): lo stato "Importazione in corso…" resta appeso perché il polling del progresso non riparte, o la griglia non si popola a job concluso | La transizione asincrona job→UI attraversa backend, worker e cache client. Nessun livello inferiore contiene tutti e tre. È anche l'unico spec che esercita davvero il worker in condizioni reali. |
| **E2E-4** | `e2e/riconciliazione-a11y.spec.ts` | Finestra di riconciliazione da sola tastiera: ordine del focus, trappola del focus nel modale, **ritorno** del focus alla chiusura; axe serious/critical = 0 sulla pagina composta (calendario + modale) | Un component test monta il modale isolato: non ha la pagina sotto, quindi non può vedere né il ritorno del focus né i conflitti di contrasto/ARIA con il resto della pagina. UX-DR10 è P0 per NFR-8. |

**Cosa NON diventa e2e, esplicitamente:** varianti di formato iCal (unit), matrice fusi
orari/DST (unit), gare (integration), `ETag`/304/redirect/timeout (integration), transizioni di
stato dei Conflitti (integration), idempotenza delle notifiche (integration). Tutto ciò che ha
un livello più basso che lo vede, ci resta.

**Rivalutazione di RT-4 (richiesta esplicita dell'incarico).** RT-4 diceva che la copertura e2e
era volutamente stretta e andava rivalutata *«quando l'Epic 2 introduce il calendario/sync
iCal»*. **Rivalutato oggi, esito: la strategia resta stretta e si estende di quattro spec, non di
più.** Da 10 spec dell'Epic 1 a ~14. La ragione per cui non si allarga di più è che l'Epic 2
aggiunge molta superficie ma **una sola classe di difetti nuova che vive nella colla** (il
derivato con cache propria, che qui compare due volte: 2.3 e 2.8): tutto il resto — parsing,
rete, concorrenza, stati — ha un livello inferiore che lo vede meglio, più in fretta e in modo
esaustivo. **RT-4 si chiude come rischio tracciato dell'Epic 1** e la regola di ammissione
diventa un criterio di gate (§9). Prossima rivalutazione: Epic 3, quando i countdown di scadenza
introdurranno derivati dipendenti dal tempo — una classe diversa da questa.

---

## 8. Fixture e dati di test (vincoli dell'Epic 2)

- **Corpus iCal versionato** in `backend/tests/fixtures/ical/`: un file per variante, con un
  `README.md` che dice cosa dimostra ciascuno. Minimo: Airbnb tipico, Booking tipico, all-day
  (`VALUE=DATE`), datetime con `TZID`, datetime in UTC (`Z`), confine dell'ora legale, righe
  folded CRLF, BOM, non-ASCII in `SUMMARY`, `UID` duplicato nel medesimo feed, VEVENT
  `STATUS:CANCELLED`, feed **valido e vuoto** (0 VEVENT — il caso che si confonde con l'errore),
  feed troncato a metà, feed oltre la soglia di dimensione.
- **NFR-16 rafforzato — la regola nuova dell'Epic 2.** I Feed reali contengono **nomi di persone
  reali**. Se l'esercizio con un feed reale viene autorizzato (raccomandazione A11 della
  retrospettiva), il suo output **non entra nel repository come fixture**: le fixture si scrivono
  a mano con nomi inventati e dominio `example.com`. È il primo Epic in cui questa regola può
  essere violata in buona fede, copiando un file "solo per riprodurre un bug".
- **Confine di rete stub-ato al trasporto**, mai al service: server HTTP locale nel test
  (`http.server` o equivalente già disponibile), con controllo su status, header, ritardo e
  dimensione della risposta. Vale per 2.1-i/l/m e 2.2-e/f/g.
- **Nessun dato Ospite in log, eventi, outbox** (AD-11/AD-17): asserito da 2.6-i, non lasciato
  alla disciplina.
- **DB reale in CI** (`HOSTPILOT_TEST_DB_REQUIRED=1`): invariato, lo skip resta un errore.
- **Isolamento**: le sei tabelle nuove vanno aggiunte a `TABELLE_DA_SVUOTARE` in `conftest.py`.
  Dimenticarne una produce flakiness intermittente, che è il debito peggiore: **criterio di
  gate** (§9).
- **Determinismo temporale**: `now` iniettato ovunque (poller, finestra di riapertura, etichette
  di sync); **mai** `sleep` per attendere una scadenza o un job. La 2.7 introduce una finestra di
  24h: se per testarla serve aspettare, il design è sbagliato, non il test.

---

## 9. Criteri di gate per le Story dell'Epic 2

Una Story è candidabile al merge umano quando:

1. **Tutti gli AC P0 della Story hanno un test verde** al livello indicato in §3.
2. **CI verde su tutti e cinque i check obbligatori**: `backend`, `frontend`, `e2e`,
   `api-contract` e **SonarCloud Quality Gate**. Zero test flaky.
3. **Ogni percorso check-then-write introdotto dalla Story ha il suo test di gara** (§6), ed è
   stato **visto rosso** prima di essere visto verde. Non basta che esista.
4. **Ogni nuovo spec e2e nomina il difetto che solo lui vede** (§7), nel titolo del test o in un
   commento in testa al file. Uno spec senza difetto nominabile va riscritto più in basso.
5. **Guardie strutturali verdi**, comprese le nuove di §5 quando la Story le rende applicabili;
   **l'allowlist della guardia di tenancy non è cresciuta** senza motivazione scritta e
   sorvegliata.
6. **Ogni superficie nuova che mostra dati da Feed espone l'ultimo sync riuscito** (SG-4).
7. **Nessun dato reale** nei fixture; nessun campo Ospite in log/eventi/outbox.
8. **Le tabelle nuove sono in `TABELLE_DA_SVUOTARE`** e le migrazioni Alembic sono forward-only.
9. **Se la Story tocca `.github/workflows/` o i lockfile**: checklist di hardening applicata
   (azione A2 — action pinnate al SHA, `npm ci --ignore-scripts`, installazione solo da lockfile,
   blocco `permissions:` minimo).
10. **I finding aperti che toccano il perimetro della Story sono chiusi** o esplicitamente
    accettati dall'umano con motivazione (azione A9: i P2 senza perimetro vanno nell'unico
    fix-batch pianificato a metà Epic, non in quattro reattivi).

Il verdetto di gate (PASS / CONCERNS / FAIL / WAIVED) è una **raccomandazione**: la decisione di
rilascio resta all'umano (Fahad). **Il verdetto del Test Architect è richiesto su ogni PR
dell'Epic — Story e fix-forward, senza eccezioni** (decisione di Fahad del 25/07).

---

## 10. Matrice di tracciabilità — **da compilare a chiusura dell'Epic 2**

Scheletro predisposto ora, di proposito vuoto: si compila quando le Story sono consegnate.
Serve perché a fine Epic la domanda «resta debito?» abbia una risposta verificabile da chi non
c'era, non un'opinione.

### 10.1 Requisiti funzionali

| Req | Story | Livello di verifica previsto | Evidenza (suite) | Stato |
| --- | --- | --- | --- | :---: |
| **FR-3** Import Feed iCal | 2.1, 2.2 | unit (corpus) + integration (HTTP + DB reali) | — | ⛔ |
| **FR-4** Calendario unificato | 2.3 | unit + integration + component + e2e | — | ⛔ |
| **FR-5** Rilevazione Conflitti | 2.5, 2.6 | unit (pura) + integration + concorrenza | — | ⛔ |
| **FR-6** Finestra di riconciliazione | 2.7, 2.8 | integration + component + e2e (a11y) | — | ⛔ |
| **FR-7** Prenotazioni manuali | 2.4 | unit + integration | — | ⛔ |

### 10.2 Invarianti architetturali esercitati

| AD | Invariante | Story | Presidio previsto | Stato |
| --- | --- | --- | --- | :---: |
| AD-3 | Semantica temporale unica | 2.1, 2.3, 2.4, 2.5 | `core/date_range` riusato, mai reimplementato (unit + review) | ⛔ |
| AD-4 | Import idempotente, append-preserving | 2.1, 2.2 | RACE-1 + **SG-3** + **SG-4** | ⛔ |
| AD-5 | Conflitti: rilevazione pura, risoluzione umana | 2.5, 2.7 | RACE-3 + **SG-5** + test "nessun percorso auto-`gestito`" | ⛔ |
| AD-10 | Scheduling durevole | 2.2, 2.6 | RACE-2 + riavvio worker + idempotenza handler | ⛔ |
| AD-13 | Notifiche mai drop silenzioso | 2.6 | crash/restart + `failed` visibile | ⛔ |
| AD-14 | Contratto API, derivati server-side | 2.3, 2.8 | CI `api-contract` + E2E-2 | ⛔ |
| AD-17 | Catalogo eventi, payload minimi | 2.4, 2.5, 2.6 | `test_events.py` esteso | ⛔ |
| AD-18 | Un solo modulo scrittore | 2.1 | guardia strutturale | ⛔ |
| AD-19 | Ciclo di vita Prenotazione e propagazione | 2.1, 2.4, 2.5 | **SG-3** + transizioni + `prenotazione.cessata` | ⛔ |
| AD-2 | Tenancy | tutte | `test_tenancy_convention.py` (allowlist invariata) | ⛔ |

### 10.3 Requisiti non funzionali

| NFR | Presidio previsto | Stato |
| --- | --- | :---: |
| **NFR-1** Affidabilità della sincronizzazione | RACE-1/2, append-preserving, resilienza al fallimento OTA | ⛔ |
| **NFR-2** Verità temporale | **SG-4** + ultimo sync **riuscito** + stato "mai sincronizzato" | ⛔ |
| **NFR-3** Affidabilità delle notifiche | job durevole + crash/restart + idempotenza | ⛔ |
| **NFR-6** Sicurezza | validatore URL (SSRF), limite di dimensione della risposta | ⛔ |
| **NFR-8** Accessibilità | axe serious/critical = 0 sulle superfici nuove + E2E-4 (tastiera) | ⛔ |
| **NFR-9** Localizzazione | formati it-IT nel testo delle notifiche e nella griglia | ⛔ |
| **NFR-14** Controllo accessi | test cross-tenant sulle sei entità nuove | ⛔ |
| **NFR-16** Nessun dato reale | corpus iCal scritto a mano; output di feed reali mai committato | ⛔ |

### 10.4 Registro dei finding dell'Epic 2

| ID | Prio | Sintesi | Origine | Chiuso da | Test di regressione |
| --- | :---: | --- | --- | :---: | --- |
| — | — | _(nessun finding aperto: l'Epic non è iniziato)_ | — | — | — |

Convenzione: un finding si dichiara chiuso **solo** con la PR che lo chiude **e** il nome del
test di regressione. Senza il test nominato, la riga resta aperta.

---

## 11. Rischi tracciati dell'Epic 1 che scadono qui

Le quattro voci `RT-n` erano rischi accettati con un **momento** di rivalutazione, non con una
data. Tre di quei momenti cadono dentro l'Epic 2.

| ID | Rischio (Epic 1) | Momento previsto | Stato oggi |
| --- | --- | --- | --- |
| **RT-3** | Namespace `1001` degli advisory lock | «al secondo advisory lock» | **Scade in questo Epic** (§6): RACE-2/RACE-3 sono il secondo e terzo uso. Richiesta ad Amelia: namespace esplicito + convenzione scritta, oppure difesa via vincolo UNIQUE e RT-3 resta dov'è. |
| **RT-4** | Copertura e2e volutamente stretta | «quando l'Epic 2 introduce calendario/sync iCal» | **Rivalutato e chiuso** (§7): +4 spec mirati, regola di ammissione promossa a criterio di gate. Prossima rivalutazione: Epic 3. |
| **RT-1** | Advisory `npm audit` transitivi in `next` | «al prossimo bump di `next`» | Non scade da solo. Se l'Epic 2 bumpa `next`, va rivisto — e `npm audit fix --force` resta da rifiutare (proporrebbe un downgrade major). |
| **RT-2** | Freno per origine su `request.client.host` | «alla prima messa in esercizio dietro proxy» | Non scade nell'Epic 2 salvo che A11 (esercizio in ambiente reale) porti l'app dietro un proxy: in quel caso la lista dei proxy fidati va configurata insieme. |

**Su A11 (esercizio con un feed reale), che non è mio da decidere.** La raccomandazione della
retrospettiva resta valida e la sostengo: nessuna fixture riproduce fedelmente formati, fusi e
latenze di un feed vero. Ma va detto con precisione **cosa** compra e cosa no: un esercizio
manuale su un feed reale è un test **esplorativo** — trova varianti di formato che non avevamo
immaginato, e ogni variante trovata diventa una fixture nuova (scritta a mano, §8). **Non**
sostituisce nessuna riga di §3 e non entra nei criteri di gate: un esercizio non ripetibile non
è un presidio. Decisione e ambiente restano di Fahad.

---

_Documento aperto per l'Epic 2. §3 è il contratto di copertura, §4 è la palla che torna a John,
§10 si compila a Epic concluso. Ogni modifica passa da una PR: il merge è di Fahad._

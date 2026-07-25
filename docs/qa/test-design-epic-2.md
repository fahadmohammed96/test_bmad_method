---
title: 'Test Design — Epic 2 (Calendario unificato e anti double-booking)'
status: 'aperto — contratto di copertura dell''Epic 2, consegnato PRIMA della Story 2.1'
phase: '4 · Implementation — gate di qualità (Murat, Test Architect)'
epic: 'Epic 2 · Story 2.1 → 2.8'
created: 2026-07-25
author: Murat — Master Test Architect
scope: 'Epic 2, Story 2.1 → 2.8'
inputDocuments:
  - docs/epics.md (Epic 2, Story 2.1–2.8, acceptance criteria Given/When/Then)
  - docs/architecture.md §3 + docs/architecture/architecture-HostPilot-2026-07-24/ARCHITECTURE-SPINE.md (AD-3, AD-4, AD-5, AD-10, AD-13, AD-14, AD-17, AD-18, AD-19)
  - docs/prd.md (FR-3…FR-7; NFR-1, NFR-2, NFR-3, NFR-16)
  - docs/ux-spec.md (UJ-1, UJ-2, §5.1, §6; UX-DR1, UX-DR4, UX-DR6, UX-DR10, UX-DR12)
  - docs/qa/test-design-epic-1.md (formato, §7.7 RT-4)
  - docs/retrospettive/epic-1.md §3, §5, §6 (azioni A1, A3, A4, A10, A11)
  - docs/product-status-epic-1.md (cosa esiste a valle dell'Epic 1)
  - main @ 7eac12e (codice e suite reali, non i documenti di piano)
  - _bmad/_memory/test-architect-sidecar/memories.md + knowledge/test-architect/lezioni.md (libreria di squadra)
related:
  - docs/qa/test-design-epic-1.md (Epic 1 chiuso a debito zero, §7.6)
---

> **Come si legge questo documento.** È il **contratto di copertura** dell'Epic 2, scritto
> **prima** della prima riga di codice (azione **A1** della retrospettiva). Non è una suite:
> dice *cosa* testare, a *quale livello*, con *quale priorità*, e traccia ogni acceptance
> criteria verso un invariante architetturale. Se stai per aprire una PR dell'Epic 2, le due
> sezioni che ti riguardano sono **§3** (la tua Story) e **§6** (i criteri di gate).
> **§7 resta vuota fino alla chiusura dell'Epic**: è la matrice di tracciabilità, e si compila
> alla fine, non adesso.

# Test Design — Epic 2

Piano di test **essenziale e risk-based** per l'Epic 2 (Calendario unificato e anti
double-booking, Story 2.1 → 2.8). Documento **nuovo**, non un'estensione di
`docs/qa/test-design-epic-1.md`, che è chiuso: stesso scheletro, contenuto indipendente,
numerazione dei finding che riparte.

**Perché esiste prima del codice.** La retrospettiva dell'Epic 1 (§3.1) misura la causa a
monte: **cinque finding su nove** vengono dalle due sole Story consegnate prima che il test
design esistesse. Le quattro Story scritte con il piano già in mano ne hanno prodotti quattro
in totale. Questo documento rimuove quella causa, non celebra un rito.

**E perché proprio in questo Epic.** L'Epic 2 è quello in cui il prodotto guadagna o perde la
fiducia dell'Host. Introduce per la prima volta: una **dipendenza di rete esterna** (oggi il
backend non ha una sola riga di codice HTTP in uscita — verificato su `main`), un **job
periodico** che lavora da solo, e una **rilevazione automatica** il cui falso negativo non è un
difetto cosmetico ma una **doppia prenotazione ospitata** (SM-1). Il costo di un difetto qui si
paga su un Ospite reale davanti a una porta.

> **Principio guida:** la profondità del test scala con il rischio (probabilità × impatto).
> Preferire sempre il livello più basso possibile (unit > integration > e2e). Le API sono
> cittadini di prima classe. Nessun dato reale di Ospiti nei fixture (NFR-16). Nessuna chiamata
> di rete reale in unit e integration.

**Convenzione degli ID di questo Epic.** Mantengo la convenzione della sidecar (`G-n` gap da
test design o review retroattiva, `F-n` finding di cross-review, `C-n` finding di
copertura/CI), **prefissata con l'Epic**: `E2-G1`, `E2-F1`, `E2-C1`. Il prefisso non è
pedanteria: senza di esso `G-1` dell'Epic 2 e `G-1` dell'Epic 1 sono indistinguibili in un
commento, e `G2-x` — la forma che verrebbe naturale — collide con le `[DECISIONE G2-A…E]` del
PRD. Un finding si chiude solo con **la PR che lo chiude e il nome del test di regressione**.

---

## 1. Valutazione del rischio (Epic 2)

Punteggio = probabilità × impatto. **Alto → P0** (obbligatorio al gate), **Medio → P1**,
**Basso → P2**.

| ID | Area di rischio | Prob. | Impatto | Punteggio | AD/NFR | Livello test prioritario |
| --- | --- | :---: | :---: | :---: | --- | --- |
| **R2-A** | **Conflitto non rilevato** — sovrapposizione che non produce un Conflitto (falso negativo): semantica di overlap sbagliata, insieme di partenza incompleto, rilevazione non rieseguita dopo un import | Media | **Critico** | **Alto** | AD-3, AD-5, FR-5, SM-1 | unit (funzione pura) + integration |
| **R2-B** | **Import non idempotente** — il ri-sync duplica o perde Prenotazioni; `(feed_id, ical_uid)` non è un vincolo del DB ma un check applicativo | Media | **Critico** | **Alto** | AD-4, NFR-1 | integration + **test di gara** |
| **R2-C** | **Cancellazione per errore di trasporto** — una risposta troncata, vuota o parziale ma con esito 200 fa marcare `rimossa_dal_feed` prenotazioni che nel feed ci sono ancora, e i Conflitti aperti su di esse `decadono` | **Alta** | **Critico** | **Alto** | AD-4, AD-19, NFR-1 | unit (parser) + integration |
| **R2-D** | **URL del Feed = input non fidato dereferenziato dal server** — SSRF verso rete interna/metadata cloud, redirect verso indirizzi privati, risposta illimitata, nessun timeout | Media | **Critico** | **Alto** | NFR-6, AD-2 | unit + integration |
| **R2-E** | **Identità del Conflitto non stabile** — due Conflitti aperti per la stessa coppia (import concorrenti, coppia non canonicalizzata `(A,B)` ≠ `(B,A)`), oppure Conflitto perso | Media | Alto | **Alto** | AD-5 | integration + **test di gara** |
| **R2-F** | **Semantica temporale** — `[check_in, check_out)` violato sui dati reali: `DTEND` inclusivo/esclusivo, `VALUE=DATE` vs `DATETIME`, `TZID` e cambio ora legale, `DTEND` assente con `DURATION` | **Alta** | Alto | **Alto** | AD-3, AD-4 | unit (tabella di casi) |
| **R2-G** | **Formati iCal reali fuori dall'alfabeto immaginato** — line folding, CRLF/LF, BOM, non-ASCII, `UID` mancante o duplicato, `RRULE`, `STATUS:CANCELLED`, VEVENT malformato | **Alta** | Alto | **Alto** | AD-4, NFR-1 | unit (parser, confini testuali) |
| **R2-H** | **Falsa sincronia** — il timestamp mostrato avanza su un run fallito, oppure l'etichetta manca su una superficie con dati da Feed: il prodotto dichiara certo ciò che non lo è | Media | Alto | **Alto** | NFR-2, UX-DR6 | integration + e2e |
| **R2-I** | **Notifica di Conflitto persa o duplicata** — consegna at-least-once senza handler idempotente, o emissione ad ogni sync invece che alla prima rilevazione | Media | Alto | **Alto** | AD-10, AD-13, NFR-3 | integration + **test di gara** |
| **R2-J** | **Stati di Prenotazione e Conflitto divergenti** — `attiva/cancellata/rimossa_dal_feed` e `rilevato/gestito/decaduto` interpretati diversamente da rilevazione, Dashboard e riconciliazione; `decaduto` confuso con `gestito` (inquina SM-C1) | Media | Alto | **Alto** | AD-19, AD-5, AD-16 | integration |
| **R2-K** | **Tenancy sulle nuove tabelle** — `feed_ical`, `sync_run`, `prenotazione`, `ospite`, `conflitto` senza `host_id`, o repository che interroga senza filtro | Bassa | **Critico** | **Alto** | AD-2, NFR-14 | **guardia strutturale** (già attiva) |
| **R2-L** | **Chiamata di rete reale dai test** — nessun presidio oggi impedisce a un test di raggiungere Internet: suite non deterministica, lenta, e che può colpire un servizio terzo | **Alta** | Medio | **Medio** | policy | **guardia strutturale** (da creare) |
| **R2-M** | **Colla fra livelli con cache propria** — griglia calendario, etichetta "aggiornati alle HH:MM" e badge Conflitti in Dashboard sono query client distinte su valori derivati dalla stessa sorgente: una mutazione che invalida solo una lascia le altre ferme | **Alta** | Medio | **Medio** | retro §3.3, AD-14 | **e2e** (unico testimone) |
| **R2-N** | **Contratto API in deriva** — nuovi endpoint calendario/conflitti senza rigenerazione di OpenAPI + client TS | Bassa | Medio | **Basso** | AD-14 | contract (CI `api-contract`) |
| **R2-O** | **Coda `job` satura o iniqua** — il poller (N Host × M Feed, tick da 15') condivide la coda con le notifiche; `claim_due` prende 10 job per giro e `job` non ha `host_id` | Bassa | Medio | **Basso** | AD-10 | integration (regime) |
| **R2-P** | **a11y sulle nuove superfici** — griglia calendario e Finestra di riconciliazione sono le prime superfici complesse; UX-DR10 richiede completabilità da tastiera sul flusso a più alta posta | Media | Medio | **Medio** | NFR-8, UX-DR10 | e2e (axe) + component |

**Lettura.** Le aree Alte sono nove: **quattro sono nuove per il progetto** (R2-C, R2-D, R2-F,
R2-G — tutte figlie della dipendenza di rete esterna e del formato iCal) e cinque sono classi
già viste nell'Epic 1 applicate a un dominio con impatto più alto. **R2-C è l'unica ad avere
probabilità Alta e impatto Critico insieme**: un'implementazione ingenua di "l'evento è sparito
dal feed ⇒ `rimossa_dal_feed`" la contiene per costruzione, ed è la ragione per cui apro
`E2-G3` in §4 prima ancora che il codice esista.

---

## 2. Strategia per livello (piramide)

### 2.1 Unit — la base larga, e in questo Epic anche la più preziosa

Logica pura senza I/O. Nell'Epic 2 è dove vive quasi tutto il rischio davvero pericoloso:

- **Normalizzatore VEVENT → `DateRange`** (AD-3, AD-4): la tabella di casi di §5.3. È il singolo
  punto in cui `[check_in, check_out)` incontra la realtà di un formato che non abbiamo scritto
  noi. Costa millisecondi e copre R2-F e R2-G interamente.
- **Parser iCal**: fold delle righe, CRLF/LF, BOM, non-ASCII, `UID` mancante/duplicato,
  `STATUS:CANCELLED`, `RRULE`, VEVENT troncato. Include i **confini testuali** raccomandati
  dalla retrospettiva (§3.2, classe "input fuori dall'alfabeto immaginato": è esattamente la
  classe che ha prodotto F-3 nell'Epic 1).
- **Rilevazione dei Conflitti** (AD-5): è dichiarata *funzione pura* dell'insieme delle
  Prenotazioni `attiva`. Se è pura, si testa senza DB e senza rete: insieme in ingresso,
  insieme di Conflitti in uscita. Se **non** si riesce a testarla così, la purezza è violata e
  quello è già un finding.
- **Validazione dell'URL del Feed** (R2-D): schema ammesso, risoluzione DNS, blocco di
  loopback/privati/link-local, politica sui redirect.
- **Intervallo adattivo del poller** (2.2): funzione da `(now, prossimo check-in)` a intervallo.

### 2.2 Integration (service/repository + PostgreSQL 18 reale)

Il cuore operativo, come nell'Epic 1: DB **reale**, mai SQLite — le proprietà che contano
(`FOR UPDATE SKIP LOCKED`, indici UNIQUE parziali, enum Postgres, `timestamptz`) sono
specifiche di Postgres. Qui vivono: upsert idempotente, ciclo di vita `sync_run`, transizioni
di stato di Prenotazione e Conflitto, riprogrammazione del poller, consegna delle notifiche,
tenancy.

**Il client HTTP è iniettato, sempre.** In integration il confine di rete è un *fake* che
restituisce fixture versionate, codici di stato, `ETag`, risposte troncate e timeout simulati.
Nessuna dipendenza da un servizio esterno, nessun `sleep` per attendere una latenza.

### 2.3 Contract

Due contratti distinti, e vanno tenuti distinti:

1. **API interna** (AD-14) — il job CI `api-contract` rigenera `backend/openapi.json` e
   `frontend/lib/api/schema.d.ts` e fallisce sul `git diff`. Vale per ogni Story che tocca
   l'API. È già attivo e va mantenuto verde.
2. **Formato iCal in ingresso** — questo è nuovo. Non c'è un fornitore con cui firmare un
   contratto: le OTA cambiano il loro export quando vogliono. Il surrogato è un **corpus di
   fixture versionate** (§5.2) che rappresenta le forme note; ogni forma nuova incontrata in
   esercizio entra nel corpus come fixture prima di essere corretta nel codice. È un contratto
   *osservato*, non *concordato*, e va scritto così nel documento per non spacciarlo per una
   garanzia che non abbiamo (vedi **A11** in §8.3).

### 2.4 Test di gara obbligatori — azione A3

**Regola dell'Epic 2: ogni percorso che legge-poi-scrive con un vincolo nasce con un test di
gara.** Nell'Epic 1 lo stesso identico difetto (check-then-write senza serializzazione) è stato
trovato **due volte a tre Story di distanza** (G-2 sulla registrazione, F-1 sul cap Strutture):
la seconda volta è la prova che una regola non scritta non vale.

**Forma richiesta** — è quella già in repo (`backend/tests/test_strutture.py::TestCapAtomico`,
righe 97-154), da riusare verbatim nella struttura:

- **8 contendenti**, non 2: con due thread una finestra critica stretta spesso non si presenta
  e il test passa a vuoto (lezione già in libreria di squadra, voce 2026-07-25).
- **`threading.Barrier(8, timeout=10)`** allineato **fra i client**, mai dentro il codice sotto
  test: se la correzione è basata su lock, un barrier interno manda il test in deadlock invece
  che in rosso e maschera l'esito.
- **Una `Session(pg_engine)` fresca per thread**, `barriera.wait()` **dentro** il blocco di
  sessione.
- **Esiti contati** (`esiti.count("creata") == 1`) **più una ri-query di post-condizione** sullo
  stato finale.
- **Il test va visto rosso prima di essere verde**: rimuovendo il vincolo/lock, deve fallire.
  Un test di gara che non ha mai visto la gara è peggio di nessun test, perché chiude la
  questione per tutti quelli che verranno dopo.

**Percorsi check-then-write dell'Epic 2 — elenco obbligatorio, non esemplificativo:**

| # | Story | Percorso | Cosa deve dimostrare il test |
| :---: | :---: | --- | --- |
| **A3-1** | **2.1** | **Upsert idempotente su `(feed_id, ical_uid)`** | Due sync dello stesso Feed in gara (8 thread, stesso `ical_uid`): **esattamente una** riga `prenotazione` per uid, nessuna `IntegrityError` che diventa 500. Il vincolo deve essere **UNIQUE nel DB** con `ON CONFLICT DO UPDATE` — a decidere è il constraint, non il pre-check applicativo (è la lezione di G-2: il pre-check va *accecato* nel test per dimostrare che il DB regge da solo) |
| **A3-2** | **2.2** | **Claim del poller** | 8 worker che chiamano `claim_due` sullo stesso job di sync: **uno solo** lo esegue (`FOR UPDATE SKIP LOCKED`), gli altri sette non ottengono nulla e non bloccano |
| **A3-3** | **2.2** | **Bootstrap/riprogrammazione periodica per Feed** | `assicura_sync_periodico` è un `SELECT`-poi-`schedule`: è un check-then-write. 8 thread al bootstrap ⇒ **un solo** job in coda per Feed. Nota: il precedente `assicura_purge_periodico` (Epic 1) ha la stessa forma e nessun test di gara; con N Feed la probabilità di collisione cresce e va coperta qui |
| **A3-4** | **2.5** | **Identità del Conflitto — «mai due aperti per la stessa coppia»** | 8 rilevazioni concorrenti sulla stessa Struttura (due Feed della stessa Struttura che concludono l'import insieme): **esattamente un** Conflitto `rilevato` per coppia. Richiede un **indice UNIQUE parziale** su `(struttura_id, prenotazione_min_id, prenotazione_max_id) WHERE stato = 'rilevato'` **con ordinamento canonico della coppia**: senza canonicalizzazione `(A,B)` e `(B,A)` sono due righe e il vincolo non morde |
| **A3-5** | **2.6** | **Notifica alla prima rilevazione** | «È già stata notificata?» seguito da «invia» è un check-then-write. 8 esecuzioni concorrenti dello stesso job ⇒ **una sola** notifica; e un secondo sync che rileva lo stesso Conflitto **non** rinotifica |
| **A3-6** | **2.7** | **Riapertura dopo `gestito`** | «Esiste già un nuovo Conflitto collegato?» poi «aprilo»: 8 sync concorrenti oltre la finestra ⇒ **un solo** nuovo Conflitto collegato al precedente, mai una catena di duplicati |

I primi tre nomi (A3-1, A3-2, A3-4) sono quelli richiesti esplicitamente dall'azione A3 della
retrospettiva; A3-3, A3-5 e A3-6 li aggiungo perché hanno la stessa identica forma e la regola
dice *ogni* check-then-write, non *quelli citati come esempio*.

### 2.5 e2e — elenco chiuso, azione A4

**Regola dell'e2e giustificato** (retrospettiva §3.3, già in libreria di squadra): *un e2e si
giustifica solo nominando la classe di difetti di cui è l'unico testimone*. Se non sai nominarla,
quel test va scritto più in basso. La copertura la danno i livelli sotto, a costo minore; l'e2e
paga solo sulla **colla fra livelli**, che ogni livello che la mocka è cieco per costruzione a
vedere.

**Questo è l'elenco chiuso degli spec e2e ammessi nell'Epic 2.** Aprire un e2e non in elenco
richiede una motivazione scritta nella PR che nomini il difetto, e passa dal verdetto.

| Spec | Story | Il difetto che **solo** questo spec vede | Stato |
| --- | :---: | --- | :---: |
| `frontend/e2e/calendario.spec.ts` | **2.3** | **Coerenza fra cache correlate sulla stessa superficie.** Griglia delle Prenotazioni ed etichetta «dati aggiornati alle HH:MM» sono **due query client distinte** su valori derivati dalla stessa sorgente. Una mutazione (Prenotazione manuale inserita, sync concluso) che invalida solo la cache delle prenotazioni lascia l'etichetta ferma su un orario vecchio — e l'etichetta ferma è **esattamente la falsa sincronia che NFR-2 vieta**. I test di componente non possono vederlo: lì gli hook sono mockati, quindi la cache non esiste nel loro mondo. È la classe che ha prodotto il difetto della Story 1.6 | ammesso |
| `frontend/e2e/dashboard-conflitti.spec.ts` | **2.8** | **Coerenza di cache fra superfici diverse.** Il badge Conflitti in Dashboard è una **terza** query sullo stesso derivato. Risolvere un Conflitto nella Finestra di riconciliazione (2.7) deve azzerare il badge **senza reload**: la mutazione avviene su una superficie e il derivato vive su un'altra. Nessun livello sotto attraversa quel confine | ammesso |
| `frontend/e2e/riconciliazione-tastiera.spec.ts` | **2.7** | **Completabilità da tastiera di un flusso modale** (UX-DR10): focus trap, ordine di tabulazione, ritorno del focus alla chiusura, equivalenti testuali. È il flusso a più alta posta del prodotto e il requisito **esiste solo nel browser** | **ammesso condizionatamente** — vedi sotto |
| *(estensione dei baseline esistenti, non spec nuovi)* | 2.3, 2.8 | Baseline **axe serious/critical = 0** estesa alle due nuove superfici, con `violazioniGravi(page)` già in `frontend/e2e/axe-utils.ts` | ammesso |

**La condizione su `riconciliazione-tastiera.spec.ts`.** L'e2e è giustificato **se** la Finestra
di riconciliazione è realizzata come **modale**: focus trap e ritorno del focus sono difetti che
vivono nel browser e nessun livello sotto li vede. Se invece è una **pagina** con navigazione
normale, il difetto scende di livello e la copertura corretta è un test di componente con
`@testing-library/user-event` (**oggi non installato**: va aggiunto, ~1 dipendenza di sviluppo).
La scelta la fa il disegno della 2.7, non questo documento: chi la implementa dichiara quale dei
due casi è, e il livello segue. Quello che **non** è ammesso è coprirla "per ispezione".

**Cosa NON è ammesso come e2e in questo Epic**, per essere espliciti: import iCal end-to-end
contro un feed reale (è A11, non un test automatico — vedi §8.3); il ciclo del poller (job
durevoli, si testano in integration); l'idempotenza dell'upsert; la rilevazione dei Conflitti;
qualunque asserzione di regola di dominio già coperta al livello sotto.

**Rivalutazione di RT-4** (rischio tracciato alla chiusura dell'Epic 1: *«copertura e2e
volutamente stretta — rivalutare quando l'Epic 2 introduce calendario/sync iCal»*). Il momento
di rivalutazione è arrivato ed è questo. **Esito: la strategia si conferma, il perimetro si
allarga in modo limitato e nominato.** Da 4 spec a 6-7 (i 4 esistenti + 2 ammessi + 1
condizionato), ciascuno con il difetto che solo lui vede scritto qui sopra. La ragione per cui
l'allargamento è giustificato *ora* e non prima è che l'Epic 2 introduce i **primi valori
derivati con cache propria distribuiti su più superfici**, che è precisamente la classe che RT-4
aveva individuato come motivo di rivalutazione. RT-4 non viene riaperto nel documento dell'Epic
1 (che è chiuso): la rivalutazione era prevista *fuori* da quel documento e il suo esito vive
qui. **RT-4 si considera esaurito**, sostituito dall'elenco chiuso di questa sezione.

Vincolo operativo, valido per tutti: `fullyParallel: false`, `workers: 1`, `retries: 1` in CI —
la flakiness è debito tecnico critico. Un e2e che ritenta per abitudine non è copertura, è
rumore.

### 2.6 Strutturale (meta-test) — la difesa più economica che abbiamo

Girano in millisecondi e coprono la classe **"assenze"**, cioè quella dove sono finiti entrambi
i P0 dell'Epic 1 (G-3, C1). Un pezzo mancante non fallisce: tace. Solo una review o un meta-test
lo vede.

**Già attive, e da mantenere verdi** (nessuna modifica richiesta, si auto-arruolano):

- `backend/tests/test_auth_convention.py` — ogni endpoint fuori dall'allowlist `PUBBLICI`
  dipende da `get_current_host`. **Ogni nuovo endpoint `/api/v1/calendario…`,
  `/api/v1/feed…`, `/api/v1/conflitti…` fallisce qui se non dichiara la sessione.** L'allowlist
  è verificata per uguaglianza esatta: non si può allargare in silenzio.
- `backend/tests/test_tenancy_convention.py` — ogni tabella dati fuori allowlist ha `host_id`
  NOT NULL **con FK verso `host`**, e ogni metodo pubblico dei repository di dominio richiede
  `host_id` in firma. **`app/calendario/repository.py` viene arruolato automaticamente**
  (`pkgutil.iter_modules` su `app`): nessuna modifica al test, ma ogni metodo pubblico deve
  avere `host_id`. Copre R2-K.

**Da creare nell'Epic 2** (sono finding aperti in §4, qui la forma):

| ID | Guardia | Cosa impedisce | Story |
| --- | --- | --- | :---: |
| **GS-1** | **Isolamento di rete nella suite** — fixture `autouse` che fallisce se un test unit/integration apre una socket verso l'esterno | Un test che raggiunge Internet: non deterministico, lento, e che colpisce un servizio terzo. Oggi **nulla** lo impedisce (R2-L) | 2.1 |
| **GS-2** | **Completezza di `TABELLE_DA_SVUOTARE`** — confronto fra `Base.metadata.tables` e la lista di TRUNCATE, con allowlist esplicita per i dati di riferimento (`regione`) | Una tabella nuova dimenticata nella lista: i test si sporcano fra loro e il fallimento appare **altrove**, giorni dopo. L'Epic 2 aggiunge 5-6 tabelle in un colpo solo | 2.1 |
| **GS-3** | **Grafo delle dipendenze fra moduli** — nessun modulo importa `repository` o `models` di un altro modulo; **nessun modulo importa `notifiche` in modo sincrono** | La regola AD-1/spine oggi è solo scritta. L'Epic 2 è il primo con un grafo non banale (`calendario → strutture`, `notifiche → identity`, `calendario -. job .-> notifiche`) | 2.6 |
| **GS-4** | **Nessuna scrittura verso l'OTA** — il client HTTP in uscita ammette **solo** `GET` verso URL di Feed | «Il sistema non scrive mai verso le OTA» (AD-5, FR-6 Out of Scope, Non-Goal §8) è un invariante di prodotto imposto oggi solo dalla buona volontà. Una guardia lo rende strutturale | 2.7 |
| **GS-5** | **Tipi di evento e job a catalogo** — ogni tipo usato dal modulo `calendario`/`notifiche` è in `core/events.py` | Tipi inventati ad hoc (AD-17). Il pattern esiste già: `test_purge_sessioni.py::test_il_tipo_di_job_e_a_catalogo` | 2.1 |

GS-5 è la più economica: il `Catalog` **valida già** nomi e chiavi di payload a runtime, quindi
il meta-test è una riga. GS-3 è la più preziosa: senza di essa il grafo dello spine è una
raccomandazione.

---

## 3. Copertura per Story (AC → livello → priorità)

Legenda livelli: **U** unit · **I** integration (PG reale) · **C** contract (CI) · **E** e2e ·
**S** strutturale (meta-test) · **Cmp** component (Vitest).
`†` = AC **derivato** da un AD/NFR o dal contesto tecnico, non scritto verbatim in `epics.md`:
è comunque vincolante al gate, ed è la parte che l'Epic 1 ha imparato a non lasciare implicita.
`⚡` = ha un **test di gara obbligatorio** (§2.4).

### Story 2.1 — Collegamento di un Feed iCal e import on-demand

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Collegare un URL valido accoda **subito** un job di sync prioritario, con progresso visibile («Importazione in corso…» → «Importate N prenotazioni — ultimo aggiornamento HH:MM») | AD-4, AD-10, UJ-1 | I + Cmp | **P0** |
| 2 | ⚡ **Upsert idempotente su chiave naturale `(feed_id, ical_uid)`**: rieseguire il sync non duplica né perde Prenotazioni. Vincolo UNIQUE nel DB, non pre-check applicativo | AD-4, NFR-1 | I (**gara A3-1**) | **P0** |
| 3 | L'import **non cancella mai**: un evento scomparso dal feed porta la Prenotazione a `rimossa_dal_feed` | AD-4, AD-19 | I | **P0** |
| 4 | † **«Scomparso» ≠ «non ricevuto»**: `rimossa_dal_feed` si applica **solo** dopo un parse completo e validato (feed terminato con `END:VCALENDAR`). Risposta troncata, vuota o parziale con esito 200 ⇒ run fallito, **nessuna** transizione di stato | AD-4, AD-19, NFR-1 | U + I | **P0** |
| 5 | URL non valido o irraggiungibile ⇒ **errore inline immediato** sul campo/Struttura, mai un fallimento silenzioso | FR-3, UX §5.1 | U + I | **P0** |
| 6 | † **URL come input non fidato**: schema `http/https` soltanto; blocco di loopback, indirizzi privati, link-local e endpoint di metadata cloud (anche **dopo** redirect); timeout di connessione e lettura; **cap sulla dimensione** della risposta; nessun credenziale nell'URL riflessa in log o errori | NFR-6, AD-2, AD-16 | U + I | **P0** |
| 7 | Ogni run scrive un record `sync_run` (esito, timestamp), anche quando fallisce | AD-4, NFR-2 | I | **P0** |
| 8 | † Le Prenotazioni importate sono associate alla **Struttura corretta** e ogni nuova tabella (`feed_ical`, `sync_run`, `prenotazione`, `ospite`, `conflitto`) porta `host_id` NOT NULL + FK | AD-2, AD-4, NFR-14 | I + **S** (guardia esistente) | **P0** |
| 9 | † **Normalizzazione VEVENT → `DateRange`**: `VALUE=DATE` vs `DATETIME`, `TZID` e cambio ora legale, `DTEND` esclusivo, `DTEND` assente con `DURATION`, date invertite. Tabella di casi in §5.3 | AD-3, AD-4 | U | **P0** |
| 10 | † Tipo di job e tipi di evento del modulo `calendario` dichiarati nel catalogo `core/events.py`, payload di **soli identificatori scalari** (mai nomi di Ospiti) | AD-17, NFR-11 | U + **S** (GS-5) | P1 |
| 11 | † **Nessuna chiamata di rete reale** nella suite: client HTTP iniettato, guardia di isolamento attiva | NFR-16, policy | **S** (GS-1) | **P0** |

**Nota di sequenza.** La 2.1 è la Story che posa le fondamenta di rete e di schema dell'intero
Epic: GS-1, GS-2 e GS-5 vanno consegnate **qui**, non rimandate. Nell'Epic 1 la guardia di
tenancy (G-3) è stata rimandata di due Story ed è costata un finding P0.

### Story 2.2 — Poller periodico di sincronizzazione durevole e resiliente

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Ogni Feed è sincronizzato a **intervallo configurabile** (default G3-5: 15') come **job durevole**, mai un timer solo in-memory | AD-10, NFR-1 | I | **P0** |
| 2 | ⚡ † Bootstrap e riprogrammazione periodica **idempotenti**: un solo job in coda per Feed, anche dopo riavvio del worker e anche sotto concorrenza | AD-10 | I (**gara A3-3**) | **P0** |
| 3 | ⚡ † Claim concorrente: un solo worker esegue il sync di un dato Feed (`FOR UPDATE SKIP LOCKED`) | AD-10 | I (**gara A3-2**) | **P0** |
| 4 | `ETag` / `If-Modified-Since` evitano scaricamenti inutili | AD-4 | I (HTTP fake) | P1 |
| 5 | † Un **304 Not Modified** non tocca alcuna Prenotazione e **non** marca nulla `rimossa_dal_feed`; il `sync_run` è comunque scritto come riuscito | AD-4, NFR-1, NFR-2 | I | **P0** |
| 6 | Un fallimento temporaneo dell'OTA lascia **intatti** i dati già importati (import append-preserving) | NFR-1, AD-4 | I | **P0** |
| 7 | Il fallimento produce un **errore visibile sulla Struttura**, non silenzioso | FR-3, NFR-1 | I + Cmp | P1 |
| 8 | **Alert interno dopo N fallimenti consecutivi** — N configurabile, mai hardcoded | AR-10, NFR-1 | I | P1 — **dipende da A10, §8.2** |
| 9 | Ogni superficie con dati da Feed espone il timestamp dell'**ultimo sync riuscito**; su un run fallito il timestamp **non avanza** | NFR-2, UX-DR6 | I + **E** (`calendario.spec.ts`) | **P0** |
| 10 | Intervallo **adattivo** fino a 5' in prossimità di un check-in (default G3-5) | AD-10, G3-5 | U | P2 |
| 11 | † Backoff e `max_attempts`: un Feed permanentemente rotto **non blocca** gli altri Feed né la coda; l'esaurimento dei tentativi è uno stato visibile, non un silenzio | AD-10, NFR-1 | I | P1 |

### Story 2.3 — Calendario unificato multi-Struttura

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Griglia (mensile/settimanale) che aggrega Prenotazioni di **tutte** le Strutture e i Canali, con distinzione visiva per Canale | FR-4 | Cmp + E | P1 |
| 2 | Ogni Prenotazione mostra **Canale d'origine, Struttura, date e Ospite** | FR-4 | I (API) + Cmp | P1 |
| 3 | Il selettore Struttura filtra fra vista aggregata e singola **senza cambiare schermata** | UX-DR1 | Cmp | P1 |
| 4 | **«dati aggiornati alle HH:MM»** sempre visibile per i dati da Feed — **etichetta persistente**, mai un tooltip nascosto | NFR-2, UX-DR6 | Cmp + **E** | **P0** |
| 5 | I dati derivati di dominio (stati, conteggi) arrivano dall'API; il frontend li **presenta**, mai li ricalcola | AD-14 | **C** (`api-contract`) + **S** | **P0** |
| 6 | † **Coerenza fra cache correlate**: una mutazione della sorgente (Prenotazione manuale, sync concluso) aggiorna **sia** la griglia **sia** l'etichetta del timestamp | retro §3.3, NFR-2 | **E** (unico testimone) | **P0** |
| 7 | † Tenancy: il calendario di un Host **non mostra mai** Prenotazioni di un altro Host (404/vuoto, mai fuga) | AD-2, NFR-14 | I | **P0** |
| 8 | † a11y: baseline **axe serious/critical = 0** sulla nuova superficie | NFR-8 | **E** (axe) | **P0** |
| 9 | Layout responsive, densità 1-3 Strutture senza degrado | UX-DR12 | Cmp | P2 |
| 10 | † Formati italiani sulla griglia (gg/mm/aaaa) dal modulo `lib/formati.ts` centralizzato | NFR-9, UX-DR11 | U + Cmp | P1 |

### Story 2.4 — Inserimento manuale di Prenotazioni

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | La Prenotazione manuale è creata in stato **`attiva`** e **partecipa** alla rilevazione dei Conflitti | FR-7, AD-19, AD-5 | I | **P0** |
| 2 | Una manuale che si sovrappone a una da Feed **genera un Conflitto** | FR-7 → FR-5 | I | **P0** |
| 3 | Una manuale **non si cancella fisicamente**: passa a `cancellata` ed emette `prenotazione.cessata` | AD-19, AD-20 | I | **P0** |
| 4 | † `prenotazione.cessata` è a catalogo con payload di soli identificatori | AD-17 | U | P1 |
| 5 | † Una manuale **non appartiene a nessun Feed**: il vincolo UNIQUE `(feed_id, ical_uid)` non deve impedirne l'inserimento né collassare più manuali in una sola riga | AD-4 | I | P1 |
| 6 | † Validazione delle date con `DateRange` (`check_out > check_in`); errore 422 `problem+json`, mai 500 | AD-3, AD-14 | U + I | P1 |
| 7 | † Tenancy: si crea una Prenotazione manuale **solo** su Strutture del proprio Host | AD-2, NFR-14 | I | **P0** |
| 8 | † Una Struttura **`archiviata`** non accetta nuove Prenotazioni manuali e i suoi Feed smettono di sincronizzare | AD-20, FR-1 | I | P1 |

### Story 2.5 — Rilevazione dei Conflitti

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | La rilevazione è una **funzione pura** dell'insieme delle Prenotazioni `attiva`, rieseguita dopo ogni import e ogni inserimento manuale — testabile senza DB e senza rete | AD-5 | U | **P0** |
| 2 | ⚡ Due Prenotazioni sovrapposte generano **esattamente un** Conflitto `rilevato`, con identità stabile `(struttura_id, coppia)` — **mai due aperti per la stessa coppia, mai Conflitti persi** | FR-5, AD-5 | U + I (**gara A3-4**) | **P0** |
| 3 | † La **coppia è canonicalizzata**: `(A,B)` e `(B,A)` sono la stessa identità. Vincolo imposto da un **indice UNIQUE parziale** su stato `rilevato`, non dall'ordine in cui arrivano | AD-5 | U + I | **P0** |
| 4 | † Sovrapposizione = intersezione **non vuota** di intervalli **semiaperti** (AD-3): `check_out` di una uguale a `check_in` dell'altra **non è** un Conflitto (il turnover dello stesso giorno è normale) | AD-3, AD-5 | U | **P0** |
| 5 | Il Conflitto registra **fonte e timestamp di sincronizzazione** di ciascuna Prenotazione coinvolta | FR-5, NFR-2 | I | **P0** |
| 6 | Se una delle due esce da `attiva` (`cancellata`, `rimossa_dal_feed`) il Conflitto passa a **`decaduto`** — transizione **di sistema**, tracciata, **distinta da `gestito`**, mai una cancellazione | AD-5, AD-19, AD-20 | I | **P0** |
| 7 | `decaduto` alimenta la misura di SM-C1 ed è distinguibile da `gestito` negli eventi di dominio | AD-5, AD-16 | I | P1 |
| 8 | Un Conflitto `rilevato` resta **in evidenza in Dashboard** finché non è gestito | FR-6 | I (API) + E (2.8) | P1 |
| 9 | † **Tre o più Prenotazioni mutuamente sovrapposte**: il criterio va **scritto e testato**. Con identità per coppia, 3 sovrapposte ⇒ **3 Conflitti**; qualunque sia la scelta, deve essere deterministica e non produrre né duplicati né buchi | AD-5 | U | **P0** |
| 10 | † La rilevazione è **scopata alla Struttura**: mai un Conflitto fra Prenotazioni di Strutture diverse, nemmeno dello stesso Host | AD-3, AD-5, AD-2 | U + I | **P0** |
| 11 | † Dopo un import **fallito o parziale** la rilevazione **non** produce falsi `decaduto` (dipende da 2.1 §4) | AD-4, AD-5 | I | **P0** |
| 12 | † `decaduto` (e gli stati Prenotazione `attiva/cancellata/rimossa_dal_feed`) sono **registrati nel Glossario** — readiness **R-2**, owner John: oggi il letterale vive solo negli AD | coerenza documentale | ispezione | P2 |

### Story 2.6 — Notifiche di Conflitto (in-app + email) — fondazione `notifiche`

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Alla prima rilevazione parte una notifica (in-app + email) via **job durevole**, mai silenziosa | FR-5, NFR-3, AD-10 | I | **P0** |
| 2 | ⚡ † La notifica parte alla **prima** sincronizzazione in cui il Conflitto emerge, **non a ogni sync** | FR-5, UJ-2 | I (**gara A3-5**) | **P0** |
| 3 | ⚡ Consegna **at-least-once** con **handler idempotente**: nessuna notifica persa per restart/crash, nessun doppione per ritentativo | AD-10, NFR-3 | I (**gara A3-5**) | **P0** |
| 4 | `notifiche` dipende **solo in lettura** da `identity`; **nessun modulo dipende sincronicamente** da `notifiche` (solo via job/eventi) | spine, AD-1 | **S** (GS-3) | **P0** |
| 5 | Le **preferenze di notifica** dell'Host (Story 1.3, FR-20) sono rispettate | FR-20, FR-5 | I | P1 |
| 6 | † Il payload dell'evento/job **non** trasporta dati dell'Ospite: soli identificatori; il testo della notifica si compone alla consegna leggendo lo stato corrente | AD-17, NFR-11 | U + I | P1 |
| 7 | Un fallimento del canale lascia il job **ritentabile**, mai marcato «inviata» | AD-13, NFR-3 | I | **P0** |
| 8 | † L'esaurimento dei tentativi produce uno stato **visibile** (`failed` osservabile), non un silenzio | AD-10, NFR-3 | I | **P0** |
| 9 | † **Nessun invio reale** nei test: canale email iniettato, guardia di isolamento di rete attiva (GS-1) | NFR-16, policy | **S** | **P0** |

**Nota di sequenza.** La 2.6 è la fondazione `notifiche` riusata da Epic 3 ed Epic 5. Il
*testable consequence* di FR-5 «l'Host riceve una notifica alla prima sincronizzazione in cui il
Conflitto emerge» è verificabile **solo quando la 2.6 esiste**: fino ad allora quell'AC della
2.5 resta scoperto e va dichiarato tale, non dato per buono.

### Story 2.7 — Finestra di riconciliazione del Conflitto

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Le due Prenotazioni sono mostrate **affiancate** con Canale, Ospite (se noto), date e **timestamp di sincronizzazione della fonte** («Airbnb — sincronizzato alle 14:32») | FR-6, NFR-2, UX-DR6 | I (API) + Cmp | **P0** |
| 2 | Istruzioni guidate passo-passo per bloccare le date sull'altro Canale; **il sistema non esegue scritture automatiche sull'OTA** | FR-6 Out of Scope, Non-Goal §8 | I + **S** (GS-4) | **P0** |
| 3 | `rilevato → gestito` **solo per azione esplicita dell'Host** — nessun percorso di codice ci arriva da solo | AD-5, FR-6 | I | **P0** |
| 4 | Il Conflitto resta nello **storico**, mai cancellato | AD-5, AD-20 | I | **P0** |
| 5 | ⚡ Se la sovrapposizione **persiste** oltre una finestra configurabile dopo `gestito` (default G3-5: 24h) si apre un **nuovo** Conflitto **collegato al precedente** | AD-5, UJ-2 edge | I (**gara A3-6**) | **P0** |
| 6 | La finestra di ri-verifica è **configurazione**, non una costante nel codice | NFR-4, AD-9 | I | P1 |
| 7 | L'intero flusso è **completabile da tastiera** e ha equivalenti testuali per screen reader | UX-DR10, NFR-8 | **E** (condizionato, §2.5) **o** Cmp | **P0** |
| 8 | † Tenancy: non si gestisce il Conflitto di un altro Host | AD-2, NFR-14 | I | **P0** |
| 9 | † Gestire un Conflitto già `gestito` o già `decaduto` è **idempotente o rifiutato esplicitamente**, mai una seconda transizione silenziosa | AD-5 | I | P1 |

### Story 2.8 — Contributo alla Dashboard — riepilogo calendario e stato Conflitti

| # | AC (sintesi) | AD/FR | Livello | Prio |
| :---: | --- | --- | --- | :---: |
| 1 | Badge di stato Conflitti con trattamento **testo + icona, mai solo colore**; contrasto ≥ 4.5:1 | UX-DR2, UX-DR4, NFR-8 | Cmp + **E** (axe) | **P0** |
| 2 | «0 conflitti» quando pulito; **conteggio e link** quando ci sono Conflitti `rilevato` | UX-DR2, FR-6 | Cmp | P1 |
| 3 | Un Conflitto `rilevato` è evidenziato con **severità alta** finché non risolto (mai auto-nascosto) | FR-6, UX §4.5 | Cmp + E | P1 |
| 4 | «dati aggiornati alle HH:MM» **coerente con il calendario** | NFR-2, UX-DR6 | **E** | **P0** |
| 5 | † **Coerenza di cache fra superfici**: risolvere un Conflitto nella Finestra di riconciliazione azzera il badge in Dashboard **senza reload** | retro §3.3 | **E** (unico testimone) | **P0** |
| 6 | † Il conteggio è calcolato **lato server** ed esposto come campo API, mai ricalcolato dal frontend | AD-14 | I + **S** | **P0** |
| 7 | † Tenancy sul conteggio: il badge conta **solo** i Conflitti del proprio Host | AD-2, NFR-14 | I | **P0** |

### Riepilogo della copertura pianificata

| Story | AC tracciati | P0 | P1 | P2 | di cui `†` derivati | test di gara |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| 2.1 Feed iCal e import on-demand | 11 | 10 | 1 | 0 | 6 | A3-1 |
| 2.2 Poller periodico | 11 | 6 | 4 | 1 | 5 | A3-2, A3-3 |
| 2.3 Calendario unificato | 10 | 5 | 4 | 1 | 5 | — |
| 2.4 Prenotazioni manuali | 8 | 4 | 4 | 0 | 5 | — |
| 2.5 Rilevazione Conflitti | 12 | 9 | 2 | 1 | 6 | A3-4 |
| 2.6 Notifiche di Conflitto | 9 | 7 | 2 | 0 | 5 | A3-5 |
| 2.7 Finestra di riconciliazione | 9 | 7 | 2 | 0 | 3 | A3-6 |
| 2.8 Dashboard Conflitti | 7 | 5 | 2 | 0 | 4 | — |
| **Totale Epic 2** | **77** | **53** | **21** | **3** | **39** | **6** |

**Nessun AC è privo di livello e di priorità.** Era il buco esatto che l'azione A1 chiude: nel
piano dell'Epic 1 gli AC derivati non erano tracciati, e cinque dei nove finding sono nati lì.
Metà degli AC di questo Epic (39 su 77) sono derivati da un AD o da un NFR e **non** compaiono
verbatim in `epics.md`: se non li si scrive qui, nessuno li scrive.

---

## 4. Gap di copertura e finding aperti

Rilievi **di progettazione**, aperti prima che il codice esista. Non sono difetti trovati in
review: sono presidi mancanti o trappole note che l'implementazione incontrerebbe per
costruzione. Sono **proposte ad Amelia**; io porto test, fixture e configurazione di qualità, le
entità applicative restano di sua competenza.

- **E2-G1 — (P0, test-infrastructure) — Nessun isolamento di rete nella suite.** Oggi nulla
  impedisce a un test di aprire una connessione verso Internet: fino all'Epic 1 non serviva
  (zero codice di rete in `backend/app`, verificato). Dall'Epic 2 in poi un fake HTTP
  dimenticato produce una suite non deterministica che colpisce un servizio di terzi, e il
  fallimento appare come flakiness. → **Guardia GS-1**: fixture `autouse` che fallisce su
  socket in uscita verso host non consentiti; client HTTP iniettato per costruzione (parametro
  del service, non import globale). **Da consegnare con la 2.1.**

- **E2-G2 — (P0, sicurezza NFR-6) — L'URL del Feed è un input non fidato che il server
  dereferenzia (SSRF).** L'Host incolla un URL e il **worker** lo scarica: è la definizione di
  SSRF. Superfici da chiudere e da testare: schema ammesso (`http`/`https` soltanto, mai
  `file`/`gopher`/`ftp`); blocco di loopback, reti private, link-local e **endpoint di metadata
  cloud**, valutato **dopo ogni redirect** e non solo sull'URL iniziale; limite al numero di
  redirect; timeout di connessione **e** di lettura; **cap sulla dimensione** della risposta
  (un feed da 2 GB non deve esaurire la memoria del worker); credenziali eventualmente presenti
  nell'URL mai riflesse in log, errori o `problem+json`. Il precedente in repo è
  `importa_comuni.py`, che valida il percorso **prima** di toccare il filesystem: qui vale lo
  stesso principio sulla rete. → Test unit sulla validazione + integration sul percorso di
  fetch. **Da consegnare con la 2.1.**

- **E2-G3 — (P0, correttezza AD-4/NFR-1) — «Scomparso dal feed» va distinto da «non
  ricevuto».** La regola append-preserving dice: evento scomparso ⇒ `rimossa_dal_feed`.
  Un'implementazione ingenua la applica a *tutto ciò che non è nel corpo scaricato*. Ma un
  corpo può essere **troncato** (connessione chiusa a metà, `Content-Length` non rispettato),
  **vuoto con esito 200**, o **parziale** — e in quel caso il sistema marcherebbe `rimossa_dal_feed`
  prenotazioni vive, facendo **`decadere` i Conflitti aperti su di esse** (AD-19 → AD-5). È la
  catena che trasforma un errore di trasporto in una **doppia prenotazione non segnalata**:
  probabilità alta, impatto critico (R2-C), e non produce alcun errore visibile. → La
  transizione si applica **solo** dopo un parse **completo e validato** (feed chiuso da
  `END:VCALENDAR`, conteggio VEVENT coerente); ogni altro esito è un run **fallito** che non
  tocca lo stato. Test: feed troncato a metà VEVENT, feed vuoto con 200, feed con solo
  l'intestazione ⇒ **nessuna** transizione di stato, `sync_run` fallito, dati intatti.
  **Da consegnare con la 2.1.**

- **E2-G4 — (P1, test-infrastructure) — `TABELLE_DA_SVUOTARE` è una stringa scritta a mano.**
  In `backend/tests/conftest.py` la lista di TRUNCATE è una stringa manuale. L'Epic 2 aggiunge
  cinque-sei tabelle in un colpo solo: una dimenticata sporca i test fra loro e il fallimento
  compare **altrove**, spesso giorni dopo, come flakiness. → **Guardia GS-2**: confronto fra
  `Base.metadata.tables` e la lista, con allowlist esplicita per i dati di riferimento
  (`regione`) **a sua volta sorvegliata** — le allowlist sono il punto in cui le guardie muoiono
  in silenzio. **Da consegnare con la 2.1.**

- **E2-G5 — (P1, test-coverage) — L'ambiente e2e non avvia il worker.** `playwright.config.ts`
  avvia backend e frontend, **non** il processo worker: negli e2e i job durevoli **non girano
  mai**. Nell'Epic 1 non mordeva (nessun AC dipendeva da un job osservabile in UI). Nell'Epic 2
  ne dipendono almeno tre: import on-demand con progresso (2.1), poller (2.2), notifica (2.6).
  Senza una decisione, quegli AC finiscono coperti «per ispezione» proprio al livello che
  dovrebbe dimostrarli. → Opzioni, in ordine di costo crescente: **(a)** non osservarli in e2e
  e coprirli in integration, seminando lo stato finale via API — **raccomandata**, coerente con
  l'elenco chiuso di §2.5; **(b)** un tick di worker invocabile da un endpoint interno protetto
  (esiste già il pattern `X-Admin-Token` usato da `regime-fiscale.spec.ts`); **(c)** un terzo
  `webServer` che avvia `python -m app.worker`. **Da decidere con la 2.1, non da scoprire con la
  2.8.**

- **E2-G6 — (P2, robustezza AD-10) — La coda `job` non ha equità fra tenant.** `claim_due`
  prende `limit=10` per giro e la tabella `job` non ha `host_id`. Con N Host × M Feed a tick di
  15', i job di sync condividono la coda con le notifiche di Conflitto, che sono la funzione di
  fiducia (NFR-3). Alla scala del pilota (decine di Host, poll da 1s) non è un collo di
  bottiglia reale — per questo è P2 e non un finding di correttezza. → Test di regime: con K
  job di sync in coda, un job di notifica scaduto viene eseguito entro un numero dichiarato di
  giri. Se il test non regge, il rimedio è architetturale e non mio (partizionamento della coda
  o priorità), e va portato a Winston.

**Riporto dall'Epic 1, non nuovo:** l'azione **A2** della retrospettiva (blocco `permissions:`
minimo in `.github/workflows/ci.yml`, oggi **assente**) resta di Amelia ed è un criterio di gate
della **prima PR dell'Epic 2 che tocca la CI** — e l'Epic 2 la toccherà (nuove tabelle, nuovo
job, eventuale worker in e2e). Non lo conto come finding di questo Epic: ha già un proprietario
e un momento.

---

## 5. Fixture e dati di test (vincoli)

### 5.1 Dati personali — NFR-16

- **Nessun dato reale di Ospiti.** Vale doppio in questo Epic: l'Epic 1 non aveva Ospiti, l'Epic
  2 li importa da una rete esterna. Nomi ed email nei feed di test sono **inventati** e su
  dominio `example.com`; nessun `.ics` proveniente da un account reale entra nel repo, nemmeno
  «anonimizzato» (un `UID` reale è un identificatore, e il nome di una Struttura reale pure).
- **`ospite` è tenant-owned e i suoi dati non escono dal DB**: il payload di eventi e job porta
  **solo identificatori** (AD-17 lo valida già a runtime: i valori devono essere scalari e le
  chiavi devono corrispondere esattamente a quelle dichiarate). Log strutturati e
  `problem+json` non contengono nomi di Ospiti. Test dedicato, non solo convenzione.
- Il modulo `privacy` e la cifratura (AD-11) riguardano `ospite_documento`, che è **Epic 3**:
  qui si tratta di anagrafica leggera. Non è una scusa per trattarla con meno cura nei fixture.

### 5.2 Corpus di fixture iCal — versionate, mai scaricate

- I feed di test sono **file `.ics` versionati** in `backend/tests/fixtures/ical/`, uno per
  forma, con un nome che dice il caso (`airbnb-date-only.ics`, `booking-tzid-dst.ics`,
  `troncato-a-meta-vevent.ics`, `uid-duplicato.ics`, …). Sono dati, quindi si leggono in diff e
  si rivedono in PR.
- **Il corpus è modellato su RFC 5545 e sulla forma documentata degli export Airbnb/Booking, non
  catturato da feed reali.** Lo scrivo esplicitamente perché è un limite, non una garanzia: la
  fedeltà ai feed veri è precisamente ciò che nessuna fixture può dimostrare, ed è la ragione
  per cui **A11** (§8.3) resta una raccomandazione aperta. Quando una forma nuova si incontra in
  esercizio, **entra nel corpus come fixture prima** che il codice venga corretto: è il ciclo
  rosso→verde applicato a un formato che non controlliamo.
- **Nessuna chiamata di rete in unit e integration** (guardia GS-1): il client HTTP è iniettato e
  il fake restituisce corpo, `status`, header (`ETag`, `Last-Modified`, `Content-Length`,
  `Content-Type`), redirect, timeout e **chiusura anticipata della connessione**. Il timeout si
  simula, non si attende: mai uno `sleep` in suite.

### 5.3 Tabella dei casi del normalizzatore — come si simulano formati, fusi e VEVENT malformati

Questa tabella è il contratto del livello unit della 2.1 (AC 9) e copre R2-F e R2-G.

| Classe | Casi minimi da coprire | Atteso |
| --- | --- | --- |
| **Tipo di data** | `DTSTART;VALUE=DATE` + `DTEND;VALUE=DATE` (forma tipica degli export OTA); `DTSTART`/`DTEND` come `DATETIME` con `Z`; `DATETIME` con `TZID=Europe/Rome`; `DATETIME` senza TZ (floating) | Sempre un `DateRange` su **date locali Europe/Rome** con `[check_in, check_out)`. `DTEND` in iCal è già **esclusivo** per i `VALUE=DATE`: la corrispondenza con AD-3 è esatta e va **asserita**, non assunta |
| **Fusi e ora legale** | Soggiorno che attraversa l'ultima domenica di marzo e quella di ottobre; `DTSTART` alle 00:30 con TZID; `Z` che in Europe/Rome cade il giorno prima | Il **giorno locale** è quello atteso in tutti i casi (`rome_day`); nessun timestamp naive persistito (`NaiveDatetimeError`) |
| **Durata** | `DTEND` assente con `DURATION:P3D`; `DTEND` assente e senza `DURATION`; `DTEND` ≤ `DTSTART` | I primi due producono rispettivamente 3 notti e un errore dichiarato; il terzo è **rifiutato**, mai un `DateRange` vuoto (`EmptyDateRangeError`) |
| **Sintassi** | Line folding a 75 ottetti con continuazione; CRLF vs LF; BOM iniziale; proprietà sconosciute; `VEVENT` senza `END:VEVENT` | Parse corretto sui primi quattro; il quinto è **feed non valido** (vedi E2-G3), non un evento in meno |
| **Identità** | `UID` assente; `UID` duplicato nello stesso feed; `UID` con spazi o differenze di sole maiuscole; `UID` molto lungo | Nessun crash. `UID` assente ⇒ evento **registrato come malformato con errore visibile**, mai scartato in silenzio (NFR-1: nessuna Prenotazione persa). Duplicato ⇒ criterio deterministico dichiarato e testato |
| **Confini testuali** | `SUMMARY`/`DESCRIPTION` non-ASCII (accenti, emoji, cirillico); stringa vuota; escape iCal (`\,` `\;` `\n`) | Nessuna eccezione, nessun mojibake. È la classe che nell'Epic 1 ha prodotto **F-3** (byte non-ASCII in un header ⇒ 500): costa poche righe e va messa dove attraversa un confronto o un parsing |
| **Semantica** | `STATUS:CANCELLED`; `TRANSP:TRANSPARENT`; `RRULE` (evento ricorrente); `EXDATE` | Comportamento **dichiarato** per ciascuno. In particolare `RRULE`: se l'MVP non espande le ricorrenze, deve dirlo — un evento ricorrente ignorato in silenzio è una Prenotazione persa, cioè NFR-1 violato |
| **Trasporto** | Corpo troncato a metà `VEVENT`; corpo vuoto con 200; solo intestazione `VCALENDAR`; `Content-Type` inatteso; risposta oltre il cap di dimensione; `304` | Nessuna transizione a `rimossa_dal_feed` (E2-G3); `sync_run` fallito dove serve; per il `304` run **riuscito** e dati intatti |

### 5.4 Determinismo

- **DB reale in CI** (`HOSTPILOT_TEST_DB_REQUIRED=1`): lo skip dei test su Postgres è un
  **errore** in pipeline. Una CI verde implica sempre che quei test sono girati davvero. Da
  mantenere, senza eccezioni per il nuovo modulo.
- **Isolamento fra test**: ogni nuova tabella va in `TABELLE_DA_SVUOTARE` — e la guardia GS-2
  (E2-G4) toglie questo passaggio dalla memoria di chi scrive.
- **Determinismo temporale**: il tempo si **inietta** come parametro (`now: datetime | None`, il
  pattern già usato da `claim_due` e `run_due_jobs`) o si scrive lo stato nel passato/futuro con
  `utcnow() ± timedelta`. Mai uno `sleep` per attendere una scadenza. Nell'Epic 2 questo vale
  anche per la **finestra di ri-verifica di 24h** della 2.7 e per l'intervallo adattivo della
  2.2: entrambi devono essere testabili in millisecondi.
- **Concorrenza**: 8 contendenti e barrier fra i client (§2.4). Nessun test di gara conta come
  verde se non è stato visto rosso.

---

## 6. Criteri di gate per le Story dell'Epic 2

Una Story è candidabile al **merge umano** quando **tutte** queste condizioni sono vere. Il
verdetto (PASS / CONCERNS / FAIL / WAIVED) è una **raccomandazione**: la decisione di rilascio
resta a Fahad.

1. **Tutti gli AC P0 della Story hanno un test verde al livello indicato in §3.** Gli AC
   derivati (`†`) valgono quanto quelli scritti in `epics.md`: sono la metà del piano e sono la
   metà che l'Epic 1 ha imparato a non lasciare implicita.
2. **CI verde su tutti e cinque i check obbligatori**: `backend`, `frontend`, `e2e`,
   `api-contract` e **SonarCloud Quality Gate**. Zero test flaky. Una CI rossa — Sonar incluso —
   non riceve APPROVA.
3. **Guardie strutturali verdi**: `test_auth_convention.py` e `test_tenancy_convention.py`
   (esistenti, si auto-arruolano sul modulo `calendario`) più quelle introdotte dalla Story
   secondo §2.6 (GS-1, GS-2, GS-5 dalla 2.1; GS-3 dalla 2.6; GS-4 dalla 2.7). Ogni allowlist
   nuova è **esplicita e a sua volta sorvegliata** da un test che la fa decadere se cambia la
   premessa.
4. **Ogni check-then-write della Story ha il suo test di gara** (§2.4): 8 thread, barrier fra i
   client, e **la prova che il test è stato visto rosso** (nel commento della PR: quale vincolo
   è stato rimosso per farlo fallire). Senza questa prova l'AC di concorrenza non è coperto.
5. **Ogni nuovo spec e2e è nell'elenco chiuso di §2.5**, oppure la PR nomina esplicitamente il
   difetto che solo quello spec vede e chiede una deroga nel verdetto.
6. **Nessun dato reale** nei fixture (NFR-16) e **nessuna chiamata di rete reale** in unit e
   integration. Segreti fuori dal repo.
7. **Se l'API cambia**: `backend/openapi.json` e `frontend/lib/api/schema.d.ts` rigenerati e
   committati (`api-contract` fallisce sul `git diff`, non c'è modo di dimenticarsene — ma
   scoprirlo in CI costa un giro).
8. **Se lo schema cambia**: migrazione Alembic **forward-only**, tabelle nuove con `host_id`
   NOT NULL + FK, e presenza nella lista di TRUNCATE (GS-2).
9. **I finding P0/P1 aperti che toccano il perimetro della Story sono chiusi** o esplicitamente
   accettati dall'umano con motivazione. Applicazione dell'azione **A9**: ogni Story si porta in
   dote i finding aperti del suo perimetro; i P2 senza perimetro vanno in **un solo** batch
   pianificato a metà Epic, non in quattro batch reattivi come nell'Epic 1.
10. **Verdetto del Test Architect su OGNI PR prima del merge umano** — Story e **fix-forward
    inclusi** (decisione uniforme di Fahad del 25/07). Anche quando una PR implementa un mio
    finding, verifico che l'implementazione corrisponda al disegno: evidenza rosso→verde reale,
    nessun effetto collaterale fuori scope, test che coprono il caso originario.

**Regola che non si negozia:** un difetto trovato non si chiude ammorbidendo il test. Il test
descrive l'atteso, il codice si adegua.

---

## 7. Matrice di tracciabilità — chiusura Epic 2

**Da compilare alla chiusura dell'Epic, non adesso.** Struttura prevista, identica a quella che
ha retto la chiusura dell'Epic 1:

- **§7.1** Requisiti funzionali (FR-3…FR-7) → Story → livello di verifica → suite → stato
- **§7.2** Invarianti architetturali esercitati (AD-3, AD-4, AD-5, AD-10, AD-13, AD-14, AD-17,
  AD-18, AD-19, AD-20) → presidio di test
- **§7.3** Requisiti non funzionali (NFR-1, NFR-2, NFR-3, NFR-8, NFR-9, NFR-14, NFR-16)
- **§7.4** Registro dei finding dell'Epic 2 — ogni riga con **la PR che la chiude e il nome del
  test di regressione**. Senza il test nominato la riga resta aperta
- **§7.5** Copertura Story per Story (2.1 → 2.8) sui 77 AC di §3
- **§7.6** Dichiarazione di chiusura, **se** e solo se il registro è chiuso
- **§7.7** Rischi tracciati alla chiusura — che **debito non sono**: condizioni note, senza test
  rosso e senza violazione di AC, ciascuna con un **momento preciso** di rivalutazione. Debito
  zero ≠ rischio zero, e senza questa tabella i rischi noti o inquinano il registro del debito o
  spariscono e riappaiono come debito per dimenticanza

Registro dei finding aperti a oggi: **E2-G1 … E2-G6** (§4). Tutti aperti in fase di
progettazione, nessuno ancora chiuso.

---

## 8. Punti aperti — analisi, non decisione

Tre punti dell'Epic 2 sono decisioni di Fahad. **Non li chiudo.** Su uno di essi mi è stato
chiesto un contributo circoscritto, e do quello.

### 8.1 A8 — nodo shadcn/ui

Decisione di Fahad (proposta di Winston). **Nessuna raccomandazione da parte mia.** L'unica cosa
che il test design registra è che la scelta cambia il *livello* — non la copertura — di alcuni
AC di UI della 2.3 e della 2.7: componenti di libreria con a11y già garantita spostano peso dal
test alla dipendenza, componenti fatti in casa lo lasciano al test. Qualunque sia l'esito, gli
AC di §3 restano gli stessi e la baseline axe resta a serious/critical = 0.

### 8.2 A10 — osservabilità del poller: come cambia la copertura di NFR-2 nei due scenari

Questo è il punto su cui mi è stato chiesto di dire **una cosa sola**: come cambia la copertura
di NFR-2 se un minimo di osservabilità del sync viene anticipato nella 2.2, oppure rimandato
all'Epic 3. Opzioni con trade-off, non una scelta.

**Il fatto che vincola entrambi gli scenari:** la Story 2.2 ha già un AC che dice «**alert
interno dopo N fallimenti consecutivi**» (AC 8 in §3). Un alert è per definizione un'uscita
osservabile. Quell'AC esiste comunque: la domanda non è *se* servano contatore e stato, ma *fin
dove* debbano arrivare.

**Scenario A — minimo di osservabilità anticipato nella 2.2.** Il Feed espone come campi API lo
stato di sincronizzazione: `ultimo_sync_riuscito_il`, `fallimenti_consecutivi`, `ultimo_errore`
(categoria, non stacktrace).

- *Copertura NFR-2 che si guadagna:* NFR-2 diventa verificabile **al livello integration** in
  forma forte — non solo «il timestamp è visibile» ma «il timestamp **non avanza** su run
  fallito **e** il sistema sa dirti da quanti giri non riesce». Diventa testabile la proprietà
  che NFR-2 protegge davvero: *«feed fermo da tre giorni» è distinguibile da «non ci sono
  prenotazioni nuove»*. L'AC 8 della 2.2 acquista una conseguenza osservabile e smette di essere
  un AC coperto «per ispezione».
- *Costo:* campi in più nel contratto API (rigenerazione OpenAPI + client TS, un giro di
  `api-contract`); uno stato in più da mantenere coerente e da testare; una superficie UI in più
  da coprire, seppur minima.

**Scenario B — rimandato all'Epic 3 (NFR-7, Story 3.1/3.8).** Nella 2.2 resta solo il timestamp
dell'ultimo sync riuscito, come oggi previsto.

- *Copertura NFR-2 che resta:* la **lettera** di NFR-2 è comunque soddisfatta e testabile —
  «ovunque si mostri lo stato del calendario è visibile l'orario dell'ultima sincronizzazione» e
  «il timestamp non avanza su un run fallito» sono entrambi asseribili in integration e in e2e.
  Su questo non c'è degrado.
- *Copertura che si perde:* per l'**Host** un feed fermo e un feed senza novità hanno lo stesso
  aspetto — un timestamp che invecchia in silenzio. Nessun test può asserire una distinzione che
  il prodotto non fa. E soprattutto: **l'AC 8 della 2.2 non ha alcuna conseguenza osservabile**,
  quindi o si de-scopa esplicitamente (dichiarando che l'alert arriva con l'Epic 3, e quell'AC
  passa a P2 rimandato), oppure si riduce a un contatore persistito sul Feed — che però *è già*
  lo scenario A in forma minima. **Questa è la conseguenza da pesare: nello scenario B un AC
  dell'Epic 2 resta senza copertura possibile**, e nel nostro metodo un AC senza copertura o si
  copre o si de-scopa per iscritto, non si lascia in mezzo.

**Sintesi neutra:** A costa un giro di contratto e rende testabile la proprietà che NFR-2
protegge; B non degrada la lettera di NFR-2 ma lascia un AC della 2.2 senza conseguenza
osservabile, e va accompagnato da un de-scoping esplicito di quell'AC. La scelta è di Fahad.

### 8.3 A11 — un feed iCal reale in un ambiente vero

Decisione e ambiente sono di Fahad. **Non lo pianifico.** Registro solo, come test design, il
confine di ciò che il piano di test **non** può dimostrare: il corpus di fixture (§5.2) è
modellato sullo standard e sulla forma documentata degli export, non catturato da feed reali.
Copre robustezza e regressione; **non** copre la fedeltà — se Airbnb usa una proprietà che non
abbiamo immaginato, nessuna fixture lo rivela. Se A11 non viene fatto, quel rischio resta aperto
e andrà scritto in §7.7 alla chiusura, con il suo momento di rivalutazione. Se viene fatto, la
prima forma nuova incontrata entra nel corpus come fixture (§5.2) e il rischio si chiude nel
modo giusto.

---

_Documento aperto per l'Epic 2. §7 si compila alla chiusura. Il modello §1–§7 è quello che ha
retto la chiusura dell'Epic 1 (`docs/qa/test-design-epic-1.md`) e si replica qui in un documento
indipendente: l'Epic 1 è chiuso e non si riapre._

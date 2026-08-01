# Decisione — mutation testing in CI: **non si adotta**

Stato: **decisione presa.** Opzione **A — non si adotta.** Decisa da Fahad il
2026-07-30, dopo lo spike MYL-72.
Misura e raccomandazione: Murat (Test Architect), 2026-07-30.

> **Provato, misurato, scartato — non «mai provato».**
>
> Se stai leggendo questo documento perché ti stai chiedendo se valga la pena
> introdurre il mutation testing su HostPilot: è già stato valutato *sul
> codice*, non sulla carta. `mutmut` 3.6 è stato configurato, fatto girare fino
> in fondo su 1712 mutanti reali, e il suo esito è nella §2. La §4 dice a quali
> condizioni la decisione si riapre; la §5 raccoglie i costi già misurati, così
> chi ci tornerà non li rimisuri da capo.
>
> Il ciclo completo: proposta del 30/07 mattina (raccomandava **B**, report non
> bloccante) → spike autorizzato → misura → **la raccomandazione è cambiata in
> A**, e la decisione l'ha seguita. La proposta originale è conservata
> integralmente nell'**Appendice A**, perché la §3 spiega *perché* si è
> ribaltata e senza il testo di partenza non si capirebbe.

---

## 1. La decisione

**Non si adotta il mutation testing in CI.** Nessun job, nessuna dipendenza
nuova, nessuna configurazione: `mutmut` non entra in `pyproject.toml` né in
`.github/workflows/`. Il controllo di mutazione resta **manuale e occasionale**,
uno strumento in mano al Test Architect quando un modulo gli sembra troppo
tranquillo — che è il modo in cui ha prodotto valore finora.

Le tre ragioni, in ordine di peso:

1. **Non trova niente.** 1712 mutanti su codice reale, **zero sopravvissuti**
   (§2). Il report che avremmo pagato sarebbe stato vuoto — e un report vuoto
   letto come «verificato» promette più di quanto lo strumento garantisca.
2. **Il difetto che ci aveva convinti non è nel suo catalogo.** MYL-60 è lo
   scambio `timedelta(minutes=…)` → `timedelta(days=…)`, cioè la **rinomina di
   un argomento con nome**: `mutmut` non ha un operatore che la produca. Non
   l'avrebbe intercettato nemmeno se fosse stato attivo quel giorno (§B.5).
3. **Il 17,4% del codice è cieco per costruzione**, e non è un 17% qualsiasi:
   sono le funzioni e le classi *decorate*, cioè l'intero strato `api.py`
   (78–100% per file) e ogni `@dataclass` — compreso `DateRange`, quindi
   `overlaps`, cioè l'intersezione che regge l'anti-double-booking (AD-3), che
   riceve **zero** mutanti (§B.4).

## 2. L'esito misurato

Due perimetri, entrambi con configurazione pulita e verificata (§6):

| Perimetro | Mutanti | Uccisi | `no tests` | **Sopravvissuti** |
| --- | ---: | ---: | ---: | ---: |
| Campione dell'Appendice A §4 — `core/date_range.py` + `strutture/regime_fiscale.py` | 60 | 60 | 0 | **0** |
| I 7 file di `app/` toccati dalla PR #52 (Story 2.4, +605 righe) | 1652 | 1642 | 10 | **0** |
| **Totale** | **1712** | **1702** | **10** | **0** |

I 10 `no tests` sono tutti su `PrenotazioneRepository.della_struttura`
(`backend/app/calendario/repository.py:491`) e **non sono un falso positivo**:
quel metodo non è chiamato da nessuno — l'unico `della_struttura` usato in
produzione è quello di `FeedIcalRepository`. Codice morto entrato con la Story
2.4. Registrato come **P2 di Fahad**, non toccato qui.

Questo, e nient'altro, è ciò che 1712 mutanti hanno prodotto.

## 3. Perché la decisione è cambiata: i tre sopravvissuti erano un artefatto

**La decisione del mattino era corretta rispetto ai dati che aveva. I dati erano
sbagliati, e li avevo prodotti io.**

L'Appendice A §4 riporta «60 mutanti, 3 sopravvissuti, tutti e tre mutazioni
della stringa di un messaggio d'errore — falsi positivi 3 su 3». Su quel numero
poggiava l'intera raccomandazione B: *lo strumento è rumoroso, quindi parte come
report e non come cancello, e si disattivano le mutazioni sui letterali
stringa*.

Quei tre sopravvissuti **non esistono**. Erano l'effetto di una configurazione
mai letta: `mutmut` 3.6 legge `[tool.mutmut]` da `pyproject.toml`, mentre le
chiavi che avevo scritto stavano in `setup.cfg` con i nomi della serie 2.x.
Senza configurazione la sandbox `mutants/` nasceva incompleta, la raccolta
delle statistiche moriva, e **un mutante che nessun test raggiunge viene
contato come non ucciso**. Con la configurazione corretta, sullo stesso identico
campione, i sopravvissuti sono **0**.

Due conseguenze, entrambe agli atti:

- **Decade la premessa di B.** Non c'è rumore da domare, perché non c'è nulla
  che sopravviva. Il motivo per preferire il report al cancello spariva insieme
  al motivo per avere l'uno o l'altro.
- **La leva che B chiedeva non esiste comunque.** «Disattivare le mutazioni sui
  letterali stringa» non è configurabile in `mutmut` 3.6: `mutation_operators`
  è una costante di modulo. L'unica alternativa, `do_not_mutate_patterns`, è una
  regex applicata **riga per riga** e spegnerebbe anche le mutazioni di logica
  che condividono quella riga — più cieco, non meno rumoroso, e in silenzio.

Regola che ne esce, e che vale oltre questo caso: **un numero preso da un run
che so sporco non si riporta affatto.** Riportarlo «con riserva» non basta —
qui la riserva era scritta (Appendice A §5, i tre caveat) e il numero è
diventato lo stesso la base di una decisione.

## 4. Quando la decisione si riapre — trigger verificabili

Due trigger. Sono scritti per essere **controllabili da chiunque**, non
valutati a sensazione, e il momento in cui si controllano è la **chiusura di
ogni Epic**, insieme all'audit degli strumenti.

### T1 — la suite smette di essere così severa

**Condizione:** un controllo di mutazione fatto **a mano** torna a produrre un
finding vero, cioè un mutante che sopravvive e che *deve* essere ucciso.

**Come si verifica:** si conta. Ogni mutazione manuale che produce un finding
vero si registra in `docs/qa/test-design-epic-<N>.md` §4, con l'ID del finding.
**Il primo finding così registrato con data successiva al 2026-07-30 riapre
questo documento.** Non serve un secondo: l'intera premessa della decisione è
«la suite uccide tutto», e basta un contresempio per invalidarla.

**Stato al 2026-07-30:** contatore a **zero**. I tre casi citati nella proposta
(Appendice A, «l'ho applicato a mano tre volte») sono *precedenti* alla misura e
non contano come contresempi: sono la ragione per cui lo spike è stato fatto.

### T2 — `mutmut` impara a mutare le funzioni decorate

**Condizione:** una versione di `mutmut` successiva alla 3.6.0 smette di saltare
funzioni e classi decorate.

**Come si verifica**, in due passi e senza opinioni:

1. **Il predicato esatto**, oggi in `mutmut/mutation/file_mutation.py`, funzione
   `_skip_node_and_children`, in coda:

   ```python
   if isinstance(node, cst.FunctionDef) and len(node.decorators):
       if len(node.decorators) == 1:
           decorator = node.decorators[0].decorator
           if isinstance(decorator, cst.Name) and decorator.value in ("staticmethod", "classmethod"):
               return False
       return True
   if isinstance(node, cst.ClassDef) and len(node.decorators):
       return True
   ```

   Se in una release nuova questi due blocchi non ci sono più, il trigger è
   candidato ad attivarsi.

2. **La conferma quantitativa**, perché sparire dal sorgente non basta: si
   rifà il censimento della §5.3 su `backend/app/`. **Il trigger scatta se la
   quota cieca scende sotto il 5%** (oggi 17,4%) **e** `DateRange.overlaps`
   riceve almeno un mutante — quella singola funzione è il test del nove:
   finché la classe `@dataclass` che la contiene resta esclusa, il 17% che non
   guardiamo continua a essere il pezzo che conta.

### Cosa NON è un trigger

La crescita del codice, l'arrivo di un Epic nuovo, o «è passato del tempo». Il
costo non cambia con nessuna di queste cose, e nemmeno la cecità: sono
proprietà dello strumento, non del nostro calendario.

## 5. Se un giorno si riprende — i costi già misurati, da non rimisurare

Tutto ciò che segue è stato pagato una volta il 30/07. Chi riapre il dossier
parte da qui.

### 5.1 La configurazione che gira

Il punto di partenza, senza il quale si ricade nei tre caveat dell'Appendice A
§5. Va in `pyproject.toml`, **non** in `setup.cfg`:

```toml
[tool.mutmut]
source_paths = ["app"]
# La sandbox `mutants/` riceve `app/` e `tests/`, e nient'altro. Le migrazioni
# servono: `conftest.py` fa `alembic upgrade head` prima di qualunque test su
# database, e senza `alembic/` la calibrazione muore.
also_copy = ["alembic/", "alembic.ini", "scripts/", "openapi.json"]
pytest_add_cli_args_test_selection = [
    "--ignore=tests/test_copertura_convention.py",
    "--ignore=tests/test_tenancy_convention.py",
    "--ignore=tests/test_auth_convention.py",
    "--ignore=tests/test_conventions.py",
    "--ignore=tests/test_lock_convention.py",
    "--ignore=tests/test_superfici_feed_convention.py",
    "--ignore=tests/test_append_preserving_convention.py",
    "--ignore=tests/test_registro_modelli.py",
]
only_mutate = ["…i file .py di app/ toccati dalla PR…"]
```

### 5.2 Gli otto `--ignore` sono un costo, non un dettaglio di configurazione

Quel blocco disattiva **le nostre guardie strutturali**. Non perché siano
rotte: dentro la sandbox `mutmut` riscrive ogni metodo in
`xǁClasseǁmetodo__mutmut_N`, e le guardie che ispezionano il codice **per
riflessione** vedono un albero che non è il nostro.
`test_tenancy_convention.py` trova diciannove «metodi di repository senza
`host_id`» che sono tutti mutanti; `test_copertura_convention.py` legge
`.github/workflows/ci.yml` risalendo di una directory, e dalla sandbox quella
directory non esiste.

Conseguenza da tenere in mano prima di riaprire: **la suite che gira dentro la
sandbox non è la suite del repository**, e la differenza sono esattamente i
controlli che sorvegliano i controlli.

### 5.3 La cecità strutturale: 17,4%, e dove sta

258 funzioni/metodi mutabili (3909 righe) contro 53 saltati (824 righe) su
`backend/app/`. Il censimento si rifà camminando l'AST e applicando le regole
di `mutmut`: **funzione decorata → saltata** (salvo un solo `@staticmethod` o
`@classmethod`); **classe decorata → saltata con tutti i suoi metodi**;
`__getattribute__`, `__setattr__`, `__new__` mai mutati.

| File | Righe cieche / totali | |
| --- | --- | --- |
| `app/config_normativa/api.py` | 81/81 | **100%** |
| `app/strutture/api.py` | 85/91 | 93% |
| `app/identity/api.py` | 79/90 | 88% |
| `app/calendario/api.py` | 269/345 | 78% |
| `app/core/date_range.py` | 18/28 | 64% — `DateRange` è `@dataclass` |
| `app/calendario/jobs.py` | 138/294 | 47% — `@handlers.register` |

Cause, per numero di funzioni: 13 dentro classi `@dataclass`, 12 `@post`, 11
`@get`, 5 `@register`, 3 `@put`, 3 `@lru_cache`, 2 `@property`, 2 `@patch`, 1
`@field_validator`, 1 `@computed_field`.

### 5.4 Il costo scala con quanto è *importato* il modulo, non con il diff

È la stima che nella proposta era sbagliata in modo strutturale, non
approssimativo: l'Appendice A §3 stima il costo dalla **dimensione del diff**, e
misura la cosa sbagliata.

- **Costo fisso: 1 min 51 s.** Misurato con *zero* mutanti da eseguire. È la
  passata di copertura su **tutta** la suite con cui `mutmut` costruisce la
  mappa test→funzione. **Restringere il perimetro al diff non la accorcia.**
- **Costo variabile:** dipende da quanti test coprono la riga mutata.

| Perimetro | Mutazioni/s |
| --- | ---: |
| `calendario/service.py` + `repository.py` + `api.py` (+605 righe) | **15,49** |
| `core/date_range.py` (una manciata di righe) | **0,41** |

Trentotto volte più lento su un file **molto più piccolo**, perché ogni mutante
di `date_range` trascina mezza suite. **Una PR da una riga su `app/core/` può
costare più di una Story intera su un modulo foglia.** Totale misurato sulla PR
#52: ≈ 3 min 40 s.

### 5.5 Windows: `mutmut` 3.6 rifiuta di partire

```
To run mutmut on Windows, please use the WSL. Native windows support is
tracked in issue https://github.com/boxed/mutmut/issues/397
```

Verificato il 30/07 su Windows nativo con Python 3.14. Tutte le misure di questo
documento vengono da container Linux (`python:3.14-slim` + PostgreSQL 18 sul
loopback). **Chi sviluppa su Windows non riproduce un finding del report senza
WSL o senza container.**

Questa riga va nel README del backend **se e quando** si adotta, non prima: oggi
non c'è nulla da eseguire, e un avvertimento su uno strumento assente è rumore.

### 5.6 Frontend

StrykerJS non è mai stato misurato e non è stato proposto. Se un giorno si
riapre, va misurato da zero: nulla di questo documento vale per il TypeScript.

## 6. Come si riproducono le misure

Ambiente: container `python:3.14-slim`, `uv sync --locked --no-build
--no-install-project --group dev`, `uv pip install mutmut==3.6.0`, PostgreSQL 18
**sul loopback** — non su un hostname di rete, o la guardia GS-1 di
`tests/conftest.py` blocca `getaddrinfo` e la suite fallisce per il motivo
sbagliato. Poi `mutmut run --max-children 4` con la configurazione di §5.1.

**Prima di credere a uno «zero sopravvissuti», far dire allo strumento «un
sopravvissuto».** Sonda usata qui: una funzione con un ramo che nessun test
esercita, aggiunta a un modulo nel perimetro.

```python
def _sonda_spike(x: int) -> int:
    if x > 10:
        return x + 1
    return x
```

con un solo test che chiama `_sonda_spike(1)`. Esito atteso — e ottenuto — **4
sopravvissuti** riportati con il diff leggibile:

```
x__sonda_spike__mutmut_1: survived   (if x > 10   →  if x >= 10)
x__sonda_spike__mutmut_2: survived   (if x > 10   →  if x > 11)
x__sonda_spike__mutmut_3: survived   (return x+1  →  return x-1)
x__sonda_spike__mutmut_4: survived   (return x+1  →  return x+2)
```

Se la sonda non produce quei quattro, la configurazione è rotta e **qualunque
numero prodotto in quel run va buttato** — è precisamente l'errore della §3.

---

# Appendice A — la proposta com'era scritta il 30/07, prima dello spike

*Conservata integralmente come registro. Raccomandava **B**; la §3 di questo
documento spiega perché la raccomandazione si è ribaltata. Dove questa
appendice e le §1–§6 divergono, valgono le §1–§6.*

## A.0 In gioco

La copertura dice se una riga è stata *eseguita* da un test. Non dice se il test
si accorgerebbe che quella riga è **sbagliata**. Il mutation testing risponde a
quella seconda domanda: cambia il codice di proposito e controlla che almeno un
test cada. In questo Epic l'ho applicato a mano tre volte e ha trovato difetti
veri ogni volta. Questa proposta serve a togliermelo dalle mani e a farlo
diventare una proprietà del sistema.

## A.1 Opzioni

**A — Non farlo.** Costo zero. Il rischio resta quello di oggi: la forza della
suite dipende da chi la scrive e da quanto sono in vena di controllarla a mano.
Nessun cancello se ne accorge.

**B — Report non bloccante sul diff (raccomandata).** Su ogni PR gira sui soli
file cambiati e **commenta** i mutanti sopravvissuti. Non blocca il merge.
Costo stimato **2–5 minuti** di CI per PR (dettaglio in A.4). Se il rumore è
tollerabile dopo un Epic, si valuta di renderlo bloccante.

**C — Cancello bloccante subito.** Stesso costo di CI, ma una PR può diventare
rossa per un mutante che nessuno dovrebbe uccidere. A.5 mostra che, sul campione
misurato, sarebbe **capitato al primo colpo**.

## A.2 Raccomandazione

**B.** Il mutation testing è utile quanto è credibile, e la credibilità la
perde al primo rosso che tutti sanno di dover ignorare. Parte come report, e la
promozione a cancello è una decisione che si prende con i dati di un Epic, non
adesso. Il salto B→C è una riga di configurazione.

## A.3 Strumento scelto: `mutmut` 3.6 (Python), rimandato per il frontend

`mutmut` è l'unico strumento Python maturo con supporto reale al 2026. Misurato
il 30/07, sul serio e non da documentazione:

| Cosa ho provato | Esito |
| --- | --- |
| `mutmut` 2.5.1 su Python 3.14 | **non parte** — `TypeError: cannot pickle 'itertools.count' object`. Tira dentro `pony` e `glob2`, con `SyntaxWarning` su 3.14. |
| `mutmut` 3.6.0 su Windows nativo | **rifiuta di partire**: «To run mutmut on Windows, please use the WSL» ([issue 397](https://github.com/boxed/mutmut/issues/397)). |
| `mutmut` 3.6.0 su Linux (container, Python 3.14) | **funziona**, con caveat in A.6. |

Conseguenza pratica da mettere agli atti: in CI (Linux) va bene; **in locale su
Windows non è eseguibile senza WSL**. Chi sviluppa su Windows non potrà
riprodurre un finding del report senza passare da un container. È un costo reale
di adozione, non un dettaglio.

Per il frontend TypeScript lo strumento sarebbe **StrykerJS**. Non l'ho
misurato: non lo propongo in questo giro. Un cancello a metà è più facile da
tarare di due tarati male insieme.

## A.4 Costo in minuti di CI *(stima poi smentita — vedi §5.4)*

Mutare tutto `backend/app/` significherebbe circa **1150 mutanti** (densità
misurata: 60 mutanti su 131 righe di sorgente, ≈ 0.46 mutanti per riga, su 2524
statement). Fuori discussione a ogni PR. Perimetro proposto: i file `.py` sotto
`backend/app/` **toccati dalla PR**; un diff tipico (50–150 statement cambiati)
produce **25–70 mutanti**.

Misurato in container Linux, `--max-children 4`:

- throughput osservato: **44.87 mutazioni/secondo** sul campione (la maggior
  parte scartata subito perché priva di test che la coprano — vedi A.6);
- i mutanti effettivamente eseguiti sono costati **≈ 0.7 s ciascuno** con un
  sottoinsieme di test da 1.34 s e parallelismo 4;
- costo fisso del job: checkout + `uv sync --locked` + run di calibrazione
  ≈ **1.5–2 minuti**.

| Scenario | Mutanti | Stima |
| --- | --- | --- |
| PR su moduli puri (`date_range`, `regime_fiscale`, `normalizzazione`, `uscita_rete`) | 25–70 | **2–3 min** |
| PR su moduli che toccano il DB (`service`, `repository`) | 25–70 | **3–5 min**, alta varianza |
| PR di soli documenti | 0 | job saltato |

Con un **tetto di tempo** sul job (proposta: 8 minuti) il costo resta
prevedibile. Il tetto va **dichiarato nel report**: un troncamento silenzioso si
legge come «tutto verificato».

## A.5 Come si evita che diventi un cancello rumoroso *(misura poi smentita — vedi §3)*

Qui la misura è netta, e da sola giustifica la raccomandazione B.

Sui due moduli del campione: **60 mutanti, 3 sopravvissuti**. Tutti e tre sono
mutazioni della **stringa di un messaggio d'errore**, non della logica:

```diff
 def rome_day(instant: datetime) -> date:
     if instant.tzinfo is None:
-        raise NaiveDatetimeError("datetime naive: serve un istante timezone-aware")
+        raise NaiveDatetimeError(None)
+        raise NaiveDatetimeError("XXdatetime naive: serve un istante timezone-awareXX")
+        raise NaiveDatetimeError("DATETIME NAIVE: SERVE UN ISTANTE TIMEZONE-AWARE")
```

Nessuno di questi tre mutanti **deve** essere ucciso: un test che asserisse il
testo esatto di un messaggio d'errore interno sarebbe un test peggiore di quello
che c'è ora, e si romperebbe alla prima riformulazione. Sul campione misurato il
tasso di falsi positivi è **3 su 3, cioè 100%**.

Le tre leve, in ordine di efficacia:

1. **Disattivare le mutazioni sui letterali stringa.** È la fonte del rumore
   misurato. Da sola porta il campione da 3 sopravvissuti a 0.
2. **Report, non cancello** (opzione B): un mutante sopravvissuto diventa una
   domanda in una PR, non un rosso da aggirare.
3. **Ignora esplicito e versionato**: quando un mutante sopravvive per una
   ragione legittima, si registra con il *perché* — così la lista degli ignore è
   rivedibile in PR e non un cassetto.

E una regola che non è tecnica: **un mutante sopravvissuto non si chiude
scrivendo il test che lo uccide.** Si chiede prima se quel mutante descrive un
comportamento che ci interessa. Se sì, il test va scritto e il finding è vero. Se
no, va nell'ignore con la motivazione. Inseguire il punteggio produce test che
congelano dettagli di implementazione, cioè la forma di debito più costosa che
conosco.

## A.6 Caveat da chiudere in uno spike *(tutti e tre chiusi — vedi §3 e §5.1)*

Non ho ottenuto un run pulito end-to-end su questo repository, e lo dico prima
che qualcuno prenda le stime di A.4 per definitive:

- Con `tests_dir = ["tests/"]` la raccolta di calibrazione **falla**:
  `ModuleNotFoundError: No module named 'app.main'` da `tests/test_api.py` dentro
  la sandbox `mutants/` di mutmut, e il run si interrompe con
  `failed to collect stats`.
- Con `tests_dir` puntato ai due file di test, **54 mutanti su 60** risultano
  `no tests` — mutmut non ha associato loro alcun test, benché i test esistano.
- Le chiavi che ho usato sono **deprecate** in 3.6: `paths_to_mutate` →
  `source_paths`, `tests_dir` → `pytest_add_cli_args_test_selection`. È la
  spiegazione più probabile del punto precedente, e va verificata.

Spike proposto: **mezza giornata**, con esito «configurazione che gira e numeri
confermati» oppure «non è affidabile su questo stack, si rimanda». Le stime di
A.4 vanno considerate un ordine di grandezza fino a quel momento.

## A.7 Cosa chiedo di decidere

1. A, B o C.
2. Se B: autorizzo lo spike di mezza giornata di A.6.
3. Se B: il job è **non bloccante**, con tetto di 8 minuti e troncamento
   dichiarato nel report.

Non implemento nulla prima di questa decisione: il costo ricorrente è di Fahad.

---

# Appendice B — dettaglio tecnico della misura

## B.1 I tre caveat erano un'unica causa

Tutti e tre venivano dal fatto che **`mutmut` 3.6 non leggeva alcuna
configurazione**. Le chiavi stavano in `setup.cfg` con i nomi 2.x, e 3.6 legge
`[tool.mutmut]` da `pyproject.toml` quando `pyproject.toml` esiste — cioè
sempre, qui. Senza configurazione la sandbox `mutants/` nasceva incompleta, la
calibrazione moriva su `ModuleNotFoundError: app.main`, e i mutanti restavano
`no tests` perché la mappa test→funzione non veniva mai costruita.
Configurazione funzionante in §5.1.

## B.2 Il verificatore è verificato

Vedi §6: sonda con un ramo non testato, 4 sopravvissuti riportati con diff
leggibile. Quando lo strumento dice zero, zero è un esito e non un guasto.

## B.3 Determinismo e database

`conftest.py` costruisce lo schema con `DROP SCHEMA public CASCADE` +
`alembic upgrade head` in una fixture di **sessione**, e svuota le tabelle fra i
test. Con `--max-children N > 1` più processi di mutazione condividono lo stesso
database: se un giorno si riapre, ogni figlio ha bisogno del **proprio**
database, altrimenti un mutante può risultare «ucciso» perché un altro processo
gli ha tolto lo schema da sotto — cioè un punteggio gonfiato, nella direzione
che non se ne accorge nessuno.

## B.4 Perché lo strato API è cieco

`mutmut` salta le funzioni decorate perché i trampolini romperebbero
`@property` e duplicherebbero gli `@app.post("/foo")` (l'esecuzione del
decoratore a tempo di definizione registrerebbe la rotta una volta per mutante).
È una scelta difendibile dello strumento, non un bug — ed è per questo che è
strutturale e non si aggira dalla configurazione. Numeri e ripartizione in §5.3.

## B.5 Perché MYL-60 non sarebbe stato preso

Il catalogo di `mutmut` (`mutation/mutators.py`) contiene operatori su numeri,
stringhe, nomi, assegnamenti, operatori binari, `lambda`, `match`, argomenti di
chiamata e metodi di stringa simmetrici. **Nessuno rinomina un argomento con
nome.** `operator_dict_arguments` tocca solo la forma `dict(a=b)`;
`operator_arg_removal` sostituisce il *valore* di un argomento con `None` o lo
toglie. `timedelta(minutes=X)` → `timedelta(days=X)` non è un mutante che
`mutmut` sappia generare.

L'altro testimone citato nel mandato dello spike — l'AC 6 della Story 2.4,
verde con il meccanismo cancellato — era già dichiarato fuori portata perché
e2e. Restano **zero** dei due casi che giustificavano il costo ricorrente.

## B.6 Nota di metodo: la baseline è costata più dello spike

Su `main` (b15591e) la suite non partiva: 431 test in errore, per due migrazioni
che dichiaravano entrambe `revision = "0013"`. La causa è fuori da questo
documento e si è chiusa con MYL-75 (PR #56, che ripara la catena e aggiunge la
guardia `TestCatenaLineare`). Il punto di metodo però resta: **ho misurato la
suite prima di misurare lo strumento**, e senza quel passaggio avrei attribuito
a `mutmut` un guasto che non era suo — che è la stessa forma dell'errore della
§3, dove un guasto mio era stato attribuito allo strumento.

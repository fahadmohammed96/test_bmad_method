# Proposta — mutation testing in CI sui soli file cambiati

Stato: **spike eseguito, adozione NON raccomandata.** Decide Fahad; il costo
ricorrente di CI è suo.
Autore: Murat (Test Architect), 2026-07-30.

> **Leggi prima la §7.** Lo spike autorizzato (MYL-72) ha girato, e ha
> **smentito le misure di §3 e §4** su cui poggiava la raccomandazione B. Le
> sezioni §1–§6 restano com'erano scritte, come registro di ciò che avevo
> stimato: la §7 dice che cosa ho poi misurato. Dove le due parti divergono,
> vale la §7.

## In gioco

La copertura dice se una riga è stata *eseguita* da un test. Non dice se il test
si accorgerebbe che quella riga è **sbagliata**. Il mutation testing risponde a
quella seconda domanda: cambia il codice di proposito e controlla che almeno un
test cada. In questo Epic l'ho applicato a mano tre volte e ha trovato difetti
veri ogni volta. Questa proposta serve a togliermelo dalle mani e a farlo
diventare una proprietà del sistema.

## Opzioni

**A — Non farlo.** Costo zero. Il rischio resta quello di oggi: la forza della
suite dipende da chi la scrive e da quanto sono in vena di controllarla a mano.
Nessun cancello se ne accorge.

**B — Report non bloccante sul diff (raccomandata).** Su ogni PR gira sui soli
file cambiati e **commenta** i mutanti sopravvissuti. Non blocca il merge.
Costo stimato **2–5 minuti** di CI per PR (dettaglio in §3). Se il rumore è
tollerabile dopo un Epic, si valuta di renderlo bloccante.

**C — Cancello bloccante subito.** Stesso costo di CI, ma una PR può diventare
rossa per un mutante che nessuno dovrebbe uccidere. §4 mostra che, sul campione
misurato, sarebbe **capitato al primo colpo**.

## Raccomandazione

**B.** Il mutation testing è utile quanto è credibile, e la credibilità la
perde al primo rosso che tutti sanno di dover ignorare. Parte come report, e la
promozione a cancello è una decisione che si prende con i dati di un Epic, non
adesso. Il salto B→C è una riga di configurazione.

---

# Dettaglio tecnico

## 1. Strumento scelto: `mutmut` 3.6 (Python), rimandato per il frontend

`mutmut` è l'unico strumento Python maturo con supporto reale al 2026. Misurato
il 30/07, sul serio e non da documentazione:

| Cosa ho provato | Esito |
| --- | --- |
| `mutmut` 2.5.1 su Python 3.14 | **non parte** — `TypeError: cannot pickle 'itertools.count' object`. Tira dentro `pony` e `glob2`, con `SyntaxWarning` su 3.14. |
| `mutmut` 3.6.0 su Windows nativo | **rifiuta di partire**: «To run mutmut on Windows, please use the WSL» ([issue 397](https://github.com/boxed/mutmut/issues/397)). |
| `mutmut` 3.6.0 su Linux (container, Python 3.14) | **funziona**, con caveat in §5. |

Conseguenza pratica da mettere agli atti: in CI (Linux) va bene; **in locale su
Windows non è eseguibile senza WSL**. Chi sviluppa su Windows non potrà
riprodurre un finding del report senza passare da un container. È un costo reale
di adozione, non un dettaglio.

Per il frontend TypeScript lo strumento sarebbe **StrykerJS**. Non l'ho
misurato: non lo propongo in questo giro. Un cancello a metà è più facile da
tarare di due tarati male insieme.

## 2. Perimetro: il diff, non il repository

Mutare tutto `backend/app/` significherebbe circa **1150 mutanti** (densità
misurata: 60 mutanti su 131 righe di sorgente, ≈ 0.46 mutanti per riga, su 2524
statement). Fuori discussione a ogni PR.

Perimetro proposto: i file `.py` sotto `backend/app/` **toccati dalla PR**, con
`mutmut` che per costruzione esegue solo i test che coprono la riga mutata. Un
diff tipico di questo progetto (50–150 statement cambiati) produce **25–70
mutanti**.

## 3. Costo in minuti di CI

Misurato in container Linux, `--max-children 4`:

- throughput osservato: **44.87 mutazioni/secondo** sul campione (la maggior
  parte scartata subito perché priva di test che la coprano — vedi §5);
- i mutanti effettivamente eseguiti sono costati **≈ 0.7 s ciascuno** con un
  sottoinsieme di test da 1.34 s e parallelismo 4;
- costo fisso del job: checkout + `uv sync --locked` + run di calibrazione
  ≈ **1.5–2 minuti**.

| Scenario | Mutanti | Stima |
| --- | --- | --- |
| PR su moduli puri (`date_range`, `regime_fiscale`, `normalizzazione`, `uscita_rete`) | 25–70 | **2–3 min** |
| PR su moduli che toccano il DB (`service`, `repository`) | 25–70 | **3–5 min**, alta varianza |
| PR di soli documenti | 0 | job saltato |

Il secondo scenario è quello da tenere d'occhio: i test che coprono
`calendario/service.py` girano su Postgres reale, e lì il costo per mutante è di
secondi, non di millisecondi. Con un **tetto di tempo** sul job (proposta: 8
minuti, oltre i quali il job si ferma e riporta quanti mutanti sono rimasti non
verificati) il costo resta prevedibile. Il tetto va **dichiarato nel report**:
un troncamento silenzioso si legge come «tutto verificato».

## 4. Come si evita che diventi un cancello rumoroso

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

## 5. Caveat da chiudere in uno spike, prima di attivare qualunque cosa

Non ho ottenuto un run pulito end-to-end su questo repository, e lo dico prima
che qualcuno prenda le stime di §3 per definitive:

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
§3 vanno considerate un ordine di grandezza fino a quel momento.

## 6. Cosa chiedo di decidere

1. A, B o C.
2. Se B: autorizzo lo spike di mezza giornata di §5.
3. Se B: il job è **non bloccante**, con tetto di 8 minuti e troncamento
   dichiarato nel report.

Non implemento nulla prima di questa decisione: il costo ricorrente è di Fahad.

---

# 7. Esito dello spike (MYL-72, 30/07) — e perché non ho implementato il report

## In gioco

Lo strumento **funziona**: la configurazione che non girava adesso gira, e
quando trova qualcosa lo dice in modo leggibile. Ma su questo codice, oggi,
**non trova niente**: gliel'ho dato in pasto su 1712 modifiche deliberate al
codice di produzione e la suite le ha respinte tutte. Zero segnalazioni.

Non è una buona notizia soltanto: significa anche che il motivo per cui volevamo
lo strumento — il difetto MYL-60, l'unità di misura sbagliata nella
riprogrammazione — **non è del tipo che questo strumento sa fabbricare**. Non
l'avrebbe trovato nemmeno se fosse stato attivo quel giorno.

## Opzioni, con le conseguenze pratiche

| | Cosa comporta | Costo ricorrente |
| --- | --- | --- |
| **A — non adottare (raccomandata)** | resta il rischio di oggi; il controllo a mano continua quando serve | zero |
| **B' — adottarlo comunque come report** | ~4 minuti di CI per PR e un report che, sui dati di oggi, sarebbe vuoto; il rischio è che «report vuoto» venga letto come «verificato», che è più di quanto lo strumento garantisca | ~4 min/PR |

## Raccomandazione: A, con una data di riesame

Non adottarlo **adesso**. Non perché sia inaffidabile — l'ho verificato e
riporta correttamente — ma perché il rapporto fra ciò che costa e ciò che vede
non regge oggi: paga 4 minuti a PR per esaminare l'83% del codice e non trovare
nulla, e il 17% che non esamina è proprio lo strato che va in mano all'utente.

Si rivaluta quando accade **una** di queste tre cose, e la prima è la più
probabile: (1) un controllo manuale di mutazione trova di nuovo un difetto vero
— cioè la suite ha smesso di essere così severa; (2) `mutmut` impara a mutare
le funzioni decorate; (3) entra in gioco un secondo team che non ha scritto
questi test e la severità della suite smette di essere una proprietà nota.

**Non ho implementato il report** perché il punto 2 dell'incarico — «con le
mutazioni sui letterali stringa disattivate» — poggia su una misura che non si
riproduce (§7.2) e chiede una leva che nello strumento **non esiste** (§7.3).
Implementarlo lo stesso avrebbe prodotto un cancello diverso da quello
deliberato, con l'aria di essere quello deliberato.

---

## Dettaglio tecnico

### 7.1 La configurazione: i tre caveat di §5 erano miei, e sono chiusi

Tutti e tre venivano dalla stessa causa: **`mutmut` 3.6 non leggeva nessuna
configurazione**. Le chiavi stavano in `setup.cfg` con i nomi 2.x, e 3.6 legge
`[tool.mutmut]` da `pyproject.toml` quando `pyproject.toml` esiste — cioè
sempre, qui. Senza configurazione la sandbox `mutants/` nasceva incompleta, la
calibrazione moriva su `ModuleNotFoundError: app.main`, e i mutanti restavano
`no tests` perché la mappa test→funzione non veniva mai costruita.

Configurazione che gira, misurata:

```toml
[tool.mutmut]
source_paths = ["app"]
# La sandbox `mutants/` riceve `app/` e `tests/`, e nient'altro. Le
# migrazioni servono: `conftest.py` fa `alembic upgrade head` prima di
# qualunque test su database.
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

Quel blocco di otto `--ignore` **è esso stesso un costo di adozione**, e va
letto per quello che è: sono le nostre guardie strutturali, e cadono dentro la
sandbox non perché il codice sia rotto ma perché `mutmut` riscrive ogni metodo
in `xǁClasseǁmetodo__mutmut_N`. `test_tenancy_convention.py` ispeziona i
repository per riflessione e trova diciannove «metodi senza `host_id`» che sono
tutti mutanti; `test_copertura_convention.py` legge `.github/workflows/ci.yml`
risalendo di una directory, e dalla sandbox quella directory non esiste.
Conseguenza: **la suite che gira dentro la sandbox non è la suite del
repository**, e la differenza sono proprio i controlli che sorvegliano i
controlli.

### 7.2 Lo strumento è credibile — e non trova niente

Prima di credere a un «zero sopravvissuti» ho verificato che lo strumento sappia
*dire* «sopravvissuto». Sonda: una funzione con un ramo che nessun test
esercita, aggiunta ad `app/core/date_range.py`.

```
app.core.date_range.x__sonda_spike__mutmut_1: survived   (if x > 10  →  if x >= 10)
app.core.date_range.x__sonda_spike__mutmut_2: survived   (if x > 10  →  if x > 11)
app.core.date_range.x__sonda_spike__mutmut_3: survived   (return x + 1  →  return x - 1)
app.core.date_range.x__sonda_spike__mutmut_4: survived   (return x + 1  →  return x + 2)
```

Quattro sopravvissuti, con il diff leggibile che servirebbe al report. **Il
verificatore è verificato**: quando dice zero, zero è un esito.

E dice zero. Su codice reale, con la configurazione di §7.1:

| Perimetro | Mutanti | Uccisi | `no tests` | **Sopravvissuti** |
| --- | ---: | ---: | ---: | ---: |
| `core/date_range.py` + `strutture/regime_fiscale.py` (il campione di §4) | 60 | 60 | 0 | **0** |
| I 7 file di `app/` toccati dalla PR #52 (Story 2.4, +605 righe) | 1652 | 1642 | 10 | **0** |

**I 3 sopravvissuti di §4 non esistono.** Erano l'effetto della calibrazione
fallita: senza la mappa test→funzione, un mutante che nessun test raggiunge
viene contato come non ucciso. Quindi il «100% di falsi positivi» che
giustificava la leva sulle stringhe **non si riproduce**, e con esso decade il
punto 2 dell'incarico.

L'unico segnale prodotto da 1712 mutanti sono i 10 `no tests`, tutti su
`PrenotazioneRepository.della_struttura` (`app/calendario/repository.py:491`).
Non è un falso positivo: quel metodo **non è chiamato da nessuno** — l'unico
`della_struttura` usato in produzione è quello di `FeedIcalRepository`. Codice
morto entrato con la Story 2.4. Vale una riga di pulizia, non un cancello.

### 7.3 «Disattivare le mutazioni sui letterali stringa» non è una cosa che si può fare

In `mutmut` 3.6 `mutation_operators` è una costante di modulo
(`mutmut/mutation/mutators.py`): **non c'è nessuna opzione per spegnere un
operatore**. Le uniche leve sono due, e nessuna delle due fa quello che serve:

- `# pragma: no mutate` **nel sorgente di produzione** — commenti di
  configurazione di uno strumento di QA sparsi nel codice applicativo;
- `do_not_mutate_patterns`, che è una regex applicata **riga per riga**: la riga
  che combacia esce *interamente* dalla mutazione. Una regex che prenda i
  letterali stringa spegnerebbe anche le mutazioni di logica che condividono
  quella riga — cioè renderebbe lo strumento più cieco, non meno rumoroso, e in
  silenzio.

### 7.4 Cecità strutturale: 17.4% di `backend/app/`, concentrato sullo strato API

`mutmut` **salta per costruzione** le funzioni decorate (tranne un solo
`@staticmethod`/`@classmethod`) e le classi decorate con tutti i loro metodi. È
documentato nel suo sorgente: i trampolini rompono `@property` e duplicherebbero
gli `@app.post("/foo")`. Misurato su `backend/app/` — 258 funzioni mutabili
(3909 righe) contro 53 saltate (824 righe):

| File | Righe cieche / totali |
| --- | --- |
| `app/config_normativa/api.py` | 81/81 — **100%** |
| `app/strutture/api.py` | 85/91 — 93% |
| `app/identity/api.py` | 79/90 — 88% |
| `app/calendario/api.py` | 269/345 — 78% |
| `app/calendario/jobs.py` | 138/294 — 47% |
| `app/core/date_range.py` | 18/28 — 64% (la classe `DateRange` è `@dataclass`) |

Vale la pena fermarsi sull'ultima riga: `DateRange.overlaps` — l'intersezione
che regge l'anti-double-booking (AD-3) — riceve **zero mutanti**, perché la
classe è un `@dataclass`. E su `calendario/jobs.py` la cecità è dovuta a
`@handlers.register`, cioè gli handler dei job.

### 7.5 Il difetto che motivava l'adozione non sarebbe stato preso

MYL-60 è uno scambio di unità di misura: `timedelta(minutes=…)` →
`timedelta(days=…)`. È la **rinomina di un argomento con nome**, e nel catalogo
di `mutmut` non esiste un operatore che la produca: `operator_dict_arguments`
tocca solo `dict(a=b)`, `operator_arg_removal` sostituisce il *valore* con
`None` o toglie l'argomento. Quel mutante non viene mai generato.

L'altro testimone citato nell'incarico — l'AC 6 della Story 2.4, verde con il
meccanismo cancellato — era già dichiarato fuori portata perché e2e. Restano
**zero** dei due casi che giustificavano il costo ricorrente.

### 7.6 Il costo: non è quello stimato, e non scala con la dimensione del diff

Il costo si divide in due, e la parte grossa **non dipende dal diff**:

- **Fisso: 1 min 51 s.** Misurato con *zero* mutanti da eseguire
  (`only_mutate = ["app/api/health.py"]`, che è 100% decorato). È la passata di
  copertura su **tutta** la suite con cui `mutmut` costruisce la mappa
  test→funzione. Restringere il perimetro al diff non la accorcia.
- **Variabile:** sulla PR #52, 1652 mutanti a 15.49 mutazioni/s ≈ 1 min 47 s.
  **Totale ≈ 3 min 40 s**, dentro il tetto di 8 minuti proposto in §3.

Ma la variabile non si comporta come dice l'intuizione. Throughput misurato:

| Perimetro | Mutazioni/s |
| --- | ---: |
| `calendario/service.py` + `repository.py` + `api.py` (+605 righe) | **15.49** |
| `core/date_range.py` (una manciata di righe) | **0.41** |

Trentotto volte più lento su un file **molto più piccolo**, perché `mutmut`
esegue i test che *coprono* la riga mutata: `date_range` è importato ovunque,
quindi ogni suo mutante trascina mezza suite. **Il costo scala con quanto è
importato il modulo toccato, non con quante righe ha cambiato la PR.** Una PR da
una riga su `app/core/` può costare più di una Story intera su un modulo
foglia — e la stima di §3, costruita sulla dimensione del diff, misura la cosa
sbagliata.

### 7.7 Windows: confermato

`mutmut` 3.6.0 su Windows nativo, Python 3.14, verificato di nuovo il 30/07:

```
To run mutmut on Windows, please use the WSL. Native windows support is
tracked in issue https://github.com/boxed/mutmut/issues/397
```

Tutte le misure di questa sezione vengono da un container Linux
(`python:3.14-slim` + PostgreSQL 18 sul loopback). Chi sviluppa su Windows non
riproduce un finding del report senza WSL o senza container: se un giorno il
report si adotta, questa riga va nel README del backend e non solo qui.

### 7.8 Nota di metodo

La baseline è costata più dello spike. Su `main` (b15591e) la suite non parte:
431 test in errore. La causa è fuori da questo documento (due migrazioni
`0013`, vedi `backend/tests/test_migrations.py`), ma il punto di metodo resta:
**ho misurato la suite prima di misurare lo strumento**, e senza quel passaggio
avrei attribuito a `mutmut` un guasto che non era suo — che è esattamente
l'errore da cui nascono i tre caveat di §5.

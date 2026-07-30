# Proposta — mutation testing in CI sui soli file cambiati

Stato: **proposta, non implementata.** Decide Fahad; il costo ricorrente di CI è suo.
Autore: Murat (Test Architect), 2026-07-30.

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

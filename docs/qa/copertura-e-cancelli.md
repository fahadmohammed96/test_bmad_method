# Copertura dei test e cancelli di qualità

Stato: **attivo dal 2026-07-30**. Chiude MYL-59.
Autore: Murat (Test Architect). Aggiornare via PR quando i numeri o i cancelli cambiano.

Questo documento esiste per una ragione precisa: per settimane ogni consegna di
questa squadra ha citato «SonarCloud Quality Gate verde» come parte
dell'evidenza, e quella evidenza **non diceva nulla sulla copertura**. Chi legge
un verdetto deve poter sapere, senza aprire un workflow, che cosa è stato
misurato davvero.

---

## 1. Che cosa misura il Quality Gate SonarCloud (misurato, non supposto)

Interrogato il 2026-07-30 via `api/measures/component` sul progetto
`fahadmohammed96_test_bmad_method`, il campo `quality_gate_details` riporta
**cinque** condizioni, tutte `OK`:

| Condizione | Soglia |
| --- | --- |
| `new_reliability_rating` | > 1 → fallisce |
| `new_security_rating` | > 1 → fallisce |
| `new_maintainability_rating` | > 1 → fallisce |
| `new_duplicated_lines_density` | > 3% → fallisce |
| `new_security_hotspots_reviewed` | < 100% → fallisce |

`"ignoredConditions": false`. **Nessuna condizione riguarda la copertura.**

Non solo la condizione manca: il dato non esiste. Le metriche `coverage`,
`new_coverage` e `tests` non sono presenti nella risposta, e
`new_uncovered_lines` vale `0` con `bestValue: true` su `new_lines: 27292` —
cioè SonarCloud crede che **zero** righe su ventisettemila siano scoperte,
perché non ha mai ricevuto un report. Il `0.0% Coverage on New Code` mostrato
sul widget delle PR non era un esito basso: era l'assenza del dato.

Causa: l'analisi in uso è la **Automatic Analysis** di SonarCloud, che per
costruzione non importa report di copertura. Non esiste
`sonar-project.properties` nel repository e non c'è alcuno step Sonar in
`.github/workflows/`.

**Come va letto, quindi, «SonarCloud verde» in un verdetto:** dice che il codice
nuovo non introduce bug o vulnerabilità note allo strumento, non è duplicato e
non lascia security hotspot da rivedere. **Non dice niente sui test.** Chi cita
quel check come evidenza di copertura sta citando la cosa sbagliata.

---

## 2. Che cosa misura la CI, da oggi

La copertura è diventata una proprietà della **nostra** pipeline, che non
dipende da un servizio esterno, da un segreto, né da una configurazione che non
possiamo leggere.

### 2.1 I numeri reali al 2026-07-30 (`main` a `7d4eb7c`)

| | Test | Copertura misurata |
| --- | --- | --- |
| Backend (`pytest --cov`, riga + ramo) | 658 verdi | **96.44%** — 2524 statement, 72 scoperti |
| Frontend (`vitest --coverage`, v8) | 140 verdi | **73.93%** di riga, 86.86% di ramo |

La disciplina di test c'era; era la misura a non esserci.

### 2.2 Il cancello: copertura del **diff**

Il job `copertura` in `ci.yml` gira su ogni PR, scarica i report prodotti dai job
`backend` e `frontend`, e fa fallire la PR se le righe **toccate** non sono
coperte:

- backend: soglia **90%**
- frontend: soglia **75%**

### 2.3 Il backstop: pavimenti globali

`fail_under = 93` in `backend/pyproject.toml`, `thresholds` in
`frontend/vitest.config.ts` (70% riga, 80% ramo).

**Questi pavimenti non sono il cancello, e la differenza è misurata.** Togliendo
`backend/tests/test_calendario_sync.py` intero — 81 test, il file che copre il
modulo più rischioso del progetto — il totale scende da **96.44% a 95.16%**: un
pavimento a 93 non se ne accorge. Un totale globale è tenuto su dai test che
attraversano le stesse righe per altri motivi, e si diluisce sul codice che
cresce. Serve comunque, perché intercetta il crollo (una suite che smette di
girare, uno strato intero consegnato senza test) — che è esattamente ciò che
nessuno misurava prima.

### 2.4 Perché le due soglie sono diverse

Il frontend parte da 73.93% e non da 96% per una ragione **strutturale**, non di
disciplina: le `page.tsx` e `lib/api/hooks.ts` sono esercitate dagli **e2e
Playwright**, la cui copertura non viene raccolta. Chiedere 90% di patch
coverage al frontend produrrebbe rossi su codice che *è* coperto — il cancello
rumoroso che si impara a ignorare, che è un modo più lento di non avere un
cancello.

**Limite noto da registrare, non da nascondere:** finché la copertura degli e2e
non viene raccolta, il numero del frontend sottostima la realtà e la soglia resta
prudente. Raccoglierla è il naturale seguito di questo lavoro.

### 2.5 Le forme di silenzio sorvegliate

Un difetto di **assenza** non produce righe rosse: la configurazione della
copertura vive in tre posti e toglierne uno non rompe niente di visibile.
`backend/tests/test_copertura_convention.py` fa cadere la suite se sparisce una
di queste cose. Tutte riprodotte a mano il 2026-07-30:

| Se sparisce | Cosa succede senza la guardia |
| --- | --- |
| `--cov` dallo step di test | nessun `coverage.xml`: il job `copertura` non ha input |
| `npm run test:coverage` | nessun `lcov.info`: metà cancello inesistente |
| `sed 's|^SF:|SF:frontend/|'` | `diff-cover` stampa «No lines with coverage information» ed **esce 0** |
| `all: true` da vitest | un componente senza test **esce** dalla misura invece di abbassarla |
| `omit = []` che si popola | il numero sale senza che nessuno scriva un test |
| `--fail-under` | `diff-cover` diventa un report travestito da cancello |

La terza riga merita una nota: i percorsi `SF:` di lcov sono relativi a
`frontend/`, mentre `git diff` parla in percorsi relativi alla radice. Senza la
normalizzazione i due insiemi non si intersecano e il cancello **passa a vuoto**.
Riprodotto su un file TS nuovo e interamente scoperto: passava. Per questo il job
contiene anche una guardia esplicita che distingue «la PR non tocca codice
misurato» (legittimo) da «il report non conosce il codice che la PR tocca»
(guasto).

Nota sui pathspec: le graffe sono espanse a mano perché `:(glob)` di git usa
wildmatch, che **non** conosce `{app,components,lib}`. La forma compatta non dà
errore: torna zero file, e disattiva la guardia da sola.

---

## 3. Che cosa resta da fare, e non è del Test Architect

Due cose richiedono i permessi di amministrazione del progetto SonarCloud e i
segreti del repository. Nessuna delle due è necessaria perché il cancello del
punto 2 funzioni: servono per far dire a Sonar la verità, non per averla.

### 3.1 Far arrivare la copertura a SonarCloud

1. Disattivare la **Automatic Analysis** nel progetto SonarCloud (le due si
   escludono).
2. Aggiungere il segreto `SONAR_TOKEN` al repository.
3. Committare `sonar-project.properties`:

   ```properties
   sonar.projectKey=fahadmohammed96_test_bmad_method
   sonar.organization=fahadmohammed96
   sonar.sources=backend/app,frontend/app,frontend/components,frontend/lib
   sonar.tests=backend/tests,frontend/e2e
   sonar.exclusions=frontend/lib/api/schema.d.ts,backend/alembic/versions/**
   sonar.python.version=3.14
   sonar.python.coverage.reportPaths=backend/coverage.xml
   sonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info
   ```

4. Aggiungere alla CI `sonarqube-scan-action` **pinnata al commit SHA**, dopo il
   download degli artefatti di copertura.

Questo file **non è committato in questa PR di proposito**: con la Automatic
Analysis attiva, introdurlo cambia il comportamento dell'unico check Sonar
esistente e non posso verificarne l'esito senza i permessi di amministrazione.
Consegnare una configurazione che non ho potuto provare sarebbe la stessa classe
di errore che questo documento chiude.

### 3.2 Mettere la copertura *nel* gate

Anche con la copertura che arriva, il gate non la valuta: la condizione va
aggiunta a mano fra le cinque del punto 1 (`new_coverage`, tipicamente ≥ 80% sul
nuovo codice). **Finché non c'è, «Sonar verde» continuerà a non dire nulla sui
test** — e il cancello che conta resterà quello della nostra CI.

---

## 4. Come citare la copertura in un verdetto

Forma corretta, dal 2026-07-30:

> Copertura del diff: backend N% (soglia 90), frontend M% (soglia 75) — job
> `copertura`. SonarCloud verde su affidabilità, sicurezza, manutenibilità,
> duplicazione e hotspot; **il gate Sonar non valuta la copertura**.

Forma da non usare più: «CI + Sonar verdi» come evidenza implicita che i test
coprano il codice nuovo.

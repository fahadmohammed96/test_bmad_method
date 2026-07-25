---
title: 'Retrospettiva — Epic 1 (Fondamenta della piattaforma e gestione delle Strutture)'
status: 'consegnata via PR — merge umano'
phase: '4 · Implementation — rito di chiusura Epic 1, passo 2'
epic: 'Epic 1 · Story 1.1 → 1.6'
created: 2026-07-25
facilitator: Amelia — Senior Software Engineer
inputDocuments:
  - docs/qa/test-design-epic-1.md §7 (matrice finale di Murat — PR #25, branch qa/epic1-chiusura-debito-zero)
  - docs/stories/story-1.1 … story-1.6 (sezioni Dev Agent Record, Note di completamento, Change log)
  - docs/epics.md (Epic 1 e Epic 2), docs/implementation-readiness.md, docs/project-context.md
  - _bmad/_memory/dev-sidecar/memories.md
  - cronologia git del repo (56 commit, 25 PR) e messaggi di commit dei fix-batch
---

# Retrospettiva — Epic 1

## 0. Nota di metodo (leggere prima)

La skill `bmad-retrospective` **è installata** in questo runtime. Non l'ho eseguita come
previsto, e va detto perché: è progettata come sessione **interattiva in party mode**, con
tredici passi che si fermano ad attendere le risposte dell'umano e con dialoghi recitati fra
agenti. Qui non c'è un interlocutore in linea e gli altri agenti non hanno parlato: eseguirla
alla lettera avrebbe prodotto un verbale di una riunione mai avvenuta, con battute messe in
bocca a Murat e a John.

Ho quindi seguito la **sostanza** del workflow — analisi profonda dei record di story (passo 3),
verifica della retrospettiva precedente (passo 4: non esiste, questa è la prima), preview
dell'Epic successivo (passo 5), sintesi delle azioni (passo 9), readiness check (passo 10) — e
l'ho scritta come documento strutturato. Nessun dialogo simulato. Le opinioni qui dentro sono
mie, di Amelia; dove riporto il lavoro di altri, riporto l'artefatto, non una frase inventata.

Il passo 12 della skill vorrebbe aggiornare `sprint-status.yaml`: **quel file non esiste in
questo repo** (non è mai stato generato dalla sprint planning). Le azioni di §6 restano quindi
in questo documento, ed è a questo documento che vanno riferite.

---

## 1. L'Epic 1 in numeri verificabili

| Dato | Valore | Dove si verifica |
| --- | --- | --- |
| Story consegnate | 6 su 6 (1.1 → 1.6) | PR #9, #10, #13, #14, #16, #19 |
| Acceptance criteria coperti | 48 su 48, tutti con test verde al livello previsto | matrice §7.5 |
| Finding di qualità aperti nell'Epic | 9 (2 P0, 4 P1, 3 P2) | matrice §7.4 |
| Finding chiusi entro l'Epic | 9 su 9, nessun waiver | matrice §7.4, §7.6 |
| Test backend a fine Epic | 62 → 159 su PostgreSQL 18 reale | Dev Agent Record 1.1 → 1.6 |
| Test frontend / e2e a fine Epic | 29 component + 10 e2e (chromium + mobile), axe serious/critical = 0 | Dev Agent Record 1.6 |
| Guardie strutturali attive | 2 (`test_auth_convention.py`, `test_tenancy_convention.py`) | matrice §7.2 |
| PR totali dell'Epic | 16 | cronologia git |
| — di cui consegnano funzionalità | **6** | #9, #10, #13, #14, #16, #19 |
| — di cui sono correzione | **4** fix-batch | #12, #18, #21, #23 |
| — di cui sono tracciamento QA | **6** | #11, #15, #17, #20, #22, #24 |
| Rischi tracciati alla chiusura (non debito) | 4 (RT-1 … RT-4) | matrice §7.7 |

Il numero che conta più degli altri è l'ultimo blocco: **su 16 PR dell'Epic, 6 portano valore
e 10 sono correzione o contabilità.** Non è un fallimento — il debito zero è reale ed è stato
pagato — ma è la misura onesta di quanto sia costato arrivarci.

---

## 2. Cosa ha funzionato

Cinque cose, tutte con un'evidenza che sopravvive a chi le ha fatte.

**2.1 — Le guardie strutturali.** `test_auth_convention.py` e `test_tenancy_convention.py`
non testano un comportamento: camminano lo schema e le route e falliscono quando una
convenzione è violata. Il risultato è che un modulo scritto fra sei mesi da chi non c'era
**non può** dimenticare `host_id` o esporre un endpoint senza sessione. Le eccezioni stanno in
allowlist esplicite, a loro volta sorvegliate da un test che fa decadere l'esenzione se
l'oggetto esentato cambia natura. È il singolo investimento con il rapporto valore/costo più
alto di tutto l'Epic, ed è anche l'unico presidio che non si degrada con il tempo.

**2.2 — Il contratto API imposto dalla pipeline.** Il job `api-contract` rigenera OpenAPI e
client TypeScript e fallisce sul `git diff`. In sei story il contratto non è mai andato alla
deriva, senza che nessuno se ne dovesse ricordare.

**2.3 — Il DB reale in CI, senza scorciatoie.** `HOSTPILOT_TEST_DB_REQUIRED=1` rende errore
lo *skip* dei test su Postgres. Vuol dire che una pipeline verde implica sempre che quei test
sono girati davvero: la CI non può essere verde a vuoto. Vale la pena sottolinearlo perché è
esattamente la difesa che il resto di questa retrospettiva dimostra essere insufficiente **da
sola**, ma senza la quale non avremmo nemmeno un punto di partenza.

**2.4 — Il degrado sicuro come scelta di prodotto.** `configurazione_non_disponibile` invece
di un default inventato (Story 1.5) è la decisione di cui andrei più fiero: il sistema
preferisce dire "non so" piuttosto che dare un numero sbagliato a un host che poi ci costruisce
sopra un versamento. Il tono informativo invece che d'errore ha anche un test che vieta le
parole di colpa. È architettura e prodotto che dicono la stessa cosa.

**2.5 — Il test-first, dove è stato fatto davvero.** Il caso più netto è la Story 1.6: il test
di ridiscesa-e-risalita (3 Strutture → archivio → nuova terza) ha mostrato che legare la
conferma di lettura al conteggio non bastava, e **il design è cambiato per via del test**, non
il test per via del design. Quello è il ciclo che funziona.

---

## 3. Cosa NON ha funzionato

Questa è la parte che conta. Ogni voce prova a rispondere a *perché è successo*, non solo a
*cosa è successo*.

### 3.1 — La causa a monte: il kickoff di qualità è stato saltato

Il documento di test design lo dice di sé stesso: *«Recupera il kickoff di qualità saltato»*.
È arrivato (PR #11) **dopo** che la Story 1.1 e la Story 1.2 erano già mergiate.

Il conto: dei nove finding dell'Epic, **quattro nascono dalla sola Story 1.2** (G-2, G-3, G-4,
G-5) e uno dalla 1.1 (G-1, aperto da una «review retroattiva»). Cinque su nove — la maggioranza
— vengono dalle due story consegnate senza un piano di test davanti. Le story successive, quelle
scritte con il piano già esistente, ne hanno generati quattro in totale.

Perché è successo: la Fase 4 è partita subito dopo il gate G3 e il modulo TEA è entrato in
parallelo invece che prima. Non è colpa di nessuno in particolare, è un ordine sbagliato nella
sequenza. E il costo non si vede nella qualità finale (il debito è zero) ma nel **percorso**:
quei cinque finding sono diventati due fix-batch, sei PR di tracciamento e un debito della 1.2
che si è chiuso solo alla PR #23, cioè all'ultimo respiro dell'Epic.

### 3.2 — Due difetti trovati dalla review e invisibili a una CI verde

I due sono **F-1** (il cap "3 Strutture attive" non era atomico: due `POST` concorrenti potevano
lasciarne 4) e **F-3** (`secrets.compare_digest` su un header non-ASCII sollevava `TypeError`,
restituendo 500 invece di 403). Entrambi trovati in review, entrambi con la pipeline verde,
entrambi chiusi dallo stesso fix-batch (PR #21).

**Cosa rende un difetto invisibile a una CI verde.** Una pipeline verde non dimostra che il
codice è corretto: dimostra che *gli input che le abbiamo dato* producono l'atteso. I difetti
che sopravvivono sono quelli il cui input la suite non genera mai. Nell'Epic 1 se ne sono viste
quattro classi distinte:

1. **Interleaving.** Nessun test produce una gara se non la si costruisce apposta. F-1 e G-2
   sono lo stesso identico difetto — leggi, decidi, scrivi, senza serializzazione — trovato due
   volte a tre story di distanza. La seconda volta è la prova che la prima non ci aveva insegnato
   niente.
2. **Input fuori dall'alfabeto immaginato.** F-3 è un byte non-ASCII in un'intestazione HTTP.
   Nessuno scrive quel test perché nessuno pensa a quell'input: le intestazioni sono decodificate
   latin-1 e il confronto su `str` esplode.
3. **Assenze.** G-3 (nessuna guardia di tenancy) e C1 (nessuna copertura a11y/e2e in CI) non
   hanno un test rosso perché non hanno codice. Un pezzo mancante non fallisce: tace. Questa
   classe la vede solo una review, o un meta-test che verifica l'esistenza di un presidio.
4. **La colla fra livelli mockati** — vedi §3.3.

**Cosa possiamo spostare dentro la CI senza renderla lenta.** Il criterio è: aggiungere test
che costano *unità*, non aggiungere fasi che costano *pipeline*.

- **Un test di gara per ogni check-then-write.** Costo: una manciata di secondi per test. Il
  pattern è già scritto (8 thread + `threading.Barrier`; con 2 thread l'interleaving spesso non
  capita). Va reso obbligatorio, non facoltativo.
- **Property test leggeri sui confini testuali** (non-ASCII, stringa vuota, unicode) sugli input
  che attraversano confronti binari, header e parsing. Poche righe, nessun costo di pipeline.
- **Altre guardie strutturali.** Sono la difesa più economica che abbiamo: girano in millisecondi
  e coprono la classe "assenze", che è quella dove sono finiti entrambi i P0.
- **Un job di supply chain informativo** (`npm audit --omit=dev` + audit delle dipendenze Python)
  che riporti senza bloccare, così RT-1 non si scopre a fine Epic.

**Cosa invece NON va spostato in CI: altri e2e.** RT-4 dice che la copertura e2e è volutamente
stretta ed è una scelta corretta. L'e2e paga solo dove è l'unico livello che vede il difetto
(§3.3); altrove è flakiness travestita da copertura.

### 3.3 — Il difetto di cache che solo l'e2e poteva vedere

Nella Story 1.6, dopo l'archiviazione di una Struttura, il pannello Regime fiscale continuava a
dire "3 Strutture attive". Le mutazioni invalidavano la cache `strutture` ma non quella
`regime-fiscale`, che è una query separata su un valore **derivato** dallo stesso conteggio.

I test di componente non potevano vederlo, e non per distrazione: in quei test gli hook sono
mockati, quindi **la cache non esiste nel loro mondo**. Il difetto non vive in un livello, vive
nella colla fra due livelli — e ogni livello che mocka la colla è cieco per costruzione.

Scritta come regola, non come aneddoto:

> **Regola dell'e2e giustificato.** Un valore derivato che ha una propria query lato client
> richiede almeno un percorso end-to-end che **muti la sorgente e osservi il derivato**.
> L'e2e full-stack non si giustifica con la copertura — quella la danno i livelli sotto, a costo
> minore — ma con la **classe di difetti di cui è l'unico testimone**: quelli che stanno fra i
> componenti, non dentro. Corollario: se non sai nominare quale difetto solo l'e2e vedrebbe,
> quell'e2e non serve e va scritto più in basso.

Questa regola è già depositata nella libreria di squadra (voce del 2026-07-25 in
`knowledge/dev/lezioni.md`, PR #2 mergiata). È l'unica cosa che rende il costo dell'e2e in CI
difendibile davanti a chi lo vede solo come tempo di pipeline.

### 3.4 — I finding Sonar sulla supply chain sono arrivati tre story dopo la CI

La CI è nata con la Story 1.1. Il quality gate SonarCloud l'ha bocciata alla **Story 1.4**, con
sei vulnerabilità MAJOR e un Security Rating "C" sul nuovo codice: action di terze parti non
pinnate al commit SHA (il tag è mutabile), `uv sync` e `npm ci` che eseguivano script di terze
parti, `npx` che installa pacchetti on-demand invece di usare il lockfile. Nella stessa story
`npm ci` falliva per un `package-lock.json` fuori sync. E non è bastato un giro: il branch della
1.4 porta **due** commit di correzione Sonar consecutivi (`9f82b9f`, poi `e83722f`), perché il
primo non aveva coperto tutti i job. La 1.5 ne ha aggiunto un terzo (`8931fe7`, validazione del
percorso CSV) che il Change log della story **non registra nemmeno**.

**Perché è successo.** Alla Story 1.1 la CI è stata scritta come *impalcatura*: "far girare i
test". Non è stata trattata come codice soggetto alle stesse regole del codice applicativo, e
soprattutto non è stata scritta contro un modello di minaccia. Un workflow di CI ha accesso al
repository, ai segreti e alla rete: è la superficie di attacco più privilegiata del progetto, e
l'abbiamo scritta con meno attenzione di un endpoint.

**Cosa avremmo dovuto sapere alla Story 1.1.** Questa checklist, applicata *prima* di scrivere
la prima riga di `.github/workflows/`:

- action di terze parti **pinnate al commit SHA**, mai al tag;
- installazione **solo da lockfile** e **senza esecuzione di script**
  (`uv sync --locked --no-build --no-install-project`, `npm ci --ignore-scripts`);
- mai `npx` in pipeline: `npm exec --no --` usa la versione del lockfile;
- il lockfile si verifica con `npm ci`, **non** con `npm install` (le opzionali multipiattaforma
  restano disallineate e fanno cadere tutti i job che installano il frontend);
- blocco `permissions:` esplicito e minimo a livello di workflow.

L'ultimo punto è ancora aperto oggi: `.github/workflows/ci.yml` **non ha un blocco
`permissions:`**, quindi il `GITHUB_TOKEN` gira con i permessi di default del repository. Non è
stato segnalato da nessuno e non è un finding dell'Epic 1 — lo scrivo qui perché è esattamente
il tipo di cosa che si scopre alla prossima story se non la mettiamo in lista adesso.

Nota di merito, per equilibrio: la correzione è stata fatta bene. Il pin SHA è stato esteso a
tutti i job, non solo a quello che Sonar aveva bocciato, e il commento in testa al workflow
documenta la postura invece di lasciarla implicita.

### 3.5 — La regola «verdetto prima del merge» è arrivata a metà Epic

Introdotta da Murat dalla Story 1.3 in poi, dopo che una PR di fix-forward era stata mergiata
senza verdetto. **Ha funzionato**, e la prova è nel prezzo pagato dalle PR che l'hanno preceduta:
#12 (G-1, G-2, G-4) e #18 (F-2) sono state **verificate retroattivamente**. La verifica è stata
fatta e documentata, non saltata — ma è lavoro fatto due volte, e con l'aggravante che una
verifica retroattiva su codice già in `main` ha meno potere di una prima del merge: se avesse
trovato un problema, il rimedio sarebbe stato un'altra PR, non una correzione sul branch.

**Va estesa, ristretta o resa esplicita?** Va **resa esplicita**, ed è già uniforme per
decisione di Fahad del 25/07 (ogni PR, story e fix-forward, nessuna eccezione). Il problema è
che questa decisione vive nelle istruzioni degli agenti e **non** in `docs/project-context.md`,
che è la costituzione del progetto e dice esplicitamente di prevalere in caso di conflitto. Chi
legge solo il repo non trova la regola.

C'è anche un'incoerenza numerica da sanare nello stesso passaggio: `project-context.md` §4 dice
*«Oltre due giri sullo stesso punto: fermarsi e segnalare all'umano»*, mentre la mia Agent
Identity dice di escalare *«al 5° giro complessivo»*. Due numeri diversi per la stessa regola.
Finora non ha morso perché non siamo mai arrivati a due giri sullo stesso punto, ma è una mina
sotto il pavimento.

### 3.6 — Il debito della Story 1.2 ha attraversato l'intero Epic

G-5 è stato aperto dalla cross-review della Story 1.2 e chiuso dalla PR #23, l'ultima dell'Epic.
Nel mezzo: quattro story consegnate su una base con sessioni scadute che non venivano mai
raccolte e un login senza alcun freno ai tentativi ripetuti. Era P2, la valutazione era corretta,
e nessuno ha sbagliato la priorità.

Il difetto è nel **meccanismo**: un finding P2 non ha un momento in cui viene ripreso. Non
appartiene a nessuna story, quindi aspetta che qualcuno decida di dispacciarlo, e nel frattempo
il costo di ricostruire il contesto cresce ogni volta. I quattro fix-batch sono quattro branch,
quattro PR, quattro giri di CI e Sonar, quattro verdetti — per contenuti che in un caso
(F-3) erano **una chiamata a `.encode()`**.

Alternativa concreta per l'Epic 2: ogni story si porta in dote i finding aperti che toccano il
suo perimetro, e i P2 senza perimetro si raggruppano in **un solo** batch pianificato a metà
Epic. Un batch programmato costa un giro; quattro batch reattivi ne costano quattro.

### 3.7 — Incoerenze fra artefatti (il metodo guidato dai documenti si è slabbrato)

Quattro casi, tutti verificabili oggi:

1. **shadcn/ui è ratificato a G3 (decisione G3-1) e non è mai stato inizializzato.** È stato
   rinviato quattro volte con motivazione ragionevole ogni volta (1.1 → 1.3 → 1.4 → 1.5:
   "si attiva alla prossima story con form complessi"). Il risultato netto è che
   `project-context.md` §6 dichiara come stack qualcosa che il codice non usa. Un artefatto
   ratificato e mai applicato è una bugia nel documento, non un rinvio.
2. **Tutte e sei le story sono ancora `status: in_review`**, a Epic dichiarato chiuso e PR
   mergiate. Lo stato nei file story ha smesso di essere un'informazione: se è sempre
   `in_review`, non distingue nulla.
3. **Su `main` il documento QA dice ancora che l'Epic ha debito aperto.** La matrice finale e la
   dichiarazione di debito zero vivono nella PR #25, non mergiata. Chi oggi apre il repo legge
   `status: draft` e G-5 in corso. Lo stato pubblicato è indietro rispetto alla realtà, e
   l'artefatto che dovrebbe essere la fonte di verità è quello che non si può leggere.
4. **`sprint-status.yaml` non esiste.** Le skill BMAD (retrospettiva compresa) lo assumono come
   perno del tracciamento. Abbiamo tenuto il tracciamento nelle issue Multica, che ha funzionato,
   ma significa che metà del macchinario BMAD gira a vuoto e va detto invece che scoperto ogni
   volta da chi invoca una skill.

Nessuno di questi quattro punti ha prodotto un difetto nel prodotto. Tutti e quattro producono
lo stesso effetto: **il documento smette di essere affidabile, e chi arriva dopo deve chiedere
invece di leggere.** In un metodo che si dichiara guidato dai documenti, è la prima cosa da non
lasciar scivolare.

### 3.8 — Attriti nel dispatch (richiesti esplicitamente, li scrivo)

John ha chiesto di dire se qualcosa nel modo di dispatchare il lavoro mi ha rallentato. Tre cose.

**Gli artefatti di ingresso vivono in PR non mergiate.** Per questa retrospettiva la matrice
finale era su `qa/epic1-chiusura-debito-zero`; per la Story 1.3 il prerequisito era il fix-batch
PR #12. Funziona finché qualcuno mi dice *dove* guardare — e qui John lo ha fatto, con un
aggiornamento esplicito dell'issue, che è il comportamento giusto. Ma il pattern non regge la
crescita: con il merge umano come collo di bottiglia, il numero di artefatti "consegnati ma
invisibili su `main`" cresce a ogni fase, e ogni handoff diventa un puntatore da mantenere a
mano. Non chiedo di cambiare il gate umano: chiedo che quando un artefatto è un **prerequisito**
di un altro task, il suo merge venga messo in coda *prima* del dispatch del task che lo consuma,
non in parallelo.

**Il dispatch reattivo dei finding.** Vedi §3.6: quattro batch invece di uno pianificato. Ogni
batch è arrivato subito e con scope rigido — che è corretto e lo confermo — ma la reattività ha
un costo fisso per giro che nessuno stava contando.

**Il ciclo review-dopo-consegna sposta il costo sulla story successiva.** La review di una story
arriva quando la story è già mergiata, quindi i suoi finding si pagano dentro la successiva
(la 1.3 non poteva partire senza la PR #12; la 1.6 dipendeva dal fix-batch #18). Il risultato è
che ogni story porta il debito della precedente e la catena di dipendenze si allunga. Non ho una
soluzione pulita da proporre entro i gate attuali — segnalo che è una proprietà del flusso, non
un incidente, e che con story più grandi diventerà evidente.

Sul resto del metodo, per onestà nell'altra direzione: **la cadenza una-story-alla-volta ha
funzionato**, nessuna contesa e nessun merge conflict in sei story; **il confine sidecar/libreria
è chiaro** e non ho mai dovuto chiedermi dove scrivere una cosa; **i gate umani non mi hanno mai
bloccato**, hanno bloccato solo il merge, che è il loro mestiere.

---

## 4. Le quattro domande del supervisore — dove trovano risposta

| # | Domanda | Risposta |
| :---: | --- | --- |
| 1 | Due difetti invisibili alla CI verde: perché, e cosa spostare in CI? | §3.2 — quattro classi di cecità; test di gara, property test sui confini testuali, più guardie strutturali, audit informativo. **Non** più e2e. |
| 2 | Il difetto di cache visto solo dagli e2e | §3.3 — scritto come *Regola dell'e2e giustificato*, già in libreria di squadra |
| 3 | I finding Sonar sulla supply chain arrivati dopo la CI | §3.4 — la CI è stata scritta come impalcatura invece che come codice privilegiato; checklist da applicare prima del primo workflow |
| 4 | La regola «verdetto prima del merge» | §3.5 — ha funzionato, il costo dell'assenza è misurato in due verifiche retroattive; va **resa esplicita** in `project-context.md`, con il tetto dei giri allineato |

---

## 5. Lezioni (regole, non buoni propositi)

1. **Il piano di test precede la prima riga di codice dell'Epic, non la insegue.** Cinque
   finding su nove vengono dalle due story consegnate prima che il test design esistesse.
2. **Una CI verde prova solo che gli input che le hai dato producono l'atteso.** Le classi che
   sfuggono sono sempre le stesse quattro: interleaving, input fuori alfabeto, assenze, colla fra
   livelli mockati.
3. **Check-then-write senza serializzazione è un difetto, non un rischio.** Lo abbiamo trovato
   due volte (G-2, F-1). La seconda volta è la dimostrazione che una regola non scritta non vale.
4. **La pipeline è la superficie più privilegiata del progetto** e va scritta contro un modello
   di minaccia, con la checklist di §3.4 in mano, prima e non dopo.
5. **L'e2e si giustifica nominando il difetto che solo lui vede.** Se non sai nominarlo, quel
   test va scritto più in basso.
6. **Un artefatto ratificato e non applicato è un errore nel documento.** O si applica, o si
   registra che non è stato adottato — non si rinvia indefinitamente (shadcn/ui, §3.7).
7. **Un finding senza una story che lo ospiti non ha un momento in cui viene ripreso.** Assegnargli
   un perimetro alla nascita costa meno che ridispacciarlo quattro volte.

---

## 6. Azioni per l'Epic 2

Concrete, con proprietario e momento. Nessuna scadenza di calendario: il momento è un evento
del flusso, che è l'unica cosa che qui ha significato.

| # | Azione | Proprietario | Quando | Fatto quando |
| :---: | --- | --- | --- | --- |
| **A1** | Test design dell'Epic 2 (`docs/qa/test-design-epic-2.md`) **prima** che parta la Story 2.1: ogni AC con livello e priorità assegnati | Murat, richiesto da John | prima del dispatch della 2.1 | il documento è mergiato su `main` prima del primo commit di codice dell'Epic 2 |
| **A2** | Checklist di hardening della pipeline (§3.4) applicata prima di toccare `.github/workflows/`; **aggiungere subito il blocco `permissions:` minimo**, oggi assente | Amelia | con la prima modifica CI dell'Epic 2 | Sonar non apre nulla di nuovo sui job aggiunti nell'Epic 2 |
| **A3** | Test di gara obbligatorio per ogni check-then-write (8 thread + barrier). Nell'Epic 2 tocca almeno: idempotenza dell'import iCal (2.1), claim del poller (2.2), identità del Conflitto «mai due aperti per la stessa coppia» (2.5) | Amelia, verifica Murat | dentro ciascuna story | i tre percorsi hanno un test concorrente verde |
| **A4** | Estendere l'e2e **solo** dove il difetto vive nella colla: un percorso per ogni valore derivato con cache propria (calendario 2.3, Dashboard conflitti 2.8). Rivalutare RT-4 come previsto | Amelia + Murat | con 2.3 e 2.8 | ogni nuovo spec e2e nomina il difetto che solo lui vede |
| **A5** | Rendere esplicita in `docs/project-context.md` §4 la regola «verdetto del Test Architect prima del merge, ogni PR» e **allineare il tetto dei giri** (§4 dice due, l'Agent Identity dice cinque) | John, su decisione di Fahad | prima del kickoff Epic 2 | `project-context.md` contiene entrambe le regole con un solo numero |
| **A6** | Portare su `main` gli artefatti di chiusura dell'Epic 1 (PR #25 e questa retrospettiva): finché non sono mergiati, il repo dichiara un debito che non esiste più | Fahad (merge), sollecito di John | prima del kickoff Epic 2 | `docs/qa/test-design-epic-1.md` su `main` riporta §7.6 |
| **A7** | Decidere lo stato terminale delle story: portare le sei a `done` dopo il merge, oppure dichiarare che `in_review` è terminale in questo pilota | John | prima del kickoff Epic 2 | i file story dicono una cosa vera |
| **A8** | Sciogliere il nodo shadcn/ui (§3.7): attivarlo con la prima superficie complessa dell'Epic 2 (griglia calendario 2.3 o finestra di riconciliazione 2.7), **oppure** registrare in `project-context.md` §6 che il seed ratificato a G3-1 non è stato adottato | Winston propone, Fahad decide | prima della 2.3 | documento e codice dicono la stessa cosa |
| **A9** | Un solo fix-batch **pianificato** a metà Epic 2 per i finding P2 senza perimetro; i finding con perimetro vengono assorbiti dalla story che li tocca | John (dispatch), Amelia (esecuzione) | pianificato a metà Epic | il numero di PR di sola correzione dell'Epic 2 è inferiore a quattro |

### Azioni condizionate (non avviate — servono decisioni di Fahad)

Il kickoff dell'Epic 2 non parte: due punti sono parcheggiati. Queste restano **raccomandazioni
condizionate**, non piani in corso.

- **A10 — Osservabilità del poller (dipende da una decisione di piano).** L'Epic 2 introduce la
  prima dipendenza di rete esterna (Story 2.1) e un job periodico che sincronizza da solo
  (Story 2.2). NFR-7 (osservabilità compliance) è però mappato sull'**Epic 3** (Story 3.1, 3.8).
  Senza almeno *ultimo sync riuscito* e *contatore di fallimenti* visibili, «il feed non si
  aggiorna da tre giorni» diventa indistinguibile da «non ci sono prenotazioni nuove» — e NFR-2
  (verità temporale delle OTA) è un requisito **dell'Epic 2**, non dell'Epic 3. Raccomandazione:
  valutare se un minimo di osservabilità del sync vada anticipato dentro la 2.2, o se NFR-2 sia
  soddisfabile senza. È l'unico punto di questa retrospettiva che può toccare il piano dell'Epic 2.
- **A11 — Nessuno ha mai visto l'app girare fuori dalla CI.** Tutta l'evidenza dell'Epic 1 è test
  e pipeline. Per l'Epic 1 è accettabile: nessun input esterno, nessun ambiente. Per l'Epic 2 il
  calcolo cambia — i feed iCal reali di Airbnb e Booking hanno formati, fusi orari e latenze che
  nessuna fixture riproduce fedelmente (ed è proprio il rischio che l'architettura chiama
  «lag del canale»). Raccomandazione condizionata: prima di dichiarare fatta la 2.2, far girare
  almeno **un** feed reale in un ambiente vero, anche un solo calendario di prova. Decisione e
  ambiente sono di Fahad.
- **A12 — G2-B (perimetro iniziale Comuni/Regioni) e R-5 (verifica legale).** Nessuno dei due
  blocca l'Epic 2: il calendario e la sincronizzazione non toccano la configurazione normativa, e
  il sistema degrada in sicurezza per qualunque Comune non configurato. **Entrambi diventano
  bloccanti per l'Epic 3** (adempimenti). Raccomandazione: possono restare parcheggiati per tutto
  l'Epic 2 senza costo, ma vanno decisi prima del kickoff dell'Epic 3. Non avvio nulla.

---

## 7. Readiness check — l'Epic 1 è davvero chiuso?

| Dimensione | Stato | Nota |
| --- | :---: | --- |
| Copertura degli AC | ✅ | 48/48, nessuno coperto "per ispezione" (matrice §7.5) |
| Finding aperti | ✅ | 0 su 9, nessun waiver (§7.4, §7.6) |
| CI e quality gate | ✅ | cinque check verdi sul commit `61d7ac4`, SonarCloud incluso |
| Verdetto pre-merge | ✅ | dato su ogni PR; le due precedenti alla regola verificate retroattivamente |
| Artefatti su `main` | ⚠️ | matrice finale e questa retrospettiva ancora in PR — vedi **A6** |
| Stato delle story | ⚠️ | sei su sei ferme a `in_review` — vedi **A7** |
| Coerenza documento/codice | ⚠️ | shadcn/ui ratificato e non adottato — vedi **A8** |
| Esercizio fuori dalla CI | ❌ | mai eseguito in un ambiente reale — accettabile per l'Epic 1, vedi **A11** per l'Epic 2 |
| Accettazione dell'umano | ⏳ | il merge è di Fahad, per definizione |

**Lettura.** L'Epic 1 è chiuso sul piano che conta — funzionalità, test, debito. Le tre ⚠️ non
sono difetti del prodotto: sono disallineamenti fra ciò che il repository dichiara e ciò che è
vero, e si chiudono tutte con un merge o una riga di documento. La ❌ non è un problema
dell'Epic 1: è un rischio dell'Epic 2 che va deciso prima, non scoperto dopo.

---

## 8. Libreria di squadra

Prima di questa retrospettiva `knowledge/dev/lezioni.md` conteneva **cinque** lezioni: tre
mergiate (PR #2 — convenzioni imposte da test runtime con allowlist sorvegliata; tabelle di
configurazione a validità temporale; invalidazione della cache dei valori derivati) e due in PR
aperta (PR #4 — freno agli accessi ripetuti; attività periodiche su coda di job durevole).

La retrospettiva ne ha fatte emergere **due che quelle cinque non coprono**, entrambe riusabili
su un cliente diverso, entrambe aggiunte alla PR #4 già aperta:

- **La pipeline è codice privilegiato** — la checklist di hardening di §3.4, da applicare prima
  di scrivere il primo workflow e non dopo la prima bocciatura di un quality gate.
- **Check-then-write è un difetto, non un rischio** — ogni percorso che legge-poi-scrive con un
  vincolo nasce con un test di gara; con due thread l'interleaving spesso non si presenta.

Non ho aperto una PR nuova: la #4 è ancora aperta e il contratto della libreria preferisce una
consegna sola. Il merge resta umano, come per ogni voce.

---

## 9. Cosa questa retrospettiva NON dice

Non dice che l'Epic 1 è stato eseguito male: il risultato è sei story consegnate, quarantotto
acceptance criteria coperti e zero debito. Dice che il **percorso** per arrivarci è costato dieci
PR di correzione e contabilità contro sei di valore, e che quasi tutto quel costo si spiega con
due cause a monte — un piano di test arrivato in ritardo e una pipeline scritta senza modello di
minaccia — entrambe evitabili al prossimo giro senza cambiare nulla del metodo.

Non dice nulla sul kickoff dell'Epic 2, che **non parte**: G2-B e R-5 restano parcheggiati in
attesa di Fahad, e ogni azione che li presuppone è scritta sopra come raccomandazione condizionata.

---

_Retrospettiva dell'Epic 1 — Amelia, Senior Software Engineer, 2026-07-25. Consegnata via PR;
il merge è di Fahad. Il modello di questo documento (§1 numeri, §2/§3 evidenza, §5 regole,
§6 azioni, §7 readiness) si replica per l'Epic 2 in un documento nuovo._

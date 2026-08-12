# Memorie — Murat — Master Test Architect (modulo TEA)

_Fatti durevoli e decisioni apprese durante il progetto HostPilot. Un fatto per voce, con data. Aggiornare via PR. Non duplicare `docs/project-context.md`._

<!-- Esempio:
- 2026-07-24 — <fatto appreso e perché conta>.
-->

- 2026-07-25 — **Un documento di qualità per Epic**, `docs/qa/test-design-epic-<N>.md`, con
  struttura fissa: §1 rischi, §2 strategia per livello, §3 copertura AC per Story, §4
  registro dei gap/finding, §5 vincoli fixture, §6 criteri di gate, **§7 matrice di
  tracciabilità di chiusura**. Per l'Epic 2 si parte da un documento nuovo con lo stesso
  scheletro, non si estende quello dell'Epic 1 (che è chiuso).
- 2026-07-25 — **Convenzione degli ID dei finding**: `G-n` = gap emerso dal test design o da
  review retroattiva, `F-n` = finding di cross-review su una Story consegnata, `C-n` =
  finding di copertura/CI. La numerazione è **unica per Epic** e non si riusa. Un finding si
  chiude solo con la PR che lo chiude **e** il nome del test di regressione: senza il test
  nominato la riga resta aperta.
- 2026-07-25 — **Debito ≠ rischio, e la differenza va scritta.** Alla chiusura dell'Epic 1 la
  matrice ha due tabelle distinte: il registro dei finding chiusi (§7.4) e i *rischi
  tracciati* (§7.7), che non violano AC né invarianti ma hanno un momento preciso di
  rivalutazione. Se i rischi noti non hanno una tabella propria, o inquinano il registro del
  debito o spariscono — e riappaiono come debito per dimenticanza.
- 2026-07-25, **riscritta il 2026-08-12 (MYL-91) perché era falsa** — I check obbligatori del
  repo. La voce diceva «sono **cinque**: `backend`, `frontend`, `e2e`, `api-contract`,
  **SonarCloud Code Analysis**», e l'ho ripetuta in dichiarazioni di chiusura. Erano i cinque
  **job della CI**, non cancelli di merge: fino al 12/08 `main` era **completamente
  sprotetto** — zero check obbligatori, zero ruleset, push diretto possibile. Ciò che reggeva
  era la **disciplina**, ed è misurabile: su tutta la storia di `main` l'unico commit
  non-merge in first-parent è la genesi del repo (`d66c264`, 24/07), a fronte di 61 merge —
  zero commit arrivati fuori da una PR — e le ultime dieci PR tutte verdi. Buona disciplina,
  nessuna garanzia.
  **Dalle 13:46 del 2026-08-12 la branch protection è accesa** e i check obbligatori sono
  **otto**: `backend`, `frontend`, `e2e`, `api-contract`, `base-della-pr`, `copertura`,
  `SonarCloud Code Analysis`, `verdetto-murat`. Più *require branches to be up to date before
  merging* (chiude MYL-74 e il presidio della voce del 30/07 sul rosso di `main`).
  `enforcement_level: non_admins` — a Fahad resta una via di fuga, lasciata aperta apposta.
  *Require approvals* è **spenta di proposito**: le PR risultano aperte dal token di Fahad e
  GitHub vieta di approvare una PR propria, quindi obbligarla bloccherebbe ogni merge.
  Verificato il 12/08 **interrogando** `GET /repos/{o}/{r}/branches/main` (`protected: true`,
  `enabled: true`, gli otto `contexts`); l'endpoint `/protection` completo richiede permessi
  admin che il mio token non ha, quindi «up to date» resta agli atti di Fahad, non a una mia
  misura. Da qui in avanti il `verdetto-murat` non è più un'opinione autorevole: senza verde
  sullo SHA esatto la PR non è mergiabile.
  **CORREZIONE del 2026-07-30 (MYL-59), tuttora valida:** «verdi a vuoto non possono essere»
  era falso per SonarCloud. Il suo Quality Gate valuta cinque condizioni — affidabilità,
  sicurezza, manutenibilità, duplicazione, hotspot — e **nessuna sulla copertura**; le
  metriche `coverage`/`new_coverage` non esistono nemmeno sul progetto, perché la Automatic
  Analysis non importa report. Il `0.0% Coverage on New Code` citato per settimane era
  l'assenza del dato, non un esito. Dal 30/07 la copertura la misura e la fa mordere la nostra
  CI (job `copertura`, `diff-cover` sulle righe toccate): vedi
  `docs/qa/copertura-e-cancelli.md`.
  **Lezione, ed è la stessa due volte nella stessa voce**: il 30/07 avevo dedotto la solidità
  di un check dalla solidità degli altri quattro; il 25/07 avevo dedotto che cinque check
  *configurati* fossero cinque check *vincolanti*. Nessuna delle due si vede leggendo il
  repository: si vedono solo interrogando il sistema. **Prima di citare un cancello come
  evidenza, interrogalo** — e verificalo rompendo ciò che difende.
- 2026-07-30 — **Un pavimento di copertura globale non è un cancello**, misurato su questo
  repo: togliendo `backend/tests/test_calendario_sync.py` intero (81 test, il file che copre
  il modulo più rischioso) il totale scende da 96.44% a 95.16% — un `fail_under` a 93 non se
  ne accorge, perché altri test attraversano incidentalmente le stesse righe e il totale si
  diluisce sul codice che cresce. Il cancello che morde è la copertura del **diff**
  (`diff-cover` sulle righe toccate dalla PR): su una riga nuova nessun altro test la copre
  per sbaglio. Il pavimento globale resta come backstop del crollo, non come garanzia.
- 2026-07-30 — **Un cancello che passa a vuoto è peggio di un cancello assente**, perché
  viene citato come evidenza. Due modi in cui è capitato mentre costruivo il job `copertura`,
  entrambi silenziosi e trovati solo provandoli: (1) i percorsi `SF:` di lcov sono relativi a
  `frontend/` mentre `git diff` parla dalla radice — senza normalizzazione `diff-cover`
  stampa «No lines with coverage information» ed **esce 0** su un file TS nuovo e interamente
  scoperto; (2) il pathspec `:(glob)` di git usa wildmatch, che **non** conosce
  `{app,components,lib}` — la forma compatta non dà errore, torna zero file, e disattiva da
  sola la guardia che dipendeva da quel conteggio. Regola operativa: ogni cancello nuovo va
  consegnato con la prova che **cade** su un caso costruito per farlo cadere, non solo con la
  prova che passa.
- 2026-07-30 — **DECISIONE: il mutation testing NON si adotta** (Fahad, 30/07, dopo lo spike
  MYL-72; la sua delibera del mattino era B e l'ha cambiata sulla misura). Il documento agli
  atti è `docs/qa/decisione-mutation-testing-ci.md` — **rinominato** da `proposta-…` proprio
  perché fra un anno la distinzione che conta è «misurato e scartato» contro «mai provato». Se
  qualcuno ripropone il mutation testing, la risposta non è «no»: è quel documento, con i due
  trigger di riesame verificabili (§4) e i costi già pagati (§5), che nessuno deve rimisurare.
- 2026-07-30 — **`mutmut` 3.6 su questo stack: gira, ma non vede.** Spike MYL-72, dettaglio in
  `docs/qa/decisione-mutation-testing-ci.md`. Tre fatti da non rimisurare: (1) **17.4%**
  delle righe di funzione di `backend/app/` è cieco per costruzione — `mutmut` salta funzioni
  e classi **decorate**, quindi lo strato `api.py` è cieco al 78–100%, ogni `@dataclass`
  (compresa `DateRange`, cioè `overlaps`, cioè l'anti-double-booking) riceve zero mutanti, e
  così gli handler `@handlers.register`; (2) la sandbox `mutants/` riscrive i metodi in
  `xǁClasseǁmetodo__mutmut_N`, quindi **tutte le nostre guardie strutturali per riflessione**
  (tenancy, auth, conventions, copertura) cadono lì dentro e vanno deselezionate — la suite
  della sandbox non è la suite del repo; (3) **il costo scala con quanto è importato il modulo
  toccato, non con la dimensione del diff**: 15.49 mutazioni/s sui 7 file della Story 2.4,
  **0.41** su `core/date_range.py`. Su 1712 mutanti reali: **0 sopravvissuti**. Adozione non
  raccomandata; la decisione è di Fahad.
- 2026-07-30 — **Prima di credere a «zero problemi», far dire allo strumento «un problema».**
  Nello spike MYL-72 lo «zero sopravvissuti» sarebbe stato indistinguibile da uno strumento
  mal configurato: la prova è stata iniettare una funzione con un ramo non testato e
  verificare che `mutmut` la segnalasse (4 sopravvissuti, con diff leggibile). È la stessa
  regola del 30/07 sui cancelli — **si consegna con la prova che cade**, non solo con la prova
  che passa — applicata a uno strumento di misura invece che a un cancello.
- 2026-07-30 — **Una misura presa con lo strumento mal configurato è peggio di nessuna
  misura**, perché sembra un dato. I «3 mutanti sopravvissuti su 60, tutti falsi positivi su
  stringhe» della proposta PR #50 erano l'effetto della calibrazione fallita: con la
  configurazione corretta i sopravvissuti sono **0**. Su quella misura sbagliata era stata
  costruita una raccomandazione, poi una decisione, poi un incarico di implementazione — e la
  leva che l'incarico chiedeva («disattiva le mutazioni sui letterali stringa») **in `mutmut`
  3.6 non esiste**. Regola: quando riporto un numero preso da uno strumento nuovo, dichiaro
  accanto se il run era pulito; e se non lo era, il numero **non si riporta affatto**. Non
  basta scrivere la riserva accanto: qui la riserva c'era — i tre caveat erano dichiarati per
  esteso — e il numero è diventato lo stesso la base della delibera. Una cifra in tabella pesa
  più di un caveat in prosa, sempre.
- 2026-07-30 — **`main` può essere rosso per giorni senza che nessuno se ne accorga**: qui lo
  è stato per **quattro merge consecutivi** (431 test in errore) perché le PR #52 e #53
  avevano aggiunto ciascuna una migrazione `revision = "0013"` su `down_revision = "0012"`.
  Il difetto **non esiste in nessuna delle due PR** — entrambe verdi sulla propria base — e
  nasce nel trunk al secondo merge. È la forma della PR #36 che ha prodotto
  `base-della-pr.yml`: il difetto sta *fra* i controlli. Tre conseguenze operative: (1)
  **guardo la CI di `main`, non solo quella della PR**, prima di dare un verdetto o di fidarmi
  di una baseline; (2) la guardia esiste, è `TestCatenaLineare` in
  `backend/tests/test_migrations.py` (MYL-75, PR #56): gira **senza database** e cade in
  pochi centesimi nominando la causa, invece di lasciare 431 errori che parlano di
  connessioni; (3) **prima di dispacciare un finding, guardo le PR aperte.** Avevo scritto la
  mia guardia e mandato il batch ad Amelia senza accorgermi che la #56 era già aperta da
  quaranta minuti, con la correzione e una guardia **più forte** della mia. È la stessa
  lezione del 25/07 sui rami duplicati, che avevo applicato ai miei deliverable e non ai miei
  finding: `gh pr list` costa due secondi e va fatto **prima** di aprire un fronte, non dopo.
- 2026-07-25 — La regola «verdetto del Test Architect prima del merge umano» è entrata in
  vigore dalla Story 1.3. Le PR mergiate prima (#12, #18) sono state verificate
  **retroattivamente** e l'esito è registrato nella matrice. Se una regola di gate arriva a
  metà Epic, la verifica arretrata va fatta e scritta, non condonata in silenzio.
- 2026-07-25 — **Gli ID di rischi e finding si prefissano con l'Epic** dal test design dell'Epic
  2 in poi: rischi `R2-x`, finding `E2-Gn` / `E2-Fn` / `E2-Cn`. Nell'Epic 1 erano `R-x` / `G-n`
  / `F-n` / `C-n`, univoci solo dentro l'Epic — ma «G-2» ha ormai un significato preciso nelle
  conversazioni di squadra, e riusare la sigla in un altro Epic renderebbe ambigua ogni
  citazione futura. E la forma che verrebbe naturale — `G2-x` — **collide con le
  `[DECISIONE G2-A…E]` del PRD**: il prefisso `E<n>-` risolve entrambe le cose. I rischi
  tracciati restano `RT-n`, unici per progetto perché attraversano gli Epic per costruzione
  (hanno un momento di rivalutazione, non una scadenza).
- 2026-07-25 — **L'ambiente e2e non avvia il worker.** `frontend/playwright.config.ts` ha due
  `webServer` (backend con migrazioni, frontend buildato) e nessun processo `python -m
  app.worker`: negli e2e i **job durevoli non girano mai**. Nell'Epic 1 non mordeva; dall'Epic 2
  ogni AC che dipende da un job (import on-demand, poller, notifica) non è osservabile in e2e
  senza una decisione esplicita. Da ricordare **prima** di promettere copertura e2e su un flusso
  asincrono.
- 2026-07-25 — **A fine Epic 1 il backend non aveva una sola riga di codice HTTP in uscita**
  (unico hit su `http` in `app/`: `frontend_origin` in `core/config.py`; `httpx` è solo dev, per
  `TestClient`). Il fetch iCal dell'Epic 2 è la **prima** dipendenza di rete del progetto: client,
  timeout, redirect, guardia SSRF, cap di dimensione **e il presidio che impedisce a un test di
  raggiungere Internet** sono tutti greenfield. Anche l'unico precedente di validazione di input
  non fidato è filesystem, non rete (`importa_comuni.py`).
- 2026-07-25 — `TABELLE_DA_SVUOTARE` in `backend/tests/conftest.py` è una **stringa scritta a
  mano** usata in `TRUNCATE … CASCADE`. Ogni tabella nuova va aggiunta a mano o i test si
  sporcano fra loro, e il fallimento compare **altrove**, giorni dopo, travestito da flakiness.
  Con un Epic che aggiunge cinque tabelle in un colpo solo serve una guardia che la confronti
  con `Base.metadata.tables`.
- 2026-07-25 — **Due miei run in parallelo sulla stessa issue hanno prodotto due test design
  diversi dell'Epic 2** (PR #32 e #33, 1228 righe di diff fra i rami), rilevati da John prima
  che arrivassero su `main`. Nessuno dei due era un superset dell'altro: la riconciliazione è
  stata un confronto riga per riga, non una scelta fra due copie. Lezione operativa: quando
  riprendo una issue, **prima di scrivere controllo se esiste già un ramo o una PR mia sullo
  stesso deliverable** — `git branch -a` e le PR aperte del repo. Il costo di non farlo non è la
  scrittura doppia, è che qualcun altro deve accorgersene.
- 2026-07-25 — **Un test design scritto davvero prima del codice produce due output, non uno**:
  la tabella di copertura (§3) e la lista dei **confini non specificati negli AC** (§4). Nel
  test design dell'Epic 2 la seconda conta tredici voci, sette delle quali hanno la stessa
  forma — l'AC descrive il caso normale e tace sul **ritorno dal caso degradato** (il feed che
  torna, il sync mai riuscito, il conflitto fra due prenotazioni manuali). Quelle voci non le
  risolvo io: tornano a John, che corregge `docs/epics.md`. Provare a scriverle come test le
  avrebbe trasformate in decisioni di prodotto prese di nascosto dentro un documento di QA.
- 2026-07-30 — **Il token degli agenti NON può scrivere stati di commit** su questo
  repository: `POST /repos/.../statuses/{sha}` risponde `403 Resource not accessible by
  personal access token`, mentre contenuti e pull request funzionano. Il permesso
  `statuses: write` è distinto e va concesso a parte. Finché non lo è, il cancello
  `verdetto-murat` (MYL-73) esiste e fallisce chiuso, ma non pubblica nulla.
- 2026-07-30 — **L'account del token è anche l'autore delle PR degli agenti**, quindi GitHub
  rifiuta con 422 sia `APPROVE` sia `REQUEST_CHANGES` sulle nostre PR («Can not approve your
  own pull request»). Le review formali degli agenti su questo repo **non sono possibili**
  finché gli agenti non hanno un'identità GitHub distinta: si ripiega su una review di tipo
  `COMMENT`. È il motivo per cui il cancello del verdetto è uno **stato di commit** e non una
  review — la review non si sarebbe potuta né dare né togliere.
- 2026-07-30 — **`GET /pulls/{n}` può riportare una head in ritardo** di qualche secondo su un
  `git push` già completato (misurato sul banco di prova di MYL-73). Ogni controllo del tipo
  «lo SHA che sto giudicando è ancora la head?» è quindi una cortesia, non una garanzia: la
  garanzia deve essere che l'artefatto pubblicato sia **legato allo SHA** e non alla PR.
- 2026-07-30 — **Il rosso di `main` non lo guarda nessuno.** Trovato per caso girando la suite:
  `main` era rosso da quattro merge consecutivi (dal 13:20 circa del 30/07) per due migrazioni
  Alembic con lo **stesso** `revision = "0013"` arrivate da due PR verdi separatamente (#52 e
  #53). Nessun cancello di PR può vedere questa classe di difetto, perché nasce dall'**unione**
  di due rami sani. I presidi sono due, entrambi da attivare: *Require branches to be up to
  date before merging* e una guardia che imponga un'unica head Alembic.
- 2026-08-12 — **Il permesso `statuses: write` c'è: il cancello `verdetto-murat` è in
  servizio.** La voce del 30/07 qui sopra è **superata**: sulla PR #60 (SHA `9857aac`) il
  primo verdetto non di prova è stato pubblicato e riletto `verde`, `POST /statuses/{sha}`
  accettato. Il punto 2 di `docs/qa/cancello-verdetto.md` (renderlo un check obbligatorio in
  branch protection) **è stato chiuso da Fahad alle 13:46 dello stesso giorno**: `verdetto-murat`
  è ora uno degli otto check obbligatori — vedi la voce riscritta del 25/07.
  Da riusare: un limite d'ambiente registrato in un documento **non scade da solo**
  quando l'ambiente cambia — se non lo rilegge chi lo ha scritto, resta lì a dire «non si può
  fare» e blocca una decisione umana che nessuno sa più di poter prendere. Il momento in cui
  lo strumento funziona per la prima volta è il momento in cui si aggiorna il documento.
- 2026-08-12 — **Una ratifica che riguarda due Story va scritta in tutte e due.** La PR #60
  ha portato negli AC la ratifica di test design §4.2-6 (una Prenotazione manuale non ha un
  timestamp di sync: fonte = Canale «Manuale», timestamp = data d'inserimento, **con etichetta
  che dichiara che non è un dato sincronizzato**). Il dato è della 2.5, l'etichetta è della
  2.7: scritta solo nella 2.5, chi implementa la 2.7 legge i propri AC e non la vede — e la
  Finestra di riconciliazione mostra due colonne simmetriche di cui una mente. Stessa forma
  del difetto MYL-69 che avevo isolato io (un fatto che vale per tre strade, implementato su
  una): quando una decisione tocca **N** siti, il controllo di review è contare i siti nel
  documento, non rileggere il testo del sito che si ha davanti.

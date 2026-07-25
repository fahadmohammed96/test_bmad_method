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
- 2026-07-25 — I check obbligatori del repo sono **cinque**: `backend`, `frontend`, `e2e`,
  `api-contract` e **SonarCloud Code Analysis**. Verdi a vuoto non possono essere:
  `HOSTPILOT_TEST_DB_REQUIRED=1` rende errore lo skip dei test su Postgres reale e
  `api-contract` fallisce sul `git diff` se OpenAPI/client TS divergono dal codice. È questo
  che rende «CI verde» un'evidenza citabile in una dichiarazione di chiusura.
- 2026-07-25 — La regola «verdetto del Test Architect prima del merge umano» è entrata in
  vigore dalla Story 1.3. Le PR mergiate prima (#12, #18) sono state verificate
  **retroattivamente** e l'esito è registrato nella matrice. Se una regola di gate arriva a
  metà Epic, la verifica arretrata va fatta e scritta, non condonata in silenzio.
- 2026-07-25 — **Gli ID dei finding vanno prefissati con l'Epic**: `E2-G1`, `E2-F1`, `E2-C1`.
  La numerazione riparte a ogni Epic, quindi senza prefisso `G-1` dell'Epic 2 e `G-1`
  dell'Epic 1 sono indistinguibili in un commento; e la forma naturale `G2-x` **collide con le
  `[DECISIONE G2-A…E]` del PRD**. Il prefisso `E<n>-` risolve entrambe le cose.
- 2026-07-25 — **L'ambiente e2e non avvia il worker.** `frontend/playwright.config.ts` ha due
  `webServer` (backend con migrazioni, frontend buildato) e nessun processo `python -m
  app.worker`: negli e2e i **job durevoli non girano mai**. Nell'Epic 1 non mordeva; dall'Epic 2
  ogni AC che dipende da un job (import on-demand, poller, notifica) non è osservabile e2e senza
  una decisione esplicita. Da ricordare prima di promettere copertura e2e su un flusso asincrono.
- 2026-07-25 — **A fine Epic 1 il backend non aveva una sola riga di codice HTTP in uscita**
  (unico hit su `http` in `app/`: `frontend_origin` in `core/config.py`; `httpx` è solo dev, per
  `TestClient`). Il fetch iCal dell'Epic 2 è la **prima** dipendenza di rete del progetto: tutto
  ciò che le sta attorno è greenfield — client, timeout, redirect, guardia SSRF, cap di
  dimensione, **e il presidio che impedisce a un test di raggiungere Internet**, che oggi non
  esiste. Anche il precedente di validazione input non fidato è filesystem, non rete
  (`importa_comuni.py`).
- 2026-07-25 — `TABELLE_DA_SVUOTARE` in `backend/tests/conftest.py` è una **stringa scritta a
  mano** usata in `TRUNCATE … CASCADE`. Ogni tabella nuova va aggiunta a mano o i test si
  sporcano fra loro, e il fallimento compare **altrove**, giorni dopo, travestito da flakiness.
  Con un Epic che aggiunge cinque tabelle in un colpo solo, serve una guardia che la confronti
  con `Base.metadata.tables`.

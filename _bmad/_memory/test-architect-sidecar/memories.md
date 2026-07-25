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
- 2026-07-25 — **Gli ID di rischi e finding si prefissano con l'Epic** dal test design dell'Epic
  2 in poi: rischi `R2-x`, finding `E2-Gn` / `E2-Fn` / `E2-Cn`. Nell'Epic 1 erano `R-x` / `G-n`
  / `F-n` / `C-n`, univoci solo dentro l'Epic — ma «G-2» ha ormai un significato preciso nelle
  conversazioni di squadra, e riusare la sigla in un altro Epic renderebbe ambigua ogni
  citazione futura. I rischi tracciati restano `RT-n`, unici per progetto perché attraversano
  gli Epic per costruzione (hanno un momento di rivalutazione, non una scadenza).
- 2026-07-25 — **Un test design scritto davvero prima del codice produce due output, non uno**:
  la tabella di copertura (§3) e la lista dei **confini non specificati negli AC** (§4). Nel
  test design dell'Epic 2 la seconda conta tredici voci, sette delle quali hanno la stessa
  forma — l'AC descrive il caso normale e tace sul **ritorno dal caso degradato** (il feed che
  torna, il sync mai riuscito, il conflitto fra due prenotazioni manuali). Quelle voci non le
  risolvo io: tornano a John, che corregge `docs/epics.md`. Provare a scriverle come test le
  avrebbe trasformate in decisioni di prodotto prese di nascosto dentro un documento di QA.

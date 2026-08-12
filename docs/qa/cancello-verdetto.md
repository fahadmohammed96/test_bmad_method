# Il cancello del verdetto — `verdetto-murat`

_MYL-73 · 30/07/2026 · Murat, Test Architect_
_Aggiornato il 12/08/2026 (MYL-97): il cancello è vincolante, vedi l'ultima
sezione. Le parti che lo davano per «informativo» erano false dalle 13:46 del
12/08 e sono state corrette in loco, non affiancate._

## Da dove nasce

Il 30/07 alle 13:37:29 la PR #48 è stata mergiata sulla head `51a52cb`, cioè
sulla versione per cui l'ultimo verdetto era **BOCCIA** (finding F11). Non è
stata disattenzione: sulla pagina GitHub della PR non esisteva **nulla** che lo
dicesse. Sette check verdi, `mergeable: clean`, pulsante verde. Il verdetto
viveva su Multica, il merge avviene su GitHub, e fra i due non c'era alcun
collegamento.

Con cinque PR aperte insieme, la sorpresa è che sia successo una volta sola. Il
rimedio non è chiedere più attenzione a chi mergia: è rendere il verdetto un
**dato che GitHub espone**.

## Il meccanismo

`backend/scripts/verdetto_gate.py` pubblica due cose, con ruoli **diversi**:

| Cosa | Dove | Ruolo |
|---|---|---|
| Stato di commit, contesto `verdetto-murat` | `POST /repos/{o}/{r}/statuses/{sha}` | **è il cancello** |
| Review sulla PR | `POST /repos/{o}/{r}/pulls/{n}/reviews` | visibilità per l'umano |

La distinzione è la cosa più importante del documento. Il cancello è lo stato,
perché è l'unico dei due che:

- è legato allo **SHA esatto**, quindi un push produce un commit che nasce
  **senza** stato: un'approvazione «vecchia di un push» smette di valere da
  sola, senza che nessuno debba ricordarsene;
- è **leggibile in modo meccanico** da una branch protection e dal controller
  di auto-merge previsto a fine Epic 2, senza interpretare della prosa.

### Uso

```bash
# pubblica il verdetto (dalla directory backend/)
uv run python scripts/verdetto_gate.py pubblica \
    --repo fahadmohammed96/test_bmad_method --pr 54 \
    --sha <40 esadecimali> --verdetto approva|boccia \
    --commento https://<link al verdetto esteso su Multica> \
    --motivo "una riga di sintesi"

# chiede a GitHub se quello SHA ha il verdetto (uscita 0 solo se verde)
uv run python scripts/verdetto_gate.py verifica \
    --repo fahadmohammed96/test_bmad_method --sha <sha>
```

Il token si legge da `GITHUB_TOKEN` / `GH_TOKEN`, non viene mai stampato, e lo
strumento **non mergia e non chiude nulla**.

## Fallire in sicurezza

L'ordine delle scritture non è estetica, è la garanzia:

- **BOCCIA** → lo stato `failure` si scrive **per primo**. Se la review poi
  fallisce, il cancello è comunque già chiuso.
- **APPROVA** → lo stato `success` si scrive **per ultimo**, e solo dopo che
  tutto il resto è riuscito. È l'unica scrittura che apre il cancello.

Ne segue la proprietà richiesta: **qualunque cosa vada storta — permessi, rete,
SHA che cambia sotto le mani — il cancello non risulta verde.** Un cancello
bloccato per errore costa un run in più; un cancello aperto per errore costa una
PR mergiata senza verdetto.

Un corollario meno ovvio, aggiunto dopo la prova live: se la review APPROVA
passa e lo stato no, lo strumento pubblica sulla PR un **ritiro esplicito**
(«questo APPROVA non è pubblicato come cancello»). Senza, la pagina della PR
direbbe «APPROVA» a cancello chiuso: è l'incidente di partenza con i ruoli
invertiti — la pagina che afferma qualcosa di diverso dalla verità.

## Evidenze

### Suite automatica

`backend/tests/test_verdetto_gate.py` — 28 test, nessuno tocca la rete
(`httpx.MockTransport`), tutte le richieste registrate così che **anche
l'ordine delle scritture** sia asserito e non solo l'esito.

I tre casi chiesti dalla issue, provati e non descritti:

| Caso | Test che lo tiene chiuso |
|---|---|
| PR senza alcun verdetto → cancello non verde | `test_pr_senza_verdetto_ha_il_cancello_assente`, `test_altri_check_verdi_non_aprono_il_cancello`, `test_verifica_esce_diversa_da_zero_senza_verdetto` |
| APPROVA, poi un push → il nuovo SHA non ha stato | `test_lo_stato_non_si_eredita_dopo_un_push`, `test_verdetto_su_uno_sha_che_non_e_piu_la_head_non_scrive_nulla` |
| Pubblicazione dello stato fallita → non risulta approvato | `test_stato_fallito_su_approva_non_risulta_approvato`, `test_rete_caduta_su_approva_non_risulta_approvato`, `test_review_impossibile_su_approva_non_pubblica_alcuno_stato`, `test_stato_fallito_dopo_la_review_ritira_l_approvazione` |

Un difetto trovato **dal test durante la scrittura**, che vale la pena
registrare: la prima versione del finto GitHub teneva gli stati in una lista
sola, condivisa fra tutti i commit. Con quella,
`test_lo_stato_non_si_eredita_dopo_un_push` passava leggendo lo stato del commit
**precedente** — cioè verificava il doppio invece del prodotto, proprio sulla
proprietà che dichiarava di sorvegliare. L'ha rivelato perché era scritto per
cadere su quel caso.

### Prova live (PR di prova #55, chiusa e ramo cancellato)

Il contratto reale delle API non si deduce da un mock. Provato il 30/07 contro
GitHub, con lo strumento vero:

1. **PR senza verdetto** → `cancello verdetto-murat su 71ac625…: assente`,
   uscita `1`. Il caso base dell'incidente, verificato sul campo.
2. **Verdetto su uno SHA che non è più la head** → `la head della PR #55 è
   77703a4…, non 71ac625…: … Non pubblico nulla`, uscita `1`, nessuna
   scrittura.
3. **Pubblicazione dello stato rifiutata** (403, vedi sotto) → uscita `1`, e
   sulla PR compare il ritiro dell'approvazione.

### Primo verdetto reale (PR #60, 2026-08-12)

Il meccanismo è **entrato in servizio**: primo verdetto non di prova pubblicato
sulla PR #60, SHA `9857aacc96be07658c353b73e196195004dfa969`.

```
verdetto pubblicato: review `COMMENT` sulla PR #60,
cancello `verdetto-murat` su 9857aac… = verde
$ verdetto_gate.py verifica --sha 9857aac…
cancello `verdetto-murat` su 9857aac…: verde        (uscita 0)
```

La rilettura non è una formalità: è la stessa `verifica` che chiunque — umano o
controller di auto-merge — può eseguire senza fidarsi di ciò che lo strumento
dichiara di aver scritto.

## I limiti reali, emersi solo dalla prova live

Nessuno si vedeva dai mock. Il primo è caduto il 2026-08-12; gli altri due
richiedono ancora una decisione umana.

### 1. ~~Il token non può scrivere stati di commit~~ — **risolto il 2026-08-12**

Il 30/07 la pubblicazione dello stato tornava:

```
HTTP 403: Resource not accessible by personal access token
```

Il permesso sugli **stati di commit** (`statuses: write`) è distinto da
`contents` e `pull requests`, e il token dell'ambiente agenti aveva i secondi
due ma non il primo. Finché non è stato concesso, il meccanismo funzionava ma
**non poteva pubblicare nulla**: si è comportato come da progetto — fallendo
chiuso — e nessun verdetto arrivava su GitHub. Non l'ho aggirato e non ho
allargato i permessi da solo.

**Il permesso c'è dal 2026-08-12**, verificato non con una prova sintetica ma
con il primo verdetto vero (sopra): `POST /statuses/{sha}` accettato, `201`,
rilettura `verde`. Caduto il limite 1, restava solo la decisione di Fahad sul
**punto 2** — rendere `verdetto-murat` un check obbligatorio. **È stata presa
alle 13:46 dello stesso giorno**: vedi «Il cancello è vincolante» qui sotto.

### 2. Un account non può approvare le proprie PR

```
422 — "Can not approve your own pull request"
422 — "Can not request changes on your own pull request"
```

Su questo repository l'account che apre le PR degli agenti e l'account del token
sono **lo stesso**, quindi GitHub rifiuta le review formali `APPROVE` e
`REQUEST_CHANGES`. Lo strumento ricade su una review di tipo `COMMENT` che
dichiara il verdetto in chiaro (verificato live: passa). La visibilità si
degrada — niente pallino verde o rosso di review, niente conteggio nelle
approvazioni richieste — mentre **il cancello resta corretto**, perché non
dipende dalla review.

Il rimedio strutturale è dare agli agenti un'identità GitHub distinta da quella
che apre le PR. È una scelta di piattaforma, non di questa PR.

### 3. La head letta dall'API può essere in ritardo su un push

Misurato sul banco di prova: subito dopo un `git push` andato a buon fine,
`GET /pulls/{n}` ha continuato a riportare la head **precedente** per qualche
secondo. Il controllo «lo SHA è ancora la head?» è quindi una **cortesia, non
la garanzia**: in quella finestra il verdetto verrebbe pubblicato sul commit
vecchio — e la head vera resterebbe comunque senza stato, cancello non verde.

Che questo non sia un buco dipende dall'architettura (lo stato è legato allo
SHA), non dalla fortuna. È l'argomento più forte a favore dello stato di commit
rispetto a qualunque presidio che ragioni «sulla PR».
`test_la_head_in_ritardo_non_apre_il_cancello_sulla_head_vera` lo tiene fermo.

## Il cancello è vincolante — dalle 13:46 del 2026-08-12

Fino a quel momento questo documento chiudeva dicendo che il cancello era
**informativo** e che «un merge su uno SHA senza verdetto è ancora possibile».
Da quell'ora **è falso**, e la riga qui sotto è la correzione: Fahad ha acceso la
protezione del ramo su `main`.

Non lo deduco dalla comunicazione della decisione — lo interrogo, che è la
lezione stessa di questo documento. `GET /repos/{o}/{r}/branches/main`:

```
protected: true
required_status_checks.enforcement_level: non_admins
contexts: backend, frontend, e2e, api-contract, base-della-pr,
          copertura, SonarCloud Code Analysis, verdetto-murat
```

E il cancello si verifica **rompendo ciò che difende**: sulle PR aperte il
12/08, quelle senza lo stato sullo SHA non sono mergiabili — non «segnalate»,
non mergiabili.

| PR | `verdetto-murat` sullo SHA | `mergeable_state` |
|---|---|---|
| #64, #65, #67, #68 | `success` | `clean` |
| #63, #66 | **assente** | `blocked` |

Due conseguenze operative, entrambe già viste sul campo:

- **Un push richiude il cancello.** Lo stato è legato allo SHA, quindi un
  verdetto «vecchio di un push» non vale più e la PR torna `blocked` da sola.
- **Approvare sul thread di Multica non basta più.** La PR #66 era approvata a
  voce e `blocked` in GitHub, perché lo stato non era stato pubblicato: il
  verdetto esiste per chi mergia solo se sta sul commit.

### Cosa resta all'umano

1. ~~Concedere al token degli agenti il permesso di scrittura sugli **stati di
   commit** (limite 1).~~ **Fatto: verificato il 2026-08-12 sulla PR #60.**
2. ~~Rendere `verdetto-murat` un **check obbligatorio** nella branch protection
   di `main`.~~ **Fatto alle 13:46 del 2026-08-12, misurato qui sopra.**
3. *Require branches to be up to date before merging* — la condizione che
   avrebbe intercettato la collisione di migrazioni che ha lasciato `main`
   rosso il 30/07, in cui due PR verdi separatamente hanno prodotto un `main`
   rotto una volta unite. Risulta **attivata insieme al resto**, ma è l'unica
   voce che **non ho potuto misurare**: sta solo in `/branches/main/protection`,
   che risponde `403` al token degli agenti. Resta agli atti di Fahad, non a una
   mia verifica — e finché è così va letta come dichiarata, non come provata.

Due riserve che il documento deve portare esplicite, perché «vincolante» non
vuol dire «inaggirabile»:

- `enforcement_level: non_admins`: **Fahad, come amministratore, può mergiare
  oltre il cancello.** È una via di fuga lasciata aperta di proposito, non una
  falla — ma un merge senza verdetto resta possibile per lui, e questo documento
  non deve far credere il contrario.
- *Require approvals* è **spenta di proposito**: le PR degli agenti risultano
  aperte dal token di Fahad e GitHub vieta di approvare una PR propria
  (limite 2), quindi obbligarla bloccherebbe ogni merge. È la stessa causa che
  degrada le review formali in review di tipo `COMMENT`.

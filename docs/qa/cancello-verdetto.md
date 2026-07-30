# Il cancello del verdetto — `verdetto-murat`

_MYL-73 · 30/07/2026 · Murat, Test Architect_

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

## Due limiti reali, emersi solo dalla prova live

Nessuno dei due si vedeva dai mock. Entrambi richiedono una decisione umana.

### 1. Il token non può scrivere stati di commit — il cancello oggi non si apre

```
HTTP 403: Resource not accessible by personal access token
```

Il permesso sugli **stati di commit** (`statuses: write`) è distinto da
`contents` e `pull requests`, e il token dell'ambiente agenti ha i secondi due
ma non il primo. Finché non viene concesso, il meccanismo funziona ma **non può
pubblicare nulla**: si comporta come da progetto — fallisce chiuso — e nessun
verdetto arriva su GitHub.

Non l'ho aggirato e non ho allargato i permessi da solo.

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

## Cosa manca, e spetta all'umano

Il meccanismo esiste; **renderlo vincolante no**, ed è deliberato: la
protezione del ramo riguarda anche i merge di Fahad.

1. Concedere al token degli agenti il permesso di scrittura sugli **stati di
   commit** (limite 1). Senza, il resto non si attiva.
2. Rendere `verdetto-murat` un **check obbligatorio** nella branch protection di
   `main` (Settings → Branches → `main` → *Require status checks to pass*).
   Da quel momento una PR senza verdetto sullo SHA corrente non è mergiabile.
3. Valutare, insieme, *Require branches to be up to date before merging*: è la
   condizione che avrebbe intercettato anche la collisione di migrazioni che ha
   lasciato `main` rosso il 30/07, in cui due PR verdi separatamente hanno
   prodotto un `main` rotto una volta unite.

Finché il punto 2 non è fatto, il cancello è **informativo**: comparirà sulla
pagina della PR, ma non impedirà nulla.

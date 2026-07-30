"""Cancello del verdetto — il verdetto del Test Architect come fatto che GitHub conosce.

Nasce dall'incidente del 30/07 (MYL-73): la PR #48 è stata mergiata su una head
il cui verdetto era BOCCIA. Non è stata disattenzione — sulla pagina GitHub
della PR non esisteva **nulla** che lo dicesse: sette check verdi,
`mergeable: clean`, pulsante verde. Il verdetto viveva su Multica, il merge
avviene su GitHub, e fra i due non c'era alcun collegamento. Il rimedio non è
chiedere più attenzione a chi mergia: è rendere il verdetto un dato che GitHub
espone.

## Due pubblicazioni, due ruoli diversi

* Uno **stato di commit** nel contesto ``verdetto-murat`` sullo SHA esatto.
  **Questo è il cancello**: è ciò che una branch protection — o il controller di
  auto-merge di fine Epic 2 — può leggere in modo verificabile, senza
  interpretare della prosa.
* Una **review sulla PR** (``APPROVE`` / ``REQUEST_CHANGES``). Questa è la
  visibilità per l'umano che guarda la pagina della PR, e **non** è il cancello.

La distinzione non è accademica: su questo repository l'account che apre le PR
degli agenti e l'account del token sono lo stesso, e GitHub rifiuta con 422 una
review ``APPROVE``/``REQUEST_CHANGES`` sulla propria PR. Se la review fosse il
cancello, il cancello non si potrebbe chiudere né aprire. Lo stato di commit non
ha quella restrizione. Quando la review formale è rifiutata si ricade su una
review di tipo ``COMMENT`` che dichiara il verdetto in chiaro: la visibilità si
degrada, il cancello no.

## Perché lo stato di commit, e non un commento in prosa

Uno stato è legato allo SHA. Un push produce uno SHA nuovo, che nasce **senza**
stato: un'approvazione «vecchia di un push» smette di valere da sola, senza che
nessuno debba ricordarsene. È la stessa disciplina del «verdetto sullo SHA
esatto» applicata a mano fino a oggi, delegata a GitHub.

## Fallire in sicurezza

L'ordine delle scritture non è estetica:

* **BOCCIA** → lo stato ``failure`` si pubblica **per primo**. Se la review poi
  fallisce, il cancello è comunque già chiuso.
* **APPROVA** → lo stato ``success`` si pubblica **per ultimo**, e solo dopo che
  tutto il resto è riuscito. È l'unica scrittura che apre il cancello, e non
  deve mai avvenire per inerzia.

Ne segue la proprietà che serve: **qualunque cosa vada storta — permessi, rete,
SHA che cambia sotto le mani — il cancello non risulta verde**. Un cancello
bloccato per errore costa un run in più; un cancello aperto per errore costa una
PR mergiata senza verdetto, che è l'incidente da cui questo file nasce.

## Cosa questo strumento NON fa

Non mergia, non chiude PR, non tocca la protezione del ramo. Rendere
``verdetto-murat`` un check *obbligatorio* è una configurazione del repository
che spetta all'umano, e riguarda anche i suoi merge: qui si costruisce il
meccanismo, non la sua obbligatorietà.

## Uso

    python scripts/verdetto_gate.py pubblica \\
        --repo owner/nome --pr 48 --sha <40 esadecimali> \\
        --verdetto approva|boccia --commento <url del verdetto esteso> \\
        [--motivo "una riga"] [--prova-a-vuoto]

    python scripts/verdetto_gate.py verifica --repo owner/nome --sha <sha>

Il token si legge da ``GITHUB_TOKEN`` o ``GH_TOKEN`` e non viene mai stampato:
ogni uscita passa da :func:`maschera`. Codici di uscita: ``0`` esito atteso,
``1`` pubblicazione fallita o cancello non verde, ``2`` uso o ambiente errati.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from enum import StrEnum

import httpx

#: Il nome del check che comparirà sulla PR. Cambiarlo significa che ogni
#: protezione di ramo configurata sul vecchio nome smette di sorvegliare
#: qualcosa, **restando verde**: è la forma di guasto silenzioso che questo
#: file esiste per evitare. `tests/test_verdetto_convention.py` lo blocca.
CONTESTO = "verdetto-murat"

API = "https://api.github.com"
TIMEOUT = 15.0

#: GitHub tronca la `description` di uno stato a 140 caratteri. Troncare qui è
#: esplicito: meglio una frase tagliata da noi che una tagliata da loro a metà
#: di una parola che cambia il senso.
LIMITE_DESCRIZIONE = 140

USCITA_OK = 0
USCITA_CANCELLO_CHIUSO = 1
USCITA_USO = 2

#: `owner/nome`, e nient'altro. Questi due pezzi finiscono dentro un percorso
#: URL: senza validazione un valore come `../..` o `owner/nome/../altro`
#: manderebbe la richiesta su una risorsa diversa da quella dichiarata. Che a
#: lanciare lo script sia un agente e non un umano non cambia nulla — anzi,
#: l'argomento arriva da un prompt, che è input non fidato per definizione.
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}$")

#: SHA **completo**, minuscolo. Gli SHA abbreviati sono rifiutati di proposito:
#: un prefisso può diventare ambiguo, e soprattutto lo stato andrebbe pubblicato
#: su una risorsa che non è letteralmente quella su cui il verdetto è stato
#: dato. Il senso di tutto il meccanismo è «questo esatto commit».
_SHA = re.compile(r"^[0-9a-f]{40}$")


class ErroreVerdetto(RuntimeError):
    """Qualcosa ha impedito di pubblicare il verdetto in modo attendibile.

    Sollevarla significa sempre la stessa cosa: **il cancello non è verde**.
    Nessun percorso di questo modulo pubblica lo stato `success` dopo aver
    incontrato un errore.
    """


class Verdetto(StrEnum):
    APPROVA = "approva"
    BOCCIA = "boccia"

    @property
    def evento_review(self) -> str:
        return "APPROVE" if self is Verdetto.APPROVA else "REQUEST_CHANGES"

    @property
    def stato_commit(self) -> str:
        return "success" if self is Verdetto.APPROVA else "failure"


def maschera(testo: str, token: str | None) -> str:
    """Sostituisce il token ovunque compaia nel testo.

    Un messaggio di errore di un client HTTP può contenere l'URL, gli header o
    il corpo della richiesta. Il token non deve finire in un log, in un
    commento o in un output di CI nemmeno per incidente, e l'unico modo per
    esserne certi è non fidarsi di *dove* potrebbe comparire.
    """
    if not token:
        return testo
    return testo.replace(token, "***")


def leggi_token() -> str:
    for nome in ("GITHUB_TOKEN", "GH_TOKEN"):
        valore = os.environ.get(nome, "").strip()
        if valore:
            return valore
    raise ErroreVerdetto(
        "nessun token in GITHUB_TOKEN o GH_TOKEN: senza credenziali non posso "
        "pubblicare nulla, e senza stato pubblicato il cancello resta chiuso."
    )


def crea_client(
    token: str, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """Client HTTP verso l'API di GitHub.

    `transport` esiste per i test: la suite gira contro un finto GitHub
    (`httpx.MockTransport`) e non tocca la rete. Un cancello che si può provare
    solo in produzione non si prova.
    """
    return httpx.Client(
        base_url=API,
        timeout=TIMEOUT,
        transport=transport,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hostpilot-cancello-verdetto",
        },
    )


def _valida(repo: str, sha: str) -> None:
    if not _REPO.match(repo):
        raise ErroreVerdetto(
            f"repository non valido: {repo!r}. Atteso `owner/nome`, senza "
            "percorsi né caratteri fuori da [A-Za-z0-9._-]."
        )
    if not _SHA.match(sha):
        raise ErroreVerdetto(
            f"SHA non valido: {sha!r}. Atteso lo SHA COMPLETO (40 esadecimali "
            "minuscoli): un prefisso non identifica «questo esatto commit», "
            "che è l'unica cosa che questo cancello sa dire."
        )


def _valida_url(url: str) -> None:
    if not url.startswith("https://"):
        raise ErroreVerdetto(
            f"il link al verdetto esteso deve essere `https://`, ricevuto {url!r}."
        )


def _esito(risposta: httpx.Response) -> str:
    """Riassunto leggibile di una risposta fallita, senza il corpo intero."""
    try:
        corpo = risposta.json()
        messaggio = corpo.get("message", "")
        errori = corpo.get("errors", [])
        if errori:
            messaggio = f"{messaggio} — {json.dumps(errori, ensure_ascii=False)}"
    except ValueError:
        messaggio = risposta.text[:200]
    return f"HTTP {risposta.status_code}: {messaggio}"


def head_della_pr(http: httpx.Client, repo: str, pr: int) -> str:
    risposta = http.get(f"/repos/{repo}/pulls/{pr}")
    if risposta.status_code != 200:
        raise ErroreVerdetto(f"non riesco a leggere la PR #{pr}: {_esito(risposta)}")
    return str(risposta.json()["head"]["sha"])


def pubblica_stato(
    http: httpx.Client,
    repo: str,
    sha: str,
    stato: str,
    descrizione: str,
    url_verdetto: str,
) -> None:
    """Pubblica lo stato di commit. È l'atto che apre o chiude il cancello."""
    risposta = http.post(
        f"/repos/{repo}/statuses/{sha}",
        json={
            "state": stato,
            "context": CONTESTO,
            "description": descrizione[:LIMITE_DESCRIZIONE],
            "target_url": url_verdetto,
        },
    )
    if risposta.status_code != 201:
        raise ErroreVerdetto(
            f"stato `{stato}` NON pubblicato su {sha}: {_esito(risposta)}. "
            "Il cancello resta senza stato, cioè non verde: è la direzione "
            "giusta in cui fallire, ma il verdetto va ripubblicato."
        )


def pubblica_review(
    http: httpx.Client, repo: str, pr: int, sha: str, verdetto: Verdetto, corpo: str
) -> str:
    """Pubblica la review sulla PR. Torna l'evento effettivamente usato.

    Se GitHub rifiuta la review formale (422 — tipicamente «Can not approve your
    own pull request», che su questo repository è il caso NORMALE perché
    l'account del token è anche l'autore della PR) si ricade su una review di
    tipo ``COMMENT`` che dichiara il verdetto in chiaro. Il cancello non dipende
    da questa chiamata; dipende dallo stato di commit.
    """
    for evento in (verdetto.evento_review, "COMMENT"):
        risposta = http.post(
            f"/repos/{repo}/pulls/{pr}/reviews",
            json={"commit_id": sha, "event": evento, "body": corpo},
        )
        if risposta.status_code in (200, 201):
            return evento
        if risposta.status_code != 422:
            raise ErroreVerdetto(
                f"review NON pubblicata sulla PR #{pr}: {_esito(risposta)}"
            )
    raise ErroreVerdetto(
        f"review NON pubblicata sulla PR #{pr}: GitHub ha rifiutato sia "
        f"`{verdetto.evento_review}` sia `COMMENT`. Non pubblico lo stato "
        "`success`: un verdetto che nessuno può leggere sulla PR non è il "
        "meccanismo che ho costruito."
    )


def leggi_cancello(http: httpx.Client, repo: str, sha: str) -> str:
    """Stato del cancello su uno SHA: ``verde``, ``rosso`` o ``assente``.

    ``assente`` è il caso più importante dei tre, ed è il valore che risponde
    alle due domande dell'incidente: una PR senza verdetto, e uno SHA nuovo
    dopo un push. Nessuno dei due eredita nulla — non c'è nessun meccanismo di
    ereditarietà da disattivare, uno stato appartiene a un commit e basta.
    """
    _valida(repo, sha)
    risposta = http.get(f"/repos/{repo}/commits/{sha}/status")
    if risposta.status_code != 200:
        raise ErroreVerdetto(
            f"non riesco a leggere gli stati di {sha}: {_esito(risposta)}. "
            "Un cancello che non si riesce a leggere NON è verde."
        )
    for stato in risposta.json().get("statuses", []):
        if stato.get("context") == CONTESTO:
            return "verde" if stato.get("state") == "success" else "rosso"
    return "assente"


def _corpo_review(
    verdetto: Verdetto, url_verdetto: str, sha: str, motivo: str | None
) -> str:
    intestazione = (
        "🧪 **Verdetto del Test Architect: APPROVA**"
        if verdetto is Verdetto.APPROVA
        else "🧪 **Verdetto del Test Architect: BOCCIA**"
    )
    righe = [
        intestazione,
        "",
        f"Vale sullo SHA `{sha}` e su nessun altro: se arriva un push, il "
        f"commit nuovo nasce senza lo stato `{CONTESTO}` e il verdetto va "
        "rifatto.",
    ]
    if motivo:
        righe += ["", motivo]
    righe += [
        "",
        f"Verdetto esteso, con le evidenze: {url_verdetto}",
        "",
        f"_Il cancello è lo stato di commit `{CONTESTO}`, non questa review._",
    ]
    return "\n".join(righe)


def _descrizione_stato(verdetto: Verdetto, motivo: str | None) -> str:
    testa = "APPROVA" if verdetto is Verdetto.APPROVA else "BOCCIA"
    return f"{testa} — {motivo}" if motivo else f"{testa} — verdetto su questo SHA"


def pubblica_verdetto(
    http: httpx.Client,
    repo: str,
    pr: int,
    sha: str,
    verdetto: Verdetto,
    url_verdetto: str,
    motivo: str | None = None,
) -> dict[str, str]:
    """Pubblica il verdetto. Solleva :class:`ErroreVerdetto` a ogni intoppo.

    L'ordine delle scritture è la garanzia di sicurezza, non un dettaglio: vedi
    la sezione «Fallire in sicurezza» in testa al modulo.
    """
    _valida(repo, sha)
    _valida_url(url_verdetto)

    head = head_della_pr(http, repo, pr)
    if head != sha:
        raise ErroreVerdetto(
            f"la head della PR #{pr} è {head}, non {sha}: il codice è cambiato "
            "dopo il verdetto. Non pubblico nulla — un'approvazione data su "
            "un altro albero non è un'approvazione. Rifai la review sulla head."
        )

    corpo = _corpo_review(verdetto, url_verdetto, sha, motivo)
    descrizione = _descrizione_stato(verdetto, motivo)

    if verdetto is Verdetto.BOCCIA:
        # `failure` per PRIMO: se la review poi fallisce, il cancello è già
        # chiuso. L'ordine inverso lascerebbe una finestra in cui la PR è
        # bocciata e GitHub non lo sa.
        pubblica_stato(http, repo, sha, "failure", descrizione, url_verdetto)
        evento = pubblica_review(http, repo, pr, sha, verdetto, corpo)
    else:
        # `success` per ULTIMO. Ogni riga sopra questa può fallire, e finché
        # non è eseguita il cancello non è verde.
        evento = pubblica_review(http, repo, pr, sha, verdetto, corpo)
        pubblica_stato(http, repo, sha, "success", descrizione, url_verdetto)

    # Rilettura di controllo. Uno strumento che dichiara di aver pubblicato uno
    # stato senza averlo mai riletto è esattamente il tipo di cancello non
    # verificato da cui nasce MYL-59: se la rilettura non conferma, il verdetto
    # non è pubblicato, punto.
    atteso = "verde" if verdetto is Verdetto.APPROVA else "rosso"
    letto = leggi_cancello(http, repo, sha)
    if letto != atteso:
        raise ErroreVerdetto(
            f"pubblicato `{verdetto.stato_commit}` su {sha}, ma la rilettura "
            f"del cancello dice `{letto}` invece di `{atteso}`. Non dichiaro "
            "pubblicato un verdetto che non riesco a rileggere."
        )
    return {"evento_review": evento, "cancello": letto}


def _argomenti(argv: Sequence[str] | None) -> argparse.Namespace:
    comune = argparse.ArgumentParser(add_help=False)
    comune.add_argument("--repo", required=True, help="owner/nome")
    comune.add_argument("--sha", required=True, help="SHA completo, 40 esadecimali")

    parser = argparse.ArgumentParser(
        prog="verdetto_gate.py",
        description=(
            "Pubblica e verifica il cancello `verdetto-murat`. Non mergia mai."
        ),
    )
    sotto = parser.add_subparsers(dest="comando", required=True)

    pubblica = sotto.add_parser(
        "pubblica", parents=[comune], help="pubblica il verdetto sulla PR e sullo SHA"
    )
    pubblica.add_argument("--pr", required=True, type=int)
    pubblica.add_argument(
        "--verdetto", required=True, choices=[v.value for v in Verdetto]
    )
    pubblica.add_argument(
        "--commento",
        required=True,
        help="URL https del verdetto esteso (il commento su Multica)",
    )
    pubblica.add_argument("--motivo", default=None, help="una riga di sintesi")
    pubblica.add_argument(
        "--prova-a-vuoto",
        action="store_true",
        help="stampa cosa farebbe e non scrive nulla",
    )

    sotto.add_parser(
        "verifica",
        parents=[comune],
        help="dice se lo SHA ha il verdetto (uscita 0 solo se verde)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _argomenti(argv)
    token = None
    try:
        if args.comando == "pubblica" and args.prova_a_vuoto:
            _valida(args.repo, args.sha)
            _valida_url(args.commento)
            print(
                f"[a vuoto] pubblicherei `{Verdetto(args.verdetto).stato_commit}` "
                f"nel contesto `{CONTESTO}` su {args.repo}@{args.sha} "
                f"e una review sulla PR #{args.pr}. Nessuna scrittura eseguita."
            )
            return USCITA_OK

        token = leggi_token()
        with crea_client(token) as http:
            if args.comando == "verifica":
                stato = leggi_cancello(http, args.repo, args.sha)
                print(f"cancello `{CONTESTO}` su {args.sha}: {stato}")
                return USCITA_OK if stato == "verde" else USCITA_CANCELLO_CHIUSO

            esito = pubblica_verdetto(
                http,
                args.repo,
                args.pr,
                args.sha,
                Verdetto(args.verdetto),
                args.commento,
                args.motivo,
            )
        print(
            f"verdetto pubblicato: review `{esito['evento_review']}` sulla PR "
            f"#{args.pr}, cancello `{CONTESTO}` su {args.sha} = "
            f"{esito['cancello']}."
        )
        return USCITA_OK
    except ErroreVerdetto as errore:
        print(maschera(f"cancello NON verde: {errore}", token), file=sys.stderr)
        return USCITA_CANCELLO_CHIUSO
    except httpx.HTTPError as errore:  # rete, DNS, timeout
        print(
            maschera(
                f"cancello NON verde: la chiamata a GitHub non è riuscita "
                f"({type(errore).__name__}: {errore}).",
                token,
            ),
            file=sys.stderr,
        )
        return USCITA_CANCELLO_CHIUSO


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

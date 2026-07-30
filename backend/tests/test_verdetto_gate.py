"""Il cancello `verdetto-murat` fallisce in sicurezza — chiude MYL-73.

Questi test non verificano che il meccanismo *funzioni*: quello è il caso
facile, ed è anche l'unico che si verifica da solo il giorno in cui lo usi.
Verificano che **non risulti approvato niente che non lo sia**, che è la
proprietà da cui nasce l'incidente del 30/07 (PR #48 mergiata su una head il
cui verdetto era BOCCIA, senza che sulla pagina GitHub esistesse nulla che lo
dicesse).

I tre casi che la issue chiedeva provati e non descritti, con il nome del test
che li tiene chiusi:

1. PR senza alcun verdetto → nessuno stato `verdetto-murat` → il cancello non è
   verde → `test_pr_senza_verdetto_ha_il_cancello_assente`.
2. Verdetto APPROVA, poi un push nuovo → il nuovo SHA non ha stato →
   `test_lo_stato_non_si_eredita_dopo_un_push` e
   `test_verdetto_su_uno_sha_che_non_e_piu_la_head_non_scrive_nulla`.
3. Pubblicazione dello stato fallita (permessi, rete) → il verdetto **non**
   risulta approvato → `test_stato_fallito_su_approva_non_risulta_approvato`,
   `test_rete_caduta_su_approva_non_risulta_approvato`,
   `test_review_impossibile_su_approva_non_pubblica_alcuno_stato`.

Il finto GitHub è un `httpx.MockTransport`: la suite non tocca la rete, e ogni
richiesta viene registrata, così l'ordine delle scritture — che è la garanzia
di sicurezza, non un dettaglio estetico — è a sua volta asserito.
"""

import json

import httpx
import pytest

from scripts.verdetto_gate import (
    CONTESTO,
    ErroreVerdetto,
    Verdetto,
    crea_client,
    leggi_cancello,
    main,
    maschera,
    pubblica_verdetto,
)

REPO = "fahadmohammed96/test_bmad_method"
SHA = "a" * 40
SHA_NUOVO = "b" * 40
PR = 48
URL = "https://app.multica.ai/issue/MYL-73#verdetto"

REVIEWS = f"/repos/{REPO}/pulls/{PR}/reviews"
STATUSES = f"/repos/{REPO}/statuses/{SHA}"


class FintoGitHub:
    """GitHub finto e registratore.

    `esiti` mappa `(metodo, percorso)` su una lista di risposte da restituire
    in sequenza: è così che si costruisce «la review passa, lo stato no».

    Gli stati sono indicizzati **per SHA**, come su GitHub. La prima stesura di
    questo finto li teneva in una lista sola, condivisa fra tutti i commit: con
    quella,`test_lo_stato_non_si_eredita_dopo_un_push` passava leggendo lo
    stato del commit precedente, cioè verificava il finto invece del prodotto.
    È il modo tipico in cui un doppio troppo permissivo nasconde proprio la
    proprietà che il test dichiara di sorvegliare — qui l'ha rivelato il test,
    perché era scritto per fallire su quel caso.
    """

    def __init__(
        self,
        head: str = SHA,
        stati: list[dict] | None = None,
        esiti: dict[tuple[str, str], list[httpx.Response]] | None = None,
    ) -> None:
        self.head = head
        self.stati: dict[str, list[dict]] = {SHA: list(stati)} if stati else {}
        self.esiti = esiti or {}
        self.chiamate: list[tuple[str, str, dict | None]] = []

    @property
    def scritture(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.chiamate if c[0] == "POST"]

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._gestisci)

    def _gestisci(self, richiesta: httpx.Request) -> httpx.Response:
        percorso = richiesta.url.path
        corpo = None
        if richiesta.method == "POST":
            corpo = json.loads(richiesta.content)
        self.chiamate.append((richiesta.method, percorso, corpo))

        coda = self.esiti.get((richiesta.method, percorso))
        if coda:
            return coda.pop(0)

        if percorso == f"/repos/{REPO}/pulls/{PR}":
            return httpx.Response(200, json={"head": {"sha": self.head}})
        if percorso.startswith(f"/repos/{REPO}/statuses/"):
            assert corpo is not None
            sha = percorso.rsplit("/", 1)[1]
            # Come su GitHub: l'ultimo stato di un contesto sostituisce il
            # precedente, e solo su QUESTO commit.
            correnti = [
                s for s in self.stati.get(sha, []) if s["context"] != corpo["context"]
            ]
            correnti.append({"context": corpo["context"], "state": corpo["state"]})
            self.stati[sha] = correnti
            return httpx.Response(201, json={})
        if percorso == f"/repos/{REPO}/pulls/{PR}/reviews":
            return httpx.Response(200, json={})
        if percorso.endswith("/status"):
            sha = percorso.split("/commits/")[1].removesuffix("/status")
            return httpx.Response(200, json={"statuses": self.stati.get(sha, [])})
        return httpx.Response(404, json={"message": f"non gestito: {percorso}"})


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    finto = "ghp_" + "z" * 36
    monkeypatch.setenv("GITHUB_TOKEN", finto)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    return finto


def _client(finto: FintoGitHub) -> httpx.Client:
    return crea_client("ghp_irrilevante", transport=finto.transport())


# --------------------------------------------------------------------------
# 1. Nessun verdetto → cancello non verde
# --------------------------------------------------------------------------


def test_pr_senza_verdetto_ha_il_cancello_assente() -> None:
    """Il caso base dell'incidente: nessuno ha dato un verdetto su questo SHA."""
    finto = FintoGitHub(stati=[])
    with _client(finto) as http:
        assert leggi_cancello(http, REPO, SHA) == "assente"


def test_altri_check_verdi_non_aprono_il_cancello() -> None:
    """Sette check verdi non sono un verdetto.

    È letteralmente la pagina che Fahad ha visto il 30/07: `backend`,
    `frontend`, `e2e`, `api-contract`, SonarCloud tutti verdi e
    `mergeable: clean`. Il cancello del verdetto guarda UN solo contesto.
    """
    finto = FintoGitHub(
        stati=[
            {"context": "backend", "state": "success"},
            {"context": "frontend", "state": "success"},
            {"context": "e2e", "state": "success"},
            {"context": "api-contract", "state": "success"},
            {"context": "SonarCloud Code Analysis", "state": "success"},
        ]
    )
    with _client(finto) as http:
        assert leggi_cancello(http, REPO, SHA) == "assente"


def test_verifica_esce_diversa_da_zero_senza_verdetto(token: str) -> None:
    """La forma che un controller di auto-merge leggerà: il codice di uscita."""
    finto = FintoGitHub(stati=[])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.verdetto_gate.crea_client",
            lambda t, transport=None: _client(finto),
        )
        assert main(["verifica", "--repo", REPO, "--sha", SHA]) != 0


# --------------------------------------------------------------------------
# 2. Un push nuovo azzera l'approvazione
# --------------------------------------------------------------------------


def test_lo_stato_non_si_eredita_dopo_un_push() -> None:
    """APPROVA su uno SHA, poi un push: il commit nuovo nasce senza stato.

    Non c'è alcun meccanismo di ereditarietà da disattivare — è questa la
    ragione per cui il cancello è uno stato di *commit* e non un'etichetta
    sulla PR, che invece sopravviverebbe al push.
    """
    finto = FintoGitHub(head=SHA)
    with _client(finto) as http:
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
        assert leggi_cancello(http, REPO, SHA) == "verde"

        # Arriva un push: la head cambia, e il commit nuovo non ha stati.
        finto.head = SHA_NUOVO
        assert leggi_cancello(http, REPO, SHA_NUOVO) == "assente"


def test_verdetto_su_uno_sha_che_non_e_piu_la_head_non_scrive_nulla() -> None:
    """Se il codice è cambiato fra la review e la pubblicazione, non pubblico.

    La gara è reale: la review dura minuti, un push dura un secondo. Pubblicare
    comunque non aprirebbe il cancello sulla head (lo stato andrebbe sul
    commit vecchio), ma lascerebbe sulla PR una review di approvazione su un
    albero che nessuno ha guardato.
    """
    finto = FintoGitHub(head=SHA_NUOVO)
    with _client(finto) as http, pytest.raises(ErroreVerdetto, match="head della PR"):
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
    assert finto.scritture == []


# --------------------------------------------------------------------------
# 3. Ogni guasto fallisce nella direzione del cancello chiuso
# --------------------------------------------------------------------------


def test_stato_fallito_su_approva_non_risulta_approvato() -> None:
    """Permessi mancanti sulla POST dello stato: nessuna approvazione.

    403 su `statuses` è lo scenario concreto — il permesso `statuses: write` è
    distinto da `contents` e `pull requests`, e un token può averne due su tre.
    """
    finto = FintoGitHub(
        esiti={
            ("POST", f"/repos/{REPO}/statuses/{SHA}"): [
                httpx.Response(403, json={"message": "Resource not accessible"})
            ]
        }
    )
    with _client(finto) as http:
        with pytest.raises(ErroreVerdetto, match="NON pubblicato"):
            pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
        assert leggi_cancello(http, REPO, SHA) == "assente"


def test_rete_caduta_su_approva_non_risulta_approvato(token: str) -> None:
    """La rete cade a metà: uscita non zero, e nessuno stato pubblicato."""

    def cade(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("rete assente")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.verdetto_gate.crea_client",
            lambda t, transport=None: crea_client(
                "ghp_irrilevante", transport=httpx.MockTransport(cade)
            ),
        )
        uscita = main(
            [
                "pubblica",
                "--repo",
                REPO,
                "--pr",
                str(PR),
                "--sha",
                SHA,
                "--verdetto",
                "approva",
                "--commento",
                URL,
            ]
        )
    assert uscita != 0


def test_review_impossibile_su_approva_non_pubblica_alcuno_stato() -> None:
    """Se nemmeno la review-commento passa, il cancello non si apre.

    Il ripiego su `COMMENT` copre il caso normale (GitHub rifiuta con 422 una
    review formale sulla propria PR). Se anche quello è rifiutato, l'umano che
    guarda la PR non vedrebbe alcun verdetto: aprire il cancello lasciando la
    pagina muta è esattamente l'incidente di partenza.
    """
    rifiuto = [
        httpx.Response(422, json={"message": "Can not approve your own pull request"}),
        httpx.Response(422, json={"message": "no"}),
    ]
    finto = FintoGitHub(esiti={("POST", f"/repos/{REPO}/pulls/{PR}/reviews"): rifiuto})
    with _client(finto) as http:
        with pytest.raises(ErroreVerdetto, match="rifiutato"):
            pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
    assert not [c for c in finto.scritture if "/statuses/" in c[1]]


def test_rilettura_incoerente_non_dichiara_approvato() -> None:
    """La POST risponde 201 ma la rilettura non vede lo stato: non è approvato.

    Uno strumento che dichiara pubblicato ciò che non ha mai riletto è la
    stessa forma di guasto di MYL-59 — un cancello che nessuno ha interrogato.
    """
    finto = FintoGitHub(
        esiti={
            ("GET", f"/repos/{REPO}/commits/{SHA}/status"): [
                httpx.Response(200, json={"statuses": []})
            ]
        }
    )
    with _client(finto) as http, pytest.raises(ErroreVerdetto, match="rilettura"):
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)


# --------------------------------------------------------------------------
# Ordine delle scritture: la garanzia di sicurezza, asserita
# --------------------------------------------------------------------------


def test_approva_pubblica_lo_stato_success_per_ultimo() -> None:
    finto = FintoGitHub()
    with _client(finto) as http:
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
    percorsi = [c[1] for c in finto.scritture]
    assert percorsi == [REVIEWS, STATUSES]
    assert finto.scritture[-1][2] == {
        "state": "success",
        "context": CONTESTO,
        "description": "APPROVA — verdetto su questo SHA",
        "target_url": URL,
    }


def test_boccia_pubblica_lo_stato_failure_per_primo() -> None:
    """Chiudere prima e parlare dopo.

    Con l'ordine inverso, una review che fallisce lascerebbe una PR bocciata su
    cui GitHub non sa nulla: la stessa pagina verde del 30/07.
    """
    finto = FintoGitHub()
    with _client(finto) as http:
        pubblica_verdetto(
            http, REPO, PR, SHA, Verdetto.BOCCIA, URL, motivo="F11 aperto"
        )
    percorsi = [c[1] for c in finto.scritture]
    assert percorsi == [STATUSES, REVIEWS]
    assert finto.scritture[0][2] is not None
    assert finto.scritture[0][2]["state"] == "failure"


def test_review_fallita_dopo_una_boccia_lascia_il_cancello_chiuso() -> None:
    """Il caso che l'ordine protegge, verificato e non dedotto."""
    finto = FintoGitHub(
        esiti={
            ("POST", f"/repos/{REPO}/pulls/{PR}/reviews"): [
                httpx.Response(500, json={"message": "boom"}),
                httpx.Response(500, json={"message": "boom"}),
            ]
        }
    )
    with _client(finto) as http:
        with pytest.raises(ErroreVerdetto):
            pubblica_verdetto(http, REPO, PR, SHA, Verdetto.BOCCIA, URL)
        assert leggi_cancello(http, REPO, SHA) == "rosso"


def test_boccia_non_pubblica_mai_uno_stato_success() -> None:
    finto = FintoGitHub()
    with _client(finto) as http:
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.BOCCIA, URL)
    stati = [c[2] for c in finto.scritture if "/statuses/" in c[1]]
    assert stati and all(s is not None and s["state"] == "failure" for s in stati)


def test_ripiego_su_commento_quando_github_rifiuta_la_review_formale() -> None:
    """Il caso NORMALE su questo repository: token e autore della PR coincidono."""
    finto = FintoGitHub(
        esiti={
            ("POST", f"/repos/{REPO}/pulls/{PR}/reviews"): [
                httpx.Response(
                    422, json={"message": "Can not approve your own pull request"}
                ),
                httpx.Response(200, json={}),
            ]
        }
    )
    with _client(finto) as http:
        esito = pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, URL)
    assert esito == {"evento_review": "COMMENT", "cancello": "verde"}
    review = [c for c in finto.scritture if c[1].endswith("/reviews")]
    assert [c[2]["event"] for c in review if c[2]] == ["APPROVE", "COMMENT"]
    # Il verdetto deve restare leggibile anche quando la review è un commento:
    # è tutta la visibilità che resta all'umano sulla pagina della PR.
    assert "APPROVA" in review[-1][2]["body"]  # type: ignore[index]
    assert SHA in review[-1][2]["body"]  # type: ignore[index]


# --------------------------------------------------------------------------
# Input non fidato e segreti
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "repo, sha",
    [
        ("owner/nome/../altro", SHA),
        ("../../etc", SHA),
        ("owner nome", SHA),
        ("owner/nome", "abc123"),  # SHA abbreviato
        ("owner/nome", "A" * 40),  # maiuscolo: non è la forma che GitHub usa
        ("owner/nome", SHA + "a"),
    ],
)
def test_argomenti_malformati_non_producono_nessuna_chiamata(
    repo: str, sha: str
) -> None:
    """`repo` e `sha` finiscono dentro un percorso URL: si validano.

    Che a lanciare lo script sia un agente e non un umano non attenua nulla —
    l'argomento arriva da un prompt, che è input non fidato per definizione.
    """
    finto = FintoGitHub()
    with _client(finto) as http, pytest.raises(ErroreVerdetto):
        pubblica_verdetto(http, repo, PR, sha, Verdetto.APPROVA, URL)
    assert finto.chiamate == []


def test_link_al_verdetto_deve_essere_https() -> None:
    finto = FintoGitHub()
    with _client(finto) as http, pytest.raises(ErroreVerdetto, match="https"):
        pubblica_verdetto(http, REPO, PR, SHA, Verdetto.APPROVA, "javascript:alert(1)")
    assert finto.chiamate == []


def test_il_token_non_compare_mai_nelle_uscite(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un errore che cita l'URL o gli header non deve consegnare il token."""
    segreto = "ghp_" + "s" * 36
    monkeypatch.setenv("GITHUB_TOKEN", segreto)

    def cade(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"connessione fallita con Bearer {segreto}")

    monkeypatch.setattr(
        "scripts.verdetto_gate.crea_client",
        lambda t, transport=None: crea_client(t, transport=httpx.MockTransport(cade)),
    )
    assert main(["verifica", "--repo", REPO, "--sha", SHA]) != 0
    catturato = capsys.readouterr()
    assert segreto not in catturato.out + catturato.err
    assert "***" in catturato.err


def test_maschera_sostituisce_ogni_occorrenza() -> None:
    assert maschera("a ghp_x b ghp_x", "ghp_x") == "a *** b ***"
    assert maschera("niente da mascherare", None) == "niente da mascherare"


def test_senza_token_non_si_pubblica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert main(["verifica", "--repo", REPO, "--sha", SHA]) != 0


def test_prova_a_vuoto_non_scrive_nulla(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--prova-a-vuoto` non deve nemmeno costruire un client."""
    monkeypatch.setattr(
        "scripts.verdetto_gate.crea_client",
        lambda *a, **k: pytest.fail("nessun client in prova a vuoto"),
    )
    uscita = main(
        [
            "pubblica",
            "--repo",
            REPO,
            "--pr",
            str(PR),
            "--sha",
            SHA,
            "--verdetto",
            "approva",
            "--commento",
            URL,
            "--prova-a-vuoto",
        ]
    )
    assert uscita == 0

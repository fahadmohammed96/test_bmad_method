"""Guardia sulla convenzione dei lock consultivi — chiude RT-3.

RT-3 (test design dell'Epic 1, §7.7) diceva: «il cap Strutture usa
`pg_advisory_xact_lock(1001, hashtext(host_id))`. Oggi è l'unico advisory lock
del progetto: nessuna collisione possibile. **Al secondo advisory lock**
introdotto nel codice va usato un namespace diverso e la convenzione va
scritta.» Il secondo advisory lock è il bootstrap del poller (A3-3), quindi il
debito scade qui.

Perché una guardia e non solo un commento: `pg_advisory_xact_lock` prende due
interi e li tratta come una chiave sola. Due percorsi che scelgono lo stesso
namespace si serializzano a vicenda **senza alcun errore** — un Host che
collega un Feed aspetterebbe un altro Host che registra una Struttura. Il
sintomo è latenza sotto carico, il che significa che si scopre in produzione e
si attribuisce al database. Un difetto che non produce un errore va impedito
per costruzione, non ricordato.
"""

import ast
import pathlib

import pytest

from app.core import lock

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MODULO_DEI_LOCK = BACKEND / "app" / "core" / "lock.py"

PREFISSO_NAMESPACE = "NAMESPACE_"


def _namespace_dichiarati() -> dict[str, int]:
    return {
        nome: valore
        for nome, valore in vars(lock).items()
        if nome.startswith(PREFISSO_NAMESPACE) and isinstance(valore, int)
    }


def test_esiste_piu_di_un_namespace() -> None:
    # La guardia ha senso da due in su; se tornassero a essere zero o uno,
    # qualcuno ha smontato la convenzione e questo test lo dice.
    assert len(_namespace_dichiarati()) >= 2


def test_i_namespace_sono_tutti_distinti() -> None:
    dichiarati = _namespace_dichiarati()
    valori = list(dichiarati.values())
    assert len(set(valori)) == len(valori), (
        f"namespace di lock duplicati: {dichiarati} — due percorsi con lo "
        "stesso namespace si serializzano a vicenda senza alcun errore"
    )


def test_il_namespace_storico_del_cap_strutture_non_e_cambiato() -> None:
    # 1001 è in uso su installazioni esistenti: cambiarlo mentre un'altra
    # transazione tiene il vecchio farebbe convivere due regimi di
    # serializzazione sullo stesso percorso.
    assert lock.NAMESPACE_CAP_STRUTTURE == 1001


def _chiamate_advisory(albero: ast.AST) -> list[int]:
    """Le righe con un `pg_advisory_*` dentro una stringa letterale."""
    return [
        nodo.lineno
        for nodo in ast.walk(albero)
        if isinstance(nodo, ast.Constant)
        and isinstance(nodo.value, str)
        and "pg_advisory" in nodo.value
    ]


def test_solo_app_core_lock_scrive_un_pg_advisory() -> None:
    # Il SQL del lock vive in un posto solo. Sparso, ogni chiamante
    # sceglierebbe il proprio namespace in linea e la distinzione tornerebbe
    # a essere una proprietà che nessuno può verificare.
    fuori_norma = []
    for percorso in (BACKEND / "app").rglob("*.py"):
        if percorso == MODULO_DEI_LOCK:
            continue
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        fuori_norma += [
            f"{percorso.relative_to(BACKEND)}:{riga}"
            for riga in _chiamate_advisory(albero)
        ]
    assert fuori_norma == [], (
        f"`pg_advisory_*` fuori da app/core/lock.py: {fuori_norma} — "
        "i lock consultivi passano dal modulo che dichiara i namespace (RT-3)"
    )


def _namespace_dichiarati_nel_sorgente(albero: ast.AST) -> list[tuple[str, int]]:
    """Assegnazioni a un nome che comincia per `NAMESPACE_`.

    Prende l'ALBERO e non il percorso, come `_chiamate_advisory`: è ciò che
    permette di puntarla su un sorgente finto e pretendere che segnali. La
    versione precedente richiedeva anche `"LOCK" in nome`, e nessuna costante
    del progetto contiene `LOCK` — `NAMESPACE_CAP_STRUTTURE` e
    `NAMESPACE_SYNC_PERIODICO` non lo contengono, e non lo conteneva nemmeno
    il `NAMESPACE_QUALCOSA` che il commento portava come esempio della
    violazione da intercettare. Il predicato non poteva essere vero, e
    l'assenza di una sentinella è precisamente il motivo per cui è passato:
    una guardia che non morde è una ragione scritta perché il prossimo non
    guardi.
    """
    trovati: list[tuple[str, int]] = []
    for nodo in ast.walk(albero):
        bersagli = (
            nodo.targets
            if isinstance(nodo, ast.Assign)
            else [nodo.target]
            if isinstance(nodo, ast.AnnAssign)
            else []
        )
        for bersaglio in bersagli:
            if isinstance(bersaglio, ast.Name) and bersaglio.id.startswith(
                PREFISSO_NAMESPACE
            ):
                trovati.append((bersaglio.id, nodo.lineno))
    return trovati


def test_nessun_modulo_dichiara_un_namespace_per_conto_proprio() -> None:
    # Un `NAMESPACE_QUALCOSA = 1002` in un modulo di dominio ricreerebbe
    # esattamente la situazione che RT-3 chiedeva di chiudere: due costanti
    # in due file, e nessun posto in cui si vede che collidono.
    fuori_norma = []
    for percorso in (BACKEND / "app").rglob("*.py"):
        if percorso == MODULO_DEI_LOCK:
            continue
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        fuori_norma += [
            f"{percorso.relative_to(BACKEND)}:{riga} {nome}"
            for nome, riga in _namespace_dichiarati_nel_sorgente(albero)
        ]
    assert fuori_norma == [], (
        f"namespace di lock dichiarati fuori da app/core/lock.py: {fuori_norma}"
    )


@pytest.mark.parametrize(
    "sorgente",
    [
        "NAMESPACE_QUALCOSA = 1002\n",
        "NAMESPACE_SYNC_PERIODICO = 1002\n",
        "NAMESPACE_LOCK_CAP_STRUTTURE = 1001\n",
        "NAMESPACE_ALTRO: int = 1004\n",
    ],
)
def test_la_guardia_riconosce_un_namespace_dichiarato_fuori_posto(
    sorgente: str,
) -> None:
    # La sentinella che mancava. Include i due nomi REALI del progetto: se il
    # predicato tornasse a chiedere una sottostringa che le costanti vere non
    # hanno, questo caso lo dice subito.
    assert _namespace_dichiarati_nel_sorgente(ast.parse(sorgente))


@pytest.mark.parametrize(
    "sorgente",
    [
        "PREFISSO = 'NAMESPACE_'\n",
        "def usa(namespace: int) -> None: ...\n",
        "SOGLIA_ALERT = 3\n",
    ],
)
def test_la_guardia_non_segnala_un_sorgente_innocuo(sorgente: str) -> None:
    # L'altra metà: una guardia che segnala tutto non discrimina. In
    # particolare una STRINGA che contiene il prefisso non è una
    # dichiarazione, e un parametro di funzione nemmeno.
    assert _namespace_dichiarati_nel_sorgente(ast.parse(sorgente)) == []


def test_la_guardia_vede_i_namespace_VERI_del_progetto() -> None:
    # Il legame fra la guardia e la realtà: il predicato deve riconoscere le
    # costanti che esistono davvero, altrimenti sorveglia una convenzione che
    # nessuno usa. Le si fa esaminare il modulo dei lock, dove sono legittime.
    albero = ast.parse(MODULO_DEI_LOCK.read_text(encoding="utf-8"))
    nomi = {nome for nome, _ in _namespace_dichiarati_nel_sorgente(albero)}
    assert set(_namespace_dichiarati()) <= nomi, (
        f"la guardia non riconosce {sorted(set(_namespace_dichiarati()) - nomi)}: "
        "sorveglia una forma di nome che il progetto non usa"
    )


def test_la_sentinella_dell_advisory_riconosce_un_sorgente_fuori_posto(
    tmp_path: pathlib.Path,
) -> None:
    # Sentinella: le si fa esaminare un sorgente finto e si pretende che lo
    # segnali. Una guardia mai vista mordere è un'affermazione, non un test.
    finto = tmp_path / "finto.py"
    finto.write_text(
        'db.execute(text("SELECT pg_advisory_xact_lock(1002, 7)"))\n',
        encoding="utf-8",
    )
    assert _chiamate_advisory(ast.parse(finto.read_text(encoding="utf-8"))) == [1]


def test_la_sentinella_dell_advisory_non_segnala_un_sorgente_innocuo(
    tmp_path: pathlib.Path,
) -> None:
    finto = tmp_path / "innocuo.py"
    finto.write_text('db.execute(text("SELECT 1"))\n', encoding="utf-8")
    assert _chiamate_advisory(ast.parse(finto.read_text(encoding="utf-8"))) == []

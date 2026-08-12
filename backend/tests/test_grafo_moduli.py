"""Guardia GS-3 (E2-G6, AD-1): il grafo dello spine è imposto, non raccomandato.

`ARCHITECTURE-SPINE.md` disegna chi può chiamare chi e chiude con «ogni
dipendenza non disegnata è vietata. Nessun modulo dipende in modo sincrono da
`notifiche`». Finora quella riga era solo scritta. L'Epic 2 è il primo Epic con
un grafo non banale, e la Story 2.6 introduce il modulo che l'Epic 3 e l'Epic 5
devono poter riusare: se `notifiche` nascesse legato al calendario, nessun test
funzionale fallirebbe — è la classe delle **assenze**, quella in cui sono
finiti entrambi i P0 dell'Epic 1. Si scoprirebbe fra due Epic, quando riusarlo
costa una riscrittura.

Tre regole, tutte con la loro sentinella:

1. **Nessun modulo importa `models` o `repository` di un altro modulo.** Gli
   strati interni non attraversano i confini: si passa dal `service`, che è
   l'interfaccia che il modulo dichiara. Le due eccezioni storiche sono
   elencate e a loro volta sorvegliate — un'allowlist che può crescere in
   silenzio è il punto in cui le guardie muoiono.
2. **Nessun modulo di dominio importa `notifiche`.** Il collegamento passa da
   eventi e job, e vive nella radice di composizione (`app/cablaggio.py`).
3. **`notifiche` importa solo `core` e `identity`**, che è la sola freccia
   piena che lo spine disegna verso di lui, in sola lettura (AC 4). È anche la
   parte verificabile oggi di AC 11 — «questa fondazione è riusata da Epic 3
   ed Epic 5» è un'affermazione su codice futuro, e ciò che se ne può provare
   adesso è che l'interfaccia non conosce il dominio chiamante.
"""

import ast
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
APP = BACKEND / "app"

# `core` è lo shared kernel: importabile da tutti, non contiene stato di
# dominio. `api` è plumbing HTTP. Nessuno dei due è un modulo di dominio.
NON_DI_DOMINIO = frozenset({"core", "api"})

# Moduli alla RADICE di `app/` (non pacchetti): sono la radice di
# composizione. Possono conoscere più moduli insieme perché è esattamente il
# loro mestiere — `main` monta i router, `worker` registra handler e
# subscriber, `cablaggio` collega `calendario` a `notifiche` senza che nessuno
# dei due importi l'altro, `registro_modelli` scopre le tabelle per Alembic.
RADICE_DI_COMPOSIZIONE = frozenset({"main", "worker", "cablaggio", "registro_modelli"})

# Le frecce piene dello spine più quelle che il codice consegnato ha e il
# diagramma non disegna. La differenza è un finding aperto (vedi la story
# 2.6): `strutture → config_normativa` regge AD-12 (parametri fiscali) e
# `calendario|config_normativa → identity` regge `CurrentHost`, cioè
# l'autenticazione, che attraversa tutto per costruzione. Sono legittime; è il
# diagramma a essere indietro, e finché non lo si allinea l'elenco vive qui.
DIPENDENZE_AMMESSE = {
    "strutture": frozenset({"identity", "config_normativa"}),
    "calendario": frozenset({"identity", "strutture", "config_normativa"}),
    "config_normativa": frozenset({"identity"}),
    "identity": frozenset(),
    "notifiche": frozenset({"identity"}),
}

# Import di `models`/`repository` attraverso un confine di modulo presenti su
# `main` prima della Story 2.6. Sono DEBITO, non precedente: la forma corretta
# è un metodo sul `service` del modulo proprietario. Elencati perché la
# guardia possa nascere verde e mordere su tutto il resto — allargare questo
# insieme richiede di toccare questa riga, che è il punto.
ECCEZIONI_STORICHE = frozenset(
    {
        ("strutture", "app.config_normativa.repository"),
        ("strutture", "app.config_normativa.models"),
    }
)

STRATI_INTERNI = ("models", "repository")


def _moduli_importati(albero: ast.AST) -> set[str]:
    """I moduli `app.*` importati da un sorgente, in forma piena.

    `from app.calendario import service` e `from app.calendario.service import
    X` devono produrre lo stesso nome: sono lo stesso import, e distinguerli
    lascerebbe alla guardia un modo di essere aggirata scrivendo l'altro.
    """
    trovati: set[str] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            trovati.update(
                alias.name for alias in nodo.names if alias.name.startswith("app.")
            )
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level or not nodo.module or not nodo.module.startswith("app"):
                continue
            pezzi = nodo.module.split(".")
            if len(pezzi) >= 3:
                trovati.add(nodo.module)
            elif len(pezzi) == 2:
                trovati.update(f"{nodo.module}.{alias.name}" for alias in nodo.names)
            else:
                # `from app import cablaggio`
                trovati.update(f"app.{alias.name}" for alias in nodo.names)
    return trovati


def _modulo_del_file(percorso: pathlib.Path) -> str:
    """Il pacchetto proprietario di un sorgente; `''` per la radice."""
    relativo = percorso.relative_to(APP)
    return relativo.parts[0] if len(relativo.parts) > 1 else ""


def _sorgenti() -> list[pathlib.Path]:
    return sorted(APP.rglob("*.py"))


def _archi() -> list[tuple[str, str, str]]:
    """`(modulo del file, percorso del file, modulo importato)` per ogni import."""
    archi = []
    for percorso in _sorgenti():
        proprietario = _modulo_del_file(percorso)
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        for importato in _moduli_importati(albero):
            archi.append(
                (proprietario, percorso.relative_to(BACKEND).as_posix(), importato)
            )
    return archi


def _pacchetto_importato(importato: str) -> str:
    pezzi = importato.split(".")
    return pezzi[1] if len(pezzi) > 1 else ""


def test_nessun_modulo_importa_gli_strati_interni_di_un_altro() -> None:
    fuori_norma = []
    for proprietario, file, importato in _archi():
        pacchetto = _pacchetto_importato(importato)
        if pacchetto in (proprietario, "", *NON_DI_DOMINIO):
            continue
        if importato.split(".")[-1] not in STRATI_INTERNI:
            continue
        if (proprietario, importato) in ECCEZIONI_STORICHE:
            continue
        fuori_norma.append(f"{file} → {importato}")
    assert fuori_norma == [], (
        f"strati interni attraversati: {fuori_norma} — un modulo si raggiunge "
        "dal suo `service`, che è l'interfaccia che dichiara (AD-1)"
    )


def test_le_eccezioni_storiche_esistono_ancora_e_non_sono_cresciute() -> None:
    # Un'allowlist che nomina un import che non c'è più smette di essere un
    # debito e diventa una porta aperta per il prossimo.
    presenti = {
        (proprietario, importato)
        for proprietario, _, importato in _archi()
        if importato.split(".")[-1] in STRATI_INTERNI
        and _pacchetto_importato(importato) not in (proprietario, "", *NON_DI_DOMINIO)
    }
    assert presenti == ECCEZIONI_STORICHE, (
        f"l'elenco delle eccezioni non descrive più il codice: {presenti}"
    )


def test_nessun_modulo_di_dominio_importa_notifiche() -> None:
    # «Nessun modulo dipende in modo sincrono da `notifiche`» (spine). Un
    # import da un modulo di dominio è precisamente quella dipendenza, e non
    # farebbe fallire niente: il collegamento funzionerebbe, e il modulo
    # smetterebbe di essere riusabile senza che nessuno se ne accorga.
    fuori_norma = [
        f"{file} → {importato}"
        for proprietario, file, importato in _archi()
        if _pacchetto_importato(importato) == "notifiche"
        and proprietario not in ("", "notifiche")
    ]
    assert fuori_norma == [], (
        f"`notifiche` importato da un modulo di dominio: {fuori_norma} — il "
        "collegamento passa da eventi e job, e vive in app/cablaggio.py"
    )


def test_solo_la_radice_di_composizione_conosce_notifiche() -> None:
    # L'insieme ESATTO dei file che lo importano, non un «al più»: se domani
    # `app/main.py` montasse un router di `notifiche`, questa riga lo dice.
    conoscono = {
        file
        for proprietario, file, importato in _archi()
        if _pacchetto_importato(importato) == "notifiche" and proprietario == ""
    }
    assert conoscono == {"app/cablaggio.py", "app/worker.py"}, (
        f"radice di composizione inattesa: {sorted(conoscono)}"
    )


def test_notifiche_dipende_solo_da_identity() -> None:
    # AC 4, e la parte verificabile oggi di AC 11: l'interfaccia non conosce
    # il dominio chiamante. Un import di `calendario` qui non fallirebbe —
    # tacerebbe — e si scoprirebbe quando l'Epic 3 prova a riusare il modulo.
    fuori_norma = [
        f"{file} → {importato}"
        for proprietario, file, importato in _archi()
        if proprietario == "notifiche"
        and _pacchetto_importato(importato)
        not in ("notifiche", "", *NON_DI_DOMINIO, *DIPENDENZE_AMMESSE["notifiche"])
    ]
    assert fuori_norma == [], (
        f"`notifiche` dipende da un modulo che lo spine non gli concede: "
        f"{fuori_norma} — la sola freccia piena è `notifiche → identity`, in "
        "sola lettura"
    )


def test_ogni_dipendenza_fra_moduli_e_dichiarata() -> None:
    fuori_norma = []
    for proprietario, file, importato in _archi():
        pacchetto = _pacchetto_importato(importato)
        if proprietario in ("", *NON_DI_DOMINIO) or pacchetto in (
            proprietario,
            "",
            *NON_DI_DOMINIO,
        ):
            continue
        if pacchetto not in DIPENDENZE_AMMESSE.get(proprietario, frozenset()):
            fuori_norma.append(f"{file} → {importato}")
    assert fuori_norma == [], (
        f"dipendenze non disegnate: {fuori_norma} — «ogni dipendenza non "
        "disegnata è vietata» (spine)"
    )


def test_la_guardia_vede_i_moduli_veri_del_progetto() -> None:
    # Il legame fra la guardia e la realtà: se il grafo si svuotasse — perché
    # l'estrazione ha smesso di riconoscere una forma di import — tutti i
    # test sopra resterebbero verdi sorvegliando l'insieme vuoto.
    archi = _archi()
    proprietari = {proprietario for proprietario, _, _ in archi}
    assert {"calendario", "notifiche", "identity", "strutture"} <= proprietari
    assert any(
        _pacchetto_importato(importato) == "notifiche" for _, _, importato in archi
    ), "nessun file importa `notifiche`: il cablaggio non è più collegato"
    assert any(
        proprietario == "calendario" and _pacchetto_importato(importato) == "strutture"
        for proprietario, _, importato in archi
    ), "l'estrazione non riconosce più `calendario → strutture`"


@pytest.mark.parametrize(
    ("sorgente", "atteso"),
    [
        ("from app.calendario.repository import X\n", {"app.calendario.repository"}),
        ("from app.calendario import repository\n", {"app.calendario.repository"}),
        ("import app.calendario.models\n", {"app.calendario.models"}),
        ("from app.calendario import service as s\n", {"app.calendario.service"}),
        ("from app import cablaggio\n", {"app.cablaggio"}),
        ("from app.core.db import Base\n", {"app.core.db"}),
        (
            "from app.identity import models, service\n",
            {"app.identity.models", "app.identity.service"},
        ),
    ],
)
def test_la_sentinella_riconosce_ogni_forma_di_import(
    sorgente: str, atteso: set[str]
) -> None:
    # Le due forme `from app.X import strato` e `from app.X.strato import
    # nome` sono lo stesso import: se la guardia ne vedesse una sola,
    # aggirarla sarebbe questione di stile di scrittura.
    assert _moduli_importati(ast.parse(sorgente)) == atteso


@pytest.mark.parametrize(
    "sorgente",
    [
        "import uuid\n",
        "from datetime import date\n",
        "from sqlalchemy.orm import Session\n",
        "apparato = 'app.calendario.models'\n",
    ],
)
def test_la_sentinella_non_segnala_un_sorgente_innocuo(sorgente: str) -> None:
    # Una guardia che segnala tutto non discrimina: in particolare una
    # STRINGA che nomina un modulo non è un import.
    assert _moduli_importati(ast.parse(sorgente)) == set()


def test_la_guardia_riconosce_una_violazione_costruita(
    tmp_path: pathlib.Path,
) -> None:
    # Sentinella sulla regola, non solo sull'estrazione: le si fa esaminare la
    # violazione che questa Story esiste per impedire e si pretende che la
    # veda. Una guardia mai vista mordere è un'affermazione, non un test.
    finto = tmp_path / "finto.py"
    finto.write_text(
        "from app.calendario.repository import ConflittoRepository\n",
        encoding="utf-8",
    )
    importati = _moduli_importati(ast.parse(finto.read_text(encoding="utf-8")))
    assert {
        importato
        for importato in importati
        if importato.split(".")[-1] in STRATI_INTERNI
    } == {"app.calendario.repository"}

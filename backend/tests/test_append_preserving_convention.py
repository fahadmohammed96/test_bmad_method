"""Guardia GS-6 (E2-G7): append-preserving è un invariante di DATO.

Gli AC delle Story 2.1, 2.4 e 2.7 asseriscono ciascuno che *quel* percorso
transiziona invece di cancellare. Nessuno di essi impedisce a un percorso
**futuro** — una rotta di amministrazione, uno script di manutenzione, una FK
dichiarata distrattamente con `ondelete="CASCADE"` — di distruggere
Prenotazioni, Conflitti o `sync_run`.

Un test di percorso dimostra che quel percorso non cancella, non che nessuno
cancelli. La classe di difetti è quella delle **assenze**: un pezzo mancante
non fallisce, tace. Questa guardia non difende il codice di oggi: difende
quello che verrà scritto quando nessuno si ricorderà del perché (AD-4, AD-19,
AD-20).

Due difese indipendenti:

1. sul **modello** — nessuna FK verso una tabella protetta dichiara `ondelete`,
   quindi il database non può cancellare a cascata;
2. sul **sorgente** — nessun modulo di dominio scrive un `delete()` su una
   tabella protetta, e i moduli proprietari non chiamano `.delete()` affatto.
"""

import ast
import importlib
import pathlib

import pytest

from tests.modello import carica_modelli

Base = carica_modelli()

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# Tabelle che devono sopravvivere a tutto: si archivia, mai si distrugge.
# `ospite` è entrata con la Story 2.3 e la sua presenza qui è la forma in cui
# AD-21 diventa strutturale: la retention dell'anagrafica azzera i CAMPI, e
# una `DELETE` della riga sarebbe una quarta cancellazione distruttiva, cioè
# fuori dalla lista esaustiva di AD-20. `conflitto` è entrata con la Story
# 2.5, come la riga sopra prevedeva: un Conflitto non si cancella MAI, nemmeno
# quando decade — `decaduto` è una transizione tracciata, ed è ciò che rende
# misurabile SM-C1. Cancellarlo invece di farlo decadere non romperebbe nulla
# oggi e renderebbe la metrica inutilizzabile domani.
# `test_le_tabelle_protette_esistono` impedisce che la lista contenga nomi
# morti che la svuoterebbero in silenzio.
#
# `regime_lettura` entra con la decisione MYL-68: porta l'evidenza datata che
# l'Host è stato informato della soglia fiscale, e il suo rientro sotto soglia
# è ora una revoca tracciata. È la prima tabella protetta fuori da
# `calendario`, ed è la ragione per cui i modelli protetti sono raggruppati
# per modulo proprietario qui sotto.
TABELLE_PROTETTE = frozenset(
    {"prenotazione", "sync_run", "feed_ical", "ospite", "conflitto", "regime_lettura"}
)

# Modelli protetti per modulo PROPRIETARIO (AD-18): il modulo serve a ritrovare
# il modello, e un raggruppamento per stringa fissa terrebbe insieme cose che
# vivono in file diversi senza dire dove cercarle.
MODELLI_PROTETTI_PER_MODULO = {
    "calendario": frozenset(
        {"Prenotazione", "SyncRun", "FeedIcal", "Ospite", "Conflitto"}
    ),
    "strutture": frozenset({"RegimeLettura"}),
}

MODELLI_PROTETTI = frozenset(
    nome for modelli in MODELLI_PROTETTI_PER_MODULO.values() for nome in modelli
)

# Moduli il cui sorgente non può contenere alcuna cancellazione: sono i
# proprietari unici scrittori delle tabelle protette (AD-18).
#
# `strutture` entra con MYL-68, e non è un contorno: il difetto trovato lì era
# `self._db.delete(lettura)`, cioè una cancellazione di ISTANZA, che il
# controllo per tabella qui sotto non può attribuire a `regime_lettura` — solo
# la regola più stretta sul modulo proprietario la vede. Aggiungere la tabella
# all'elenco senza aggiungere il modulo qui avrebbe lasciato la guardia verde
# proprio sulla forma del difetto che ha motivato la decisione.
MODULI_SENZA_CANCELLAZIONI = ("calendario", "strutture")


def test_le_tabelle_protette_esistono() -> None:
    mancanti = TABELLE_PROTETTE - set(Base.metadata.tables)
    assert mancanti == set(), (
        f"tabelle protette inesistenti: {sorted(mancanti)} — un nome morto "
        "svuoterebbe la guardia senza farla fallire"
    )


def test_nessuna_fk_verso_una_tabella_protetta_cancella_a_cascata() -> None:
    fuori_norma = []
    for tabella in Base.metadata.tables.values():
        for colonna in tabella.columns:
            for fk in colonna.foreign_keys:
                if fk.column.table.name not in TABELLE_PROTETTE:
                    continue
                if fk.ondelete is not None:
                    fuori_norma.append(
                        f"{tabella.name}.{colonna.name} -> "
                        f"{fk.column.table.name} (ondelete={fk.ondelete})"
                    )
    assert fuori_norma == [], (
        f"FK che cancellano dati append-only: {fuori_norma} (AD-4, AD-20)"
    )


def test_i_modelli_protetti_corrispondono_alle_tabelle_protette() -> None:
    # Se un modello venisse rinominato, `MODELLI_PROTETTI` conterrebbe un nome
    # morto e la guardia sul sorgente non troverebbe più nulla da controllare.
    tabelle = set()
    for modulo, modelli in MODELLI_PROTETTI_PER_MODULO.items():
        models = importlib.import_module(f"app.{modulo}.models")
        tabelle |= {
            getattr(models, nome).__tablename__
            for nome in modelli
            if hasattr(models, nome)
        }
    assert tabelle == set(TABELLE_PROTETTE), (
        f"modelli protetti disallineati dalle tabelle protette: {tabelle}"
    )


def _cancellazioni(albero: ast.AST) -> list[tuple[str, int]]:
    """`delete(Modello)` e `<qualcosa>.delete(...)` presenti nel sorgente."""
    trovate: list[tuple[str, int]] = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Call):
            continue
        funzione = nodo.func
        nome = (
            funzione.attr
            if isinstance(funzione, ast.Attribute)
            else funzione.id
            if isinstance(funzione, ast.Name)
            else ""
        )
        if nome != "delete":
            continue
        argomenti = [
            argomento.id for argomento in nodo.args if isinstance(argomento, ast.Name)
        ]
        trovate.append((",".join(argomenti) or "<istanza>", nodo.lineno))
    return trovate


def test_nessun_modulo_cancella_una_tabella_protetta() -> None:
    fuori_norma = []
    for percorso in (BACKEND / "app").rglob("*.py"):
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        for bersaglio, riga in _cancellazioni(albero):
            if set(bersaglio.split(",")) & MODELLI_PROTETTI:
                fuori_norma.append(
                    f"{percorso.relative_to(BACKEND)}:{riga} delete({bersaglio})"
                )
    assert fuori_norma == [], (
        f"cancellazioni su tabelle append-only: {fuori_norma} — "
        "si transiziona lo stato, non si distrugge la riga (AD-4, AD-19)"
    )


def test_il_modulo_proprietario_non_cancella_nulla() -> None:
    # Sui moduli proprietari la regola è più stretta: `session.delete(istanza)`
    # non dice staticamente su quale tabella agisca, quindi in un modulo che
    # possiede tabelle protette non è ammesso affatto.
    fuori_norma = []
    for modulo in MODULI_SENZA_CANCELLAZIONI:
        cartella = BACKEND / "app" / modulo
        assert cartella.is_dir(), f"modulo sorvegliato assente: {modulo}"
        for percorso in cartella.rglob("*.py"):
            albero = ast.parse(percorso.read_text(encoding="utf-8"))
            for bersaglio, riga in _cancellazioni(albero):
                fuori_norma.append(
                    f"{percorso.relative_to(BACKEND)}:{riga} delete({bersaglio})"
                )
    assert fuori_norma == [], (
        f"il modulo proprietario delle tabelle append-only cancella: {fuori_norma}"
    )


def _migrazioni_sospette(cartella: pathlib.Path) -> list[str]:
    """Migrazioni che distruggono dati append-only, nella cartella data.

    Prende la cartella come parametro perche' la sentinella qui sotto la punti
    su una migrazione finta: una guardia si verifica facendole trovare
    qualcosa, non rileggendo il proprio sorgente.
    """
    sospette = []
    for percorso in sorted(cartella.glob("*.py")):
        testo = percorso.read_text(encoding="utf-8")
        for tabella in TABELLE_PROTETTE:
            # ENTRAMBI gli stili di virgolette: autogenerate emette apici
            # singoli, `ruff format` li normalizza a doppi. Una guardia che ne
            # conosce uno solo e' appesa a un formattatore.
            forme = [
                f"drop_table('{tabella}'",
                f'drop_table("{tabella}"',
                f"DELETE FROM {tabella}",
                f"delete_from('{tabella}'",
                f'delete_from("{tabella}"',
            ]
            sospette += [
                f"{percorso.name}: {forma}" for forma in forme if forma in testo
            ]
    return sospette


def test_la_cartella_delle_migrazioni_non_e_vuota() -> None:
    # Senza questo, puntare la guardia su un percorso rinominato la fa passare
    # ispezionando ZERO bersagli. È la stessa classe chiusa per tenancy e per
    # `registro_modelli`: una guardia che non trova nulla da controllare deve
    # fallire, non tacere.
    migrazioni = sorted((BACKEND / "alembic" / "versions").glob("*.py"))
    assert len(migrazioni) >= 8, (
        f"solo {len(migrazioni)} migrazioni trovate: la guardia sta guardando "
        "nel posto sbagliato"
    )


def test_nessuna_migrazione_cancella_una_tabella_protetta() -> None:
    # Le migrazioni sono forward-only (AR-11) e le modifiche distruttive sono
    # vietate salvo AD-20: un `drop_table` o un `DELETE FROM` su una tabella
    # protetta e' la via piu' silenziosa per perdere Prenotazioni.
    sospette = _migrazioni_sospette(BACKEND / "alembic" / "versions")
    assert sospette == [], f"migrazioni distruttive su dati append-only: {sospette}"


@pytest.mark.parametrize(
    "istruzione",
    [
        "op.drop_table('prenotazione')",
        'op.drop_table("prenotazione")',
        "op.execute('DELETE FROM sync_run')",
        "op.delete_from('feed_ical')",
    ],
)
def test_la_guardia_riconosce_una_migrazione_distruttiva(
    tmp_path: pathlib.Path, istruzione: str
) -> None:
    # Sentinella della guardia: le si fa esaminare una migrazione finta e si
    # pretende che la segnali. La versione precedente rileggeva il PROPRIO
    # sorgente e asseriva la presenza di un letterale che stava sulla riga
    # dell'assert stesso — non poteva fallire, cioe' reintroduceva una riga
    # sotto la classe di difetti che questo file esiste per chiudere.
    (tmp_path / "20260101_9999_finta.py").write_text(
        "def upgrade() -> None:\n    " + istruzione + "\n", encoding="utf-8"
    )

    assert _migrazioni_sospette(tmp_path), (
        f"la guardia non riconosce '{istruzione}' come distruttiva"
    )


def test_la_guardia_non_segnala_una_migrazione_innocua(
    tmp_path: pathlib.Path,
) -> None:
    # L'altra metà: una guardia che segnala tutto non discrimina.
    (tmp_path / "20260101_9999_innocua.py").write_text(
        "def upgrade() -> None:\n    op.add_column('prenotazione', colonna)\n",
        encoding="utf-8",
    )

    assert _migrazioni_sospette(tmp_path) == []

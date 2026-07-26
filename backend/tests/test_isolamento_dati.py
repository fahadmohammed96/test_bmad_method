"""Guardia GS-2 (E2-G4): la lista di TRUNCATE non resta indietro.

`TABELLE_DA_SVUOTARE` in `conftest.py` è una stringa scritta a mano. Una
tabella nuova dimenticata non fa fallire nulla: sporca i test fra loro, e il
fallimento compare **altrove**, spesso giorni dopo, come flakiness. L'Epic 2
aggiunge tre tabelle in un colpo solo — è il momento in cui la lista smette di
essere memorizzabile.

L'allowlist dei dati di riferimento è **esplicita e a sua volta sorvegliata**:
le allowlist sono il punto in cui le guardie muoiono in silenzio.
"""

from tests.conftest import (
    TABELLE_DA_SVUOTARE,
    TABELLE_DI_RIFERIMENTO_NON_SVUOTATE,
)
from tests.modello import carica_modelli

Base = carica_modelli()


def _tabelle_nella_lista() -> set[str]:
    return {nome.strip() for nome in TABELLE_DA_SVUOTARE.split(",") if nome.strip()}


def test_ogni_tabella_del_modello_e_nella_lista_di_truncate() -> None:
    dichiarate = set(Base.metadata.tables)
    mancanti = dichiarate - _tabelle_nella_lista() - TABELLE_DI_RIFERIMENTO_NON_SVUOTATE
    assert mancanti == set(), (
        f"tabelle non svuotate fra i test: {sorted(mancanti)} — "
        "aggiungerle a TABELLE_DA_SVUOTARE oppure motivare l'esenzione"
    )


def test_la_lista_non_nomina_tabelle_inesistenti() -> None:
    # Una tabella rinominata lascerebbe nella lista un nome morto, e il
    # TRUNCATE fallirebbe con un errore che non dice quale sia il vero
    # problema.
    fantasmi = _tabelle_nella_lista() - set(Base.metadata.tables)
    assert fantasmi == set(), f"nomi non più esistenti nella lista: {sorted(fantasmi)}"


def test_l_allowlist_dei_dati_di_riferimento_resta_giustificata() -> None:
    # L'esenzione vale perché quelle tabelle sono popolate DALLE MIGRAZIONI e
    # valgono per tutti gli Host. Se una di esse acquisisse `host_id`
    # diventerebbe di un tenant, e svuotarla fra i test tornerebbe dovuto.
    for nome in TABELLE_DI_RIFERIMENTO_NON_SVUOTATE:
        if nome == "alembic_version":
            # Non è nel modello: è la tabella di stato di Alembic.
            assert nome not in Base.metadata.tables
            continue
        assert "host_id" not in Base.metadata.tables[nome].columns, nome


def test_le_tabelle_del_calendario_sono_sorvegliate() -> None:
    # La guardia non deve mai svuotarsi in silenzio: se il modulo
    # `calendario` sparisse dal modello, questo test lo direbbe.
    assert {"feed_ical", "sync_run", "prenotazione"} <= set(Base.metadata.tables)

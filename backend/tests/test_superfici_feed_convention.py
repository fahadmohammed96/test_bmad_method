"""Guardia GS-7 — «dati aggiornati alle HH:MM» su OGNI superficie da Feed.

NFR-2 e UX-DR6 non chiedono che *questa* risposta porti il timestamp
dell'ultimo sync riuscito: chiedono che lo porti **ogni** superficie che
mostra dati derivati da un Feed. Gli AC della Story lo asseriscono per le
superfici che esistono oggi, e non dicono niente su quella che qualcuno
aggiungerà con la griglia del calendario (2.3), con l'inserimento manuale
(2.4) o con i Conflitti (2.5).

È la classe di difetti delle **assenze**: un pezzo mancante non fallisce,
tace. E qui il silenzio ha una forma precisa — una schermata che mostra
prenotazioni vecchie di tre giorni senza dire che sono vecchie di tre giorni.
L'Host non ha modo di accorgersene, perché il difetto è esattamente
l'assenza del segnale che glielo direbbe.

**Come la guardia resta viva.** Ogni schema di risposta del modulo va
classificato in UNA delle due liste. Un modello nuovo che non compare in
nessuna delle due fa fallire `test_ogni_schema_e_classificato`: chi lo
aggiunge deve DECIDERE se è una superficie da Feed, invece di poterla
dimenticare. È la forma richiesta dal criterio di gate 3 — un'allowlist
esplicita e a sua volta sorvegliata.
"""

import inspect

import pytest
from pydantic import BaseModel

from app.calendario import schemas

# Superfici che mostrano dati derivati da un Feed: DEVONO esporre la verità
# temporale. `FeedIcalOutput` è lo stato del Feed stesso;
# `PrenotazioniDelFeedOutput` è l'envelope delle Prenotazioni importate;
# `CalendarioOutput` è la griglia unificata, che aggrega dati di PIÙ Feed —
# ed è la superficie per cui questa guardia è stata scritta un Epic prima
# che esistesse.
SUPERFICI_CON_DATI_DA_FEED = frozenset(
    {"FeedIcalOutput", "PrenotazioniDelFeedOutput", "CalendarioOutput"}
)

# Schemi che NON sono una superficie, con il motivo per cui non lo sono.
# Il motivo è dato: un'esenzione senza motivo è un'esenzione che si allarga.
SUPERFICI_ESENTI = {
    "FeedIcalInput": "input del client, non mostra nulla",
    "PrenotazioneOutput": (
        "elemento dentro `PrenotazioniDelFeedOutput`, che porta il timestamp "
        "per l'intera risposta: ripeterlo su ogni riga direbbe la stessa cosa "
        "N volte e inviterebbe a mostrarlo dove non serve"
    ),
    "VoceCalendarioOutput": (
        "elemento dentro `CalendarioOutput`, che porta il timestamp per "
        "l'intera griglia: la freschezza è una proprietà della vista, non "
        "della singola Prenotazione"
    ),
    "StrutturaDelCalendarioOutput": (
        "etichetta di riga (id + nome della Struttura): non mostra alcun dato "
        "derivato da un Feed"
    ),
    "AzzeramentoInput": "input dell'endpoint interno, non mostra nulla",
    "AzzeramentoOutput": (
        "evidenza di un azzeramento su richiesta (NFR-15): conteggi e "
        "identificatori di ciò che è stato appena CANCELLATO, non dati "
        "mostrati all'Host — la freschezza di un Feed non ha alcun ruolo qui, "
        "e aggiungerla suggerirebbe che questa risposta parli di dati vivi"
    ),
}

# I campi che costituiscono la verità temporale (NFR-2, UX-DR6).
CAMPI_RICHIESTI = ("ultimo_sync_riuscito_il", "stato_sync")


def _schemi() -> dict[str, type[BaseModel]]:
    """Ogni `BaseModel` DEFINITO in `app/calendario/schemas.py`.

    Nessun filtro sul nome: `endswith("Output")` sarebbe cieco a una
    rinomina, ed è lo stesso errore già corretto nella guardia di tenancy.
    """
    return {
        nome: classe
        for nome, classe in inspect.getmembers(schemas, inspect.isclass)
        if issubclass(classe, BaseModel)
        and classe is not BaseModel
        and classe.__module__ == schemas.__name__
    }


def test_la_guardia_trova_qualcosa_da_controllare() -> None:
    # Una guardia che ispeziona zero bersagli non fallisce, tace. Se il modulo
    # venisse rinominato o spostato, questo test lo dice subito.
    assert len(_schemi()) >= 4


def test_ogni_schema_e_classificato() -> None:
    # Il cuore di GS-7: uno schema nuovo NON può restare non classificato.
    # Chi aggiunge la griglia del calendario deve dichiarare se mostra dati
    # da Feed — e se sì, la riga sotto gli chiede il timestamp.
    classificati = SUPERFICI_CON_DATI_DA_FEED | set(SUPERFICI_ESENTI)
    non_classificati = set(_schemi()) - classificati
    assert non_classificati == set(), (
        f"schemi non classificati: {sorted(non_classificati)} — ogni risposta "
        "del modulo `calendario` va dichiarata superficie da Feed (e allora "
        f"espone {CAMPI_RICHIESTI}) oppure esente, con il motivo (NFR-2, UX-DR6)"
    )


def test_nessuna_lista_contiene_nomi_morti() -> None:
    # L'altra metà: un nome morto in una delle due liste la svuoterebbe senza
    # farla fallire. È lo stesso presidio di `TABELLE_PROTETTE` in GS-6.
    esistenti = set(_schemi())
    morti = (SUPERFICI_CON_DATI_DA_FEED | set(SUPERFICI_ESENTI)) - esistenti
    assert morti == set(), f"schemi inesistenti nelle liste: {sorted(morti)}"


def test_le_due_liste_non_si_sovrappongono() -> None:
    # Uno schema insieme sorvegliato ed esente sarebbe solo esente.
    assert SUPERFICI_CON_DATI_DA_FEED & set(SUPERFICI_ESENTI) == set()


@pytest.mark.parametrize("nome", sorted(SUPERFICI_CON_DATI_DA_FEED))
def test_ogni_superficie_espone_la_verita_temporale(nome: str) -> None:
    campi = set(_schemi()[nome].model_fields)
    mancanti = [campo for campo in CAMPI_RICHIESTI if campo not in campi]
    assert mancanti == [], (
        f"{nome} non espone {mancanti}: una superficie che mostra dati da Feed "
        "senza dire quando sono stati aggiornati li dichiara certi (NFR-2)"
    )


def test_il_timestamp_e_OPZIONALE_perche_puo_non_esistere() -> None:
    # Il campo non basta che ci sia: deve poter dire «mai sincronizzato».
    # Un `datetime` non nullable costringerebbe a inventare un orario per il
    # Feed che non ha mai avuto un sync riuscito — che è precisamente il caso
    # in cui la falsa sincronia fa il danno massimo (AC 11).
    for nome in SUPERFICI_CON_DATI_DA_FEED:
        campo = _schemi()[nome].model_fields["ultimo_sync_riuscito_il"]
        assert not campo.is_required() or _ammette_none(campo.annotation), (
            f"{nome}.ultimo_sync_riuscito_il non ammette «non lo so»"
        )


def _ammette_none(annotazione: object) -> bool:
    import types
    import typing

    if annotazione is type(None):
        return True
    if typing.get_origin(annotazione) in (typing.Union, types.UnionType):
        return type(None) in typing.get_args(annotazione)
    return False


def test_la_guardia_riconosce_una_superficie_incompleta() -> None:
    # Sentinella: le si fa esaminare uno schema finto e si pretende che lo
    # segnali. Una guardia che non è mai stata vista mordere è un'asserzione
    # sulla propria correttezza, non un test.
    class SuperficieDimenticata(BaseModel):
        prenotazioni: list[str]

    campi = set(SuperficieDimenticata.model_fields)
    assert [campo for campo in CAMPI_RICHIESTI if campo not in campi] == list(
        CAMPI_RICHIESTI
    )

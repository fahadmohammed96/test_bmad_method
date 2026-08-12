"""AC 8: un Conflitto `rilevato` resta in evidenza finché non è gestito.

È un invariante di **assenza di comportamento**, gemello di AD-8 («nessun
percorso di codice arriva a `completato` da solo»): non c'è una funzione da
verificare, c'è una funzione che non deve esistere. Le assenze non
falliscono, tacciono — e questa tace nel modo peggiore, perché il prodotto
smetterebbe di segnalare una doppia prenotazione che è ancora lì.

Due difese, e la seconda è quella che invecchia meglio:

1. **sul comportamento** — un Conflitto vecchio di mesi è ancora fra quelli
   che aspettano una decisione, e nessuna rilevazione successiva lo spegne;
2. **sul sorgente** — nessun modulo scrive lo stato `gestito`. La transizione
   `rilevato → gestito` avviene SOLO per azione esplicita dell'Host (AD-5,
   FR-6) e arriva con la Story 2.7: finché quella superficie non esiste,
   qualunque scrittura di quel valore è un percorso che chiude un Conflitto
   da solo.

**Nota per chi implementerà la 2.7.** La guardia 2 non va cancellata: va
sostituita con quella che verifica ciò che oggi non è verificabile — che
l'unico scrittore di `gestito` sia il percorso che parte da una richiesta
dell'Host. Toglierla e basta riporterebbe l'invariante a essere una
promessa nel commento.
"""

import ast
import pathlib
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import StatoConflitto
from app.core.date_range import utcnow
from tests.calendario import Contesto, conflitti, crea_manuale

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# Gli stati che un percorso di questa Story può scrivere: l'apertura e la
# transizione di SISTEMA. `gestito` non è dei nostri.
STATI_SCRIVIBILI = frozenset({"RILEVATO", "DECADUTO"})


def _stati_conflitto_scritti(sorgente: str) -> list[tuple[str, int]]:
    """`StatoConflitto.X` usato come VALORE scritto, con la riga.

    **Default-deny, e non un elenco di forme di scrittura.** La prima
    versione cercava `stato=…` fra gli argomenti nominati e le assegnazioni,
    e non vedeva `literal(StatoConflitto.RILEVATO, …)` — cioè non vedeva la
    scrittura che il repository fa davvero. Una guardia che conosce le forme
    che sa immaginare lascia fuori quella che verrà scritta domani, ed era
    già verde su questo file.

    Qui si parte dal contrario: **ogni** uso di `StatoConflitto.X` è una
    scrittura, TRANNE quelli in un confronto — `stato == StatoConflitto.X`,
    `stato != …`, `stato in (…)`. Leggere è il caso enumerabile; scrivere no.

    La distinzione serve: `stato == StatoConflitto.GESTITO` è la lettura che
    impedisce alla rilevazione di riaprire un Conflitto già gestito dall'Host.
    Una guardia che non distingue leggere da scrivere vieterebbe proprio la
    difesa che vuole ottenere.
    """
    albero = ast.parse(sorgente)

    def riferimenti(nodo: ast.AST | None) -> list[ast.Attribute]:
        if nodo is None:
            return []
        return [
            figlio
            for figlio in ast.walk(nodo)
            if isinstance(figlio, ast.Attribute)
            and isinstance(figlio.value, ast.Name)
            and figlio.value.id == "StatoConflitto"
        ]

    letti: set[int] = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Compare):
            for parte in [nodo.left, *nodo.comparators]:
                letti.update(id(riferimento) for riferimento in riferimenti(parte))

    return [
        (riferimento.attr, riferimento.lineno)
        for riferimento in riferimenti(albero)
        if id(riferimento) not in letti
    ]


def test_nessun_modulo_porta_un_conflitto_a_gestito() -> None:
    fuori_norma = []
    for percorso in (BACKEND / "app").rglob("*.py"):
        for stato, riga in _stati_conflitto_scritti(
            percorso.read_text(encoding="utf-8")
        ):
            if stato not in STATI_SCRIVIBILI:
                fuori_norma.append(
                    f"{percorso.relative_to(BACKEND)}:{riga} stato={stato}"
                )
    assert fuori_norma == [], (
        f"un percorso di codice porta un Conflitto a `gestito`: {fuori_norma} — "
        "quella transizione è un'azione ESPLICITA dell'Host (AD-5, FR-6, "
        "Story 2.7), e un percorso che ci arriva da solo chiude un Conflitto "
        "al posto suo"
    )


@pytest.mark.parametrize(
    "chiusura",
    [
        "db.execute(update(Conflitto).values(stato=StatoConflitto.GESTITO))",
        "conflitto.stato = StatoConflitto.GESTITO",
        "db.execute(insert(Conflitto).from_select(colonne, "
        "select(literal(StatoConflitto.GESTITO, tipo))))",
        "aggiorna(conflitto, StatoConflitto.GESTITO)",
    ],
)
def test_la_guardia_riconosce_una_chiusura_automatica(chiusura: str) -> None:
    # Sentinella: le si fanno esaminare quattro forme diverse della stessa
    # chiusura, compresa quella POSIZIONALE che la prima versione di questa
    # guardia non vedeva. Una guardia mai vista mordere è un'asserzione sulla
    # propria correttezza, non un test.
    scritture = _stati_conflitto_scritti(f"def chiudi(db):\n    {chiusura}\n")

    assert [stato for stato, _ in scritture] == ["GESTITO"]


def test_la_guardia_non_segnala_una_lettura() -> None:
    # L'altra metà: leggere `gestito` è ciò che impedisce alla rilevazione di
    # riaprire un Conflitto che l'Host ha già chiuso. Vietarlo insieme alla
    # scrittura toglierebbe la difesa invece di aggiungerne una.
    assert (
        _stati_conflitto_scritti(
            "aperti = select(Conflitto).where(Conflitto.stato == "
            "StatoConflitto.GESTITO)\n"
        )
        == []
    )


def test_la_guardia_trova_qualcosa_da_controllare() -> None:
    # Se il modello venisse rinominato, la guardia ispezionerebbe zero
    # bersagli e tacerebbe. Il repository DEVE scrivere almeno uno stato.
    sorgente = (BACKEND / "app" / "calendario" / "repository.py").read_text(
        encoding="utf-8"
    )

    assert {stato for stato, _ in _stati_conflitto_scritti(sorgente)} == set(
        STATI_SCRIVIBILI
    )


@pytest.mark.parametrize("giorni", [1, 30, 365])
def test_un_conflitto_vecchio_resta_in_evidenza(
    db_session: Session, contesto: Contesto, giorni: int
) -> None:
    # Nessun auto-nascondimento a tempo: un Conflitto che sparisce da sé dopo
    # N giorni è una doppia prenotazione che il prodotto ha smesso di
    # segnalare mentre era ancora lì.
    crea_manuale(
        db_session, contesto, check_in=date(2026, 10, 1), check_out=date(2026, 10, 5)
    )
    crea_manuale(
        db_session, contesto, check_in=date(2026, 10, 4), check_out=date(2026, 10, 8)
    )
    (conflitto,) = conflitti(db_session, contesto)
    conflitto.rilevato_il = utcnow() - timedelta(days=giorni)
    db_session.commit()

    vista = service.conflitti_rilevati(db_session, contesto.host_id)

    assert len(vista.conflitti) == 1
    assert vista.conflitti[0].conflitto.stato is StatoConflitto.RILEVATO


def test_rieseguire_la_rilevazione_non_chiude_niente(
    db_session: Session, contesto: Contesto
) -> None:
    # La rilevazione APRE e basta: il decadimento ha una sola causa (l'uscita
    # da `attiva`) e arriva per evento. È anche ciò che rende vero l'AC 11.
    crea_manuale(
        db_session, contesto, check_in=date(2026, 10, 1), check_out=date(2026, 10, 5)
    )
    crea_manuale(
        db_session, contesto, check_in=date(2026, 10, 4), check_out=date(2026, 10, 8)
    )

    for _ in range(10):
        service.rivaluta_conflitti(db_session, contesto.host_id, contesto.struttura_id)
        db_session.commit()

    (conflitto,) = conflitti(db_session, contesto)
    assert conflitto.stato is StatoConflitto.RILEVATO
    assert conflitto.decaduto_il is None

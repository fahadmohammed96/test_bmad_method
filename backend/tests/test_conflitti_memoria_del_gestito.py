"""F4: la decisione dell'Host sopravvive allo spegnimento dell'avviso.

Il Conflitto ha due modi di chiudersi e uno solo è una decisione: `gestito` è
l'Host che dice «questa sovrapposizione l'ho sistemata io», `decaduto` è il
sistema che constata che la sovrapposizione non c'è più (AD-5). Quando una
delle due Prenotazioni esce da `attiva`, un Conflitto `gestito` decade — ed è
giusto, perché la sovrapposizione è davvero cessata.

**Ciò che non deve cessare con lei è la memoria che l'Host aveva deciso.** La
guardia anti-riapertura di `ConflittoRepository.apri` esiste perché la
rilevazione non scavalchi la finestra di riconciliazione della Story 2.7: se
guarda lo stato corrente, dopo il decadimento non trova più niente da
proteggere, e la prima rilevazione successiva apre un `rilevato` nuovo — senza
finestra e senza collegamento al precedente. Per l'Host: ha risolto una cosa e
gliela si ripropone da capo, subito.

Il percorso di ritorno **esiste ed è quello reale**: la clausola anti-ritorno
dell'upsert copre solo `rimossa_dal_feed`, quindi una `cancellata` che il
portale RITIRA torna `attiva` — la stessa strada che `TestEventoInRitardo` di
`test_conflitti_decadimento.py` percorre per F1. Qui non serve nessuna finestra
di consegna: le due sincronizzazioni sono complete, e il difetto sta dopo.

**Questo file chiude anche F6.** La guardia anti-riapertura non aveva alcun
test, perché nessun test della suite scriveva mai `gestito`: qui `gestito` si
scrive, e la guardia viene esercitata sul ramo che la 2.7 troverà. La scrittura
sta in un helper di allestimento e **non** in `app/` — l'invariante di AC 8
(«nessun percorso di codice porta un Conflitto a `gestito` da solo») resta
imposto da `test_conflitti_niente_auto_chiusura.py`, che ispeziona il sorgente
di produzione.

Questo file **non** implementa la 2.7: nessuna finestra configurabile, nessun
collegamento al Conflitto precedente, nessuna superficie di gestione. Lascia
loro il dato su cui poggiare.
"""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import Conflitto, StatoConflitto, StatoPrenotazione
from app.core.date_range import utcnow
from app.core.outbox import OutboxEvent
from tests.calendario import (
    Contesto,
    client,
    collega,
    conflitti,
    consegna_eventi,
    crea_manuale,
    prenotazioni,
    sincronizza,
    vevent,
)
from tests.calendario import calendario as corpo_ical
from tests.server_feed import RispostaPreparata, ServerFeed

UID = "gestita@example.com"
PERCORSO = "/calendario.ics"

# Il VEVENT del portale copre 1-5 ottobre; la manuale dell'Host 4-8: una notte
# in comune, cioè la sovrapposizione che conta.
DAL = "20261001"
AL = "20261005"
ARRIVO_MANUALE = date(2026, 10, 4)
PARTENZA_MANUALE = date(2026, 10, 8)


def _eventi(db: Session, nome: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_name == nome)
        )
        or 0
    )


def _gestito_dall_host(db: Session, conflitto: Conflitto) -> None:
    """La scrittura che porterà la Story 2.7, simulata qui.

    Scritta a mano e non da un service, perché il percorso che la produce non
    esiste ancora: è l'unico modo di esercitare oggi un ramo che oggi non ha
    chiamanti. Il giorno in cui la 2.7 arriva, questo helper si sostituisce col
    suo service e i test qui sotto restano gli stessi.

    Le due scritture sono UNA cosa sola, e il CHECK
    `ck_conflitto_gestito_ha_istante` lo impone: `gestito` senza il suo istante
    sarebbe una decisione senza il quando, cioè la finestra della 2.7 senza il
    punto da cui si misura.
    """
    conflitto.stato = StatoConflitto.GESTITO
    conflitto.gestito_il = utcnow()
    db.commit()


def _gestito_poi_decaduto_poi_di_nuovo_sovrapposto(
    db: Session, contesto: Contesto, server: ServerFeed
) -> None:
    """L'Host decide, la sovrapposizione cessa, la sovrapposizione ritorna.

    Tre fatti in fila, tutti sulla **stessa coppia** di Prenotazioni: è la
    condizione del difetto, perché una coppia diversa sarebbe un Conflitto
    diverso e la guardia non c'entrerebbe nulla.
    """
    url = server.prepara(
        PERCORSO, RispostaPreparata(corpo=corpo_ical(vevent(UID, dal=DAL, al=AL)))
    )
    feed = collega(db, contesto, url)
    sincronizza(db, feed, client())
    crea_manuale(db, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE)
    (conflitto,) = conflitti(db, contesto)
    assert conflitto.stato is StatoConflitto.RILEVATO

    _gestito_dall_host(db, conflitto)

    # Il portale annulla: la Prenotazione esce da `attiva` e il Conflitto
    # decade — da `gestito`, che è il caso che questo file esiste per coprire.
    server.prepara(
        PERCORSO,
        RispostaPreparata(
            corpo=corpo_ical(vevent(UID, dal=DAL, al=AL, extra="STATUS:CANCELLED\r\n"))
        ),
    )
    sincronizza(db, feed, client())
    consegna_eventi(db)
    (conflitto,) = conflitti(db, contesto)
    assert conflitto.stato is StatoConflitto.DECADUTO, (
        "l'allestimento non riproduce il caso: un Conflitto `gestito` deve "
        "decadere quando la sovrapposizione cessa (AD-5), e il difetto vive "
        "proprio in quel passaggio"
    )

    # Il portale ritira l'annullamento: la Prenotazione torna `attiva`, la
    # coppia torna sovrapposta, e la rilevazione dentro `esegui_sync` riparte.
    server.prepara(
        PERCORSO, RispostaPreparata(corpo=corpo_ical(vevent(UID, dal=DAL, al=AL)))
    )
    sincronizza(db, feed, client())
    tornata = next(riga for riga in prenotazioni(db, feed) if riga.ical_uid == UID)
    assert tornata.stato is StatoPrenotazione.ATTIVA, (
        "l'allestimento non riproduce il caso: la Prenotazione doveva tornare "
        "`attiva` quando il portale ritira l'annullamento"
    )


class TestLaDecisioneDellHostSopravviveAlDecadimento:
    def test_la_rilevazione_non_riapre_una_coppia_gia_gestita_dall_host(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        _gestito_poi_decaduto_poi_di_nuovo_sovrapposto(
            db_session, contesto, server_feed
        )

        righe = conflitti(db_session, contesto)

        assert [riga.stato for riga in righe] == [StatoConflitto.DECADUTO], (
            "la rilevazione ha riaperto una coppia che l'Host aveva già "
            "gestito: la guardia anti-riapertura ha perso la memoria della "
            "decisione quando il Conflitto è decaduto, e la 2.7 troverebbe "
            "una finestra di riconciliazione scavalcata prima di esistere"
        )

    def test_nessun_secondo_evento_di_rilevazione_per_la_stessa_coppia(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # La metà che si vede a valle, e che nessuna correzione futura recupera:
        # `outbox` è append-only. Nella 2.6 un secondo `conflitto.rilevato` è
        # una seconda notifica per un fatto che l'Host ha già chiuso; in SM-C1
        # è rumore su «quanti Conflitti l'Host ha davvero risolto».
        _gestito_poi_decaduto_poi_di_nuovo_sovrapposto(
            db_session, contesto, server_feed
        )

        assert _eventi(db_session, service.EVENTO_CONFLITTO_RILEVATO) == 1


class TestIlDatoCheLaStoria27Trovera:
    """La 2.7 non deve ricostruire niente: il fatto è già sulla riga.

    Questa classe guarda il DATO, non il comportamento sopra. La distinzione
    conta perché la finestra configurabile della 2.7 non si misura sullo stato
    — che nel frattempo è passato a `decaduto` — ma sull'istante in cui l'Host
    ha deciso: senza quello, «riapri dopo N ore dalla decisione» non ha un
    punto da cui contare, e il rimedio sarebbe una migrazione di dati che
    nessuna tabella permette più di ricostruire.
    """

    def test_il_decadimento_non_azzera_l_istante_della_decisione(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        _gestito_poi_decaduto_poi_di_nuovo_sovrapposto(
            db_session, contesto, server_feed
        )

        (conflitto,) = conflitti(db_session, contesto)

        assert conflitto.stato is StatoConflitto.DECADUTO
        assert conflitto.decaduto_il is not None
        assert conflitto.gestito_il is not None, (
            "il Conflitto è decaduto e con lui è sparito l'istante in cui "
            "l'Host aveva deciso: la finestra di riconciliazione della 2.7 "
            "non ha più un punto da cui misurare"
        )
        # E i due istanti restano DISTINTI: `decaduto` e `gestito` sono due
        # transizioni diverse (AD-5), e SM-C1 misura «quanti Conflitti l'Host
        # ha davvero risolto» separandole. Sovrascrivere l'uno con l'altro non
        # romperebbe nulla oggi.
        assert conflitto.gestito_il < conflitto.decaduto_il

    def test_un_gestito_senza_il_suo_istante_non_e_rappresentabile(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Il CHECK, non il commento: quando la 2.7 scriverà `gestito`, il
        # database rifiuterà una decisione senza il suo quando. Senza questo
        # vincolo la colonna sarebbe una convenzione, e una convenzione non
        # sopravvive alla prima `UPDATE` scritta di fretta.
        crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        crea_manuale(
            db_session, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE
        )
        db_session.commit()
        (conflitto,) = conflitti(db_session, contesto)
        conflitto.stato = StatoConflitto.GESTITO

        with pytest.raises(IntegrityError, match="ck_conflitto_gestito_ha_istante"):
            db_session.commit()

        db_session.rollback()

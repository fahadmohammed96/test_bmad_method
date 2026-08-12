"""Il Conflitto che si spegne da solo (AC 6, 7, 11 — MYL-69 opzione A).

**Le uscite dallo stato `attiva` sono tre**, e la Story 2.5 non ne conosce
nessuna: ne ascolta una sola, `prenotazione.cessata` (AD-19, AD-5). Questo
file esercita tutte e tre le strade fino allo stesso esito, perché è
esattamente la promessa che la decisione MYL-69 fa:

| strada | chi la percorre                    | transizione                 |
| :----: | ---------------------------------- | --------------------------- |
|   1    | l'Host cancella una manuale        | `attiva → cancellata`       |
|   2    | l'evento scompare dal feed         | `attiva → rimossa_dal_feed` |
|   3    | il portale la dà `STATUS:CANCELLED`| `attiva → cancellata`       |

La 2 e la 3 sono le più frequenti nella vita reale — le disdette arrivano dai
portali, non dall'Host — ed erano quelle mute: `cessata_il` si scriveva e
nessun evento partiva. Senza di esse l'avviso di sovrapposizione resterebbe
acceso per sempre su una prenotazione che non esiste più, e l'Host vedrebbe
un allarme che non può risolvere in nessun modo.

La consegna è **at-least-once** (AD-10) e la 2.5 è il primo sottoscrittore di
`outbox` del progetto: metà di questo file esiste per l'idempotenza, che è la
proprietà che al secondo giro distingue un handler corretto da uno che
riscrive la storia.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import Conflitto, StatoConflitto, StatoPrenotazione
from app.core.outbox import OutboxEvent, subscribers
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

UID = "sovrapposta@example.com"
PERCORSO = "/calendario.ics"

# Il VEVENT del portale copre 1-5 ottobre; la manuale dell'Host 4-8: una
# notte in comune, cioè la sovrapposizione che conta.
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


def _con_conflitto_da_feed(
    db: Session, contesto: Contesto, server: ServerFeed, *, extra: str = ""
):
    """Un Conflitto fra una Prenotazione da Feed e una manuale."""
    url = server.prepara(
        PERCORSO,
        RispostaPreparata(corpo=corpo_ical(vevent(UID, dal=DAL, al=AL, extra=extra))),
    )
    feed = collega(db, contesto, url)
    sincronizza(db, feed, client())
    crea_manuale(db, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE)
    assert len(conflitti(db, contesto)) == 1
    return feed


class TestLeTreStradeArrivanoAlloStessoEsito:
    def test_strada_1_la_cancellazione_manuale_dell_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prima = crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        crea_manuale(
            db_session,
            contesto,
            check_in=ARRIVO_MANUALE,
            check_out=PARTENZA_MANUALE,
        )
        service.cancella_prenotazione(db_session, contesto.host_id, prima.id)

        consegna_eventi(db_session)

        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.DECADUTO
        assert conflitto.decaduto_il is not None

    def test_strada_2_l_evento_scompare_dal_feed(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        feed = _con_conflitto_da_feed(db_session, contesto, server_feed)
        # Il portale ripubblica il calendario SENZA quell'evento, ma con un
        # altro: un feed vuoto sarebbe un run fallito (`feed_senza_eventi`) e
        # non proverebbe niente.
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent("altra@example.com", dal="20261201", al="20261203")
                )
            ),
        )
        sincronizza(db_session, feed, client())

        consegna_eventi(db_session)

        sparita = next(
            riga for riga in prenotazioni(db_session, feed) if riga.ical_uid == UID
        )
        assert sparita.stato is StatoPrenotazione.RIMOSSA_DAL_FEED
        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.DECADUTO, (
            "l'ospite ha disdetto sul portale e l'avviso è rimasto acceso: è "
            "il caso più frequente nella vita reale (MYL-69, strada 2)"
        )

    def test_strada_3_il_portale_la_da_cancellata(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        feed = _con_conflitto_da_feed(db_session, contesto, server_feed)
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent(UID, dal=DAL, al=AL, extra="STATUS:CANCELLED\r\n")
                )
            ),
        )
        sincronizza(db_session, feed, client())

        consegna_eventi(db_session)

        annullata = next(
            riga for riga in prenotazioni(db_session, feed) if riga.ical_uid == UID
        )
        assert annullata.stato is StatoPrenotazione.CANCELLATA
        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.DECADUTO


class TestLeDueMetaDellaCoppia:
    """F3: la Prenotazione che esce può essere il `min` **o** il `max`.

    La coppia è canonicalizzata per identificatore, e `uuidv7` è monotono nel
    tempo: **la Prenotazione creata per prima è sempre il `min`**. Tutte e tre
    le strade di questo file cancellano la prima creata, quindi la colonna
    `max` non era il lato che esce in nessun test della suite — e riducendo il
    predicato di `decadi_per_prenotazione` alla sola `prenotazione_min_id`
    restavano 142 test verdi.

    Un ordine di creazione che sembra irrilevante fissa quale metà del codice
    viene esercitata. Qui esce la **seconda**, e l'asserzione sul lato è
    esplicita: senza, un cambio di generazione delle chiavi riporterebbe il
    test a esercitare di nuovo il `min` senza che nessuno se ne accorga.
    """

    def test_decade_anche_quando_la_prenotazione_e_il_lato_max(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        seconda = crea_manuale(
            db_session, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE
        )
        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.prenotazione_max_id == seconda.id, (
            "l'allestimento non esercita il lato che deve: la Prenotazione "
            "che sta per uscire non è il `max` della coppia"
        )

        service.cancella_prenotazione(db_session, contesto.host_id, seconda.id)
        consegna_eventi(db_session)

        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.DECADUTO, (
            "la Prenotazione uscita da `attiva` era il `max` della coppia e il "
            "Conflitto è rimasto acceso: metà del predicato non è presidiata"
        )
        assert conflitto.decaduto_il is not None


class TestUnaVoltaSola:
    """L'evento si emette alla TRANSIZIONE, non a ogni sync."""

    def test_un_sync_ripetuto_su_una_gia_cancellata_non_riemette(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il difetto che questo test cerca non dà alcun errore: farebbe
        # `decadere` più volte lo stesso Conflitto e sposterebbe in avanti la
        # decorrenza della retention di un dato personale (AD-21), un sync
        # alla volta.
        feed = _con_conflitto_da_feed(db_session, contesto, server_feed)
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent(UID, dal=DAL, al=AL, extra="STATUS:CANCELLED\r\n")
                )
            ),
        )
        sincronizza(db_session, feed, client())
        assert _eventi(db_session, service.EVENTO_PRENOTAZIONE_CESSATA) == 1

        for _ in range(3):
            sincronizza(db_session, feed, client())

        assert _eventi(db_session, service.EVENTO_PRENOTAZIONE_CESSATA) == 1

    def test_un_sync_ripetuto_su_una_gia_scomparsa_non_riemette(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        feed = _con_conflitto_da_feed(db_session, contesto, server_feed)
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent("altra@example.com", dal="20261201", al="20261203")
                )
            ),
        )
        sincronizza(db_session, feed, client())
        assert _eventi(db_session, service.EVENTO_PRENOTAZIONE_CESSATA) == 1

        for _ in range(3):
            sincronizza(db_session, feed, client())

        assert _eventi(db_session, service.EVENTO_PRENOTAZIONE_CESSATA) == 1

    def test_la_stessa_consegna_ripetuta_non_fa_decadere_due_volte(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # At-least-once (AD-10): l'handler viene rieseguito sullo stesso fatto
        # ogni volta che un altro handler del batch fallisce. Una seconda
        # transizione riscriverebbe `decaduto_il` — cioè la data di un fatto
        # già avvenuto, che è ciò che SM-C1 misura.
        prima = crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        crea_manuale(
            db_session, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE
        )
        service.cancella_prenotazione(db_session, contesto.host_id, prima.id)
        consegna_eventi(db_session)
        (conflitto,) = conflitti(db_session, contesto)
        decaduto_il = conflitto.decaduto_il

        # La riconsegna, chiamando l'handler sul fatto già consumato.
        assert (
            service.decadi_conflitti_della_prenotazione(
                db_session, contesto.host_id, prima.id
            )
            == 0
        )
        db_session.commit()

        db_session.expire_all()
        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.decaduto_il == decaduto_il
        assert _eventi(db_session, service.EVENTO_CONFLITTO_DECADUTO) == 1


class TestEventoInRitardo:
    """F1: un fatto vero quando è stato scritto, e falso quando lo si consuma.

    Non è un problema di idempotenza — quella regge, ed è provata sopra. È
    **staleness**: la consegna è asincrona (AD-10), e fra la scrittura
    dell'evento e la sua consegna lo stato può essere tornato indietro. Il
    percorso di ritorno esiste ed è reale: nell'upsert la clausola che
    protegge lo stato copre solo `rimossa_dal_feed`, quindi una `cancellata`
    che il portale **ritira** torna `attiva` (test design §4.2-2 riguarda il
    ritorno da `rimossa_dal_feed`, non questo).

    L'effetto è l'AC 11 dal lato opposto: un Conflitto che si spegne da solo
    su una doppia prenotazione ancora in piedi. Si risana alla rilevazione
    successiva, ma dentro quella finestra l'Host vede pulito — e a valle
    restano un `conflitto.decaduto` e un `conflitto.rilevato` di troppo, che
    nella 2.6 sono una seconda notifica per lo stesso fatto e in SM-C1 sono
    rumore.
    """

    def _prenotazione_che_torna(
        self, db: Session, contesto: Contesto, server: ServerFeed
    ):
        """Il portale annulla e poi ritira l'annullamento, senza consegne."""
        feed = _con_conflitto_da_feed(db, contesto, server)
        server.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent(UID, dal=DAL, al=AL, extra="STATUS:CANCELLED\r\n")
                )
            ),
        )
        sincronizza(db, feed, client())
        # L'evento è scritto ma NON consegnato: è la finestra in cui vive il
        # difetto, ed è la finestra reale — il worker consegna al tick
        # successivo, non nello stesso istante.
        assert _eventi(db, service.EVENTO_PRENOTAZIONE_CESSATA) == 1

        server.prepara(
            PERCORSO,
            RispostaPreparata(corpo=corpo_ical(vevent(UID, dal=DAL, al=AL))),
        )
        sincronizza(db, feed, client())
        tornata = next(riga for riga in prenotazioni(db, feed) if riga.ical_uid == UID)
        assert tornata.stato is StatoPrenotazione.ATTIVA, (
            "l'allestimento non riproduce il caso: la Prenotazione doveva "
            "tornare `attiva` quando il portale ritira l'annullamento"
        )
        return feed

    def test_un_evento_in_ritardo_non_spegne_un_conflitto_ancora_vivo(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        self._prenotazione_che_torna(db_session, contesto, server_feed)

        consegna_eventi(db_session)

        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.RILEVATO, (
            "un evento consegnato in ritardo ha spento un Conflitto fra due "
            "Prenotazioni ancora `attiva` e ancora sovrapposte "
            f"(stato: {conflitto.stato})"
        )
        assert conflitto.decaduto_il is None

    def test_un_evento_in_ritardo_non_produce_eventi_di_conflitto(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # La metà che si vede a valle: il decadimento sbagliato si risana alla
        # rilevazione successiva, ma `outbox` è append-only e i due eventi di
        # troppo restano — una seconda notifica nella 2.6, rumore in SM-C1.
        self._prenotazione_che_torna(db_session, contesto, server_feed)

        consegna_eventi(db_session)

        assert _eventi(db_session, service.EVENTO_CONFLITTO_DECADUTO) == 0
        assert _eventi(db_session, service.EVENTO_CONFLITTO_RILEVATO) == 1


class TestTracciaturaEmisura:
    """AC 6, 7: `decaduto` è tracciato, distinto da `gestito`, mai cancellato."""

    def test_il_conflitto_decaduto_resta_nello_storico(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-20, GS-6: un Conflitto non si cancella MAI, nemmeno quando
        # decade. Cancellarlo non romperebbe nulla oggi e renderebbe
        # inutilizzabile SM-C1 domani.
        prima = crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        crea_manuale(
            db_session, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE
        )
        service.cancella_prenotazione(db_session, contesto.host_id, prima.id)
        consegna_eventi(db_session)

        assert db_session.scalar(select(func.count()).select_from(Conflitto)) == 1
        # E non è più fra quelli che aspettano una decisione dell'Host.
        assert service.conflitti_rilevati(db_session, contesto.host_id).conflitti == []

    def test_il_decadimento_e_interrogabile_dagli_eventi_di_dominio(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-16: le metriche si misurano dagli eventi di dominio, senza
        # strumentazione separata. Se `decaduto` non fosse distinguibile ora,
        # lo si scoprirebbe nell'Epic 3, quando SM-C1 serve.
        prima = crea_manuale(
            db_session,
            contesto,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 5),
        )
        crea_manuale(
            db_session, contesto, check_in=ARRIVO_MANUALE, check_out=PARTENZA_MANUALE
        )
        service.cancella_prenotazione(db_session, contesto.host_id, prima.id)
        consegna_eventi(db_session)

        assert _eventi(db_session, service.EVENTO_CONFLITTO_RILEVATO) == 1
        assert _eventi(db_session, service.EVENTO_CONFLITTO_DECADUTO) == 1
        decaduto = db_session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.event_name == service.EVENTO_CONFLITTO_DECADUTO
            )
        ).one()
        # Soli identificatori: `outbox` è append-only e sopravvive alla
        # retention di AD-21 (AD-16, AD-17, NFR-11).
        assert set(decaduto.payload) == {"conflitto_id", "host_id", "struttura_id"}


class TestImportFallito:
    """AC 11: un errore di TRASPORTO non produce falsi `decaduto`."""

    def test_un_import_fallito_non_spegne_un_conflitto(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # È la catena che trasforma un errore di rete in una doppia
        # prenotazione non segnalata: attraversa due moduli, quindi nessun
        # livello sotto la vede. E il fallimento sarebbe SILENZIOSO — un run
        # in errore che spegne un avviso non dice mai di averlo spento.
        feed = _con_conflitto_da_feed(db_session, contesto, server_feed)
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=500))

        run = sincronizza(db_session, feed, client())
        consegna_eventi(db_session)

        assert run.esito.value == "fallito"
        assert _eventi(db_session, service.EVENTO_PRENOTAZIONE_CESSATA) == 0
        (conflitto,) = conflitti(db_session, contesto)
        assert conflitto.stato is StatoConflitto.RILEVATO


def test_l_ENTRYPOINT_del_worker_registra_il_consumatore(
    db_session: Session, contesto: Contesto
) -> None:
    """La registrazione è un'assenza, e le assenze tacciono.

    Se `app/worker.py` smettesse di importare `app.calendario.sottoscrizioni`,
    nessun test funzionale fallirebbe: gli eventi continuerebbero a essere
    scritti e marcati consegnati, e i Conflitti resterebbero accesi per sempre
    su Prenotazioni che non esistono più. Qui si guarda il registro di
    PRODUZIONE dopo l'import dell'entrypoint, che è la catena reale.
    """
    import app.worker  # noqa: F401 — import con effetto di registrazione

    registrati = subscribers.handlers_for(service.EVENTO_PRENOTAZIONE_CESSATA)

    assert len(registrati) == 1, (
        "il consumatore di `prenotazione.cessata` non è registrato nel "
        "registro di produzione: la consegna girerebbe a vuoto in silenzio"
    )

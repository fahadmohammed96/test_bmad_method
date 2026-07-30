"""Story 2.4 — Inserimento manuale di Prenotazioni.

Copertura secondo `docs/qa/test-design-epic-2.md` §3, Story 2.4. La colonna
«livello» del test design è rispettata: qui stanno gli **I** (service e API su
PostgreSQL reale) e gli **U** che appartengono a questa Story; l'unico **S** è
GS-6, che vive già in `test_append_preserving_convention.py` e si estende da
sé alla nuova superficie.

**AC 2 — «una manuale che si sovrappone a una da Feed genera un Conflitto» —
NON è coperto qui, ed è dichiarato invece che taciuto.** La rilevazione dei
Conflitti è la Story 2.5 e su `main` non esiste alcuna entità `conflitto`:
questa Story rende la Prenotazione manuale **indistinguibile da una da Feed
agli occhi della rilevazione** — stato `attiva`, stessa tabella, stesso
percorso di lettura — e ciò che si può osservare oggi è esattamente quella
precondizione (`TestPartecipaAllaRilevazione`). Il «genera un Conflitto» si
realizza quando atterra la 2.5, senza riaprire questa Story.

Nessun dato reale di Ospiti (NFR-16): i nomi sono inventati, gli indirizzi
sono `example.com`.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import (
    CanaleFeed,
    Ospite,
    Prenotazione,
    StatoPrenotazione,
)
from app.calendario.retention import filtro_scadute, limite_retention
from app.core.date_range import DateRange, EmptyDateRangeError, utcnow
from app.core.events import catalog
from app.core.outbox import OutboxEvent
from app.strutture import service as strutture_service
from tests.calendario import (
    Contesto,
    archivia,
    crea_contesto,
    crea_manuale,
    crea_struttura,
)

PROBLEM = "application/problem+json"

EVENTO_CESSATA = "prenotazione.cessata"

DAL = date(2026, 9, 10)
AL = date(2026, 9, 14)


def _eventi(db: Session, nome: str) -> list[OutboxEvent]:
    return list(db.scalars(select(OutboxEvent).where(OutboxEvent.event_name == nome)))


def _prenotazioni(db: Session, contesto: Contesto) -> list[Prenotazione]:
    return list(
        db.scalars(select(Prenotazione).where(Prenotazione.host_id == contesto.host_id))
    )


def _ospiti(db: Session, prenotazione: Prenotazione) -> list[Ospite]:
    return service.ospiti_della_prenotazione(db, prenotazione.host_id, prenotazione.id)


# ----------------------------------------------------------------- AC 1, 9


class TestCreazione:
    """AC 1: creata `attiva`. AC 9: il blocco date senza Ospite è ammesso."""

    def test_una_manuale_nasce_attiva_e_senza_feed(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)

        assert prenotazione.stato is StatoPrenotazione.ATTIVA
        # Il Canale del Glossario per l'inserimento manuale (PRD §4): non
        # `altro`, che è un TERZO portale — confonderli renderebbe
        # indistinguibili in griglia ciò che l'Host ha scritto e ciò che è
        # arrivato da fuori, cioè l'opposto di FR-4.
        assert prenotazione.canale is CanaleFeed.MANUALE
        assert prenotazione.feed_id is None
        assert prenotazione.ical_uid is None
        # `cessata_il` è la decorrenza della retention (AD-21): una
        # Prenotazione attiva non ha una data di cessazione, e lasciarne una
        # farebbe scadere subito l'anagrafica di un soggiorno futuro.
        assert prenotazione.cessata_il is None

    def test_il_blocco_date_si_salva_completamente_senza_ospite(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AC 9: è il caso d'uso più frequente dell'inserimento manuale, e ogni
        # percorso che assume l'anagrafica salta proprio qui.
        prenotazione = crea_manuale(
            db_session, contesto, check_in=DAL, check_out=AL, ospite=None
        )

        assert prenotazione.stato is StatoPrenotazione.ATTIVA
        assert _ospiti(db_session, prenotazione) == []

    def test_una_manuale_di_una_notte_e_valida(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=DAL + timedelta(days=1),
        )

        assert prenotazione.soggiorno.nights == 1

    def test_il_sommario_resta_il_testo_che_l_host_ha_scritto(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # `sommario` è testo OPACO (NFR-11, `[DECISIONE MYL-40]`): non diventa
        # un nome di Ospite passando di qui, e nessuna anagrafica nasce da esso.
        prenotazione = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            sommario="Blocco per manutenzione",
        )

        assert prenotazione.sommario == "Blocco per manutenzione"
        assert _ospiti(db_session, prenotazione) == []


# -------------------------------------------------------------------- AC 7


class TestTenancy:
    """AC 7: si scrive solo su Strutture del proprio Host (AD-2, NFR-14)."""

    def test_non_si_crea_su_una_struttura_di_un_altro_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        altro = crea_contesto(db_session, email="host.b@example.com", nome="Altrui")

        with pytest.raises(strutture_service.StrutturaNonTrovataError):
            crea_manuale(
                db_session,
                contesto,
                struttura_id=altro.struttura_id,
                check_in=DAL,
                check_out=AL,
            )

        # Nessuna riga scritta a metà: il perimetro si verifica PRIMA della
        # scrittura, non dopo.
        assert _prenotazioni(db_session, contesto) == []

    def test_non_si_cancella_la_prenotazione_di_un_altro_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        altro = crea_contesto(db_session, email="host.c@example.com", nome="Altrui")
        altrui = crea_manuale(db_session, altro, check_in=DAL, check_out=AL)

        with pytest.raises(service.PrenotazioneNonTrovataError):
            service.cancella_prenotazione(db_session, contesto.host_id, altrui.id)

        db_session.expire_all()
        assert altrui.stato is StatoPrenotazione.ATTIVA


# -------------------------------------------------------------------- AC 8


class TestStrutturaArchiviata:
    """AC 8: una Struttura archiviata non accetta nuove Prenotazioni (AD-20)."""

    def test_una_struttura_archiviata_rifiuta_una_manuale(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        archivia(db_session, contesto)

        with pytest.raises(strutture_service.StrutturaArchiviataError):
            crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)

        assert _prenotazioni(db_session, contesto) == []

    def test_una_struttura_archiviata_rifiuta_un_feed_nuovo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La metà «i suoi Feed smettono di sincronizzare» che questa Story può
        # chiudere per costruzione: un Feed che non si collega non sincronizza
        # mai. Sui Feed GIÀ collegati la questione resta aperta ed è dichiarata
        # nella nota di consegna — fermarli congelerebbe «dati aggiornati alle
        # HH:MM» dell'INTERO calendario, perché la freschezza aggregata è il
        # minimo fra i Feed dell'Host (NFR-2).
        archivia(db_session, contesto)

        with pytest.raises(strutture_service.StrutturaArchiviataError):
            service.collega_feed(
                db_session,
                contesto.host_id,
                service.DatiFeed(
                    struttura_id=contesto.struttura_id,
                    url="https://feed.example.com/archiviata.ics",
                    canale=CanaleFeed.AIRBNB,
                ),
            )


# -------------------------------------------------------------------- AC 6


class TestConfineDellIntervallo:
    """AC 6: `[check_in, check_out)` provato AL CONFINE, non nel mezzo.

    L'esaustività sulla semantica dell'intervallo semiaperto vive già in
    `tests/test_date_range.py::TestOverlapSemiOpen` e non si duplica: qui si
    pinna che il percorso manuale **deleghi a quella semantica** invece di
    avere una propria idea di «date valide», e che il caso normale di un
    affitto breve — il turnover dello stesso giorno — non sia una
    sovrapposizione.
    """

    @pytest.mark.parametrize(
        ("check_in", "check_out"),
        [
            (DAL, DAL),  # soggiorno di zero notti
            (AL, DAL),  # date invertite
        ],
    )
    def test_un_intervallo_vuoto_e_rifiutato(
        self,
        db_session: Session,
        contesto: Contesto,
        check_in: date,
        check_out: date,
    ) -> None:
        with pytest.raises(EmptyDateRangeError):
            crea_manuale(db_session, contesto, check_in=check_in, check_out=check_out)

        assert _prenotazioni(db_session, contesto) == []

    def test_il_turnover_dello_stesso_giorno_non_e_una_sovrapposizione(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        uscita = crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)
        ingresso = crea_manuale(
            db_session, contesto, check_in=AL, check_out=AL + timedelta(days=2)
        )

        assert not uscita.soggiorno.overlaps(ingresso.soggiorno)
        assert len(_prenotazioni(db_session, contesto)) == 2


# -------------------------------------------------------------- AC 1 e AC 2


class TestPartecipaAllaRilevazione:
    """AC 1 («partecipa») e la precondizione di AC 2, che è tutto l'osservabile.

    La rilevazione è la Story 2.5 e non esiste: quello che questa Story deve
    garantire è che una manuale arrivi alla rilevazione **indistinguibile** da
    una da Feed — nell'insieme delle `attiva` della Struttura, con un
    intervallo che si interseca. Se questo non fosse vero, la 2.5 nascerebbe
    cieca alle manuali e nessun test della 2.5 se ne accorgerebbe.
    """

    def _attive(self, db: Session, contesto: Contesto) -> list[Prenotazione]:
        """Le `attiva` della Struttura, lette dal percorso di produzione.

        Si passa da `service.calendario`, che è la lettura che esiste oggi: un
        metodo di service aggiunto solo per far girare un test sarebbe codice
        di produzione senza chiamanti, e la 2.5 lo scriverà con i suoi AC.
        """
        vista = service.calendario(
            db,
            contesto.host_id,
            da=date(2026, 9, 1),
            a=date(2026, 9, 30),
            struttura_id=contesto.struttura_id,
        )
        return [
            voce.prenotazione
            for voce in vista.voci
            if voce.prenotazione.stato is StatoPrenotazione.ATTIVA
        ]

    def test_una_manuale_e_una_da_feed_sovrapposte_stanno_nello_stesso_insieme(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        from tests.calendario import crea_prenotazione

        da_feed = crea_prenotazione(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            canale=CanaleFeed.AIRBNB,
        )
        manuale = crea_manuale(
            db_session,
            contesto,
            check_in=DAL + timedelta(days=2),
            check_out=AL + timedelta(days=2),
        )
        db_session.commit()

        attive = self._attive(db_session, contesto)

        assert {riga.id for riga in attive} == {da_feed.id, manuale.id}
        assert manuale.soggiorno.overlaps(da_feed.soggiorno)

    def test_una_manuale_cancellata_esce_dall_insieme_delle_attive(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-19: solo `attiva` concorre ai Conflitti. È la metà che fa
        # `decadere` un Conflitto nella 2.5, e dipende da questo stato.
        manuale = crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)
        service.cancella_prenotazione(db_session, contesto.host_id, manuale.id)

        assert self._attive(db_session, contesto) == []
        # E resta visibile con la sua etichetta: «archiviare, mai distruggere»
        # agli occhi dell'Host (AD-20, test design §4.2-12).
        assert len(_prenotazioni(db_session, contesto)) == 1


# -------------------------------------------------------------------- AC 5


class TestVincoloUniqueConNull:
    """AC 5: il UNIQUE `(feed_id, ical_uid)` non morde sulle manuali.

    È una proprietà del VINCOLO, non del codice: in Postgres i `NULL` sono
    distinti fra loro dentro un indice UNIQUE, quindi N manuali convivono. Va
    asserito e non assunto — un giorno qualcuno potrebbe aggiungere
    `NULLS NOT DISTINCT`, e collasserebbe tutte le manuali di un Host in una
    riga sola senza che nessun test funzionale lo veda.
    """

    def test_molte_manuali_convivono_senza_collidere(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        for scarto in range(5):
            crea_manuale(
                db_session,
                contesto,
                check_in=DAL + timedelta(days=scarto * 3),
                check_out=DAL + timedelta(days=scarto * 3 + 2),
            )

        assert len(_prenotazioni(db_session, contesto)) == 5

    def test_feed_e_uid_esistono_insieme_o_non_esistono(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Una riga con `feed_id` e `ical_uid` a `NULL` è una manuale; con
        # entrambi valorizzati è una riga da Feed. La forma MISTA — un
        # `feed_id` senza uid — sfuggirebbe al UNIQUE (i NULL sono distinti) e
        # produrrebbe duplicati silenziosi dallo stesso Feed: il CHECK la
        # rende irrappresentabile.
        from sqlalchemy.exc import IntegrityError

        feed = service.collega_feed(
            db_session,
            contesto.host_id,
            service.DatiFeed(
                struttura_id=contesto.struttura_id,
                url="https://feed.example.com/mista.ics",
                canale=CanaleFeed.AIRBNB,
            ),
        )
        db_session.add(
            Prenotazione(
                host_id=contesto.host_id,
                struttura_id=contesto.struttura_id,
                feed_id=feed.id,
                ical_uid=None,
                canale=CanaleFeed.AIRBNB,
                check_in=DAL,
                check_out=AL,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


# ------------------------------------------------------- Ospite facoltativo


class TestOspiteFacoltativoDavvero:
    """L'Host **può** — non deve — indicare l'Ospite (NFR-11, AD-21)."""

    def test_un_ospite_indicato_si_scrive_come_principale(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            ospite=service.DatiOspite(
                nome="Ospite Inventato", email="ospite.inventato@example.com"
            ),
        )

        ospiti = _ospiti(db_session, prenotazione)
        assert len(ospiti) == 1
        # `principale` è un'IDENTITÀ, non un ordine: l'Host l'ha indicato, e la
        # griglia mostra quello. Senza il flag, `_principale` sceglie l'unico
        # noto e il comportamento sarebbe identico oggi e diverso domani, al
        # primo secondo Ospite.
        assert ospiti[0].principale is True
        assert ospiti[0].nome == "Ospite Inventato"
        assert ospiti[0].telefono is None

    def test_un_ospite_con_il_solo_telefono_e_un_ospite(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Minimizzazione (AD-21 §2): si salva SOLO ciò che l'Host dà. «C'è
        # qualcuno e ho il suo numero» è un'informazione, non un errore.
        prenotazione = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            ospite=service.DatiOspite(telefono="+39 000 0000000"),
        )

        ospiti = _ospiti(db_session, prenotazione)
        assert len(ospiti) == 1
        assert ospiti[0].nome is None
        assert ospiti[0].email is None

    def test_un_ospite_senza_alcun_campo_non_e_un_ospite(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Una riga `ospite` con tre `NULL` sarebbe indistinguibile da
        # un'anagrafica azzerata dalla retention (AD-21): l'evidenza
        # `anonimizzato_il` esiste proprio per distinguerle, e scrivere righe
        # vuote la renderebbe ambigua. «Nessun contatto» si rappresenta con
        # nessuna riga.
        prenotazione = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            ospite=service.DatiOspite(),
        )

        assert _ospiti(db_session, prenotazione) == []


# ----------------------------------------------------------------- AC 3, 4


class TestCancellazione:
    """AC 3: si porta a `cancellata`, non si cancella. AC 4: evento a catalogo."""

    def test_la_cancellazione_e_una_transizione_con_evento(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        manuale = crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)

        cancellata = service.cancella_prenotazione(
            db_session, contesto.host_id, manuale.id
        )

        assert cancellata.stato is StatoPrenotazione.CANCELLATA
        # La riga esiste ancora: «archiviare, mai distruggere» (AD-20). Che
        # nessun percorso possa cancellarla è l'assenza che GS-6 impone su
        # tutta la superficie del codice.
        assert len(_prenotazioni(db_session, contesto)) == 1
        eventi = _eventi(db_session, EVENTO_CESSATA)
        assert len(eventi) == 1
        assert eventi[0].payload == {
            "prenotazione_id": str(manuale.id),
            "host_id": str(contesto.host_id),
            "struttura_id": str(contesto.struttura_id),
        }

    def test_l_uscita_da_attiva_scrive_la_decorrenza_della_retention(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-21: la retention dell'anagrafica decorre dal `check_out` **o
        # dall'uscita da `attiva` se precedente**. Senza `cessata_il` la metà
        # «se precedente» resterebbe scritta e non applicata.
        prima = utcnow()
        manuale = crea_manuale(
            db_session,
            contesto,
            check_in=date(2027, 6, 1),
            check_out=date(2027, 6, 8),
        )

        cancellata = service.cancella_prenotazione(
            db_session, contesto.host_id, manuale.id
        )

        assert cancellata.cessata_il is not None
        assert cancellata.cessata_il >= prima

    def test_cancellare_due_volte_e_idempotente_e_non_rinotifica(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Il doppio submit è il caso reale: l'Host clicca due volte. Una
        # seconda transizione silenziosa sposterebbe `cessata_il` in avanti —
        # cioè rimanderebbe la scadenza di un dato personale — e un secondo
        # `prenotazione.cessata` farebbe `decadere` due volte lo stesso
        # Conflitto nella 2.5.
        manuale = crea_manuale(db_session, contesto, check_in=DAL, check_out=AL)
        prima = service.cancella_prenotazione(db_session, contesto.host_id, manuale.id)
        decorrenza = prima.cessata_il

        seconda = service.cancella_prenotazione(
            db_session, contesto.host_id, manuale.id
        )

        assert seconda.stato is StatoPrenotazione.CANCELLATA
        assert seconda.cessata_il == decorrenza
        assert len(_eventi(db_session, EVENTO_CESSATA)) == 1

    def test_una_prenotazione_da_feed_non_si_cancella_a_mano(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Lo stato di una Prenotazione da Feed lo decide il portale (AD-4): il
        # sistema non scrive mai verso le OTA, quindi «cancellata qui» e
        # «cancellata là» divergerebbero al primo sync, e il sync
        # riporterebbe indietro lo stato senza dire niente.
        from tests.calendario import crea_prenotazione

        feed = service.collega_feed(
            db_session,
            contesto.host_id,
            service.DatiFeed(
                struttura_id=contesto.struttura_id,
                url="https://feed.example.com/dal-portale.ics",
                canale=CanaleFeed.AIRBNB,
            ),
        )
        da_feed = crea_prenotazione(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            canale=CanaleFeed.AIRBNB,
            feed_id=feed.id,
            ical_uid="uid-1@example.com",
        )
        db_session.commit()

        with pytest.raises(service.PrenotazioneNonManualeError):
            service.cancella_prenotazione(db_session, contesto.host_id, da_feed.id)

        db_session.expire_all()
        assert da_feed.stato is StatoPrenotazione.ATTIVA
        assert _eventi(db_session, EVENTO_CESSATA) == []

    def test_una_prenotazione_inesistente_non_si_cancella(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        import uuid

        with pytest.raises(service.PrenotazioneNonTrovataError):
            service.cancella_prenotazione(db_session, contesto.host_id, uuid.uuid4())


class TestEventoACatalogo:
    """AC 4: `prenotazione.cessata` è a catalogo, con soli identificatori."""

    def test_il_tipo_e_a_catalogo(self) -> None:
        assert EVENTO_CESSATA in catalog.event_names()

    def test_il_payload_non_ha_posto_per_un_dato_personale(self) -> None:
        # Il `Catalog` valida a runtime: lo schema è chiuso per uguaglianza di
        # chiavi, quindi un nome di Ospite aggiunto al payload non passa (AD-17,
        # NFR-11). Costa una riga e chiude una fuga che nessun test funzionale
        # vedrebbe.
        tipo = catalog.event(EVENTO_CESSATA)
        assert tipo.payload_keys == frozenset(
            {"prenotazione_id", "host_id", "struttura_id"}
        )

        from app.core.events import PayloadValidationError

        with pytest.raises(PayloadValidationError):
            catalog.validate_event_payload(
                EVENTO_CESSATA,
                {
                    "prenotazione_id": "x",
                    "host_id": "y",
                    "struttura_id": "z",
                    "ospite": "Ospite Inventato",
                },
            )


# -------------------------------------------------- retention (AD-21, AD-19)


class TestLaRetentionRaggiungeAncheLeManuali:
    """La verifica che l'issue chiede: nessun percorso nuovo aggira AD-21.

    Non serve codice nuovo — `filtro_scadute` è già la regola. Serve che una
    manuale **cancellata** entri in quel percorso come le altre, invece di
    restarne fuori perché nata da un ingresso diverso.
    """

    def test_una_manuale_cancellata_e_selezionata_dalla_retention(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Soggiorno FUTURO, quindi il `check_out` non ha ancora fatto decorrere
        # nulla: se questa riga viene selezionata è per l'uscita da `attiva`,
        # cioè per la metà «se precedente» di AD-21.
        manuale = crea_manuale(
            db_session,
            contesto,
            check_in=date(2099, 1, 10),
            check_out=date(2099, 1, 17),
            ospite=service.DatiOspite(nome="Ospite Inventato"),
        )
        service.cancella_prenotazione(db_session, contesto.host_id, manuale.id)

        # Il limite si sposta in avanti invece di attendere il periodo: la
        # regola è pura e prende `adesso` come argomento.
        limite = limite_retention(
            adesso=utcnow() + timedelta(days=400), periodo=timedelta(days=90)
        )
        scadute = list(
            db_session.scalars(select(Prenotazione).where(filtro_scadute(limite)))
        )

        assert [riga.id for riga in scadute] == [manuale.id]

    def test_una_manuale_attiva_e_futura_NON_e_selezionata(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # L'altra metà: senza questa il test sopra accetterebbe anche un
        # filtro che seleziona tutto.
        crea_manuale(
            db_session,
            contesto,
            check_in=date(2099, 1, 10),
            check_out=date(2099, 1, 17),
        )

        limite = limite_retention(adesso=utcnow(), periodo=timedelta(days=90))
        scadute = list(
            db_session.scalars(select(Prenotazione).where(filtro_scadute(limite)))
        )

        assert scadute == []


# ------------------------------------------------------------------- API (I)


DATI_STRUTTURA = {
    "nome": "Appartamento di prova",
    "comune": "Bologna",
    "regione": "Emilia-Romagna",
}


def _accedi(client: TestClient, email: str = "host.di.prova@example.com") -> None:
    client.post(
        "/api/v1/auth/registrazione",
        json={"email": email, "password": "una-password-lunga"},
    )


def _struttura(client: TestClient, nome: str = DATI_STRUTTURA["nome"]) -> str:
    return client.post(
        "/api/v1/strutture", json={**DATI_STRUTTURA, "nome": nome}
    ).json()["id"]


def _crea(client: TestClient, struttura_id: str, **extra):
    return client.post(
        "/api/v1/calendario/prenotazioni",
        json={
            "struttura_id": struttura_id,
            "check_in": "2026-09-10",
            "check_out": "2026-09-14",
            **extra,
        },
    )


class TestApiCreazione:
    def test_creare_una_manuale_risponde_201(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _crea(client, struttura_id)

        assert risposta.status_code == 201
        corpo = risposta.json()
        assert corpo["stato"] == "attiva"
        assert corpo["canale"] == "manuale"
        # `notti` è derivato dal server e il frontend lo presenta (AD-14): il
        # modo realistico in cui quell'invariante si perde è che il client
        # rifaccia il conto con la timezone del browser.
        assert corpo["notti"] == 4
        assert corpo["ospite_principale"] is None

    def test_un_form_che_manda_i_campi_dell_ospite_VUOTI_non_crea_un_ospite(
        self, client: TestClient
    ) -> None:
        # È la riga su cui si sbaglia in buona fede: un form HTML invia SEMPRE
        # i suoi campi, e li invia come stringa vuota. Senza normalizzazione
        # nascerebbe un'anagrafica con `nome = ""` — un valore che non è un
        # valore, indistinguibile in griglia da un nome mancante e che la
        # retention dovrebbe poi azzerare.
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _crea(
            client,
            struttura_id,
            ospite={"nome": "  ", "email": "", "telefono": ""},
        )

        assert risposta.status_code == 201
        assert risposta.json()["ospite_principale"] is None

    def test_un_ospite_indicato_torna_nella_risposta(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _crea(client, struttura_id, ospite={"nome": "Ospite Inventato"})

        assert risposta.status_code == 201
        assert risposta.json()["ospite_principale"] == "Ospite Inventato"

    def test_nessun_campo_dell_ospite_e_obbligatorio_nel_contratto(
        self, client: TestClient
    ) -> None:
        # Il contratto è ciò che il frontend genera: se un campo contatto
        # diventasse obbligatorio, il client generato lo renderebbe tale e il
        # blocco date non si potrebbe più salvare.
        schema = client.get("/api/v1/openapi.json").json()["components"]["schemas"]
        assert schema["OspiteInput"].get("required", []) == []
        richiesti = set(schema["PrenotazioneManualeInput"]["required"])
        assert richiesti == {"struttura_id", "check_in", "check_out"}

    @pytest.mark.parametrize(
        "check_out",
        [
            # Partenza = arrivo: zero notti. È il confine dell'intervallo
            # semiaperto, cioè il caso che si sbaglia per primo.
            "2026-09-10",
            # Partenza PRIMA dell'arrivo: l'errore di battitura più comune di
            # chi compila due campi data, e finora coperto solo al livello del
            # service. Il 422 lo deve dare il confine HTTP, che è dove l'Host
            # arriva.
            "2026-09-08",
        ],
    )
    def test_un_intervallo_vuoto_e_un_422_problem_json_mai_un_500(
        self, client: TestClient, check_out: str
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _crea(client, struttura_id, check_out=check_out)

        assert risposta.status_code == 422
        assert risposta.headers["content-type"].startswith(PROBLEM)
        assert risposta.json()["type"].endswith("periodo-prenotazione-non-valido")

    def test_una_struttura_di_un_altro_host_e_404(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        struttura_id = _struttura(client)
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")

        risposta = _crea(client, struttura_id)

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("struttura-not-found")

    def test_una_struttura_archiviata_e_422(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _struttura(client)
        assert (
            client.post(f"/api/v1/strutture/{struttura_id}/archivia").status_code == 200
        )

        risposta = _crea(client, struttura_id)

        assert risposta.status_code == 422
        assert risposta.json()["type"].endswith("struttura-archiviata")

    def test_senza_sessione_si_ottiene_401(self, client: TestClient) -> None:
        risposta = _crea(client, "00000000-0000-0000-0000-000000000000")
        assert risposta.status_code == 401

    def test_un_canale_manuale_non_si_puo_dichiarare_su_un_feed(
        self, client: TestClient
    ) -> None:
        # `manuale` è un Canale del Glossario, non un portale: un Feed che lo
        # dichiarasse produrrebbe Prenotazioni «inserite a mano» che nessuno ha
        # inserito, e il CHECK sulla tabella le rifiuterebbe con un 500 al
        # primo sync invece di un errore inline al collegamento.
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = client.post(
            "/api/v1/feed-ical",
            json={
                "struttura_id": struttura_id,
                "url": "https://feed.example.com/x.ics",
                "canale": "manuale",
            },
        )

        assert risposta.status_code == 422


class TestApiCancellazione:
    def test_cancellare_porta_a_cancellata(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _struttura(client)
        prenotazione_id = _crea(client, struttura_id).json()["id"]

        risposta = client.post(
            f"/api/v1/calendario/prenotazioni/{prenotazione_id}/cancellazione"
        )

        assert risposta.status_code == 200
        assert risposta.json()["stato"] == "cancellata"

    def test_la_prenotazione_cancellata_resta_visibile_in_griglia(
        self, client: TestClient
    ) -> None:
        # AD-20 agli occhi dell'Host: farla sparire senza traccia
        # contraddirebbe «archiviare, mai distruggere» per chi quella
        # prenotazione l'ha vista ieri.
        _accedi(client)
        struttura_id = _struttura(client)
        prenotazione_id = _crea(client, struttura_id).json()["id"]
        client.post(f"/api/v1/calendario/prenotazioni/{prenotazione_id}/cancellazione")

        griglia = client.get(
            "/api/v1/calendario", params={"da": "2026-09-01", "a": "2026-09-30"}
        ).json()

        voci = {voce["id"]: voce for voce in griglia["voci"]}
        assert voci[prenotazione_id]["stato"] == "cancellata"

    def test_una_prenotazione_di_un_altro_host_e_404(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        struttura_id = _struttura(client)
        prenotazione_id = _crea(client, struttura_id).json()["id"]
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")

        risposta = client.post(
            f"/api/v1/calendario/prenotazioni/{prenotazione_id}/cancellazione"
        )

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("prenotazione-not-found")

    def test_cancellare_due_volte_risponde_200_e_non_cambia_nulla(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)
        prenotazione_id = _crea(client, struttura_id).json()["id"]
        rotta = f"/api/v1/calendario/prenotazioni/{prenotazione_id}/cancellazione"

        prima = client.post(rotta).json()
        seconda = client.post(rotta).json()

        assert seconda["stato"] == "cancellata"
        assert seconda == prima


class TestGriglia:
    def test_una_manuale_compare_nella_griglia_col_suo_canale(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)
        _crea(client, struttura_id, ospite={"nome": "Ospite Inventato"})

        griglia = client.get(
            "/api/v1/calendario", params={"da": "2026-09-01", "a": "2026-09-30"}
        ).json()

        assert len(griglia["voci"]) == 1
        voce = griglia["voci"][0]
        assert voce["canale"] == "manuale"
        assert voce["ospite_principale"] == "Ospite Inventato"
        assert voce["altri_ospiti"] == 0

    def test_senza_feed_collegati_la_griglia_lo_dice_ancora(
        self, client: TestClient
    ) -> None:
        # Una manuale non è un dato da Feed: inserirla non inventa una
        # freschezza che non esiste (NFR-2). La superficie continua a dire che
        # nessun calendario è collegato, invece di mostrare un orario.
        _accedi(client)
        struttura_id = _struttura(client)
        _crea(client, struttura_id)

        griglia = client.get(
            "/api/v1/calendario", params={"da": "2026-09-01", "a": "2026-09-30"}
        ).json()

        assert griglia["feed_collegati"] == 0
        assert griglia["ultimo_sync_riuscito_il"] is None


class TestNessunDatoDellOspiteNeiLog:
    """NFR-14/NFR-11: l'anagrafica non esce in log né in eventi."""

    def test_il_log_della_cancellazione_porta_soli_identificatori(
        self,
        db_session: Session,
        contesto: Contesto,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        manuale = crea_manuale(
            db_session,
            contesto,
            check_in=DAL,
            check_out=AL,
            sommario="Nome Che Non Deve Uscire",
            ospite=service.DatiOspite(nome="Nome Che Non Deve Uscire"),
        )

        with caplog.at_level("INFO", logger="app.calendario.service"):
            service.cancella_prenotazione(db_session, contesto.host_id, manuale.id)

        # Si asserisce sui RECORD e non su `caplog.text`: gli attributi passati
        # via `extra=` non finiscono mai nel testo formattato, quindi
        # `"nome" not in caplog.text` passerebbe anche loggando in chiaro.
        assert caplog.records, "la cancellazione non lascia traccia"
        for record in caplog.records:
            valori = [str(valore) for valore in record.__dict__.values()]
            assert all("Nome Che Non Deve Uscire" not in v for v in valori)

    def test_il_log_della_creazione_porta_soli_identificatori(
        self,
        db_session: Session,
        contesto: Contesto,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """La creazione è il percorso da cui l'anagrafica ENTRA nel sistema.

        Vale più della cancellazione, non meno: alla cancellazione l'Ospite
        c'era già, alla creazione arriva adesso — e il `con_ospite` booleano nel
        log esiste proprio per dire «ce n'era uno» senza dire chi. Il `sommario`
        è nella stessa asserzione perché è testo scritto dall'Host e può
        contenere qualunque cosa, incluso un nome (NFR-11).
        """
        with caplog.at_level("INFO", logger="app.calendario.service"):
            crea_manuale(
                db_session,
                contesto,
                check_in=DAL,
                check_out=AL,
                sommario="Nome Che Non Deve Uscire",
                ospite=service.DatiOspite(
                    nome="Nome Che Non Deve Uscire",
                    email="non.deve.uscire@example.com",
                    telefono="+39 000 0000000",
                ),
            )

        assert caplog.records, "la creazione non lascia traccia"
        for record in caplog.records:
            valori = [str(valore) for valore in record.__dict__.values()]
            for personale in (
                "Nome Che Non Deve Uscire",
                "non.deve.uscire@example.com",
                "+39 000 0000000",
            ):
                assert all(personale not in valore for valore in valori)


class TestUnAltraStruttura:
    def test_si_crea_su_una_seconda_struttura_dello_stesso_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        seconda = crea_struttura(db_session, contesto.host_id, "Mare Rimini")
        db_session.commit()

        prenotazione = crea_manuale(
            db_session,
            contesto,
            struttura_id=seconda.id,
            check_in=DAL,
            check_out=AL,
        )

        assert prenotazione.struttura_id == seconda.id


def test_l_intervallo_di_una_manuale_e_quello_di_ad_3() -> None:
    """U: il soggiorno di una manuale è `[check_in, check_out)` (AD-3)."""
    soggiorno = DateRange(check_in=DAL, check_out=AL)

    assert soggiorno.nights == 4
    assert soggiorno.contains(DAL)
    # Il `check_out` NON è una notte occupata: è il confine, ed è la ragione
    # per cui il turnover dello stesso giorno non è una sovrapposizione.
    assert not soggiorno.contains(AL)

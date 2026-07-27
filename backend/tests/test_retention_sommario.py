"""Il `sommario` si azzera insieme all'anagrafica (AD-21, decisione MYL-47).

Il `SUMMARY` dei feed OTA contiene spesso il nome dell'Ospite: azzerare
l'anagrafica lasciando vivo il `sommario` **vanifica** la retention. AD-20 lo
qualifica come la STESSA cancellazione già ammessa su un campo in più, non una
quarta — la lista resta a tre, e la guardia GS-6 passa senza essere allargata.

Il caso che questi test esistono per proteggere è il **primario**, e non è
quello che verrebbe in mente per primo: l'Ospite non nasce mai dal sync — la
sua unica scrittura è il percorso manuale dell'Host — quindi la forma
tipica è la Prenotazione scaduta con il nome dentro il `SUMMARY` e **nessuna
riga `ospite`**. Un azzeramento guidato dall'Ospite lo mancherebbe al 100%,
con tutti gli altri test verdi.

L'altra metà è il NON-RIPOPOLAMENTO: una volta azzerato, il campo non torna da
un sync successivo. Vive nell'upsert e non nel job, e senza di essa
`anonimizzato_il` resterebbe ad attestare un azzeramento non più vero.

Nessun dato reale di Ospiti (NFR-16): i nomi sono inventati.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario.jobs import azzera_anagrafiche_scadute
from app.calendario.models import Ospite, Prenotazione, StatoPrenotazione
from tests.calendario import (
    Contesto,
    calendario,
    client,
    collega,
    crea_prenotazione,
    prenotazioni,
    registra_ospite,
    sincronizza,
    vevent,
)
from tests.server_feed import RispostaPreparata, ServerFeed

SOMMARIO = "Ospite Inventato - HMABCDEF"


def _scaduta_col_sommario(
    db_session: Session, contesto: Contesto, *, sommario: str | None = SOMMARIO
) -> Prenotazione:
    prenotazione = crea_prenotazione(
        db_session,
        contesto,
        check_in=date(2020, 1, 1),
        check_out=date(2020, 1, 5),
        sommario=sommario,
    )
    db_session.commit()
    return prenotazione


def _rileggi(db_session: Session, prenotazione: Prenotazione) -> Prenotazione:
    db_session.expire_all()
    riletta = db_session.get(Prenotazione, prenotazione.id)
    assert riletta is not None
    return riletta


class TestIlJobAzzeraIlSommario:
    def test_azzera_una_prenotazione_scaduta_SENZA_alcuna_riga_ospite(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Il caso primario, e quello che un'implementazione ingenua manca.

        `jobs._azzera` azzerava l'anagrafica con una `UPDATE ospite ... WHERE
        prenotazione_id IN (scadute)`. Estendere quella istruzione al
        `sommario` sembra la mossa naturale ed è il difetto: qui non esiste
        nessuna riga `ospite`, quindi non ci sarebbe niente da estendere e il
        nome resterebbe nel `SUMMARY` per sempre.
        """
        prenotazione = _scaduta_col_sommario(db_session, contesto)
        assert db_session.scalars(select(Ospite)).all() == []

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        azzerata = _rileggi(db_session, prenotazione)
        assert azzerata.sommario is None
        assert azzerata.anonimizzato_il is not None

    def test_non_tocca_una_prenotazione_ancora_nel_periodo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date.today() + timedelta(days=10),
            check_out=date.today() + timedelta(days=13),
            sommario=SOMMARIO,
        )
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        viva = _rileggi(db_session, prenotazione)
        assert viva.sommario == SOMMARIO
        assert viva.anonimizzato_il is None

    def test_non_marca_come_anonimizzata_una_prenotazione_senza_sommario(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Nessun campo da azzerare, nessuna evidenza: marcarla attesterebbe un
        # adempimento che non è avvenuto, su un dato che non è mai esistito.
        # È anche ciò che rende l'azzeramento idempotente per costruzione.
        prenotazione = _scaduta_col_sommario(db_session, contesto, sommario=None)

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        intatta = _rileggi(db_session, prenotazione)
        assert intatta.anonimizzato_il is None

    def test_rieseguirlo_non_cambia_NULLA(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Idempotenza dimostrata (AD-10): la consegna è at-least-once.

        Un `anonimizzato_il` che avanza a ogni giro sposterebbe la data
        dell'adempimento e la renderebbe inutile come prova; un
        `aggiornata_il` che avanza farebbe sembrare toccata una riga ferma.
        """
        prenotazione = _scaduta_col_sommario(db_session, contesto)
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        prima = _rileggi(db_session, prenotazione)
        istantanea = (prima.anonimizzato_il, prima.aggiornata_il)

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        dopo = _rileggi(db_session, prenotazione)
        assert (dopo.anonimizzato_il, dopo.aggiornata_il) == istantanea

    def test_un_sommario_riscritto_DOPO_l_azzeramento_scade_di_nuovo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Il filtro del job chiede «c'è qualcosa da azzerare?» (trappola 2).

        Su questo lato il non-ripopolamento è la regola — ma vive
        nell'**upsert**, che è l'unico punto in cui un `sommario` torna senza
        che nessuno l'abbia scritto. Se la stessa domanda finisse anche nel
        filtro del JOB (`anonimizzato_il IS NULL`), un `sommario` riscritto
        per un'altra strada — la Prenotazione manuale della Story 2.4, una
        correzione dell'Host — non scadrebbe mai più: cioè il difetto P1 già
        corretto sul lato `ospite`, reintrodotto qui.
        """
        prenotazione = _scaduta_col_sommario(db_session, contesto)
        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        riaperta = _rileggi(db_session, prenotazione)
        assert riaperta.anonimizzato_il is not None
        riaperta.sommario = "Testo rimesso a mano"
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        assert _rileggi(db_session, prenotazione).sommario is None

    def test_azzera_anagrafica_e_sommario_nello_stesso_giro(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Stessa scadenza, stessa evidenza (AD-21): le due metà non si
        # separano nel tempo, altrimenti fra l'una e l'altra il dato resta.
        prenotazione = _scaduta_col_sommario(db_session, contesto)
        ospite = registra_ospite(
            db_session, contesto, prenotazione, nome="Ospite Inventato"
        )
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        db_session.expire_all()

        riletto = db_session.get(Ospite, ospite.id)
        assert riletto is not None
        assert riletto.nome is None
        assert riletto.anonimizzato_il is not None
        azzerata = _rileggi(db_session, prenotazione)
        assert azzerata.sommario is None
        assert azzerata.anonimizzato_il is not None

    def test_una_prenotazione_cessata_prima_del_check_out_azzera_il_sommario(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La decorrenza anticipata di AD-21 vale per ENTRAMBI i campi: il
        # filtro del `sommario` è `filtro_scadute`, non «check_out passato».
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2030, 1, 1),
            check_out=date(2030, 1, 5),
            stato=StatoPrenotazione.CANCELLATA,
            cessata_il=datetime(2020, 1, 1, tzinfo=UTC),
            sommario=SOMMARIO,
        )
        db_session.commit()

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()

        assert _rileggi(db_session, prenotazione).sommario is None


class TestIlSommarioNonSiRipopola:
    """AD-21: «l'upsert di AD-4 NON riscrive il `sommario` di una Prenotazione
    anonimizzata».

    Senza questa guardia il difetto non è «il campo torna», è peggio: torna
    **e** `anonimizzato_il` resta lì ad attestare un azzeramento che non è più
    vero. Un'evidenza che mente è peggio dell'assenza di evidenza.
    """

    def _feed_con_soggiorno_passato(
        self,
        db_session: Session,
        contesto: Contesto,
        server_feed: ServerFeed,
        *,
        al: str = "20200105",
    ):
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(vevent("uid-passato", dal="20200101", al=al))
            ),
        )
        return collega(db_session, contesto, url)

    def test_un_sync_successivo_non_riscrive_il_sommario_azzerato(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        """Il caso (d): il feed CONSERVA il VEVENT passato.

        È la forma reale — i portali tengono in export i soggiorni conclusi
        per settimane. Il resto della riga continua a sincronizzare: la
        guardia è sul CAMPO, non sulla riga.
        """
        feed = self._feed_con_soggiorno_passato(db_session, contesto, server_feed)
        sincronizza(db_session, feed, client())
        importata = prenotazioni(db_session, feed)[0]
        assert importata.sommario is not None

        azzera_anagrafiche_scadute(db_session, {})
        db_session.commit()
        assert _rileggi(db_session, importata).sommario is None

        # Stesso UID, stesso SUMMARY, ma il soggiorno si allunga: il portale
        # ha corretto le date.
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(vevent("uid-passato", dal="20200101", al="20200107"))
            ),
        )
        sincronizza(db_session, feed, client())

        dopo = _rileggi(db_session, importata)
        assert dopo.sommario is None, (
            "il sync ha ripopolato un `sommario` azzerato: `anonimizzato_il` "
            "resterebbe ad attestare un azzeramento non più vero (AD-21)"
        )
        assert dopo.anonimizzato_il is not None
        # La riga NON è congelata: la Prenotazione anonimizzata continua a
        # sincronizzare tutto il resto.
        assert dopo.check_out == date(2020, 1, 7)
        assert dopo.stato is StatoPrenotazione.ATTIVA

    def test_una_prenotazione_MAI_azzerata_riceve_il_sommario_dal_feed(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # L'altra metà: una guardia che blocca sempre non discrimina, e il
        # `sommario` resta il testo opaco che l'Host usa per riconoscere la
        # Prenotazione per tutto il resto del suo ciclo di vita.
        feed = self._feed_con_soggiorno_passato(db_session, contesto, server_feed)
        sincronizza(db_session, feed, client())
        importata = prenotazioni(db_session, feed)[0]

        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(vevent("uid-passato", dal="20200101", al="20200107"))
            ),
        )
        sincronizza(db_session, feed, client())

        aggiornata = _rileggi(db_session, importata)
        assert aggiornata.sommario == "Prenotazione inventata uid-passato"
        assert aggiornata.anonimizzato_il is None

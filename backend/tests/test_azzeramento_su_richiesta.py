"""Cancellazione su richiesta GDPR (NFR-15, AD-21): il punto d'ingresso.

AD-21 dice che la cancellazione su richiesta «riusa la stessa procedura di
azzeramento, con evidenza». Prima di questo lotto quella frase non aveva un
percorso: l'azzeramento esisteva SOLO come job periodico che decideva da sé
chi azzerare in base alla scadenza, e il filtro non era parametrico.

Il lavoro vero non è un azzeratore nuovo — che divergerebbe dal primo al primo
cambiamento — ma rendere **parametrica la selezione**. I test che contano di
più qui sono quelli che pinnano proprio questo: che la richiesta copra anche
il `sommario` (cioè che stia usando la stessa procedura, non una copia) e che
non esista nessun percorso distruttivo.

Nessun dato reale di Ospiti (NFR-16).
"""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import (
    AmbitoAzzeramento,
    AzzeramentoAudit,
    Ospite,
    Prenotazione,
)
from app.identity.service import HostNonTrovatoError
from tests.calendario import Contesto, crea_contesto, crea_prenotazione, registra_ospite

ATTORE = "privacy@hostpilot.example"
TOKEN = {"X-Admin-Token": "token-di-test-per-endpoint-interni"}


def _con_ospite(
    db_session: Session, contesto: Contesto, *, nome: str = "Ospite Inventato"
) -> tuple[Prenotazione, Ospite]:
    """Prenotazione ANCORA NEL PERIODO: la retention non la toccherebbe.

    Deliberato: se le date fossero scadute, un test verde non distinguerebbe
    «la richiesta ha azzerato» da «il job avrebbe azzerato comunque».
    """
    prenotazione = crea_prenotazione(
        db_session,
        contesto,
        check_in=date(2030, 6, 1),
        check_out=date(2030, 6, 5),
        sommario=f"{nome} - HMABCDEF",
    )
    ospite = registra_ospite(
        db_session,
        contesto,
        prenotazione,
        nome=nome,
        email="ospite.inventato@example.com",
        telefono="+39 000 0000000",
        principale=True,
    )
    db_session.commit()
    return prenotazione, ospite


class TestUnSingoloOspite:
    def test_azzera_i_campi_e_LASCIA_la_riga(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione, ospite = _con_ospite(db_session, contesto)

        esito = service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        assert esito.anagrafiche_azzerate == 1
        db_session.expire_all()
        rimasto = db_session.get(Ospite, ospite.id)
        assert rimasto is not None, "una DELETE sarebbe una quarta forma (AD-20)"
        assert (rimasto.nome, rimasto.email, rimasto.telefono) == (None, None, None)
        assert rimasto.anonimizzato_il is not None
        assert rimasto.prenotazione_id == prenotazione.id

    def test_copre_anche_il_sommario_della_sua_prenotazione(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """La prova che sta usando LA STESSA procedura, non una copia.

        Se A2 avesse un azzeratore proprio, questo test sarebbe l'unico a
        cadere — ed è esattamente la divergenza contro cui il lotto è stato
        scritto in un solo PR.
        """
        prenotazione, ospite = _con_ospite(db_session, contesto)

        esito = service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        assert esito.sommari_azzerati == 1
        db_session.expire_all()
        riletta = db_session.get(Prenotazione, prenotazione.id)
        assert riletta is not None
        assert riletta.sommario is None
        assert riletta.anonimizzato_il is not None
        # La riga resta, con la sua storia: si azzerano i CAMPI.
        assert riletta.check_in == date(2030, 6, 1)

    def test_non_tocca_gli_altri_ospiti_della_stessa_prenotazione(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La richiesta riguarda UNA persona: l'anagrafica di chi non l'ha
        # chiesta resta. Il `sommario` invece è testo opaco del portale e non
        # è l'anagrafica di nessuno — azzerarlo non cancella un dato altrui.
        prenotazione, ospite = _con_ospite(db_session, contesto)
        altro = registra_ospite(
            db_session, contesto, prenotazione, nome="Altro Inventato"
        )
        db_session.commit()

        service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        db_session.expire_all()
        superstite = db_session.get(Ospite, altro.id)
        assert superstite is not None
        assert superstite.nome == "Altro Inventato"
        assert superstite.anonimizzato_il is None

    def test_un_ospite_di_un_ALTRO_host_non_e_raggiungibile(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Tenancy (AD-2, NFR-14): non è «zero righe azzerate», è una richiesta
        # a cui non si può rispondere — e la differenza rende leggibile
        # l'evidenza.
        altro = crea_contesto(
            db_session, email="host.secondo@example.com", nome="Altra Struttura"
        )
        _, ospite = _con_ospite(db_session, altro)

        with pytest.raises(service.OspiteNonTrovatoError):
            service.azzera_ospite_su_richiesta(
                db_session, contesto.host_id, ospite.id, attore=ATTORE
            )

        db_session.rollback()
        db_session.expire_all()
        intatto = db_session.get(Ospite, ospite.id)
        assert intatto is not None
        assert intatto.nome == "Ospite Inventato"

    def test_e_idempotente(self, db_session: Session, contesto: Contesto) -> None:
        _, ospite = _con_ospite(db_session, contesto)
        service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )
        db_session.expire_all()
        prima = db_session.get(Ospite, ospite.id)
        assert prima is not None
        istantanea = (prima.anonimizzato_il, prima.aggiornato_il)

        secondo = service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        assert (secondo.anagrafiche_azzerate, secondo.sommari_azzerati) == (0, 0)
        db_session.expire_all()
        dopo = db_session.get(Ospite, ospite.id)
        assert dopo is not None
        assert (dopo.anonimizzato_il, dopo.aggiornato_il) == istantanea


class TestTuttiGliOspitiDiUnHost:
    def test_azzera_ogni_ospite_e_ogni_sommario_dell_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _, primo = _con_ospite(db_session, contesto)
        _, secondo = _con_ospite(db_session, contesto, nome="Secondo Inventato")

        esito = service.azzera_ospiti_dell_host_su_richiesta(
            db_session, contesto.host_id, attore=ATTORE
        )

        assert (esito.anagrafiche_azzerate, esito.sommari_azzerati) == (2, 2)
        db_session.expire_all()
        for ospite in (primo, secondo):
            riletto = db_session.get(Ospite, ospite.id)
            assert riletto is not None
            assert riletto.nome is None

    def test_resta_dentro_il_perimetro_dell_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-2: «tutti gli Ospiti di un Host» non è «tutti gli Ospiti». Un
        # filtro dimenticato qui azzererebbe l'anagrafica di ogni tenant, e
        # nessuno dei due se ne accorgerebbe finché non serve un nome.
        altro = crea_contesto(
            db_session, email="host.secondo@example.com", nome="Altra Struttura"
        )
        _, mio = _con_ospite(db_session, contesto)
        prenotazione_altrui, altrui = _con_ospite(db_session, altro)

        service.azzera_ospiti_dell_host_su_richiesta(
            db_session, contesto.host_id, attore=ATTORE
        )

        db_session.expire_all()
        assert db_session.get(Ospite, mio.id).nome is None  # type: ignore[union-attr]
        superstite = db_session.get(Ospite, altrui.id)
        assert superstite is not None
        assert superstite.nome == "Ospite Inventato"
        intatta = db_session.get(Prenotazione, prenotazione_altrui.id)
        assert intatta is not None
        assert intatta.sommario is not None

    def test_un_host_inesistente_e_un_errore_non_zero_righe(
        self, db_session: Session
    ) -> None:
        # Un azzeramento «riuscito» su zero righe direbbe a chi ha fatto
        # l'istanza che è stata evasa. Non lo è.
        with pytest.raises(HostNonTrovatoError):
            service.azzera_ospiti_dell_host_su_richiesta(
                db_session, uuid.uuid4(), attore=ATTORE
            )


class TestLEvidenza:
    def test_scrive_chi_cosa_quando(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _, ospite = _con_ospite(db_session, contesto)

        esito = service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        riga = db_session.scalars(select(AzzeramentoAudit)).one()
        assert riga.attore == ATTORE
        assert riga.ambito is AmbitoAzzeramento.OSPITE
        assert riga.riferimento == ospite.id
        assert riga.host_id == contesto.host_id
        assert riga.eseguito_il == esito.eseguito_il
        assert (riga.anagrafiche_azzerate, riga.sommari_azzerati) == (1, 1)

    def test_l_evidenza_si_scrive_anche_quando_non_c_era_nulla_da_azzerare(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # «Evidenza sempre scritta»: la prova che la richiesta è stata evasa
        # non dipende da quanto c'era da cancellare. Senza, una richiesta su
        # un'anagrafica già vuota non lascerebbe traccia di essere arrivata.
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2030, 6, 1), check_out=date(2030, 6, 5)
        )
        ospite = registra_ospite(db_session, contesto, prenotazione)
        db_session.commit()

        service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        riga = db_session.scalars(select(AzzeramentoAudit)).one()
        assert (riga.anagrafiche_azzerate, riga.sommari_azzerati) == (0, 0)

    def test_l_evidenza_non_porta_dati_personali(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Un nome scritto qui sopravviverebbe all'azzeramento che questa
        # stessa riga attesta (AD-16, NFR-11) — lo stesso motivo per cui il
        # payload del job di retention è vuoto.
        _, ospite = _con_ospite(db_session, contesto)
        service.azzera_ospite_su_richiesta(
            db_session, contesto.host_id, ospite.id, attore=ATTORE
        )

        riga = db_session.scalars(select(AzzeramentoAudit)).one()
        scritto = " ".join(
            str(valore)
            for chiave, valore in vars(riga).items()
            if not chiave.startswith("_")
        )
        assert "Ospite Inventato" not in scritto
        assert "ospite.inventato@example.com" not in scritto
        assert "+39 000 0000000" not in scritto

    def test_il_log_non_porta_dati_personali(
        self,
        db_session: Session,
        contesto: Contesto,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Si assertisce sui `record`: gli attributi passati con `extra=` non
        # finiscono in `caplog.text`, quindi un `not in caplog.text`
        # passerebbe anche loggando il nome in chiaro.
        _, ospite = _con_ospite(db_session, contesto)

        with caplog.at_level("INFO", logger="app.calendario.service"):
            service.azzera_ospite_su_richiesta(
                db_session, contesto.host_id, ospite.id, attore=ATTORE
            )

        righe = [
            record
            for record in caplog.records
            if record.message == "azzeramento su richiesta eseguito"
        ]
        assert len(righe) == 1
        emesso = " ".join(str(valore) for valore in vars(righe[0]).values())
        assert "Ospite Inventato" not in emesso
        assert "ospite.inventato@example.com" not in emesso


class TestLEndpointInterno:
    """Stesso pattern dei `/interno` esistenti: token di servizio, mai sessione.

    Le guardie strutturali (`test_auth_convention.py`) lo verificano per
    costruzione su ogni rotta; qui si prova che il percorso HTTP arriva
    davvero al service e che la risposta non porta nulla di personale.
    """

    def test_azzera_un_ospite(
        self, client: TestClient, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione, ospite = _con_ospite(db_session, contesto)

        risposta = client.post(
            f"/api/v1/interno/host/{contesto.host_id}/ospiti/{ospite.id}/azzeramento",
            json={"attore": ATTORE},
            headers=TOKEN,
        )

        assert risposta.status_code == 200
        corpo = risposta.json()
        assert corpo["ambito"] == "ospite"
        assert corpo["riferimento"] == str(ospite.id)
        assert (corpo["anagrafiche_azzerate"], corpo["sommari_azzerati"]) == (1, 1)
        assert "Ospite Inventato" not in risposta.text
        db_session.expire_all()
        assert db_session.get(Ospite, ospite.id).nome is None  # type: ignore[union-attr]
        assert db_session.get(Prenotazione, prenotazione.id).sommario is None  # type: ignore[union-attr]

    def test_azzera_tutti_gli_ospiti_di_un_host(
        self, client: TestClient, db_session: Session, contesto: Contesto
    ) -> None:
        _, ospite = _con_ospite(db_session, contesto)

        risposta = client.post(
            f"/api/v1/interno/host/{contesto.host_id}/azzeramento-ospiti",
            json={"attore": ATTORE},
            headers=TOKEN,
        )

        assert risposta.status_code == 200
        assert risposta.json()["ambito"] == "host"
        db_session.expire_all()
        assert db_session.get(Ospite, ospite.id).nome is None  # type: ignore[union-attr]

    def test_senza_token_e_chiuso(
        self, client: TestClient, db_session: Session, contesto: Contesto
    ) -> None:
        _, ospite = _con_ospite(db_session, contesto)

        risposta = client.post(
            f"/api/v1/interno/host/{contesto.host_id}/ospiti/{ospite.id}/azzeramento",
            json={"attore": ATTORE},
        )

        assert risposta.status_code == 403
        db_session.expire_all()
        assert db_session.get(Ospite, ospite.id).nome == "Ospite Inventato"  # type: ignore[union-attr]

    def test_un_ospite_inesistente_e_404(
        self, client: TestClient, contesto: Contesto
    ) -> None:
        risposta = client.post(
            f"/api/v1/interno/host/{contesto.host_id}/ospiti/{uuid.uuid4()}/azzeramento",
            json={"attore": ATTORE},
            headers=TOKEN,
        )

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("ospite-not-found")

    def test_un_host_inesistente_e_404(self, client: TestClient) -> None:
        risposta = client.post(
            f"/api/v1/interno/host/{uuid.uuid4()}/azzeramento-ospiti",
            json={"attore": ATTORE},
            headers=TOKEN,
        )

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("host-not-found")

    def test_l_attore_e_obbligatorio(
        self, client: TestClient, db_session: Session, contesto: Contesto
    ) -> None:
        # Un'evidenza senza «chi» non è un'evidenza.
        _, ospite = _con_ospite(db_session, contesto)

        risposta = client.post(
            f"/api/v1/interno/host/{contesto.host_id}/ospiti/{ospite.id}/azzeramento",
            json={"attore": ""},
            headers=TOKEN,
        )

        assert risposta.status_code == 422

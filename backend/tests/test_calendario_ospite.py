"""Anagrafica Ospite (AD-21, decisione MYL-40): la sua FORMA e i suoi confini.

I cinque vincoli della decisione non sono verificabili tutti allo stesso
livello, e questo file li distribuisce dove mordono:

- **minimizzazione** — sulla forma della tabella, con una guardia: un campo
  di documento aggiunto fra sei mesi non farebbe fallire nessun test
  funzionale, perché nessun percorso lo userebbe. È la classe «assenze»
  rovesciata: qui il difetto è una PRESENZA che nessuno nota;
- **nessun valore dedotto** — sul percorso di import, dove la tentazione
  esiste davvero: il `sommario` del VEVENT è un nome scritto da un umano e
  promuoverlo costerebbe una riga;
- **tenancy e proprietà** — sui percorsi di scrittura e di lettura.

Nessun dato reale di Ospiti (NFR-16).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import Ospite
from tests.calendario import (
    Contesto,
    collega,
    crea_contesto,
    crea_prenotazione,
    fixture_ical,
    prenotazioni,
    registra_ospite,
    sincronizza,
)
from tests.calendario import client as client_feed
from tests.modello import carica_modelli
from tests.server_feed import RispostaPreparata, ServerFeed

Base = carica_modelli()

# Sottostringhe che tradiscono un campo di documento d'identità o un dato
# particolare. Non è un elenco di nomi vietati per gusto: quei dati vivono
# SOLO in `ospite_documento` (Epic 3, AD-11), cifrati a campo e con una
# retention propria — scriverli qui significherebbe averli in chiaro, senza
# quella retention e senza quella cifratura.
SPIE_DI_DOCUMENTO = (
    "documento",
    "passaporto",
    "carta_identita",
    "codice_fiscale",
    "data_nascita",
    "luogo_nascita",
    "cittadinanza",
    "nazionalita",
    "sesso",
)

CAMPI_PERSONALI = ("nome", "email", "telefono")


class TestLaFormaDellaTabella:
    """Guardia strutturale sui vincoli 2 e 4 della decisione MYL-40."""

    def test_i_campi_personali_sono_TUTTI_facoltativi(self) -> None:
        # «Mai obbligatori» è una proprietà dello SCHEMA, non del form: una
        # colonna NOT NULL costringerebbe ogni percorso di scrittura a
        # inventare un valore, ed è esattamente il modo in cui nasce un nome
        # dedotto.
        tabella = Base.metadata.tables["ospite"]
        obbligatori = [
            campo for campo in CAMPI_PERSONALI if not tabella.columns[campo].nullable
        ]
        assert obbligatori == [], (
            f"campi personali NOT NULL: {obbligatori} — l'anagrafica Ospite "
            "si popola solo con ciò che si sa davvero (AD-21, NFR-11)"
        )

    def test_non_esiste_nessun_campo_di_documento_d_identita(self) -> None:
        tabella = Base.metadata.tables["ospite"]
        sospette = [
            colonna.name
            for colonna in tabella.columns
            if any(spia in colonna.name.lower() for spia in SPIE_DI_DOCUMENTO)
        ]
        assert sospette == [], (
            f"colonne da documento su `ospite`: {sospette} — quei campi "
            "vivono SOLO in `ospite_documento` (Epic 3, AD-11), cifrati e "
            "con retention propria"
        )

    def test_la_guardia_riconoscerebbe_un_campo_di_documento(self) -> None:
        # Sentinella: le si fa esaminare un nome costruito e si pretende che
        # lo segnali. Una guardia che non è mai stata vista mordere è
        # un'affermazione sulla propria correttezza, non un test.
        finte = ("numero_documento", "codice_fiscale", "data_nascita")
        for nome in finte:
            assert any(spia in nome for spia in SPIE_DI_DOCUMENTO), nome
        assert not any(spia in "telefono" for spia in SPIE_DI_DOCUMENTO)

    def test_e_tenant_owned_come_le_altre_entita(self) -> None:
        # La guardia G-3 (`test_tenancy_convention.py`) lo impone già per
        # costruzione su ogni tabella nuova; qui si pinna il fatto che
        # `ospite` NON sia stata messa in una delle sue allowlist — che è il
        # modo realistico in cui il vincolo 4 si perderebbe.
        from tests.test_tenancy_convention import (
            TABELLE_DI_RIFERIMENTO,
            TABELLE_NON_TENANT,
            TABELLE_PRE_AUTENTICAZIONE,
        )

        esentate = (
            TABELLE_NON_TENANT | TABELLE_DI_RIFERIMENTO | TABELLE_PRE_AUTENTICAZIONE
        )
        assert "ospite" not in esentate
        colonna = Base.metadata.tables["ospite"].columns["host_id"]
        assert not colonna.nullable
        assert any(fk.column.table.name == "host" for fk in colonna.foreign_keys)

    def test_e_una_tabella_protetta_dalla_guardia_append_preserving(self) -> None:
        # L'azzeramento è distruttivo sui CAMPI; una `DELETE` della riga
        # sarebbe una quarta cancellazione, cioè fuori dalla lista esaustiva
        # di AD-20. GS-6 è ciò che lo rende impossibile per costruzione.
        from tests.test_append_preserving_convention import TABELLE_PROTETTE

        assert "ospite" in TABELLE_PROTETTE


class TestNienteValoriDedotti:
    """Vincolo 2, sul percorso dove la tentazione esiste davvero."""

    def test_l_import_di_un_feed_NON_crea_nessun_ospite(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        """La trappola numero uno: `SUMMARY` promosso a nome di Ospite.

        I VEVENT della fixture portano un `SUMMARY` che *sembra* un nome. Il
        feed non porta un'identità Ospite affidabile — è la ragione per cui
        la Story 2.1 ha deliberatamente non introdotto l'entità — quindi
        l'import non deve scrivere una riga di anagrafica, nemmeno vuota.

        Una riga vuota per Prenotazione sembrerebbe innocua e non lo è: la
        griglia mostrerebbe «Ospite non indicato» dove oggi mostra la stessa
        cosa, ma la retention comincerebbe a contare su anagrafiche che
        nessuno ha mai popolato, e il conteggio «altri Ospiti» partirebbe da
        un dato inventato.
        """
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)

        sincronizza(db_session, feed, client_feed())

        importate = prenotazioni(db_session, feed)
        assert importate != []
        assert db_session.query(Ospite).count() == 0

    def test_il_sommario_resta_sulla_prenotazione_come_testo_opaco(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # L'altra metà: non promuoverlo non significa buttarlo. Il `sommario`
        # serve all'Host a riconoscere la Prenotazione, e resta dov'è.
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client_feed())

        sommari = [riga.sommario for riga in prenotazioni(db_session, feed)]
        assert all(sommario for sommario in sommari)

    def test_un_ospite_senza_alcun_contatto_e_valido(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # «C'è qualcuno, non so chi» è un'informazione, non un errore: è il
        # caso del blocco date e della Prenotazione senza contatti.
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )

        ospite = registra_ospite(db_session, contesto, prenotazione, principale=True)
        db_session.commit()

        assert ospite.id is not None
        assert not ospite.ha_contatti


class TestProprietaEAccesso:
    """Vincoli 1 e 4: `calendario` unico scrittore, dati del solo Host."""

    def test_non_si_registra_un_ospite_sulla_prenotazione_di_un_altro_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        altro = crea_contesto(
            db_session, email="host.estraneo@example.com", nome="Altrove"
        )
        prenotazione = crea_prenotazione(
            db_session, altro, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )
        db_session.commit()

        with pytest.raises(service.PrenotazioneNonTrovataError):
            service.registra_ospite(
                db_session,
                contesto.host_id,
                prenotazione.id,
                service.DatiOspite(nome="Chiunque"),
            )

    def test_una_prenotazione_inesistente_non_diventa_un_ospite_orfano(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        with pytest.raises(service.PrenotazioneNonTrovataError):
            service.registra_ospite(
                db_session,
                contesto.host_id,
                uuid.uuid4(),
                service.DatiOspite(nome="Chiunque"),
            )

    def test_la_lettura_e_scopata_sull_host_proprietario(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )
        registra_ospite(
            db_session, contesto, prenotazione, nome="Ospite Inventato", principale=True
        )
        db_session.commit()
        altro = crea_contesto(
            db_session, email="host.curioso@example.com", nome="Altrove"
        )

        assert (
            service.ospiti_della_prenotazione(
                db_session, altro.host_id, prenotazione.id
            )
            == []
        )
        miei = service.ospiti_della_prenotazione(
            db_session, contesto.host_id, prenotazione.id
        )
        assert [ospite.nome for ospite in miei] == ["Ospite Inventato"]


class TestOspitePrincipale:
    def test_il_database_impedisce_due_principali_sulla_stessa_prenotazione(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Il vincolo è del DATABASE, non del codice applicativo.

        Con due righe marcate `principale` la griglia sceglierebbe a caso
        quale nome mostrare, e la scelta potrebbe cambiare fra due letture
        identiche. Un controllo applicativo qui sarebbe un check-then-write,
        cioè la forma che in questo repo è già costata due difetti.
        """
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )
        registra_ospite(db_session, contesto, prenotazione, principale=True)
        db_session.flush()
        registra_ospite(db_session, contesto, prenotazione, principale=True)

        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_piu_ospiti_NON_principali_convivono(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # L'indice è PARZIALE: il vincolo riguarda solo il sottoinsieme
        # marcato. Se fosse pieno, una Prenotazione non potrebbe registrare
        # più di un Ospite — che è l'opposto di ciò che l'ERD prevede.
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )
        for indice in range(3):
            registra_ospite(db_session, contesto, prenotazione, nome=f"Ospite {indice}")
        db_session.commit()

        assert (
            len(
                service.ospiti_della_prenotazione(
                    db_session, contesto.host_id, prenotazione.id
                )
            )
            == 3
        )

    def test_il_principale_viene_per_primo_nella_lettura(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 4)
        )
        registra_ospite(db_session, contesto, prenotazione, nome="Accompagnatore")
        db_session.flush()
        registra_ospite(
            db_session, contesto, prenotazione, nome="Intestatario", principale=True
        )
        db_session.commit()

        letti = service.ospiti_della_prenotazione(
            db_session, contesto.host_id, prenotazione.id
        )
        assert [ospite.nome for ospite in letti] == ["Intestatario", "Accompagnatore"]

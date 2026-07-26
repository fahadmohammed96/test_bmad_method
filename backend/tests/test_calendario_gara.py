"""Test di gara A3-1 — idempotenza dell'upsert sotto concorrenza.

Regola dell'Epic 2 (§2.4 del test design): **ogni percorso che legge-poi-scrive
con un vincolo nasce con un test di gara**. Nell'Epic 1 lo stesso difetto
(check-then-write senza serializzazione) è stato trovato due volte a tre Story
di distanza — G-2 sulla registrazione, F-1 sul cap Strutture.

Forma imposta, la stessa di `test_strutture.py::TestCapAtomico`:

- **8 contendenti**, non 2: con due thread una finestra critica stretta spesso
  non si presenta e il test passa a vuoto;
- `threading.Barrier(8, timeout=10)` allineato **fra i client**, mai dentro il
  codice sotto test: con un rimedio basato su lock un barrier interno andrebbe
  in deadlock invece che in rosso, mascherando l'esito;
- una `Session(pg_engine)` fresca per thread, `barriera.wait()` **dentro** il
  blocco di sessione;
- esiti contati **più** una ri-query di post-condizione.

**Cosa dimostra.** Che a decidere è il vincolo del DATABASE
(`uq_prenotazione_feed_ical_uid` + `ON CONFLICT DO UPDATE`) e non un controllo
applicativo. Nel codice sotto test non esiste alcun pre-check da accecare:
`upsert_dal_feed` è una sola istruzione. È il punto — la lezione di G-2 dice
che il pre-check è precisamente ciò che non regge, quindi qui non c'è.

**Visto rosso.** Sostituendo l'upsert con un check-then-write equivalente
(«esiste già?» poi «inserisci») e togliendo il UNIQUE dalla migrazione, questo
test produce righe duplicate. L'evidenza è nel commento della PR.
"""

import ipaddress
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import CanaleFeed, EsitoSyncRun, Prenotazione
from app.calendario.trasporto import ClientFeedHttp
from app.calendario.uscita_rete import PoliticaUscitaRete
from app.identity.models import Host
from app.strutture.models import Struttura
from tests.server_feed import RispostaPreparata, ServerFeed

CONCORRENTI = 8
UID_IN_GARA = "in-gara@example.com"

CORPO = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
    f"UID:{UID_IN_GARA}\r\n"
    "DTSTART;VALUE=DATE:20260810\r\nDTEND;VALUE=DATE:20260814\r\n"
    "SUMMARY:Prenotazione inventata in gara\r\n"
    "END:VEVENT\r\nEND:VCALENDAR\r\n"
).encode()


def _client() -> ClientFeedHttp:
    return ClientFeedHttp(
        PoliticaUscitaRete(
            timeout_connessione_secondi=5.0,
            timeout_lettura_secondi=10.0,
            dimensione_massima_byte=1_000_000,
            max_redirect=2,
            reti_consentite=(ipaddress.ip_network("127.0.0.0/8"),),
        )
    )


@pytest.fixture
def feed_pronto(
    db_session: Session, server_feed: ServerFeed
) -> tuple[uuid.UUID, uuid.UUID]:
    host = Host(email="host.in.gara@example.com", password_hash="$argon2id$finto")
    db_session.add(host)
    db_session.flush()
    struttura = Struttura(
        host_id=host.id, nome="In gara", comune="Testopoli", regione="Emilia-Romagna"
    )
    db_session.add(struttura)
    db_session.commit()

    url = server_feed.prepara("/calendario.ics", RispostaPreparata(corpo=CORPO))
    feed = service.collega_feed(
        db_session,
        host.id,
        service.DatiFeed(struttura_id=struttura.id, url=url, canale=CanaleFeed.AIRBNB),
    )
    return host.id, feed.id


class TestUpsertIdempotenteSottoConcorrenza:
    # Un deadlock del database appenderebbe `ThreadPoolExecutor.__exit__`
    # all'infinito. Sbaglia dal lato sicuro — non passa in verde — ma un hang
    # non deve essere l'unica difesa: il timeout lo trasforma in un rosso.
    @pytest.mark.timeout(60)
    def test_otto_sync_in_gara_lasciano_una_sola_prenotazione(
        self,
        pg_engine: Engine,
        feed_pronto: tuple[uuid.UUID, uuid.UUID],
    ) -> None:
        host_id, feed_id = feed_pronto
        barriera = threading.Barrier(CONCORRENTI, timeout=10)

        def sincronizza_in_gara(_: int) -> str:
            with Session(pg_engine) as db:
                barriera.wait()
                try:
                    run = service.esegui_sync(db, host_id, feed_id, client=_client())
                    db.commit()
                except Exception as exc:  # noqa: BLE001 — l'esito è il dato del test
                    return f"errore:{type(exc).__name__}"
                if run.esito is not EsitoSyncRun.RIUSCITO:
                    return f"fallito:{run.categoria_errore}"
                if run.prenotazioni_importate == 1:
                    return "importata"
                if run.prenotazioni_aggiornate == 1:
                    return "aggiornata"
                return "nessuna"

        with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
            esiti = list(esecutore.map(sincronizza_in_gara, range(CONCORRENTI)))

        # Nessun errore deve emergere: una IntegrityError che arriva fino
        # all'API è un 500 su un percorso normale.
        assert [esito for esito in esiti if esito.startswith("errore")] == []
        # Esattamente UNO ha inserito; gli altri sette hanno aggiornato.
        assert esiti.count("importata") == 1
        assert esiti.count("aggiornata") == CONCORRENTI - 1

        # Post-condizione sullo stato finale, non solo sugli esiti contati.
        with Session(pg_engine) as db:
            righe = db.scalars(
                select(Prenotazione).where(Prenotazione.ical_uid == UID_IN_GARA)
            ).all()
        assert len(righe) == 1
        assert righe[0].check_in.isoformat() == "2026-08-10"
        assert righe[0].check_out.isoformat() == "2026-08-14"

    def test_il_vincolo_di_unicita_vive_nel_database(self, pg_engine: Engine) -> None:
        # Se il UNIQUE sparisse dalla migrazione, l'idempotenza resterebbe
        # affidata al codice: questo test lo dice subito invece di lasciare
        # scoprirlo al prossimo test di gara.
        from sqlalchemy import inspect

        vincoli = inspect(pg_engine).get_unique_constraints("prenotazione")
        per_nome = {vincolo["name"]: vincolo for vincolo in vincoli}
        assert "uq_prenotazione_feed_ical_uid" in per_nome
        assert per_nome["uq_prenotazione_feed_ical_uid"]["column_names"] == [
            "feed_id",
            "ical_uid",
        ]

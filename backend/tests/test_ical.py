"""Unit del parser iCal e del normalizzatore VEVENT → DateRange.

È la tabella dei casi di §5.3 del test design (copre R2-F e R2-G): funzioni
pure su testo, il livello più basso possibile e il solo dove moltiplicare le
varianti è economico. A integration la matrice dei formati diventa
impraticabile e si finisce per campionarla.

Il corpus di fixture è in `tests/fixtures/ical/` (vedi il suo README per il
limite dichiarato: è modellato su RFC 5545, non catturato da feed reali).
"""

from datetime import date
from pathlib import Path

import pytest

from app.calendario.ical import FeedNonValidoError, analizza_feed
from app.calendario.normalizzazione import (
    EventoNonNormalizzabileError,
    normalizza,
)
from app.core.date_range import EmptyDateRangeError

FIXTURES = Path(__file__).parent / "fixtures" / "ical"


def _fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _eventi_per_uid(nome_fixture: str) -> dict[str, object]:
    feed = analizza_feed(_fixture(nome_fixture))
    return {vevent.uid: vevent for vevent in feed.eventi if vevent.uid}


class TestValiditaDelFeed:
    """E2-G3: «scomparso dal feed» ≠ «non ricevuto».

    Se il parser accettasse un corpo troncato, il chiamante non avrebbe modo
    di distinguere un errore di trasporto da un calendario svuotato — ed è la
    catena che trasforma una connessione chiusa a metà in prenotazioni
    marcate `rimossa_dal_feed`.
    """

    def test_un_feed_completo_si_analizza(self) -> None:
        feed = analizza_feed(_fixture("airbnb-date-only.ics"))
        assert len(feed.eventi) == 2

    def test_un_corpo_troncato_a_meta_vevent_e_feed_non_valido(self) -> None:
        with pytest.raises(FeedNonValidoError):
            analizza_feed(_fixture("troncato-a-meta-vevent.ics"))

    def test_un_corpo_vuoto_e_feed_non_valido(self) -> None:
        for corpo in ("", "   ", "\r\n"):
            with pytest.raises(FeedNonValidoError):
                analizza_feed(corpo)

    def test_un_html_di_cortesia_con_esito_200_e_feed_non_valido(self) -> None:
        with pytest.raises(FeedNonValidoError):
            analizza_feed("<html><body>Servizio non disponibile</body></html>")

    def test_un_vcalendar_non_chiuso_e_feed_non_valido(self) -> None:
        corpo = _fixture("airbnb-date-only.ics").replace("END:VCALENDAR\n", "")
        with pytest.raises(FeedNonValidoError):
            analizza_feed(corpo)

    def test_un_vevent_annidato_e_feed_non_valido(self) -> None:
        corpo = _fixture("airbnb-date-only.ics").replace(
            "UID:aaaa1111-0001@example.com", "BEGIN:VEVENT"
        )
        with pytest.raises(FeedNonValidoError):
            analizza_feed(corpo)

    def test_un_calendario_chiuso_senza_eventi_e_valido_ma_vuoto(self) -> None:
        # Strutturalmente valido: sta al service decidere che un feed senza
        # eventi non autorizza alcuna transizione di stato.
        feed = analizza_feed(_fixture("solo-intestazione.ics"))
        assert feed.eventi == ()


class TestConfiniDiTrasporto:
    """CRLF, LF, BOM: costruiti qui perché in un file sono invisibili."""

    def test_crlf_e_lf_danno_lo_stesso_risultato(self) -> None:
        testo = _fixture("airbnb-date-only.ics")
        con_lf = analizza_feed(testo)
        con_crlf = analizza_feed(testo.replace("\n", "\r\n"))
        con_cr = analizza_feed(testo.replace("\n", "\r"))
        assert len(con_lf.eventi) == len(con_crlf.eventi) == len(con_cr.eventi) == 2

    def test_un_bom_iniziale_non_impedisce_l_analisi(self) -> None:
        corpo = ("﻿" + _fixture("airbnb-date-only.ics")).encode("utf-8")
        assert len(analizza_feed(corpo).eventi) == 2

    def test_i_byte_utf8_si_decodificano_senza_mojibake(self) -> None:
        eventi = analizza_feed(
            _fixture("folding-e-confini-testuali.ics").encode("utf-8")
        ).eventi
        descrizione = eventi[0].valore("DESCRIPTION")
        assert descrizione is not None
        assert "à è ì ò ù" in descrizione
        assert "Привет" in descrizione
        assert "🏠" in descrizione

    def test_byte_non_utf8_non_fanno_esplodere_il_parser(self) -> None:
        # F-3 dell'Epic 1 era esattamente questo: byte fuori dall'alfabeto
        # immaginato che attraversano un confronto e diventano un 500.
        corpo = _fixture("airbnb-date-only.ics").encode("utf-8")
        corpo = corpo.replace(b"inventata 1", b"inventata \xff\xfe")
        assert len(analizza_feed(corpo).eventi) == 2


class TestSintassi:
    def test_il_folding_ricompone_la_riga(self) -> None:
        eventi = _eventi_per_uid("folding-e-confini-testuali.ics")
        assert eventi["eeee5555-folding@example.com"].valore("SUMMARY") == (
            "Sommario ripiegato su più righe che continua qui e finisce qui"
        )

    def test_gli_escape_ical_si_srotolano(self) -> None:
        eventi = _eventi_per_uid("folding-e-confini-testuali.ics")
        descrizione = eventi["eeee5555-folding@example.com"].valore("DESCRIPTION")
        assert "; emoji" in descrizione
        assert ", e una virgola" in descrizione

    def test_una_riga_ripiegata_a_75_ottetti_si_ricompone(self) -> None:
        corpo = (
            "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
            "UID:riga-lunga@example.com\r\n"
            "DTSTART;VALUE=DATE:20260810\r\n"
            "DTEND;VALUE=DATE:20260811\r\n"
            "SUMMARY:" + "a" * 66 + "\r\n\t" + "b" * 20 + "\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        evento = analizza_feed(corpo).eventi[0]
        assert evento.valore("SUMMARY") == "a" * 66 + "b" * 20

    def test_le_proprieta_sconosciute_non_disturbano_la_normalizzazione(self) -> None:
        # «Si ignorano» significa due cose precise, e la prima versione di
        # questo test non ne asseriva nessuna: la proprieta' stava a livello
        # VCALENDAR, quindi non poteva comparire fra quelle dei VEVENT
        # qualunque cosa facesse il parser. Spostata dentro il VEVENT, si
        # scopre che il parser la RACCOGLIE — e' il normalizzatore a non
        # guardarla. Ecco le due proprieta' vere:
        eventi = _eventi_per_uid("folding-e-confini-testuali.ics")
        vevent = eventi["eeee5555-folding@example.com"]

        # 1. il parser la porta senza inciampare, e non la confonde con altro
        assert vevent.valore("X-PROPRIETA-SCONOSCIUTA") == (
            "il parser la ignora senza lamentarsi"
        )
        assert {"UID", "DTSTART", "DTEND", "SUMMARY"} <= {
            proprieta.nome for proprieta in vevent.proprieta
        }

        # 2. l'evento normalizzato e' identico a quello senza la proprieta'
        righe = [
            riga
            for riga in _fixture("folding-e-confini-testuali.ics").splitlines()
            if not riga.startswith("X-PROPRIETA-SCONOSCIUTA")
        ]
        senza = analizza_feed("\n".join(righe)).eventi[0]
        assert normalizza(vevent) == normalizza(senza)

    def test_un_sommario_vuoto_resta_vuoto_senza_errori(self) -> None:
        eventi = _eventi_per_uid("folding-e-confini-testuali.ics")
        assert eventi["eeee5555-vuoto@example.com"].valore("SUMMARY") == ""


class TestIdentita:
    def test_un_vevent_senza_uid_non_e_normalizzabile(self) -> None:
        feed = analizza_feed(_fixture("eventi-malformati.ics"))
        senza_uid = [vevent for vevent in feed.eventi if vevent.uid is None]
        assert len(senza_uid) == 1
        with pytest.raises(EventoNonNormalizzabileError):
            normalizza(senza_uid[0])

    def test_un_uid_duplicato_vince_l_ultima_occorrenza(self) -> None:
        # Criterio DETERMINISTICO e dichiarato: l'ultima occorrenza nel feed
        # è quella che sopravvive, come farebbe un upsert applicato in ordine.
        feed = analizza_feed(_fixture("uid-duplicato.ics"))
        assert len(feed.eventi) == 2
        eventi = [normalizza(vevent) for vevent in feed.eventi]
        assert eventi[0].ical_uid == eventi[1].ical_uid
        assert eventi[-1].soggiorno.check_in == date(2026, 9, 1)

    def test_l_uid_si_ripulisce_degli_spazi_ma_non_delle_maiuscole(self) -> None:
        corpo = _fixture("airbnb-date-only.ics").replace(
            "UID:aaaa1111-0001@example.com", "UID:  AAAA1111-0001@example.com  "
        )
        evento = normalizza(analizza_feed(corpo).eventi[0])
        assert evento.ical_uid == "AAAA1111-0001@example.com"

    def test_un_uid_molto_lungo_non_rompe_nulla(self) -> None:
        uid_lungo = "u" * 480 + "@example.com"
        corpo = _fixture("airbnb-date-only.ics").replace(
            "UID:aaaa1111-0001@example.com", f"UID:{uid_lungo}"
        )
        assert normalizza(analizza_feed(corpo).eventi[0]).ical_uid == uid_lungo


class TestTipoDiData:
    def test_value_date_produce_un_intervallo_semiaperto(self) -> None:
        # DTEND in iCal è già ESCLUSIVO per i VALUE=DATE: la corrispondenza
        # con AD-3 [check_in, check_out) è esatta e va asserita, non assunta.
        evento = normalizza(analizza_feed(_fixture("airbnb-date-only.ics")).eventi[0])
        assert evento.soggiorno.check_in == date(2026, 8, 10)
        assert evento.soggiorno.check_out == date(2026, 8, 14)
        assert evento.soggiorno.nights == 4

    def test_una_sola_notte_e_ammessa(self) -> None:
        evento = normalizza(analizza_feed(_fixture("airbnb-date-only.ics")).eventi[1])
        assert evento.soggiorno.nights == 1

    def test_datetime_utc_si_riporta_al_giorno_locale_di_roma(self) -> None:
        eventi = _eventi_per_uid("booking-tzid-dst.ics")
        evento = normalizza(eventi["bbbb2222-utc@example.com"])
        # 20260301T230000Z in Europe/Rome è il 2 marzo alle 00:00.
        assert evento.soggiorno.check_in == date(2026, 3, 2)
        assert evento.soggiorno.check_out == date(2026, 3, 3)

    def test_un_datetime_senza_fuso_si_legge_come_ora_locale_di_roma(self) -> None:
        corpo = (
            _fixture("airbnb-date-only.ics")
            .replace("DTSTART;VALUE=DATE:20260810", "DTSTART:20260810T150000")
            .replace("DTEND;VALUE=DATE:20260814", "DTEND:20260814T100000")
        )
        evento = normalizza(analizza_feed(corpo).eventi[0])
        assert evento.soggiorno.check_in == date(2026, 8, 10)
        assert evento.soggiorno.check_out == date(2026, 8, 14)


class TestFusiEOraLegale:
    def test_il_soggiorno_a_cavallo_dell_ora_legale_di_marzo(self) -> None:
        eventi = _eventi_per_uid("booking-tzid-dst.ics")
        evento = normalizza(eventi["bbbb2222-marzo@example.com"])
        assert evento.soggiorno.check_in == date(2026, 3, 28)
        assert evento.soggiorno.check_out == date(2026, 3, 30)
        assert evento.soggiorno.nights == 2

    def test_il_soggiorno_a_cavallo_del_ritorno_all_ora_solare(self) -> None:
        eventi = _eventi_per_uid("booking-tzid-dst.ics")
        evento = normalizza(eventi["bbbb2222-ottobre@example.com"])
        assert evento.soggiorno.check_in == date(2026, 10, 24)
        assert evento.soggiorno.check_out == date(2026, 10, 26)
        assert evento.soggiorno.nights == 2

    def test_un_check_in_dopo_la_mezzanotte_resta_nel_suo_giorno(self) -> None:
        eventi = _eventi_per_uid("booking-tzid-dst.ics")
        evento = normalizza(eventi["bbbb2222-mezzanotte@example.com"])
        assert evento.soggiorno.check_in == date(2026, 9, 5)

    def test_un_tzid_sconosciuto_non_e_normalizzabile(self) -> None:
        corpo = _fixture("booking-tzid-dst.ics").replace(
            "TZID=Europe/Rome:20260328T150000", "TZID=Marte/Olympus:20260328T150000"
        )
        vevent = analizza_feed(corpo).eventi[0]
        with pytest.raises(EventoNonNormalizzabileError):
            normalizza(vevent)


class TestDurata:
    def test_duration_in_giorni_sostituisce_dtend(self) -> None:
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        evento = normalizza(eventi["7777-durata@example.com"])
        assert evento.soggiorno.nights == 3
        assert evento.soggiorno.check_out == date(2026, 10, 13)

    def test_duration_con_parte_oraria(self) -> None:
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        evento = normalizza(eventi["7777-durata-oraria@example.com"])
        assert evento.soggiorno.check_in == date(2026, 10, 20)
        assert evento.soggiorno.check_out == date(2026, 10, 23)

    def test_senza_dtend_e_senza_duration_non_e_normalizzabile(self) -> None:
        eventi = _eventi_per_uid("eventi-malformati.ics")
        with pytest.raises(EventoNonNormalizzabileError):
            normalizza(eventi["ffff6666-senza-fine@example.com"])

    def test_date_invertite_sono_rifiutate_mai_un_intervallo_vuoto(self) -> None:
        eventi = _eventi_per_uid("eventi-malformati.ics")
        with pytest.raises(EmptyDateRangeError):
            normalizza(eventi["ffff6666-invertite@example.com"])

    def test_zero_notti_e_rifiutato(self) -> None:
        eventi = _eventi_per_uid("eventi-malformati.ics")
        with pytest.raises(EmptyDateRangeError):
            normalizza(eventi["ffff6666-stessa-data@example.com"])

    def test_una_duration_non_interpretabile_non_e_normalizzabile(self) -> None:
        corpo = _fixture("semantica-e-durata.ics").replace("DURATION:P3D", "DURATION:X")
        eventi = {
            vevent.uid: vevent for vevent in analizza_feed(corpo).eventi if vevent.uid
        }
        with pytest.raises(EventoNonNormalizzabileError):
            normalizza(eventi["7777-durata@example.com"])

    def test_un_evento_regolare_nello_stesso_feed_non_si_perde(self) -> None:
        eventi = _eventi_per_uid("eventi-malformati.ics")
        buono = normalizza(eventi["ffff6666-buono@example.com"])
        assert buono.soggiorno.nights == 2


class TestSemantica:
    def test_status_cancelled_marca_l_evento_cancellato(self) -> None:
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        evento = normalizza(eventi["7777-cancellato@example.com"])
        assert evento.cancellato is True

    def test_un_evento_senza_status_non_e_cancellato(self) -> None:
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        assert normalizza(eventi["7777-durata@example.com"]).cancellato is False

    def test_transp_transparent_si_importa_comunque(self) -> None:
        # Comportamento DICHIARATO: le OTA usano TRANSP in modo non
        # affidabile e un blocco date trasparente occupa comunque
        # l'appartamento. Ignorarlo perderebbe una Prenotazione (NFR-1).
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        evento = normalizza(eventi["7777-trasparente@example.com"])
        assert evento.cancellato is False
        assert evento.soggiorno.nights == 2

    def test_una_rrule_entra_come_singola_occorrenza_ed_e_segnalata(self) -> None:
        # L'MVP non espande le ricorrenze. Un evento ricorrente ignorato in
        # silenzio sarebbe una Prenotazione persa (NFR-1): entra come prima
        # occorrenza e il flag lo rende visibile a chi guarda il sync.
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        evento = normalizza(eventi["7777-ricorrente@example.com"])
        assert evento.ricorrente is True
        assert evento.soggiorno.check_in == date(2026, 9, 1)
        assert evento.soggiorno.check_out == date(2026, 9, 3)

    def test_exdate_e_letto_ma_non_applicato(self) -> None:
        # Comportamento DICHIARATO: senza espansione delle ricorrenze un
        # EXDATE non ha niente da escludere. Il valore c'e' nel VEVENT e non
        # tocca l'intervallo dell'occorrenza base.
        eventi = _eventi_per_uid("semantica-e-durata.ics")
        vevent = eventi["7777-ricorrente@example.com"]
        assert vevent.valore("EXDATE") == "20260915"
        evento = normalizza(vevent)
        assert evento.soggiorno.check_in == date(2026, 9, 1)
        assert evento.soggiorno.check_out == date(2026, 9, 3)


class TestSommario:
    def test_il_sommario_arriva_nell_evento_normalizzato(self) -> None:
        evento = normalizza(analizza_feed(_fixture("airbnb-date-only.ics")).eventi[0])
        assert evento.sommario == "Prenotazione inventata 1"

    def test_un_sommario_oltre_il_limite_di_colonna_si_tronca(self) -> None:
        corpo = _fixture("airbnb-date-only.ics").replace(
            "SUMMARY:Prenotazione inventata 1", "SUMMARY:" + "x" * 600
        )
        evento = normalizza(analizza_feed(corpo).eventi[0])
        assert evento.sommario is not None
        assert len(evento.sommario) == 500

"""Unit della politica di uscita di rete verso i Feed iCal (NFR-17, E2-G2).

L'URL del Feed è input non fidato che il server dereferenzia: è la
definizione di SSRF. Qui la matrice degli indirizzi è esaustiva e costa
millisecondi — nessuna rete, il risolutore DNS è iniettato.

Due errori distinti, e la distinzione è il punto:
- `UrlFeedNonValidoError` si scopre SENZA rete (schema, host) ⇒ 422 inline;
- `DestinazioneNonAmmessaError` viene dall'indirizzo risolto e in superficie
  diventa lo stesso «non raggiungibile» di una connessione fallita, così
  l'errore non rivela l'esito della risoluzione.
"""

import ipaddress

import pytest

from app.calendario.uscita_rete import (
    DestinazioneNonAmmessaError,
    PoliticaUscitaRete,
    UrlFeedNonValidoError,
    url_redatto,
    valida_destinazione,
    valida_formato,
)
from app.core.config import Settings

POLITICA = PoliticaUscitaRete(
    timeout_connessione_secondi=1.0,
    timeout_lettura_secondi=1.0,
    dimensione_massima_byte=1024,
    max_redirect=2,
)


def _risolutore(mappa: dict[str, list[str]]):
    def risolvi(host: str) -> list[str]:
        return mappa[host]

    return risolvi


class TestSchemi:
    @pytest.mark.parametrize(
        "url",
        [
            "http://feed.example.com/calendario.ics",
            "https://feed.example.com/calendario.ics",
            "HTTPS://Feed.Example.COM/calendario.ics",
        ],
    )
    def test_ammette_solo_http_e_https(self, url: str) -> None:
        assert valida_formato(url).scheme in {"http", "https"}

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "gopher://feed.example.com/1",
            "ftp://feed.example.com/calendario.ics",
            "javascript:alert(1)",
            "data:text/calendar,BEGIN:VCALENDAR",
            "webcal://feed.example.com/calendario.ics",
        ],
    )
    def test_rifiuta_ogni_altro_schema(self, url: str) -> None:
        with pytest.raises(UrlFeedNonValidoError):
            valida_formato(url)

    @pytest.mark.parametrize("url", ["", "   ", "feed.example.com/x.ics", "http://"])
    def test_rifiuta_url_senza_schema_o_senza_host(self, url: str) -> None:
        with pytest.raises(UrlFeedNonValidoError):
            valida_formato(url)

    def test_la_validazione_di_formato_non_tocca_la_rete(self) -> None:
        # Un host inesistente supera la validazione SINCRONA: l'errore
        # inline immediato non può dipendere da una risoluzione DNS
        # (test design §4.2-1). Se questa chiamata risolvesse, la guardia
        # di isolamento di rete della suite la farebbe fallire.
        assert valida_formato("https://host-che-non-esiste.invalid/f.ics").hostname == (
            "host-che-non-esiste.invalid"
        )


class TestDenylistDegliIndirizzi:
    @pytest.mark.parametrize(
        "indirizzo",
        [
            "127.0.0.1",  # loopback
            "127.1.2.3",
            "10.0.0.7",  # privati RFC 1918
            "172.16.5.4",
            "192.168.1.10",
            "169.254.169.254",  # metadati d'istanza AWS/Azure/GCP
            "169.254.0.1",  # link-local
            "100.100.100.200",  # metadati Alibaba Cloud
            "100.64.0.1",  # CGNAT
            "0.0.0.0",  # unspecified
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
            "192.0.0.1",  # IETF protocol assignments
        ],
    )
    def test_rifiuta_gli_indirizzi_ipv4_vietati(self, indirizzo: str) -> None:
        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("http://feed.example.com/f.ics"),
                POLITICA,
                _risolutore({"feed.example.com": [indirizzo]}),
            )

    @pytest.mark.parametrize(
        "indirizzo",
        [
            "::1",  # loopback
            "fd00::1",  # unique local
            "fe80::1",  # link-local
            "::ffff:127.0.0.1",  # IPv4-mapped verso loopback
            "::ffff:169.254.169.254",  # IPv4-mapped verso i metadati
            "64:ff9b::7f00:1",  # NAT64 verso loopback
            "::",  # unspecified
        ],
    )
    def test_rifiuta_gli_indirizzi_ipv6_vietati(self, indirizzo: str) -> None:
        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("http://feed.example.com/f.ics"),
                POLITICA,
                _risolutore({"feed.example.com": [indirizzo]}),
            )

    def test_rifiuta_un_ip_letterale_vietato_senza_passare_dal_dns(self) -> None:
        def risolutore_che_non_va_chiamato(host: str) -> list[str]:
            raise AssertionError("un IP letterale non si risolve")

        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("http://169.254.169.254/latest/meta-data/"),
                POLITICA,
                risolutore_che_non_va_chiamato,
            )

    def test_un_solo_indirizzo_vietato_basta_a_rifiutare(self) -> None:
        # DNS a round-robin con un indirizzo pubblico e uno interno: se
        # validassimo «almeno uno va bene» il bypass sarebbe gratuito.
        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("https://feed.example.com/f.ics"),
                POLITICA,
                _risolutore({"feed.example.com": ["93.184.216.34", "10.1.1.1"]}),
            )

    def test_un_host_che_non_risolve_e_una_destinazione_non_ammessa(self) -> None:
        def risolutore_che_fallisce(host: str) -> list[str]:
            raise OSError("Name or service not known")

        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("https://host.invalid/f.ics"),
                POLITICA,
                risolutore_che_fallisce,
            )

    def test_ammette_un_indirizzo_pubblico(self) -> None:
        indirizzi = valida_destinazione(
            valida_formato("https://feed.example.com/f.ics"),
            POLITICA,
            _risolutore({"feed.example.com": ["93.184.216.34", "2606:2800:220::1"]}),
        )
        assert indirizzi == ("93.184.216.34", "2606:2800:220::1")

    def test_ammette_una_porta_non_standard(self) -> None:
        url = valida_formato("https://feed.example.com:8443/f.ics")
        assert url.port == 8443
        assert valida_destinazione(
            url, POLITICA, _risolutore({"feed.example.com": ["93.184.216.34"]})
        )


class TestEsenzioniSorvegliate:
    """L'unica via per ammettere una rete vietata è la configurazione."""

    def test_una_rete_consentita_esplicitamente_passa(self) -> None:
        politica = PoliticaUscitaRete(
            timeout_connessione_secondi=1.0,
            timeout_lettura_secondi=1.0,
            dimensione_massima_byte=1024,
            max_redirect=2,
            reti_consentite=(ipaddress.ip_network("127.0.0.0/8"),),
        )
        assert valida_destinazione(
            valida_formato("http://127.0.0.1:9/f.ics"), politica, _risolutore({})
        ) == ("127.0.0.1",)

    def test_la_configurazione_di_default_non_consente_nessuna_rete(self) -> None:
        # Se questo test cade, la denylist si è allentata per svista: è la
        # ragione per cui il parametro esiste con default vuoto.
        assert PoliticaUscitaRete.da_configurazione(Settings()).reti_consentite == ()

    def test_i_parametri_arrivano_dalla_configurazione_non_dal_codice(self) -> None:
        # NFR-4: timeout e cap sono configurazione. Cambiare l'impostazione
        # deve cambiare la politica, altrimenti sono costanti travestite.
        settings = Settings(
            feed_timeout_connessione_secondi=2.5,
            feed_timeout_lettura_secondi=7.5,
            feed_dimensione_massima_byte=123,
            feed_max_redirect=1,
            feed_reti_consentite="10.0.0.0/8, 127.0.0.0/8",
        )
        politica = PoliticaUscitaRete.da_configurazione(settings)
        assert politica.timeout_connessione_secondi == 2.5
        assert politica.timeout_lettura_secondi == 7.5
        assert politica.dimensione_massima_byte == 123
        assert politica.max_redirect == 1
        assert politica.reti_consentite == (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("127.0.0.0/8"),
        )


class TestCredenzialiNellUrl:
    """Le credenziali nell'URL non si riflettono in log ed errori (AD-16)."""

    def test_url_redatto_nasconde_utente_e_password(self) -> None:
        redatto = url_redatto("https://utente:segretissima@feed.example.com/f.ics")
        assert "segretissima" not in redatto
        assert "utente" not in redatto
        assert redatto == "https://***@feed.example.com/f.ics"

    def test_url_redatto_lascia_intatto_un_url_senza_credenziali(self) -> None:
        assert (
            url_redatto("https://feed.example.com/f.ics?token=x")
            == "https://feed.example.com/f.ics?token=x"
        )

    def test_un_url_con_credenziali_resta_valido(self) -> None:
        url = valida_formato("https://utente:pw@feed.example.com/f.ics")
        assert url.hostname == "feed.example.com"

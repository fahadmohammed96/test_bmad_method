"""Guardia GS-1 (E2-G1): la suite non esce in rete.

Dall'Epic 2 il backend ha per la prima volta codice HTTP in uscita. Un client
dimenticato non-fake produrrebbe una suite non deterministica che colpisce un
servizio di terzi, e il fallimento apparirebbe come **flakiness** — cioè la
forma in cui i difetti smettono di essere cercati.

La fixture `isolamento_di_rete` di `conftest.py` è `autouse`: si applica a
ogni test senza che nessuno debba ricordarsene. Questi test dimostrano che la
guardia **morde davvero**: una guardia che non si verifica è una guardia che
un giorno smette di funzionare in silenzio.
"""

import socket

import pytest

from app.calendario.trasporto import ClientFeedHttp, UrlNonRaggiungibileError
from app.calendario.uscita_rete import (
    DestinazioneNonAmmessaError,
    PoliticaUscitaRete,
    risolutore_di_sistema,
    valida_destinazione,
    valida_formato,
)
from tests.conftest import TentativoDiUscitaDiRete

POLITICA_APERTA = PoliticaUscitaRete(
    timeout_connessione_secondi=1.0,
    timeout_lettura_secondi=1.0,
    dimensione_massima_byte=1024,
    max_redirect=1,
    # Anche ammettendo TUTTO nella politica applicativa, la guardia della
    # suite resta l'ultima linea: sono due difese indipendenti.
    reti_consentite=(),
)


def test_una_connessione_verso_un_indirizzo_pubblico_e_bloccata() -> None:
    with pytest.raises(TentativoDiUscitaDiRete):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_una_socket_verso_un_indirizzo_pubblico_e_bloccata() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as presa:
        with pytest.raises(TentativoDiUscitaDiRete):
            presa.connect(("93.184.216.34", 80))


def test_la_risoluzione_di_un_nome_esterno_e_bloccata() -> None:
    with pytest.raises(TentativoDiUscitaDiRete):
        socket.getaddrinfo("feed.example.com", 443)


def test_anche_il_risolutore_di_produzione_e_bloccato() -> None:
    # `risolutore_di_sistema` è l'unico punto in cui la produzione fa DNS:
    # se un test lo usasse senza iniettare un fake, la guardia lo dice.
    with pytest.raises(TentativoDiUscitaDiRete):
        risolutore_di_sistema("feed.example.com")


def test_il_loopback_resta_ammesso() -> None:
    # Il database dei test e il server HTTP di `tests/server_feed.py` vivono
    # sul loopback: bloccarlo renderebbe la guardia inservibile.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as presa:
        presa.settimeout(0.5)
        # Porta chiusa: ci interessa che la guardia non intervenga, non che
        # qualcuno risponda.
        with pytest.raises(OSError):
            presa.connect(("127.0.0.1", 1))


def test_la_guardia_non_e_assorbita_dalla_conversione_in_destinazione_vietata() -> None:
    # `valida_destinazione` converte `OSError` in `DestinazioneNonAmmessaError`:
    # se la guardia derivasse da `Exception` sarebbe assorbita qui, e un test
    # senza risolutore iniettato passerebbe per il motivo sbagliato.
    with pytest.raises(TentativoDiUscitaDiRete):
        valida_destinazione(
            valida_formato("https://feed.example.com/f.ics"), POLITICA_APERTA
        )
    assert not issubclass(TentativoDiUscitaDiRete, Exception)
    assert not issubclass(TentativoDiUscitaDiRete, DestinazioneNonAmmessaError)


def test_la_guardia_non_e_assorbita_dal_client_del_trasporto() -> None:
    # Stessa proprietà sul percorso completo: `ClientFeedHttp` converte gli
    # errori di rete in `UrlNonRaggiungibileError`, ma non può ingoiare la
    # guardia.
    client = ClientFeedHttp(POLITICA_APERTA)
    with pytest.raises(TentativoDiUscitaDiRete):
        client.scarica("https://feed.example.com/calendario.ics")
    assert not issubclass(TentativoDiUscitaDiRete, UrlNonRaggiungibileError)

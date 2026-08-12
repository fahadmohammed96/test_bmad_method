"""AC 10 — nessun invio reale nella suite: proprietà del TEST, non del prodotto.

La può asserire solo un meta-test. Le difese sono due e sono indipendenti, il
che è il punto: la fixture `isolamento_canale_email` del conftest impedisce di
arrivare al canale di produzione, e GS-1 impedisce comunque la socket a chi ci
arrivasse. Una difesa sola sarebbe un unico punto di rottura silenzioso —
toglierla non farebbe fallire nulla, e la suite comincerebbe a mandare posta.

Questi test dimostrano che mordono davvero: una guardia che non si verifica è
una guardia che un giorno smette di funzionare senza dirlo.
"""

import smtplib

import pytest

from app.core.config import get_settings
from app.notifiche.canali import (
    CanaleEmailNonConfigurato,
    CanaleEmailSmtp,
    ConsegnaFallitaError,
    canale_email_di_produzione,
    canali,
)
from app.notifiche.models import CanaleConsegna
from app.notifiche.registro import Messaggio
from tests.conftest import TentativoDiInvioReale, TentativoDiUscitaDiRete

MESSAGGIO = Messaggio(oggetto="oggetto di prova", corpo="corpo di prova")
DESTINATARIO = "host.di.prova@example.com"


class TestLaGuardiaSulCanale:
    def test_il_canale_email_installato_nella_suite_solleva(self) -> None:
        # Prima difesa: nessun test raggiunge il canale di produzione, nemmeno
        # per sbaglio, e il fallimento è immediato e leggibile.
        with pytest.raises(TentativoDiInvioReale):
            canali.per(CanaleConsegna.EMAIL).invia(DESTINATARIO, MESSAGGIO)

    def test_la_guardia_non_e_assorbita_dal_percorso_di_consegna(self) -> None:
        # Il percorso converte i guasti del canale in un job ritentabile: se
        # la guardia derivasse da `Exception` verrebbe ingoiata lì e il test
        # passerebbe per il motivo sbagliato — un job fallito invece di un
        # invio impedito.
        assert not issubclass(TentativoDiInvioReale, Exception)
        assert not issubclass(TentativoDiInvioReale, ConsegnaFallitaError)

    def test_il_canale_in_app_resta_disponibile(self) -> None:
        # La guardia riguarda ciò che ESCE dal prodotto: bloccare anche
        # l'in-app la renderebbe inservibile, perché quella consegna è una
        # riga di database e non ha destinatari esterni.
        assert canali.per(CanaleConsegna.IN_APP).invia(DESTINATARIO, MESSAGGIO) is None


class TestIlCanaleDiProduzione:
    def test_senza_smtp_configurato_il_canale_fallisce_invece_di_fingere(
        self,
    ) -> None:
        # Il default degli ambienti è «nessun SMTP»: deve produrre un
        # fallimento esplicito, mai una notifica dichiarata inviata e mai
        # partita (NFR-3).
        assert get_settings().smtp_host == ""
        canale = canale_email_di_produzione()
        assert isinstance(canale, CanaleEmailNonConfigurato)
        with pytest.raises(ConsegnaFallitaError):
            canale.invia(DESTINATARIO, MESSAGGIO)

    def test_con_smtp_configurato_il_canale_e_quello_smtp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOSTPILOT_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("HOSTPILOT_SMTP_MITTENTE", "notifiche@example.com")
        get_settings.cache_clear()
        assert isinstance(canale_email_di_produzione(), CanaleEmailSmtp)

    def test_il_canale_smtp_reale_muore_comunque_contro_la_guardia_di_rete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Seconda difesa, indipendente dalla prima: anche installando il
        # canale vero, la suite non esce in rete (GS-1). È ciò che rende le
        # due difese davvero due.
        monkeypatch.setenv("HOSTPILOT_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("HOSTPILOT_SMTP_MITTENTE", "notifiche@example.com")
        get_settings.cache_clear()
        canale = canale_email_di_produzione()
        with pytest.raises(TentativoDiUscitaDiRete):
            canale.invia(DESTINATARIO, MESSAGGIO)


class TestLaComposizioneDelMessaggio:
    def test_il_messaggio_smtp_porta_mittente_destinatario_oggetto_e_corpo(
        self,
    ) -> None:
        # La connessione è un parametro, non un dettaglio nascosto: è ciò che
        # permette di provare la composizione senza una socket.
        spediti = []

        class ConnessioneFinta:
            def __enter__(self) -> "ConnessioneFinta":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def send_message(self, posta: object) -> None:
                spediti.append(posta)

        canale = CanaleEmailSmtp(
            mittente="notifiche@example.com",
            apri_connessione=lambda: ConnessioneFinta(),  # type: ignore[arg-type]
        )
        canale.invia(DESTINATARIO, MESSAGGIO)

        assert len(spediti) == 1
        posta = spediti[0]
        assert posta["From"] == "notifiche@example.com"
        assert posta["To"] == DESTINATARIO
        assert posta["Subject"] == MESSAGGIO.oggetto
        assert MESSAGGIO.corpo in posta.get_content()

    def test_un_guasto_del_trasporto_diventa_una_consegna_fallita(self) -> None:
        # Il chiamante deve poter distinguere «non consegnato» da qualunque
        # altra cosa senza conoscere `smtplib`.
        def esplodi() -> object:
            raise smtplib.SMTPServerDisconnected("relay caduto")

        canale = CanaleEmailSmtp(
            mittente="notifiche@example.com",
            apri_connessione=esplodi,  # type: ignore[arg-type]
        )
        with pytest.raises(ConsegnaFallitaError) as errore:
            canale.invia(DESTINATARIO, MESSAGGIO)
        # La categoria, mai il contenuto: questo testo finisce in
        # `job.last_error`, che nessuno ripulisce (AD-16, NFR-11).
        assert DESTINATARIO not in str(errore.value)
        assert MESSAGGIO.corpo not in str(errore.value)

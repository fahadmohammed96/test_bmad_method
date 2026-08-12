"""AC 5 — le preferenze di notifica dell'Host sono rispettate (FR-20, FR-5).

Il pannello esiste dall'Epic 1 (Story 1.3) **senza consumatori**: questa è la
prima Story in cui può essere ignorato in silenzio, e ignorarlo non
produrrebbe nessun errore — l'Host compilerebbe una preferenza che il sistema
non guarda, che è peggio di un pannello assente.

Qui sta anche la guardia sull'allineamento dei due vocabolari. `identity`
possiede la preferenza (una colonna di `host`), `notifiche` possiede i canali
di consegna: sono due enum in due moduli, e devono restare la stessa lista. Se
`identity` ne aggiungesse uno — web push è già nel Deferred dello spine — un
Host che lo scegliesse resterebbe senza notifiche in uscita e nulla
fallirebbe. È una classe «assenze», quindi va imposta.
"""

import pytest

from app.identity.models import CanaleNotifica
from app.notifiche.models import CanaleConsegna
from app.notifiche.service import canali_da_servire


class TestVocabolariAllineati:
    def test_ogni_canale_preferibile_esiste_come_canale_di_consegna(self) -> None:
        preferibili = {canale.value for canale in CanaleNotifica}
        consegnabili = {canale.value for canale in CanaleConsegna}
        assert preferibili <= consegnabili, (
            f"canali preferibili senza consegna: {sorted(preferibili - consegnabili)} "
            "— un Host che li scegliesse resterebbe senza notifiche, in silenzio"
        )

    @pytest.mark.parametrize("preferito", list(CanaleNotifica))
    def test_ogni_preferenza_produce_almeno_un_canale(
        self, preferito: CanaleNotifica
    ) -> None:
        # Nessuna preferenza deve poter significare «non notificare»: il
        # pannello sceglie DOVE ricevere, non SE ricevere (FR-20).
        assert canali_da_servire(preferito)


class TestCanaliDaServire:
    def test_con_email_preferita_partono_in_app_ed_email(self) -> None:
        assert canali_da_servire(CanaleNotifica.EMAIL) == (
            CanaleConsegna.IN_APP,
            CanaleConsegna.EMAIL,
        )

    def test_con_in_app_preferita_nessuna_email(self) -> None:
        # È la metà osservabile della preferenza: ciò che ESCE dal prodotto e
        # arriva addosso all'Host segue quello che ha scelto.
        assert canali_da_servire(CanaleNotifica.IN_APP) == (CanaleConsegna.IN_APP,)

    @pytest.mark.parametrize("preferito", list(CanaleNotifica))
    def test_l_in_app_c_e_sempre(self, preferito: CanaleNotifica) -> None:
        # L'in-app non è un modo di raggiungere l'Host: è la traccia del fatto
        # dentro il prodotto, quella su cui la Dashboard (2.8) costruirà il
        # badge. Toglierla renderebbe l'app cieca su un Conflitto appena
        # notificato per email.
        assert CanaleConsegna.IN_APP in canali_da_servire(preferito)

    def test_il_default_di_registrazione_e_l_email(self) -> None:
        # Un Host che non ha mai aperto il pannello riceve comunque l'email:
        # il default di `host.canale_notifica_preferito` è `email` dalla
        # Story 1.2, e questa Story è la prima che lo trasforma in un
        # comportamento osservabile.
        from app.identity.models import Host

        assert Host.__table__.c.canale_notifica_preferito.default.arg is (
            CanaleNotifica.EMAIL
        )

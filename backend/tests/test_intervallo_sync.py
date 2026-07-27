"""AC 10 della Story 2.2 — intervallo adattivo, unit e nient'altro.

È una funzione pura da `(adesso, prossimo check-in, parametri)` a un
intervallo: il test design la mette a livello unit e non altrove, e il tempo
si INIETTA — mai uno `sleep` per attendere una scadenza (§5.4).

**Cosa questi test non chiudono.** «In prossimità di check-in» non è
quantificato in `epics.md` (test design §4.2-8): quante ore prima, e rispetto
a quale Prenotazione. Qui si prova che la funzione rispetta i TRE PARAMETRI
proposti dal test design, non che una soglia particolare sia quella giusta —
quella resta una decisione di prodotto, e l'AC 10 resta tracciato come non
chiudibile finché §4.2-8 è aperta.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.calendario.intervallo import (
    ParametriIntervallo,
    ParametriIntervalloNonValidiError,
    intervallo_di_sync,
)
from app.core.config import get_settings
from app.core.date_range import TZ_ROME

PARAMETRI = ParametriIntervallo(
    intervallo_minuti=15,
    intervallo_minimo_minuti=5,
    finestra_prossimita_ore=24,
)

# Mezzogiorno a Roma il 10 agosto 2026 (ora legale: UTC+2).
ADESSO = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)


def calcola(
    prossimo_check_in: date | None,
    *,
    adesso: datetime = ADESSO,
    parametri: ParametriIntervallo = PARAMETRI,
) -> timedelta:
    return intervallo_di_sync(
        adesso=adesso, prossimo_check_in=prossimo_check_in, parametri=parametri
    )


class TestRitmoPieno:
    def test_senza_alcun_check_in_futuro_e_l_intervallo_pieno(self) -> None:
        assert calcola(None) == timedelta(minutes=15)

    def test_un_check_in_lontano_non_accorcia_nulla(self) -> None:
        assert calcola(date(2026, 9, 1)) == timedelta(minutes=15)

    def test_un_check_in_gia_iniziato_non_accorcia_nulla(self) -> None:
        # La finestra è quella che PRECEDE l'arrivo: è lì che una
        # cancellazione tardiva non vista si trasforma in un ospite davanti a
        # una porta chiusa. Dopo, accelerare non serve più a niente.
        assert calcola(date(2026, 8, 10)) == timedelta(minutes=15)

    def test_un_check_in_passato_non_accorcia_nulla(self) -> None:
        assert calcola(date(2026, 7, 1)) == timedelta(minutes=15)


class TestRitmoStretto:
    def test_un_check_in_domani_porta_al_minimo(self) -> None:
        # Mezzanotte dell'11 agosto a Roma è a 14 ore da adesso: dentro la
        # finestra di 24.
        assert calcola(date(2026, 8, 11)) == timedelta(minutes=5)

    def test_il_confine_della_finestra_e_incluso(self) -> None:
        # Adesso = 22:00 del 9 agosto a Roma; il check-in dell'11 comincia
        # esattamente 26 ore dopo → fuori. Con 26 ore di finestra → dentro.
        adesso = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
        assert calcola(date(2026, 8, 11), adesso=adesso) == timedelta(minutes=15)
        larga = ParametriIntervallo(
            intervallo_minuti=15, intervallo_minimo_minuti=5, finestra_prossimita_ore=26
        )
        assert calcola(date(2026, 8, 11), adesso=adesso, parametri=larga) == timedelta(
            minutes=5
        )


class TestFusoOrario:
    def test_il_confronto_usa_l_inizio_del_giorno_a_ROMA(self) -> None:
        # Il check-in è una data di calendario Europe/Rome (AD-3). Il 10
        # agosto 2026 comincia alle 22:00 UTC del 9: un istante appena prima
        # è ancora «domani», uno appena dopo non lo è più.
        inizio_a_roma = datetime(2026, 8, 10, 0, 0, tzinfo=TZ_ROME).astimezone(UTC)
        assert calcola(
            date(2026, 8, 10), adesso=inizio_a_roma - timedelta(minutes=1)
        ) == timedelta(minutes=5)
        assert calcola(
            date(2026, 8, 10), adesso=inizio_a_roma + timedelta(minutes=1)
        ) == timedelta(minutes=15)

    def test_attraverso_il_cambio_dell_ora_l_ora_non_si_perde(self) -> None:
        # L'ultima domenica di ottobre 2026 l'Italia torna all'ora solare: il
        # 25 ottobre dura 25 ore. Sottrarre DATE invece che istanti
        # perderebbe proprio i sessanta minuti che questa regola esiste per
        # proteggere.
        inizio_26_a_roma = datetime(2026, 10, 26, 0, 0, tzinfo=TZ_ROME).astimezone(UTC)
        stretta = ParametriIntervallo(
            intervallo_minuti=15, intervallo_minimo_minuti=5, finestra_prossimita_ore=24
        )
        # 24 ore e mezza prima: fuori finestra, e lo si vede solo contando
        # istanti reali.
        adesso = inizio_26_a_roma - timedelta(hours=24, minutes=30)
        assert calcola(
            date(2026, 10, 26), adesso=adesso, parametri=stretta
        ) == timedelta(minutes=15)
        adesso = inizio_26_a_roma - timedelta(hours=23, minutes=30)
        assert calcola(
            date(2026, 10, 26), adesso=adesso, parametri=stretta
        ) == timedelta(minutes=5)


class TestParametriDiConfigurazione:
    def test_i_valori_arrivano_dai_parametri_non_da_costanti(self) -> None:
        # «Configurabile» si prova cambiando il parametro e vedendo cambiare
        # il risultato: altrimenti è una parola del documento.
        altri = ParametriIntervallo(
            intervallo_minuti=42, intervallo_minimo_minuti=7, finestra_prossimita_ore=48
        )
        assert calcola(None, parametri=altri) == timedelta(minutes=42)
        assert calcola(date(2026, 8, 11), parametri=altri) == timedelta(minutes=7)

    @pytest.mark.parametrize(
        ("minuti", "minimo", "finestra"),
        [
            (15, 0, 24),  # minimo nullo: il poller girerebbe in ciclo stretto
            (15, -5, 24),
            (5, 15, 24),  # pieno più corto del minimo: la regola si inverte
            (15, 5, -1),
        ],
    )
    def test_una_configurazione_assurda_si_rifiuta_alla_costruzione(
        self, minuti: int, minimo: int, finestra: int
    ) -> None:
        # Un parametro sbagliato letto dall'ambiente deve fermare l'avvio, non
        # degradare in un difetto di regime che nessuno collega alla causa: un
        # `intervallo = 0` riaccoderebbe il job già scaduto e il poller
        # consumerebbe la coda di TUTTI gli Host.
        with pytest.raises(ParametriIntervalloNonValidiError):
            ParametriIntervallo(
                intervallo_minuti=minuti,
                intervallo_minimo_minuti=minimo,
                finestra_prossimita_ore=finestra,
            )

    def test_i_default_dell_ambiente_sono_quelli_di_G3_5(self) -> None:
        # G3-5: 15 minuti, adattivo fino a 5. Se qualcuno cambia il default
        # nel codice invece che nell'ambiente, questo test lo dice.
        impostazioni = get_settings()
        assert impostazioni.feed_sync_intervallo_minuti == 15
        assert impostazioni.feed_sync_intervallo_minimo_minuti == 5
        # I default devono essere accettabili dalla validazione, altrimenti
        # il worker non parte affatto.
        ParametriIntervallo(
            intervallo_minuti=impostazioni.feed_sync_intervallo_minuti,
            intervallo_minimo_minuti=impostazioni.feed_sync_intervallo_minimo_minuti,
            finestra_prossimita_ore=impostazioni.feed_sync_finestra_prossimita_ore,
        )

"""Rilevazione dei Conflitti: la REGOLA, senza database (AD-5, AD-3).

Story 2.5 AC 1: «la rilevazione è una funzione pura rieseguita sull'insieme
delle Prenotazioni in stato `attiva` di una Struttura». Se lo è davvero,
l'intera matrice delle sovrapposizioni costa millisecondi ed è **esaustiva**
invece che campionata — e questo file non importa `Session`, `Engine` né
alcun modello: la purezza non è dichiarata, è la firma di questi test.

Il confine è il difetto più probabile dell'intero Epic: `check_out` di una
uguale al `check_in` dell'altra **non è** un Conflitto, perché il turnover
dello stesso giorno è il caso normale di un affitto breve (AD-3). Per questo
i casi al confine sono elencati uno per uno, nei due ordini, invece che
rappresentati da un esempio.
"""

import uuid
from datetime import date

import pytest

from app.calendario.conflitti import (
    CoppiaSovrapposta,
    PrenotazioneAttiva,
    coppie_sovrapposte,
)
from app.core.date_range import DateRange

STRUTTURA = uuid.UUID("11111111-1111-1111-1111-111111111111")
ALTRA_STRUTTURA = uuid.UUID("22222222-2222-2222-2222-222222222222")

# Id ordinati per costruzione: la canonicalizzazione della coppia si osserva
# solo se si sa quale dei due è il minore.
PRIMO = uuid.UUID("00000000-0000-0000-0000-00000000000a")
SECONDO = uuid.UUID("00000000-0000-0000-0000-00000000000b")
TERZO = uuid.UUID("00000000-0000-0000-0000-00000000000c")


def prenotazione(
    identificativo: uuid.UUID,
    *,
    dal: date,
    al: date,
    struttura_id: uuid.UUID = STRUTTURA,
) -> PrenotazioneAttiva:
    return PrenotazioneAttiva(
        id=identificativo,
        struttura_id=struttura_id,
        soggiorno=DateRange(check_in=dal, check_out=al),
    )


class TestConfineDellIntervalloSemiaperto:
    """AC 4: sovrapposizione = intersezione NON vuota di `[in, out)` (AD-3)."""

    @pytest.mark.parametrize(
        ("dal_b", "al_b", "sovrapposte", "caso"),
        [
            (date(2026, 9, 20), date(2026, 9, 25), False, "disgiunte, prima"),
            (date(2026, 10, 10), date(2026, 10, 15), False, "disgiunte, dopo"),
            (date(2026, 9, 26), date(2026, 10, 1), False, "adiacenti: turnover"),
            (date(2026, 10, 3), date(2026, 10, 8), False, "adiacenti: turnover"),
            (date(2026, 10, 2), date(2026, 10, 6), True, "parziale, in coda"),
            (date(2026, 9, 28), date(2026, 10, 2), True, "parziale, in testa"),
            (date(2026, 10, 1), date(2026, 10, 2), True, "inclusa"),
            (date(2026, 9, 29), date(2026, 10, 5), True, "contenente"),
            (date(2026, 10, 1), date(2026, 10, 3), True, "identiche"),
            (date(2026, 10, 2), date(2026, 10, 3), True, "ultima notte in comune"),
        ],
    )
    def test_la_coppia_al_confine(
        self, dal_b: date, al_b: date, sovrapposte: bool, caso: str
    ) -> None:
        # A occupa le notti del 1 e del 2 ottobre: `[2026-10-01, 2026-10-03)`.
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 3))
        b = prenotazione(SECONDO, dal=dal_b, al=al_b)

        assert bool(coppie_sovrapposte([a, b])) is sovrapposte, caso
        # Nei due ordini: un criterio che dipende dall'ordine d'arrivo è la
        # forma in cui «mai Conflitti persi» si perde su un feed che riordina.
        assert bool(coppie_sovrapposte([b, a])) is sovrapposte, caso

    def test_il_turnover_dello_stesso_giorno_non_e_un_conflitto(self) -> None:
        # Il caso normale di un affitto breve: chi parte il 3 e chi arriva il
        # 3 non si incontrano. Vale anche per due soggiorni di una notte.
        uscente = prenotazione(PRIMO, dal=date(2026, 10, 2), al=date(2026, 10, 3))
        entrante = prenotazione(SECONDO, dal=date(2026, 10, 3), al=date(2026, 10, 4))

        assert coppie_sovrapposte([uscente, entrante]) == []

    def test_la_stessa_notte_singola_e_un_conflitto(self) -> None:
        prima = prenotazione(PRIMO, dal=date(2026, 10, 3), al=date(2026, 10, 4))
        seconda = prenotazione(SECONDO, dal=date(2026, 10, 3), al=date(2026, 10, 4))

        assert coppie_sovrapposte([prima, seconda]) == [
            CoppiaSovrapposta(
                struttura_id=STRUTTURA,
                prenotazione_min_id=PRIMO,
                prenotazione_max_id=SECONDO,
            )
        ]


class TestIdentitaDellaCoppia:
    """AC 3 (§4.2-4): `(A,B)` e `(B,A)` sono la STESSA identità."""

    def test_la_coppia_e_canonicalizzata_qualunque_sia_l_ordine(self) -> None:
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))
        b = prenotazione(SECONDO, dal=date(2026, 10, 3), al=date(2026, 10, 7))

        attesa = CoppiaSovrapposta(
            struttura_id=STRUTTURA,
            prenotazione_min_id=PRIMO,
            prenotazione_max_id=SECONDO,
        )
        assert coppie_sovrapposte([a, b]) == [attesa]
        assert coppie_sovrapposte([b, a]) == [attesa]

    def test_una_coppia_sola_per_due_prenotazioni(self) -> None:
        # «Mai due Conflitti aperti per la stessa coppia» comincia qui: se la
        # funzione pura emettesse `(A,B)` e `(B,A)`, il vincolo del database
        # riceverebbe due righe da inserire e ne rifiuterebbe una con un
        # errore — cioè un 500 su un percorso normale.
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))
        b = prenotazione(SECONDO, dal=date(2026, 10, 2), al=date(2026, 10, 4))

        assert len(coppie_sovrapposte([a, b])) == 1

    def test_una_prenotazione_non_e_in_conflitto_con_se_stessa(self) -> None:
        # Il caso non è teorico: basta che il chiamante passi due volte la
        # stessa riga (una lettura ripetuta, una `union` sbagliata) perché una
        # Prenotazione si sovrapponga a sé stessa in modo perfetto.
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))

        assert coppie_sovrapposte([a, a]) == []


class TestUnitaDiRilevazione:
    """AC 9 (§4.2-5): l'unità è la COPPIA, non il gruppo."""

    def test_tre_mutuamente_sovrapposte_danno_tre_conflitti(self) -> None:
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 10))
        b = prenotazione(SECONDO, dal=date(2026, 10, 2), al=date(2026, 10, 9))
        c = prenotazione(TERZO, dal=date(2026, 10, 3), al=date(2026, 10, 8))

        coppie = coppie_sovrapposte([a, b, c])

        assert len(coppie) == 3
        coinvolte = {
            (riga.prenotazione_min_id, riga.prenotazione_max_id) for riga in coppie
        }
        assert coinvolte == {
            (PRIMO, SECONDO),
            (PRIMO, TERZO),
            (SECONDO, TERZO),
        }

    def test_una_catena_produce_solo_le_coppie_che_si_toccano(self) -> None:
        # A-B si sovrappongono, B-C si sovrappongono, A-C no: due Conflitti.
        # Con l'unità «gruppo» ne verrebbe uno solo, e il badge della 2.8
        # conterebbe un numero diverso — che è la ragione per cui §4.2-5 non
        # è un dettaglio interno.
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 4))
        b = prenotazione(SECONDO, dal=date(2026, 10, 3), al=date(2026, 10, 7))
        c = prenotazione(TERZO, dal=date(2026, 10, 6), al=date(2026, 10, 9))

        coppie = coppie_sovrapposte([a, b, c])

        coinvolte = {
            (riga.prenotazione_min_id, riga.prenotazione_max_id) for riga in coppie
        }
        assert coinvolte == {
            (PRIMO, SECONDO),
            (SECONDO, TERZO),
        }


class TestPerimetroDellaStruttura:
    """AC 10: mai un Conflitto fra Strutture diverse (AD-2, AD-3, NFR-14)."""

    def test_due_strutture_diverse_non_producono_conflitti(self) -> None:
        # Stesse identiche date: se la Struttura non entrasse nel criterio,
        # questo sarebbe il Conflitto più «evidente» possibile — ed è invece
        # un Host con due appartamenti pieni la stessa settimana, cioè il
        # caso in cui il prodotto funziona.
        qui = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))
        altrove = prenotazione(
            SECONDO,
            dal=date(2026, 10, 1),
            al=date(2026, 10, 5),
            struttura_id=ALTRA_STRUTTURA,
        )

        assert coppie_sovrapposte([qui, altrove]) == []

    def test_le_coppie_restano_dentro_la_propria_struttura(self) -> None:
        qui_a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))
        qui_b = prenotazione(SECONDO, dal=date(2026, 10, 2), al=date(2026, 10, 6))
        altrove = prenotazione(
            TERZO,
            dal=date(2026, 10, 1),
            al=date(2026, 10, 6),
            struttura_id=ALTRA_STRUTTURA,
        )

        coppie = coppie_sovrapposte([qui_a, qui_b, altrove])

        assert coppie == [
            CoppiaSovrapposta(
                struttura_id=STRUTTURA,
                prenotazione_min_id=PRIMO,
                prenotazione_max_id=SECONDO,
            )
        ]


class TestDeterminismo:
    """La stessa rilevazione, rieseguita, dà lo stesso risultato (AD-5)."""

    def test_l_esito_non_dipende_dall_ordine_dell_insieme(self) -> None:
        a = prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 6))
        b = prenotazione(SECONDO, dal=date(2026, 10, 2), al=date(2026, 10, 7))
        c = prenotazione(TERZO, dal=date(2026, 10, 3), al=date(2026, 10, 8))

        # Non solo lo stesso INSIEME: la stessa SEQUENZA. Un ordine che
        # dipende dal piano del database renderebbe irriproducibile ogni
        # confronto fra due esecuzioni, a partire da questi test.
        assert coppie_sovrapposte([a, b, c]) == coppie_sovrapposte([c, b, a])

    def test_l_insieme_vuoto_e_la_prenotazione_sola_non_producono_nulla(self) -> None:
        assert coppie_sovrapposte([]) == []
        assert (
            coppie_sovrapposte(
                [prenotazione(PRIMO, dal=date(2026, 10, 1), al=date(2026, 10, 5))]
            )
            == []
        )

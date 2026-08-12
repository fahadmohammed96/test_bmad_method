"""AC 9 — il copy è funzione pura del dato, in italiano (NFR-9, UX-DR11).

Unit, e nient'altro: non c'è database, non c'è orologio, non c'è sessione. È
proprio l'assenza dell'orologio la proprietà che vale la pena provare — un
formato che dipende dall'anno corrente produrrebbe due testi diversi per lo
stesso Conflitto a seconda di quando lo si consegna, e il test che lo scopre
sarebbe rosso solo a Capodanno.

L'intervallo si stampa in NOTTI: il soggiorno è semiaperto [check_in,
check_out) (AD-3), quindi il `check_out` non è una notte occupata. Scriverlo
darebbe all'Host un giorno in più proprio nel messaggio con cui deve decidere
se ha una doppia prenotazione.
"""

from datetime import date

import pytest

from app.notifiche.testo import MESI_IT, intervallo_it


class TestIntervalloIt:
    def test_l_esempio_dell_epic(self) -> None:
        # «Bologna Centro, 15-17 agosto» di `epics.md`: tre notti, dal 15 al
        # 17 compresi, quindi check_out il 18.
        assert intervallo_it(date(2026, 8, 15), date(2026, 8, 18)) == "15-17 agosto"

    def test_una_notte_sola_non_diventa_un_intervallo(self) -> None:
        # «15-15 agosto» si legge come un errore di battitura.
        assert intervallo_it(date(2026, 8, 15), date(2026, 8, 16)) == "15 agosto"

    def test_il_check_out_non_e_una_notte(self) -> None:
        # La proprietà da cui dipendono tutti gli altri casi (AD-3).
        assert intervallo_it(date(2026, 8, 15), date(2026, 8, 17)) == "15-16 agosto"

    def test_a_cavallo_di_due_mesi_il_mese_compare_due_volte(self) -> None:
        assert (
            intervallo_it(date(2026, 8, 30), date(2026, 9, 2))
            == "30 agosto - 1 settembre"
        )

    def test_a_cavallo_di_due_anni_compare_l_anno(self) -> None:
        # Senza anno, «30 dicembre - 1 gennaio» non dice quale dei due anni
        # sia quale: è la sola forma in cui l'ambiguità è nel dato.
        assert (
            intervallo_it(date(2026, 12, 30), date(2027, 1, 2))
            == "30 dicembre 2026 - 1 gennaio 2027"
        )

    def test_l_anno_non_compare_quando_l_intervallo_non_lo_attraversa(self) -> None:
        # Il complemento del caso sopra: se comparisse sempre, il formato
        # dell'esempio dell'Epic sarebbe sbagliato.
        assert "2026" not in intervallo_it(date(2026, 1, 1), date(2026, 1, 3))

    def test_il_giorno_non_e_zero_paddato(self) -> None:
        # «01-03 agosto» non è italiano corrente: è il formato numerico
        # gg/mm/aaaa applicato dove serve un testo.
        assert intervallo_it(date(2026, 8, 1), date(2026, 8, 4)) == "1-3 agosto"

    def test_un_intervallo_senza_notti_e_rifiutato(self) -> None:
        # Non esiste un testo giusto per un intervallo vuoto: inventarne uno
        # sarebbe un messaggio su notti che nessuno ha prenotato.
        with pytest.raises(ValueError):
            intervallo_it(date(2026, 8, 15), date(2026, 8, 15))

    def test_il_testo_non_dipende_dall_orologio(self) -> None:
        # La proprietà di purezza, asserita direttamente: la stessa coppia di
        # date produce la stessa stringa sempre. Un `today()` dentro la
        # funzione la romperebbe solo in certi giorni dell'anno, cioè
        # apparirebbe come flakiness.
        prima = intervallo_it(date(2026, 8, 15), date(2026, 8, 18))
        dopo = intervallo_it(date(2026, 8, 15), date(2026, 8, 18))
        assert prima == dopo == "15-17 agosto"


class TestMesiIt:
    def test_i_dodici_mesi_sono_in_italiano_e_minuscoli(self) -> None:
        assert len(MESI_IT) == 12
        assert MESI_IT[0] == "gennaio"
        assert MESI_IT[11] == "dicembre"
        assert all(mese == mese.lower() for mese in MESI_IT)

    @pytest.mark.parametrize("mese", range(1, 13))
    def test_ogni_mese_dell_anno_ha_il_suo_nome(self, mese: int) -> None:
        # Un `IndexError` su dicembre sarebbe un errore che compare una volta
        # l'anno: qui si presenta subito.
        testo = intervallo_it(date(2026, mese, 1), date(2026, mese, 2))
        assert testo == f"1 {MESI_IT[mese - 1]}"

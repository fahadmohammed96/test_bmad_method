"""Modulo `calendario`: Feed iCal, Prenotazioni, run di sincronizzazione.

Proprietario unico scrittore di `feed_ical`, `sync_run` e `prenotazione`
(AD-18). L'import è append-preserving: una Prenotazione si transiziona,
mai si cancella (AD-4, AD-19, AD-20).
"""

"""Modulo `notifiche` — la fondazione dei canali verso l'Host (AD-13, AD-10).

Nasce con la Story 2.6 per le notifiche di Conflitto ed è riusato dall'Epic 3
(promemoria ed escalation degli Adempimenti) e dall'Epic 5 (Messaggi Ospiti).
Per questo **non conosce il dominio che lo chiama**: il tipo di notifica è una
stringa a catalogo e il testo lo compone un `Compositore` registrato dalla
radice di composizione (`app/cablaggio.py`), mai un import di `calendario`.

Le due sole dipendenze ammesse dallo spine sono `core` e `identity` in sola
lettura (destinatario e preferenze); nessun modulo dipende sincronicamente da
`notifiche`, che si raggiunge solo per evento o per job. La guardia
strutturale `tests/test_grafo_moduli.py` (GS-3) lo impone: è una regola che
un import sbagliato non violerebbe rumorosamente — tacerebbe, e si
scoprirebbe quando l'Epic 3 prova a riusare il modulo e se lo trova legato al
calendario.
"""

# Corpus di fixture iCal (test design Epic 2, §5.2)

Un file per **forma** del feed, con un nome che dice il caso. Sono dati:
si leggono in diff e si rivedono in PR.

**Limite dichiarato, non garanzia.** Il corpus è modellato su RFC 5545 e
sulla forma documentata degli export Airbnb/Booking, **non catturato da
feed reali**. Copre robustezza e regressione; **non** copre la fedeltà — se
un portale usa una proprietà che non abbiamo immaginato, nessuna fixture lo
rivela (è il punto A11 del test design, che resta aperto).

Quando una forma nuova si incontra in esercizio, **entra qui come fixture
prima** che il codice venga corretto: è il ciclo rosso→verde applicato a un
formato che non controlliamo.

**Nessun dato reale (NFR-16).** Nomi ed email sono inventati e su dominio
`example.com`; nessun `.ics` proveniente da un account reale entra nel
repository, nemmeno «anonimizzato»: un `UID` reale è un identificatore, e il
nome di una Struttura reale pure.

I file sono in LF. Le varianti puramente testuali del *trasporto* (CRLF, BOM
iniziale) si costruiscono nel test a partire da queste, perché un BOM o un
CRLF sono invisibili in una review: metterli in un file darebbe l'illusione
di un caso coperto senza mostrare quale.

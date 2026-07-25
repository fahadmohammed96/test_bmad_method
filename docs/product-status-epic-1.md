---
title: 'Stato del prodotto — HostPilot a fine Epic 1'
status: 'fotografia a fine Epic 1 (debito zero, vedi docs/qa/test-design-epic-1.md §7.6)'
created: 2026-07-25
author: Paige — Technical Writer
audience: 'chi arriva sul progetto dopo — umano o agente — e vuole sapere cosa fa il prodotto oggi, senza leggere codice o piano'
inputDocuments:
  - main @ 61d7ac4 (verità sul codice)
  - docs/qa/test-design-epic-1.md §7.1–§7.7 (matrice di chiusura Epic 1, mappa di ciò che è verificato)
  - docs/architecture.md, docs/epics.md, docs/prd.md (visione e piano — non fonte di verità sul "cosa fa oggi")
related:
  - docs/architecture.md (fondamenta tecniche, in dettaglio)
  - docs/epics.md (piano completo, Epic 2+)
---

# Stato del prodotto — HostPilot a fine Epic 1

> Questo documento risponde a una sola domanda: **cosa può fare oggi un Host che usa HostPilot?**
> Non "cosa è stato progettato", non "cosa arriverà" — cosa è vero adesso, verificato sul
> codice in `main` (commit `61d7ac4`), non sui documenti di piano. Dove PRD/epics/story e
> codice divergono, vince il codice: qui non risultano divergenze aperte.

## 1. In una frase

HostPilot oggi è **l'ingresso e la casa base di un Host**: si registra, accede, e censisce
fino a 3 Strutture con l'inquadramento normativo del Comune in cui si trovano e il proprio
Regime fiscale. Tutto il resto del prodotto — calendario, prezzi, adempimenti, pulizie e
messaggi — è visibile in navigazione ma esplicitamente **non ancora costruito**.

## 2. Cosa può fare un Host oggi

### 2.1 Account e accesso

Un Host si registra con email e password, accede con una sessione server-side (non un token
nel browser) e gestisce le proprie preferenze da una pagina Account dedicata. Non esiste
ancora un flusso di recupero password né autenticazione a più fattori: fuori scopo per il
pilota.

### 2.2 App navigabile in italiano

L'app ha una shell con **5 voci di navigazione**: Dashboard, Strutture, Calendario, Prezzi,
Adempimenti, Operatività. Tutta l'interfaccia è in italiano, inclusi i formati di data e
valuta. La Dashboard mostra oggi uno stato vuoto onesto — non un dato vuoto travestito da
errore — con i riquadri di Calendario, Adempimenti e Prezzi pronti ad accogliere contenuto
quando quegli Epic arriveranno.

### 2.3 Strutture: fino a 3, con archiviazione

Un Host registra le proprie Strutture (l'appartamento o le poche unità che gestisce), fino a
un **cap di 3 attive** applicato in modo atomico anche sotto richieste concorrenti — due
richieste di creazione contemporanee non riescono a superare il cap. Una Struttura può essere
**archiviata**, mai cancellata: la storia resta, coerente con la scelta di prodotto di non
distruggere mai dati operativi.

### 2.4 Anagrafica Comune/Regione e configurazione normativa

Alla creazione di una Struttura, l'Host la lega a un Comune/Regione dell'anagrafica ISTAT
integrata nel prodotto. Da quel legame il sistema deriva la **configurazione normativa**
applicabile (soglie, aliquote) in quel momento: i parametri normativi sono trattati come dati
versionati nel tempo, non come costanti nel codice, cosa che permette di aggiornarli quando
cambia una delibera comunale senza un rilascio software. Se l'anagrafica per un Comune non è
disponibile, il prodotto degrada in modo sicuro (nessun dato inventato, nessun crash) invece
di bloccare l'Host.

### 2.5 Regime fiscale — segnalato, non un adempimento

In base al numero di Strutture registrate, il prodotto **segnala** all'Host il Regime fiscale
che presumibilmente lo riguarda. È un'informazione derivata al volo dal numero di Strutture
attive — **mai salvata** come dato persistito — e non sostituisce una consulenza fiscale: è un
aiuto a orientarsi, non una dichiarazione.

## 3. Confini onesti — cosa non c'è ancora

Le voci di navigazione Calendario, Adempimenti, Prezzi e Operatività **esistono nell'app**,
ma aprendole l'Host trova una pagina che dichiara esplicitamente "arriva con un prossimo ciclo
di lavoro" — non una pagina rotta, non un placeholder silenzioso scambiabile per un bug:

- **Calendario unificato e sync iCal**: nessuna sincronizzazione con Airbnb/Booking, nessun
  rilevamento di doppie prenotazioni. Arriva con l'Epic che introduce il calendario.
- **Motore di Regole di prezzo**: nessuna regola di prezzo, nessuna anteprima.
- **Adempimenti italiani** (Alloggiati Web/Questura, tassa di soggiorno, ISTAT, CIN): nessuna
  compilazione assistita, nessun promemoria di scadenza. Solo la configurazione normativa di
  base (§2.4) è pronta come fondamenta per questo Epic.
- **Operatività** (turni di pulizia, messaggi automatici agli Ospiti): non esiste ancora.

Nessuna di queste assenze è un difetto: è la sequenza di consegna pianificata (vedi
`docs/epics.md` per il piano completo). Il punto di questa sezione è che un lettore non deve
*dedurre* dall'assenza — l'app stessa lo dichiara.

## 4. Fondamenta tecniche (per chi arriva dopo)

Questa sezione non duplica `docs/architecture.md` — vi rimanda per il dettaglio. Qui solo il
livello che serve a orientarsi:

- **Monorepo**, monolite modulare + worker: un backend FastAPI, un frontend Next.js, un
  worker per i job durevoli, un solo PostgreSQL. Nessun microservizio, nessuna coda esterna
  (Redis/broker) alla scala del pilota — vedi `docs/architecture.md` §1.
- **Kernel `core`**: le convenzioni condivise (tenancy, outbox, scheduling dei job) vivono in
  un modulo comune riusato da ogni feature, non reinventate story per story.
- **Job durevoli e outbox transazionale**: gli effetti asincroni (es. eventi generati da
  un'azione dell'Host) sono scritti nella stessa transazione del dato che li genera e
  processati da un worker con retry e backoff — mai un timer in-memory che si perde a un
  riavvio.
- **Contratto API `/api/v1`**: un solo schema OpenAPI generato dal backend, da cui il client
  TypeScript del frontend è generato — i due lati non possono divergere silenziosamente (una
  CI dedicata lo verifica a ogni cambiamento).
- **Tenancy per `host_id`**: ogni tabella e ogni endpoint che tocca dati di un Host è
  sorvegliato da una guardia strutturale automatica, non solo da una convenzione scritta —
  un Host non può leggere o scrivere dati di un altro Host per costruzione verificata.

Per l'elenco completo degli invarianti architetturali (AD-1…AD-20) e la loro copertura di
test, vedi `docs/qa/test-design-epic-1.md` §7.2.

## 5. Qualità alla chiusura dell'Epic

Il Test Architect (Murat) ha dichiarato l'Epic 1 **chiuso a debito zero** il 2026-07-25: 9
finding di qualità/sicurezza emersi durante l'Epic, tutti chiusi con una PR e un test di
regressione nominato; 48 acceptance criteria su 48 coperti da test verdi al livello previsto;
CI verde su `main` sui cinque check obbligatori. Restano 4 rischi noti e accettati
consapevolmente (non debito) con un momento preciso per rivalutarli — advisory di sicurezza
transitivi nella toolchain frontend, il freno anti-abuso login basato sull'origine di rete
dietro un eventuale reverse proxy futuro, il namespace del primo advisory lock Postgres, la
copertura e2e volutamente stretta. Il dettaglio completo, verificabile riga per riga, è in
`docs/qa/test-design-epic-1.md` §7.4–§7.7.

---

_Fotografia valida per il commit `61d7ac4` (fine Epic 1). Aggiornare o sostituire con
l'equivalente per l'Epic successivo quando quell'Epic chiude — non incrementare questo
documento in-place oltre l'Epic 1._

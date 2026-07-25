---
title: 'PRD — HostPilot'
status: approved
gate: G2
gate_status: 'approvato da Fahad al gate G3 (2026-07-24), insieme a UX Spec, Architettura, Epics/Stories e Readiness. Esiti [DECISIONE G2] registrati in §14. Ultimi punti aperti (set G2-B, owner R-5) chiusi da Fahad il 2026-07-25 — §14.1.'
created: 2026-07-24
updated: 2026-07-25
author: John — Product Manager
phase: '2 · Planning'
depends_on:
  - docs/project-brief.md (approvato, gate G1)
  - docs/project-context.md (costituzione di progetto)
related:
  - UX Spec (Sally) — issue separata, co-input del gate G2
  - Architettura + Epics/Stories (Winston) — Fase 3, gate G3
---

# PRD: HostPilot

> Gestionale in abbonamento per l'host privato italiano di affitti brevi (1-3 unità): calendario unificato, prezzi, adempimenti italiani.

## 0. Scopo del documento

Questo PRD è l'artefatto principale della **Fase 2 (Planning)** del pilota BMAD Squad. È scritto per l'umano decisore (Fahad, al gate **G2**), per Sally (UX Spec, co-input dello stesso gate) e per Winston (Fase 3 — Architettura + Epics/Stories, che ne è il consumatore a valle). Costruisce sul **Project Brief approvato** (`docs/project-brief.md`, gate G1) e sulla **costituzione di progetto** (`docs/project-context.md`); non li duplica — dove serve, li referenzia.

Struttura: vocabolario ancorato al **Glossario** (§4, usato verbatim ovunque), feature raggruppate con requisiti funzionali (**FR-N**) numerati globalmente e stabili, requisiti non funzionali trasversali separati, assunzioni marcate inline con `[ASSUNZIONE]` e indicizzate in §16. Le **decisioni di prodotto** non chiuse dal brief non sono decise qui: sono presentate come **opzioni con trade-off e una raccomandazione** e raccolte in §14 (`[DECISIONE G2]`) per la chiusura al gate. Coerente con `project-context.md` §2: mai colmare un bivio di prodotto con una scelta d'ufficio.

**Vincoli di consegna** (da `project-context.md` §4): documento in italiano, in `docs/`, consegnato via Pull Request verso `main`, mai push diretto. Il merge e l'approvazione del gate sono dell'umano.

---

## 1. Vision

HostPilot è l'unico posto dove l'host privato italiano di affitti brevi guarda ogni settimana per gestire calendario, prezzo e adempimenti — al posto delle 5-6 schede di browser e del foglio Excel che usa oggi. È dimensionato esplicitamente per **1-3 unità** gestite in proprio, non per il property manager multi-unità: il valore non è la potenza di un PMS, è togliere all'host il rischio di una doppia prenotazione e la paura di una scadenza normativa dimenticata.

Il prodotto tiene insieme quattro pilastri — calendario unificato con anti double-booking, motore di regole di prezzo, adempimenti italiani "in regola", operatività (pulizie + messaggi ospiti) — con una tesi di fondo: per questo segmento la profondità della **copertura normativa italiana nativa** (Alloggiati Web, tassa di soggiorno comunale, ISTAT/ROSS1000, CIN) e la cura dell'esperienza per un utente non tecnico valgono più di qualsiasi sofisticazione tecnica. HostPilot **assiste e ricorda**; non sostituisce il commercialista e non certifica al posto di un professionista.

Se il pilota valida ritenzione e disponibilità a pagare sul segmento privato, la direzione a 2-3 anni è l'estensione al property manager multi-unità — esplicitamente fuori dallo scope di questo MVP.

---

## 2. Perché ora (timing normativo)

Il timing è **portante**, non incidentale: la normativa italiana sugli affitti brevi si è irrigidita nel biennio 2025-2026 proprio mentre il segmento target si trova a ridosso delle nuove soglie critiche.

- **CIN obbligatorio** dal 2 gennaio 2025, "a regime" nel 2026, esposto in ogni annuncio; sanzioni citate fino a **8.000€ per immobile** senza CIN.
- **Soglia dei tre immobili** (Legge di Bilancio 2026): dal 3° immobile scatta la presunzione di imprenditorialità e l'obbligo di Partita IVA — soglia abbassata da 5 a 3 unità, esattamente dentro la fascia target del pilota.
- **Alloggiati Web** trattato come **reato** (non semplice sanzione amministrativa) in caso di omissione, con termini stretti (24h dall'arrivo, 6h per soggiorni < 24h).

> ⚠️ Tutte le cifre e qualificazioni normative provengono dalla ricerca del brief (§ "Ricerca normativa"), basata su **fonti editoriali di settore, non testi di legge primari**. Restano da verificare con un commercialista/legale **prima dell'implementazione** delle funzionalità di compliance (non prima del PRD). Vedi §15 Rischi.

L'implicazione di prodotto: HostPilot deve nascere come **strumento di compliance-assistita**, con l'urgenza percepita dall'host come leva di adozione primaria — da bilanciare però con l'assunzione non ancora validata su quanto l'host *senta* davvero questo rischio (§15).

---

## 3. Utente target

### 3.1 Jobs To Be Done

L'host privato italiano, 1-3 appartamenti, gestione diretta su Airbnb e/o Booking.com, non tecnico, oggi su Excel:

- **Funzionale — "Nessuno deve prenotare due volte lo stesso appartamento lo stesso giorno."** Oggi riconcilia calendari a mano perché i feed OTA sono di sola lettura e non in tempo reale.
- **Funzionale — "Non voglio più dimenticare una comunicazione obbligatoria."** Alloggiati Web, tassa di soggiorno, ISTAT/ROSS1000, CIN: scadenze strette, sparse su portali diversi, ciascuno con login e logica proprie.
- **Funzionale — "Voglio impostare prezzi per stagione/weekend/last-minute senza ricalcolare tutto a mano."**
- **Funzionale — "Voglio coordinare pulizie e messaggi ospiti senza rincorrere WhatsApp e promemoria sparsi."**
- **Emotivo — "Voglio dormire tranquillo": non temere una sanzione per dimenticanza** e non fare brutta figura con l'ospite per un doppio-booking.
- **Sociale — "Non voglio sembrare un dilettante"** né dover chiamare il commercialista per ogni dubbio operativo.

### 3.2 Non-utenti (v1)

- **Property manager multi-unità** (5+ unità, ruoli, reportistica aggregata): fuori scope, ottica futura. Feature e pricing per questo segmento non vanno progettati ora per non diluire il focus.
- **Host che vuole delegare tutto** (consulenza fiscale/dichiarativa sostitutiva del commercialista): HostPilot assiste e ricorda, non decide né certifica.
- **Host non italiano / immobili fuori Italia**: la value proposition è la copertura normativa italiana.

### 3.3 User Journeys

_Narrazioni con protagonista nominato; numerate UJ-1…UJ-N; le FR le referenziano per ID. Persona-context inline. Il dettaglio di schermi e flussi è di competenza della **UX Spec di Sally** — qui si fissa la spina narrativa, lì si disegna._

- **UJ-1. Marco collega i suoi due appartamenti la prima sera.**
  - **Persona + contesto:** Marco, 44 anni, impiegato, due bilocali a Bologna su Airbnb + Booking; oggi tiene tutto su un Excel condiviso con la moglie. Non tecnico.
  - **Stato d'ingresso:** primo accesso, nessun dato inserito.
  - **Percorso:** crea l'account → aggiunge la Struttura "Bologna Centro" → incolla l'URL del feed **iCal** Airbnb e Booking → il sistema importa le prenotazioni esistenti e mostra il **Calendario unificato** → indica il Comune (per la tassa di soggiorno) e inserisce il **CIN** dell'immobile.
  - **Climax:** vede in un'unica griglia le prenotazioni dei due portali e un badge "0 conflitti"; sa che il collegamento ha funzionato.
  - **Risoluzione:** onboarding completato; da qui riceve promemoria e vede i prezzi. **Edge:** se manca il CIN, il sistema non blocca l'onboarding ma segnala un adempimento aperto con priorità.

- **UJ-2. Marco evita una doppia prenotazione durante un ponte.**
  - **Persona + contesto:** alta occupazione, feed OTA non in tempo reale.
  - **Stato d'ingresso:** autenticato, calendario già collegato.
  - **Percorso:** riceve una notifica di **potenziale conflitto** (Airbnb ha una prenotazione che si sovrappone a una Booking, rilevata alla sincronizzazione) → apre la **Finestra di riconciliazione** → vede le due prenotazioni sovrapposte e la fonte/timestamp di ciascuna → conferma quale tenere e blocca le date sull'altro canale.
  - **Climax:** il conflitto è marcato "gestito"; Marco sa che non ospiterà due gruppi la stessa notte.
  - **Risoluzione:** stato pulito. **Edge:** il feed OTA aggiorna con ritardo → il sistema mostra esplicitamente "dati aggiornati alle HH:MM", non finge sincronia istantanea (vincolo tecnico §4/§5).

- **UJ-3. Laura invia la comunicazione Alloggiati Web al check-in.**
  - **Persona + contesto:** Laura, host di un monolocale a Firenze; l'ospite è appena arrivato, il termine legale è stretto.
  - **Percorso:** registra il check-in dell'Ospite → il sistema apre la **compilazione assistita** dei dati del documento d'identità (minimizzati) → Laura verifica i campi precompilati dalla prenotazione → conferma l'invio (assistito o, dove sostenibile, automatico verso Alloggiati Web).
  - **Climax:** riceve conferma dell'avvenuta comunicazione e la scadenza sparisce dalla lista "in sospeso".
  - **Risoluzione:** l'adempimento è tracciato come **completato in tempo**. **Edge:** documento illeggibile/mancante → il sistema tiene la scadenza aperta con un promemoria escalation, non la marca fatta.

- **UJ-4. Laura passa da 2 a 3 immobili e capisce che cambia il regime fiscale.**
  - **Persona + contesto:** Laura acquista un terzo immobile in affitto breve.
  - **Percorso:** aggiunge la 3ª Struttura → il sistema segnala che, secondo la normativa 2026, il 3° immobile fa scattare la **presunzione di imprenditorialità** (Partita IVA, aliquote progressive) → mostra un riepilogo informativo del regime differenziato 1-2 vs. 3 unità e invita a consultare il commercialista.
  - **Climax:** Laura capisce l'impatto **prima** di trovarselo a fine anno.
  - **Risoluzione:** il prodotto riflette il regime corretto ma **non** fa consulenza. **Edge:** copre la segnalazione, non la gestione P.IVA/fatturazione (fuori scope MVP, §8/§9).

- **UJ-5. Marco imposta i prezzi della stagione senza ricalcolare a mano.**
  - **Percorso:** definisce **Regole di prezzo** (alta stagione, weekend, last-minute, soggiorno minimo) → vede l'anteprima del prezzo applicato sul calendario per struttura.
  - **Climax:** un'unica configurazione riempie il calendario; niente più tabelle Excel.
  - **Risoluzione:** i prezzi calcolati sono un **output consultabile/esportabile** dell'host verso i portali (vedi vincolo push-OTA, §4.2 e §15).

---

## 4. Glossario

_Termini da usare **verbatim** in FR, UJ e SM. Nessun sinonimo altrove nel documento. Se una feature introduce un nuovo sostantivo di dominio, va aggiunto qui nello stesso passaggio._

- **Host** — l'utente del prodotto: privato che affitta 1-3 unità in proprio. Un account HostPilot appartiene a un Host.
- **Struttura** — un'unità immobiliare affittata (appartamento). Un Host ha da 1 a 3 Strutture nel pilota. Ogni Struttura ha un Comune, una Regione e (quando disponibile) un CIN. Una Struttura con dati collegati non si cancella: si **archivia** (`archiviata`) — esce dal conteggio del Regime fiscale e dal cap delle attive, i Feed smettono di sincronizzare, ma audit/registro/storico restano (estensione registrata al gate G3; architettura AD-20).
- **Ospite** — la persona che soggiorna. Genera i dati per Alloggiati Web, tassa di soggiorno e ISTAT/ROSS1000.
- **Prenotazione** — un soggiorno con date, canale d'origine (Airbnb/Booking/manuale), Struttura e Ospite/i. Ha uno stato: `attiva`, `cancellata`, `rimossa_dal_feed` (solo `attiva` partecipa alla rilevazione dei Conflitti e genera derivati; le Prenotazioni non si cancellano fisicamente — estensione registrata al gate G3; architettura AD-19).
- **Canale** — la fonte OTA di una Prenotazione: Airbnb, Booking.com, o inserimento manuale.
- **Feed iCal** — l'URL di sola lettura fornito dall'OTA per esportare le Prenotazioni. **Non in tempo reale** (latenza di aggiornamento).
- **Calendario unificato** — la vista aggregata delle Prenotazioni di tutte le Strutture e di tutti i Canali dell'Host.
- **Conflitto** — sovrapposizione di due Prenotazioni sulla stessa Struttura nello stesso intervallo di date. Ha uno stato: `rilevato`, `gestito`, `decaduto` (la sovrapposizione cessa da sola perché una Prenotazione esce da `attiva`: transizione di sistema tracciata, distinta da `gestito` — estensione registrata al gate G3; architettura AD-5).
- **Finestra di riconciliazione** — l'intervallo/procedura entro cui l'Host risolve un Conflitto, tenendo conto che i Feed iCal non sono sincroni.
- **Regola di prezzo** — una condizione configurabile (stagione, weekend, last-minute, soggiorno minimo) che determina il prezzo per date/Struttura.
- **Adempimento** — un obbligo normativo italiano tracciato dal prodotto. I quattro dell'MVP: **Alloggiati Web**, **Tassa di soggiorno**, **ISTAT/ROSS1000**, **CIN**. Ha uno stato: `da fare`, `in sospeso`, `completato`, `non applicabile`.
- **Alloggiati Web** — comunicazione dei dati Ospiti alla Questura (Polizia di Stato) entro i termini di legge.
- **Tassa di soggiorno** — imposta **comunale**: aliquote, esenzioni e periodicità variano per Comune. Modellata per configurazione, mai hardcodata.
- **ISTAT/ROSS1000** — rilevazione del movimento turistico via portale **regionale**; tracciato e periodicità variano per Regione.
- **CIN** — Codice Identificativo Nazionale, per Struttura, con requisiti di esposizione nell'annuncio.
- **Regime fiscale** — l'inquadramento applicabile all'Host in funzione del numero di Strutture: cedolare secca (1-2) vs. presunzione di imprenditorialità/Partita IVA (dal 3°).
- **Turno di pulizia** — attività di pulizia pianificata, tipicamente legata a un check-out/check-in.
- **Messaggio automatico** — comunicazione all'Ospite attivata da un evento (pre-arrivo, check-in, check-out).
- **Livello di automazione** — per ogni Adempimento, il grado di intervento del prodotto: **Promemoria** / **Compilazione assistita** / **Invio automatico** (vedi §14 [DECISIONE G2-A]).

---

## 5. Requisiti funzionali (Feature)

_FR numerate globalmente e stabili. "Consequences (testable)" sono condizioni verificabili per la Fase 3/4. Le FR referenziano le UJ inline. Il **Livello di automazione** degli Adempimenti è parametrizzato per non pregiudicare la [DECISIONE G2-A]: le FR descrivono la capacità "in regola", la profondità di automazione è la manopola decisa al gate._

### 5.1 Onboarding e gestione Strutture

**Descrizione:** l'Host crea l'account, registra da 1 a 3 Strutture, per ciascuna indica Comune, Regione e CIN, e collega i Canali. Realizza UJ-1. L'onboarding non è bloccato da dati normativi mancanti (es. CIN non ancora ottenuto), ma li traccia come Adempimenti aperti.

#### FR-1: Registrazione delle Strutture
L'Host può creare, modificare ed eliminare fino a 3 Strutture. Realizza UJ-1.
- **Consequences (testable):**
  - Il sistema consente al massimo 3 Strutture attive per Host nel pilota; al tentativo di aggiungere la 4ª mostra un messaggio che il pilota copre 1-3 unità e non procede.
  - Ogni Struttura richiede almeno: nome, Comune, Regione. Il CIN è opzionale alla creazione ma segnalato come Adempimento aperto se assente.
  - L'aggiunta della 3ª Struttura attiva la segnalazione di Regime fiscale (vedi FR-17). Realizza UJ-4.

#### FR-2: Anagrafica Comune/Regione della Struttura
L'Host associa ogni Struttura a un Comune e a una Regione, che parametrizzano Tassa di soggiorno e ISTAT/ROSS1000.
- **Consequences (testable):**
  - Cambiare il Comune di una Struttura ricarica la configurazione della Tassa di soggiorno applicabile (FR-12) senza perdere lo storico dei versamenti già registrati.
  - Comune/Regione non riconosciuti o non ancora configurati nel sistema producono uno stato "configurazione tassa/ISTAT non disponibile" con promemoria manuale, non un errore silenzioso. Vedi §15 (copertura Comuni/Regioni).

### 5.2 Calendario unificato e anti double-booking

**Descrizione:** il cuore operativo. Aggrega le Prenotazioni di tutti i Canali e le Strutture; rileva i Conflitti tenendo conto che i Feed iCal **non sono in tempo reale**; guida l'Host nella Finestra di riconciliazione. Realizza UJ-1, UJ-2.

#### FR-3: Import Feed iCal (Airbnb/Booking)
L'Host può collegare a ogni Struttura uno o più Feed iCal (Airbnb, Booking) tramite URL, e il sistema importa le Prenotazioni periodicamente.
- **Consequences (testable):**
  - Il sistema importa le Prenotazioni da un URL iCal valido e le associa alla Struttura corretta.
  - Il sistema mostra per ogni Feed l'orario dell'ultima sincronizzazione riuscita ("dati aggiornati alle HH:MM").
  - Un URL non valido o irraggiungibile produce un errore visibile sulla Struttura, non un fallimento silenzioso.
- **Out of Scope:** scrittura/aggiornamento verso l'OTA via iCal (i Feed sono **read-only**). La chiusura date sul canale opposto (FR-6) è un'azione guidata, non una scrittura automatica via iCal.

#### FR-4: Calendario unificato multi-Struttura
L'Host visualizza in un'unica griglia le Prenotazioni di tutte le Strutture e di tutti i Canali. Realizza UJ-1, UJ-2.
- **Consequences (testable):**
  - Ogni Prenotazione mostra Canale d'origine, Struttura, date e Ospite.
  - Il calendario distingue visivamente le Prenotazioni per Canale.

#### FR-5: Rilevazione dei Conflitti
Il sistema rileva ogni sovrapposizione di date sulla stessa Struttura e la marca come Conflitto `rilevato`. Realizza UJ-2.
- **Consequences (testable):**
  - Due Prenotazioni sovrapposte sulla stessa Struttura generano esattamente un Conflitto con stato `rilevato`.
  - L'Host riceve una notifica alla prima sincronizzazione in cui il Conflitto emerge.
  - Il Conflitto registra la fonte e il timestamp di sincronizzazione di ciascuna Prenotazione coinvolta.

#### FR-6: Finestra di riconciliazione
L'Host risolve un Conflitto scegliendo quale Prenotazione tenere e ricevendo istruzioni guidate per bloccare le date sull'altro Canale. Realizza UJ-2.
- **Consequences (testable):**
  - Alla risoluzione, il Conflitto passa a stato `gestito` e resta nello storico (non viene cancellato).
  - Il sistema non esegue scritture automatiche sull'OTA; fornisce all'Host i passi per bloccare le date manualmente sul canale.
  - Finché un Conflitto è `rilevato`, resta in evidenza nella dashboard.
- **Feature-specific NFR:** il ritardo dei Feed iCal è esplicitato in UI; il sistema non deve mai rappresentare come "certo/sincronizzato" uno stato che dipende da un Feed non aggiornato.

#### FR-7: Inserimento manuale di Prenotazioni
L'Host può inserire una Prenotazione manuale (es. prenotazione diretta, blocco date) che partecipa alla rilevazione dei Conflitti.
- **Consequences (testable):**
  - Una Prenotazione manuale che si sovrappone a una da Feed genera un Conflitto (FR-5).

### 5.3 Motore di regole di prezzo

**Descrizione:** l'Host configura Regole di prezzo per stagione, weekend, last-minute e soggiorno minimo; il sistema calcola e mostra il prezzo risultante per date/Struttura come output consultabile. Realizza UJ-5.

#### FR-8: Definizione delle Regole di prezzo
L'Host crea Regole di prezzo per Struttura: base, alta/bassa stagione, maggiorazione weekend, sconto last-minute, soggiorno minimo. Realizza UJ-5.
- **Consequences (testable):**
  - Una Regola di stagione applica il prezzo definito a tutte le date del suo intervallo.
  - Le Regole hanno una precedenza deterministica e documentata quando più Regole insistono sulla stessa data (es. last-minute > weekend > stagione — precedenza esatta da confermare in UX/architettura).

#### FR-9: Calcolo e anteprima del prezzo
Il sistema calcola il prezzo risultante per ogni data/Struttura e ne mostra l'anteprima sul calendario. Realizza UJ-5.
- **Consequences (testable):**
  - Ogni data mostra il prezzo calcolato e quale Regola l'ha determinato.
  - Il soggiorno minimo è mostrato per data.

#### FR-10: Esportazione/consultazione dei prezzi
L'Host può consultare ed esportare i prezzi calcolati per riportarli sui portali.
- **Consequences (testable):**
  - I prezzi sono esportabili in un formato consultabile dall'Host.
- **Out of Scope:** **push automatico dei prezzi verso Airbnb/Booking** (richiede API OTA di scrittura, non i Feed iCal read-only). Vedi §9 e §15 — il pricing è un motore di calcolo/decisione, non un channel manager bidirezionale.

### 5.4 Adempimenti italiani ("in regola")

**Descrizione:** il differenziatore nativo. I quattro Adempimenti — Alloggiati Web, Tassa di soggiorno, ISTAT/ROSS1000, CIN — sono **requisiti di conformità dell'MVP** (decisione G1: "MVP in regola"), non funzionalità opzionali. Il **Livello di automazione** per ciascuno è la [DECISIONE G2-A] (§14): le FR sotto descrivono la capacità "in regola" a livello di promemoria affidabile + compilazione assistita + tracciamento dello stato, con l'**invio automatico** come capacità parametrica attivabile dove legalmente e tecnicamente sostenibile. `[ASSUNZIONE: "in regola" = il prodotto garantisce che l'Host possa adempiere in tempo e ne traccia l'esito; NON garantisce l'invio automatico end-to-end per ogni Adempimento nell'MVP.]` Realizza UJ-3.

#### FR-11: Alloggiati Web — comunicazione Ospiti
Per ogni Ospite in arrivo, il sistema guida la raccolta minimizzata dei dati del documento d'identità e produce la comunicazione verso Alloggiati Web, con tracciamento della scadenza (24h/6h) e dello stato. Realizza UJ-3.
- **Consequences (testable):**
  - Al check-in registrato, il sistema apre un Adempimento Alloggiati Web con scadenza calcolata dai termini di legge configurati (24h standard, 6h per soggiorni < 24h).
  - L'Adempimento resta `in sospeso` finché l'Host non conferma l'avvenuta comunicazione; solo allora passa a `completato` con timestamp.
  - Se abilitato l'invio automatico ([DECISIONE G2-A]), il sistema registra l'esito della trasmissione (successo/errore) e mantiene `in sospeso` in caso di errore.
  - I dati del documento sono trattati secondo la policy privacy §7 (minimizzazione, retention, cifratura at-rest).
- **Feature-specific NFR:** i termini (24h/6h) sono **configurabili**, non hardcodati, per assorbire eventuali chiarimenti normativi.

#### FR-12: Tassa di soggiorno — calcolo e registro
Il sistema calcola l'importo dovuto per Struttura secondo la configurazione del Comune, tiene il registro degli incassi/versamenti e ricorda le scadenze di dichiarazione/versamento.
- **Consequences (testable):**
  - Il calcolo usa la configurazione del Comune della Struttura (aliquota, esenzioni, periodicità); nessuna aliquota è hardcodata nel codice.
  - Il sistema produce il riepilogo periodico (es. trimestrale) secondo la periodicità configurata del Comune.
  - Le esenzioni configurabili (es. minori, durata massima) sono applicate al calcolo.
  - Un Comune non ancora configurato produce lo stato "configurazione non disponibile" con promemoria manuale, non un importo errato (§15).
- **Notes:** `[NOTE FOR PM]` la Cassazione 23/01/2026 (host obbligato al versamento anche se l'Ospite rifiuta) è citata da fonte secondaria — impatta il modello del registro (responsabilità del versamento). Da verificare su fonte primaria prima dell'implementazione (§15).

#### FR-13: ISTAT/ROSS1000 — rilevazione movimento turistico
Il sistema compila la rilevazione (arrivi, presenze, provenienza Ospiti) secondo il tracciato della Regione della Struttura e ricorda la periodicità, incluso l'obbligo di risposta a "movimento zero".
- **Consequences (testable):**
  - Il tracciato e la periodicità sono determinati dalla Regione della Struttura (modello flessibile per Regione, nessun tracciato unico hardcodato).
  - Il sistema genera il promemoria anche in assenza di Prenotazioni nel periodo (movimento zero).
  - Regioni supportate all'MVP: da definire come [DECISIONE G2-B] (§14) — quali Regioni coprire al lancio del pilota.

#### FR-14: CIN — tracciamento per Struttura ed esposizione
Il sistema traccia il CIN per Struttura e verifica i requisiti di esposizione negli annunci. Realizza UJ-1.
- **Consequences (testable):**
  - Ogni Struttura ha un campo CIN; se assente, esiste un Adempimento CIN `da fare` in evidenza.
  - Il sistema fornisce una checklist dei requisiti di esposizione del CIN (es. presenza negli annunci) che l'Host può marcare come soddisfatti.
- **Out of Scope:** richiesta/emissione del CIN presso la banca dati ministeriale (BDSR) — il sistema traccia e ricorda, non emette il codice.

#### FR-15: Cruscotto Adempimenti e scadenze
L'Host vede in un unico posto tutti gli Adempimenti aperti, ordinati per scadenza e priorità, con notifiche.
- **Consequences (testable):**
  - Ogni Adempimento mostra stato (`da fare`/`in sospeso`/`completato`/`non applicabile`), scadenza e Struttura.
  - Le notifiche/promemoria sono generate con anticipo configurabile rispetto alla scadenza.
  - Un Adempimento scaduto e non completato è evidenziato come tale (mai marcato `completato` automaticamente).

#### FR-16: Livello di automazione configurabile per Adempimento
Il sistema espone, per ogni tipo di Adempimento, il Livello di automazione attivo (Promemoria / Compilazione assistita / Invio automatico) in funzione della [DECISIONE G2-A] e della sostenibilità legale/tecnica.
- **Consequences (testable):**
  - Cambiare il Livello di automazione di un Adempimento non altera lo storico degli Adempimenti già completati.
  - Dove l'Invio automatico non è disponibile, l'Adempimento resta in Compilazione assistita + Promemoria senza degradare la capacità "in regola" (tracciamento dello stato).

### 5.5 Regime fiscale e soglia dei tre immobili

**Descrizione:** il prodotto riflette il regime fiscale differenziato 1-2 vs. 3 Strutture (decisione G1), **segnalando** l'impatto senza fare consulenza. Realizza UJ-4.

#### FR-17: Segnalazione del Regime fiscale per numero di Strutture
Il sistema determina e segnala il Regime fiscale applicabile in base al numero di Strutture attive dell'Host. Realizza UJ-4.
- **Consequences (testable):**
  - Con 1-2 Strutture, il sistema indica il regime di cedolare secca applicabile (informativo).
  - All'aggiunta della 3ª Struttura, il sistema segnala la presunzione di imprenditorialità (Partita IVA, aliquote progressive 21%/26%/30% citate) con un disclaimer esplicito di rimando al commercialista.
  - Il contenuto è **informativo**, marcato come non sostitutivo di consulenza fiscale.
- **Out of Scope:** gestione operativa di Partita IVA, fatturazione, calcolo delle imposte dovute (§9). La profondità di questa segnalazione (solo avviso vs. riepilogo strutturato) è la [DECISIONE G2-C] (§14).
- **Notes:** `[NOTE FOR PM]` aliquote e soglie da verificare su fonte primaria prima dell'implementazione (§15).

### 5.6 Operatività: pulizie e messaggi Ospiti

**Descrizione:** ridurre il coordinamento manuale via WhatsApp/promemoria sparsi.

#### FR-18: Calendario Turni di pulizia
L'Host pianifica i Turni di pulizia, tipicamente legati ai check-out/check-in del Calendario unificato.
- **Consequences (testable):**
  - Un check-out genera (o suggerisce) un Turno di pulizia per quella Struttura/data.
  - L'Host può segnare un Turno come completato.
  - `[ASSUNZIONE: nell'MVP il Turno è visibile all'Host; l'assegnazione a un collaboratore esterno e le sue notifiche sono una decisione di scope da confermare — vedi §9.]`

#### FR-19: Messaggi automatici agli Ospiti
Il sistema invia Messaggi automatici all'Ospite attivati da eventi: pre-arrivo, check-in, check-out.
- **Consequences (testable):**
  - L'Host può configurare il testo dei Messaggi per evento e Struttura.
  - Un Messaggio è inviato al verificarsi dell'evento configurato.
  - `[ASSUNZIONE: il canale di invio (email vs. altri) e l'eventuale necessità di dati di contatto dell'Ospite dai portali sono da confermare in UX/architettura — i Feed iCal non sempre forniscono contatti.]`

### 5.7 Account e preferenze

**Descrizione:** infrastruttura implicita di qualunque prodotto con login, resa esplicita e ratificata al gate G3 (R-3 della Readiness; UX §2.3 `[GAP PRD]`, architettura `identity`).

#### FR-20: Account e preferenze di notifica
L'Host gestisce le proprie credenziali (email, password) e le preferenze di notifica.
- **Consequences (testable):**
  - L'Host può aggiornare email e password; le credenziali seguono la policy di sicurezza dell'architettura (sessione server-side, `identity`).
  - L'Host può impostare il canale di notifica preferito tra quelli disponibili nell'MVP (in-app, email).
  - Le preferenze di notifica sono rispettate dal motore di notifiche/promemoria (FR-15, FR-5).
- **Notes:** `[FR aggiunta al gate G3 2026-07-24]` requisito minimo per tracciabilità; nessun ampliamento di scope oltre l'infrastruttura di account già implicata.

---

## 6. Requisiti non funzionali trasversali (NFR)

_Sistemici, non legati a una singola feature. Il dettaglio implementativo (stack, meccanismi) è di Winston in Fase 3._

- **NFR-1 — Affidabilità della sincronizzazione:** l'import dei Feed iCal è periodico e resiliente ai fallimenti temporanei dell'OTA; un fallimento di sync non deve far perdere Prenotazioni già importate né marcare erroneamente stati.
- **NFR-2 — Verità temporale sui dati OTA:** ovunque si mostri lo stato del calendario, deve essere visibile l'orario dell'ultima sincronizzazione. Il sistema non rappresenta mai come sincrono ciò che dipende da un Feed non aggiornato.
- **NFR-3 — Affidabilità delle notifiche/scadenze:** i promemoria degli Adempimenti sono la funzione di fiducia del prodotto ("in regola"): una scadenza non deve essere persa per un errore di sistema. Le scadenze mancate per motivi di sistema sono un difetto di severità alta.
- **NFR-4 — Configurabilità normativa:** aliquote, tracciati, periodicità e termini (tassa di soggiorno per Comune, ISTAT per Regione, termini Alloggiati Web) sono **dati di configurazione**, mai hardcoded. Aggiornarli non richiede un rilascio di codice. (Vincolo di dominio, `project-context.md` §5.)
- **NFR-5 — Usabilità per utente non tecnico:** i flussi principali (onboarding, riconciliazione conflitto, invio Alloggiati Web) devono essere completabili da un host non tecnico senza supporto. Target di usabilità misurabili → UX Spec di Sally.
- **NFR-6 — Sicurezza dei dati personali:** vedi §7 (GDPR by design). Requisito trasversale non negoziabile per i documenti d'identità.
- **NFR-7 — Osservabilità degli esiti di compliance:** ogni Adempimento ha uno stato tracciato e verificabile; il sistema mantiene lo storico (audit dell'host) di cosa è stato comunicato e quando.
- **NFR-8 — Accessibilità:** target da definire in UX Spec (`[ASSUNZIONE: WCAG 2.1 AA come riferimento, da confermare con Sally]`).
- **NFR-9 — Localizzazione:** UI e contenuti in italiano; date, valute e formati italiani.

---

## 7. Privacy, dati sensibili e compliance GDPR

_Requisito reso concreto in Fase 2 come richiesto dal brief (§ Rischi p.4) e da `project-context.md` §5. Il dettaglio implementativo (meccanismi di cifratura, key management) è coordinato con Winston in Fase 3; qui si fissa la policy di prodotto._

- **NFR-10 — Base giuridica:** il trattamento dei documenti d'identità degli Ospiti ha come base giuridica l'**obbligo legale** (comunicazione Alloggiati Web). Nessun uso secondario dei dati identità oltre l'Adempimento.
- **NFR-11 — Minimizzazione:** si raccolgono solo i campi richiesti dalla comunicazione Alloggiati Web; nessun dato dell'Ospite eccedente lo scopo.
- **NFR-12 — Retention:** i dati del documento d'identità sono conservati solo per il tempo necessario all'Adempimento e all'eventuale prova dell'avvenuta comunicazione, poi cancellati/anonimizzati. **Il periodo esatto di retention è la [DECISIONE G2-D]** (§14): il brief segnala che nessuna retention è stata reperita nella ricerca → va fissata una policy concreta, da confermare con il legale in Fase 3 prima dell'implementazione.
- **NFR-13 — Cifratura at-rest:** i documenti d'identità e i dati personali sensibili degli Ospiti sono cifrati at-rest. `[ASSUNZIONE: cifratura anche in transito come standard; meccanismo esatto → Winston.]`
- **NFR-14 — Controllo accessi:** solo l'Host proprietario accede ai dati Ospiti delle proprie Strutture.
- **NFR-15 — Diritti dell'interessato:** predisposizione per cancellazione dei dati Ospite su richiesta, coerente con la retention.
- **NFR-16 — Nessun dato reale nei test:** nessun dato reale di Ospiti nei fixture/test (`project-context.md` §7).

> `[NOTE FOR PM]` Tutta la §7 è policy di prodotto da **validare con un legale/DPO** prima dell'implementazione della compliance, non prima del PRD. È un rischio esplicito (§15).

---

## 8. Non-Goals (espliciti)

- HostPilot **non è un commercialista**: non calcola le imposte dovute, non presenta dichiarazioni, non certifica. Assiste e ricorda.
- HostPilot **non è un channel manager bidirezionale**: non scrive prezzi/disponibilità verso Airbnb/Booking nell'MVP (Feed iCal read-only; push OTA fuori scope).
- HostPilot **non è un PMS multi-unità**: niente ruoli/permessi di team, reportistica aggregata, gestione property manager.
- HostPilot **non gestisce pagamenti/fatturazione** verso Ospiti nell'MVP.
- HostPilot **non emette il CIN** né presenta domande alla BDSR: lo traccia.
- HostPilot **non fa revenue management avanzato** (pricing dinamico algoritmico/di mercato).

## 9. Scope MVP

### 9.1 In scope
- Onboarding e gestione di 1-3 Strutture con Comune/Regione/CIN (FR-1, FR-2).
- Calendario unificato, import Feed iCal Airbnb/Booking, rilevazione Conflitti e Finestra di riconciliazione, Prenotazioni manuali (FR-3…FR-7).
- Motore di Regole di prezzo con calcolo/anteprima ed esportazione (FR-8…FR-10).
- Quattro Adempimenti "in regola" con cruscotto scadenze e Livello di automazione parametrico (FR-11…FR-16).
- Segnalazione del Regime fiscale differenziato 1-2 vs. 3 Strutture (FR-17).
- Turni di pulizia e Messaggi automatici base agli Ospiti (FR-18, FR-19).
- Policy privacy/GDPR sui dati Ospiti (§7).

### 9.2 Fuori scope MVP
- Push automatico prezzi/disponibilità verso OTA — richiede API OTA di scrittura. `[NOTE FOR PM]` emotivamente rilevante: è la differenza tra "motore di prezzo" e "channel manager"; l'host potrebbe attendersela. Da rivalutare post-pilota.
- Gestione P.IVA/fatturazione per il 3° immobile (solo segnalazione informativa nell'MVP, FR-17).
- Emissione CIN presso BDSR (solo tracciamento).
- Multi-unità/property manager (ruoli, aggregati).
- Pagamenti, revenue management avanzato, OTA oltre Airbnb/Booking.
- Assegnazione Turni di pulizia a collaboratori esterni con loro account/notifiche — `[NOTE FOR PM]` candidato v2, da confermare (FR-18).
- Scelta di stack e architettura (Fase 3, gate G3).

---

## 10. Metriche di successo

_Le metriche numeriche e le finestre temporali sono **decisioni di prodotto** (brief §Criteri di successo): sotto sono proposte come struttura con **opzioni + raccomandazione** per la [DECISIONE G2-E] (§14). I target tra parentesi sono raccomandazioni di John, da confermare da Fahad, non numeri d'ufficio._

**Primarie**
- **SM-1 — Zero double-booking:** numero di Conflitti sfuggiti (doppia prenotazione effettivamente ospitata) per Host attivo. Target raccomandato: **0** incidenti ospitati; misurato sui Conflitti `rilevato` non `gestito` prima del check-in. Valida FR-5, FR-6.
- **SM-2 — Adempimenti in tempo:** % di Adempimenti completati entro la scadenza tramite lo strumento vs. totale dovuti. Target raccomandato **≥ 90%** entro il pilota. Valida FR-11…FR-16.
- **SM-3 — Onboarding completato:** % di Host che completano l'onboarding **e** collegano almeno un Feed iCal. Target raccomandato **≥ 70%** dei registrati. Valida FR-1, FR-3.

**Secondarie**
- **SM-4 — Conversione a pagante:** % di Host che dalla prova/pilota passano ad abbonamento. Target: **[DECISIONE G2-E]** (WTP non validata, §15). Valida la tesi di business, non una singola FR.
- **SM-5 — Ritenzione operativa:** % di Host attivi settimanalmente dopo 4 settimane ("l'unico posto dove guardare"). Target raccomandato **≥ 50%**.

**Counter-metriche (non ottimizzare)**
- **SM-C1 — Falsi Conflitti:** tasso di Conflitti `rilevato` che si rivelano non-conflitti (rumore da latenza Feed). Contrappesa SM-1: azzerare i double-booking allarmando su tutto distrugge la fiducia. Da tenere basso, non a zero.
- **SM-C2 — Adempimenti falsamente "completati":** Adempimenti marcati completati senza avvenuto invio reale. Contrappesa SM-2: la % in tempo non deve essere gonfiata da chiusure ottimistiche. Deve restare **0**.

---

## 11. Dipendenze con la UX Spec (Sally) e la Fase 3 (Winston)

- **UX Spec (Sally), co-input del gate G2:** i flussi di onboarding (UJ-1), riconciliazione Conflitto (UJ-2), invio Alloggiati Web (UJ-3) e la segnalazione Regime fiscale (UJ-4) vanno disegnati in dettaglio nella UX Spec, che deve mirrorare gli ID UJ-1…UJ-5 di questo PRD e i target di usabilità/accessibilità (NFR-5, NFR-8). Feature e flussi vanno tenuti allineati: ogni FR con impatto UI ha un corrispettivo di flusso nella UX Spec.
- **Architettura (Winston, Fase 3):** consumatore a valle di questo PRD. Punti che richiedono decisione architetturale: meccanismo di sync iCal (NFR-1/NFR-2), modello dati configurabile per Comune/Regione (NFR-4), cifratura at-rest e retention dei dati Ospiti (§7), fattibilità dell'Invio automatico per Alloggiati Web (web service) vs. gli altri Adempimenti (portali comunali/regionali eterogenei).

---

## 12. Rischi e assunzioni aperte

_Da portare al gate umano; ereditati e affinati dal brief (§Rischi)._

1. **Fonti normative non primarie (rischio alto):** tutta la base normativa (termini Alloggiati Web, sanzioni, aliquote, soglie, Cassazione 23/01/2026) proviene da articoli editoriali di settore, spesso di concorrenti. **Verifica di un commercialista/legale obbligatoria prima del rilascio delle funzionalità di compliance** (non prima del PRD, non prima dello sviluppo). Mitigazione di design: tutto ciò che è normativo è **configurabile** (NFR-4), così una correzione non richiede rilascio di codice. **Owner assegnato il 2026-07-25: il commercialista di Fahad** (§14.1, R-5); risposta attesa entro la fine dell'Epic 2. Rischio residuo: la retention documenti (G2-D) è materia GDPR e potrebbe richiedere un **parere privacy separato** — il mandato obbliga il commercialista a segnalarlo.
2. **Copertura Comuni/Regioni:** la tassa di soggiorno varia su 1.000+ Comuni e ISTAT/ROSS1000 per Regione. Coprirle tutte al lancio non è realistico → perimetro iniziale deciso ([DECISIONE G2-B], §14.1: **6 Comuni**, criterio vincolante, costruzione delegata a Mary) e degrado sicuro (promemoria manuale) dove la configurazione non c'è (FR-2, FR-12, FR-13). Rischio residuo dopo la decisione: la **qualità** del perimetro dipende dalla leggibilità dei regolamenti comunali — un Comune ad alta densità con regolamento caotico si scarta, quindi il set finale potrebbe non coincidere con i Comuni commercialmente più attesi.
3. **Livello di automazione "in regola":** l'Invio automatico end-to-end è tecnicamente/legamente sostenibile solo per alcuni Adempimenti (Alloggiati Web ha un web service; tassa di soggiorno e ISTAT sono portali eterogenei). Rischio: promettere automazione che non regge → raccomandazione di partire da promemoria + compilazione assistita ([DECISIONE G2-A]).
4. **Willingness-to-pay non validata:** la fascia concorrenti (13-35€/mese) è un riferimento, non conferma che l'host paghi per un problema oggi gestito (male) gratis con Excel. Impatta SM-4.
5. **Percezione del rischio sanzionatorio:** se l'host non sente il rischio come urgente ("non mi hanno mai controllato"), la value proposition primaria si sposta da compliance a produttività — da validare con interviste host.
6. **Barriera di fiducia sui dati identità:** l'host potrebbe non voler inserire documenti d'identità in un sistema terzo → impatta l'adozione dell'Adempimento Alloggiati Web e la scelta del Livello di automazione.
7. **Analisi competitiva da approfondire (Chekin in particolare):** teardown competitivo strutturato raccomandato dal brief, non ancora fatto; Chekin sembra già posizionato su compliance italiana/europea. Rischio di sovrapposizione di posizionamento.

---

## 13. Domande aperte

1. Precedenza esatta tra Regole di prezzo concorrenti (FR-8) — da definire con Sally/Winston.
2. Canale di invio dei Messaggi automatici e disponibilità dei contatti Ospite dai Feed (FR-19).
3. Assegnazione dei Turni di pulizia a collaboratori esterni: MVP o v2? (FR-18, §9.2).
4. Formato esatto di esportazione prezzi (FR-10).
5. ~~Perimetro iniziale di Comuni/Regioni supportati — collegata a [DECISIONE G2-B].~~ **Chiusa il 2026-07-25** (§14.1): criterio e cap decisi da Fahad, lista in costruzione da Mary.

---

## 14. Decisioni per il gate G2 (`[DECISIONE G2]`)

_Bivi di prodotto che, per `project-context.md` §2, **non decido io**. Per ciascuno: opzioni, trade-off, raccomandazione di John. Fahad chiude al gate G2._

> **Esito gate G3 — 2026-07-24 (approvazione di Fahad):**
> - **G2-A** → **adottata Opz. 2** (Promemoria + Compilazione assistita per tutti e 4; Invio automatico come fast-follow dove sostenibile — candidato Alloggiati Web via WS_ALLOGGIATI).
> - **G2-B** → **approccio adottato** (perimetro ristretto ad alta densità + degrado sicuro `configurazione_non_disponibile`); il **set iniziale concreto di Comuni/Regioni è stato sciolto da Fahad il 2026-07-25** — delega a Mary con criterio vincolante e cap di 6 Comuni. Vedi **§14.1**. **Punto chiuso.**
> - **G2-C** → **adottata Opz. 1** (avviso informativo + rimando al commercialista, niente calcoli d'imposta).
> - **G2-D** → **default adottato N=30 giorni dopo `completato` / M=90 giorni dal check-out** (= G3-3), **come valore iniziale in attesa della conferma legale**. L'owner della verifica (Readiness R-5) è assegnato dal 2026-07-25 — §14.1 — con l'obbligo esplicito di segnalare se sul punto retention serve un **parere privacy separato** (è GDPR, non materia fiscale). Parametro di configurazione, modificabile senza rilascio.
> - **G2-E** → **adottati** i target proposti (SM-1=0, SM-2≥90%, SM-3≥70%, SM-5≥50%; SM-4 senza target finché la WTP non è validata) e i target di usabilità proposti da Sally (onboarding ≤10 min, riconciliazione ≤3 interazioni, Alloggiati ≤2 min) come baseline.
> - **Decisioni architetturali G3-1…5** ratificate (vedi `docs/architecture.md` §10 e `docs/project-context.md` §6).
> - **Nessun punto del gate G2/G3 resta aperto:** il set G2-B e l'owner della verifica legale (Readiness R-5) sono stati sciolti il **2026-07-25** (issue **MYL-33**) — vedi **§14.1**. Restano da produrre gli **esiti** delle due deleghe (lista Comuni di Mary; risposta del commercialista), non le decisioni.

- **[DECISIONE G2-A] — Livello di automazione degli Adempimenti nell'MVP.**
  - Opz. 1: solo Promemoria. *Trade-off:* rapido, basso rischio legale; ma poco differenziante e non "in regola" nello spirito della decisione G1.
  - Opz. 2 (**raccomandata**): Promemoria + Compilazione assistita per tutti e 4, con Invio automatico validato **come fast-follow** dove sostenibile (candidato: Alloggiati Web). *Trade-off:* copre "in regola" (l'host adempie in tempo, lo stato è tracciato) contenendo il rischio di promettere invii automatici fragili. Coerente con la raccomandazione del brief.
  - Opz. 3: Invio automatico end-to-end per tutti al lancio. *Trade-off:* massimo valore percepito, ma alto rischio tecnico/legale su portali comunali/regionali eterogenei.
- **[DECISIONE G2-B] — Perimetro iniziale Comuni (tassa) e Regioni (ISTAT/ROSS1000).**
  - Raccomandazione: partire da un set ristretto ad alta densità di host (es. i Comuni/Regioni dei primi utenti pilota) con degrado sicuro a promemoria manuale altrove (FR-2/FR-12/FR-13). Fahad conferma il set iniziale.
- **[DECISIONE G2-C] — Profondità della segnalazione Regime fiscale (3° immobile).**
  - Opz. 1 (**raccomandata**): avviso informativo + rimando al commercialista (FR-17), niente calcoli.
  - Opz. 2: riepilogo strutturato del regime differenziato (aliquote, implicazioni) — più utile ma più vicino alla consulenza (rischio di essere percepiti come commercialista, contro §8).
- **[DECISIONE G2-D] — Periodo di retention dei documenti d'identità Ospiti (§7 NFR-12).**
  - Raccomandazione: retention minima legata alla prova dell'avvenuta comunicazione, con default cautelativo breve, **da confermare col legale in Fase 3**. Serve una policy concreta al gate, non un rinvio.
- **[DECISIONE G2-E] — Target numerici delle Metriche di successo (§10).**
  - Raccomandazione: adottare i target proposti (SM-1=0 incidenti, SM-2≥90%, SM-3≥70%, SM-5≥50%) e lasciare SM-4 (conversione) senza target finché la WTP non è validata (§12.4).

### 14.1 Decisioni del supervisore — 2026-07-25 (issue MYL-33)

_Registrate verbatim nella sostanza. Chiudono i due punti che il gate G3 aveva lasciato aperti; entrambe erano bloccanti per l'**Epic 3 — Adempimenti italiani**, nessuna delle due per l'Epic 2._

**[DECISIONE G2-B] — Perimetro iniziale Comuni/Regioni: DELEGA A MARY, cap 6 Comuni.**

La lista non la sceglie Fahad né John: la costruisce **Mary (Business Analyst)** dai dati, con un **criterio vincolante** in tre punti — tutti e tre devono valere, non è una media pesata:

1. **Massima densità di host privati 1-3 unità** — il target del prodotto, **non il turismo generico**. Un Comune con molti pernottamenti ma dominato da strutture alberghiere o da property manager multi-unità non qualifica.
2. **Regolamento comunale della tassa di soggiorno pubblicato e leggibile.** Se il regolamento è caotico, **il Comune si scarta anche se è "ovvio"** che debba esserci — e lo scarto **va documentato** con il motivo.
3. **Le Regioni corrispondenti devono coprire almeno 3-4 sistemi ISTAT regionali diversi** — il perimetro serve anche a mettere alla prova la varietà dei tracciati ISTAT/ROSS1000, non solo le aliquote.

**Esito atteso:** lista motivata dei **6 Comuni + Regioni** (con i Comuni scartati e il perché), in `docs/`, consegnata via PR. Alimenta `config_normativa` (FR-2, FR-12, FR-13) e le Story 3.6/3.7. Il degrado sicuro `configurazione_non_disponibile` resta il comportamento per tutto ciò che è fuori perimetro.

**[R-5 — Readiness] — Owner della verifica legale: il commercialista di Fahad.**

**Mandato esplicito** — deve validare:

- **termini Alloggiati Web** (24h / 6h);
- **regole della tassa di soggiorno** dei Comuni scelti (esiti di G2-B);
- **obblighi ISTAT/ROSS1000**;
- **CIN**;
- **regime fiscale e soglia dei 3 immobili** (FR-17).

Sul punto **retention dei documenti d'identità Ospiti** (G2-D, 30/90 giorni) deve **segnalare esplicitamente se serve un parere privacy separato**: è materia **GDPR, non fiscale**, e una risposta rassicurante data fuori competenza vale meno del silenzio.

**Ingaggio:** a cura di Fahad. **Risposta attesa entro la fine dell'Epic 2.** Il gate resta di **RILASCIO** per le feature di compliance (Epic 3 — Story 3.9), **non di sviluppo**: l'Epic 3 si può sviluppare, non si può rilasciare a un Host reale senza la validazione.

---

## 15. Riepilogo requisiti (indice FR/NFR)

- **Feature:** Onboarding/Strutture (FR-1, FR-2) · Calendario & anti double-booking (FR-3…FR-7) · Prezzi (FR-8…FR-10) · Adempimenti (FR-11…FR-16) · Regime fiscale (FR-17) · Operatività (FR-18, FR-19) · Account e preferenze (FR-20).
- **NFR trasversali:** NFR-1…NFR-9. **Privacy/GDPR:** NFR-10…NFR-16.

## 16. Indice delle assunzioni (`[ASSUNZIONE]`)

- §5.4 FR — "in regola" = il prodotto garantisce l'adempimento in tempo e ne traccia l'esito; non garantisce l'invio automatico end-to-end per ogni Adempimento nell'MVP.
- §5.6 FR-18 — nell'MVP il Turno di pulizia è visibile all'Host; assegnazione a collaboratore esterno da confermare.
- §5.6 FR-19 — canale di invio Messaggi e disponibilità contatti Ospite dai Feed da confermare.
- §6 NFR-8 — WCAG 2.1 AA come riferimento di accessibilità, da confermare con Sally.
- §7 NFR-13 — cifratura anche in transito come standard; meccanismo esatto a Winston.

---

_Fine PRD. Stato: draft, in attesa del gate umano **G2** (PRD + UX Spec insieme). Nessun handoff alla Fase 3 prima dell'approvazione di Fahad._

---
title: 'UX Specification — HostPilot'
status: draft
gate: G2
gate_status: 'in attesa di approvazione umana (Fahad) — PRD + UX Spec insieme'
created: 2026-07-24
updated: 2026-07-24
author: Sally — UX Designer
phase: '2 · Planning'
depends_on:
  - docs/prd.md (FR-1…FR-19, UJ-1…UJ-5, NFR-5, NFR-8) — approvato in bozza, co-input dello stesso gate
  - docs/project-brief.md (approvato, gate G1)
  - docs/project-context.md (costituzione di progetto)
related:
  - PRD (John) — issue separata, co-input del gate G2
  - Architettura + Epics/Stories (Winston) — Fase 3, gate G3
---

# UX Specification: HostPilot

> Un solo posto dove l'host guarda ogni settimana. Questo documento disegna in dettaglio i flussi che il PRD fissa a livello di requisito (FR) e narrazione (UJ), a livello di **specifica**, non di implementazione: lo stack e il design system sono decisi da Winston in Fase 3 (gate G3).

## 0. Scopo del documento e come leggerlo

Questa UX Spec è il co-input, insieme al PRD (`docs/prd.md`), del gate umano **G2**. Non duplica i requisiti funzionali: li referenzia per ID (FR-N, UJ-N, NFR-N) e aggiunge il livello di dettaglio — schermate, stati, microcopy, pattern di interazione — che serve a Winston per progettare l'architettura e ad Amelia per implementare senza reinterpretare le decisioni di prodotto.

**Convenzioni:**
- Ogni **User Journey** mirrora l'ID del PRD (UJ-1…UJ-5) verbatim.
- Ogni schermata/flusso dichiara le FR che realizza.
- `[OPZIONE UX]` marca un bivio di design con alternative e una raccomandazione — non decido priorità di prodotto (coerente con `project-context.md` §2); dove il bivio è già una `[DECISIONE G2-x]` del PRD, la UX Spec resta parametrica rispetto a quella decisione, non la anticipa.
- `[GAP PRD]` segnala un punto dove la UX Spec ha bisogno di un chiarimento che il PRD non fornisce ancora.
- Il vocabolario è quello del **Glossario** del PRD (§4): Host, Struttura, Ospite, Prenotazione, Canale, Conflitto, Adempimento, ecc. Nessun sinonimo.

---

## 1. Principi UX e target

**Target primario:** Marco e Laura del PRD (§3) — host privati italiani, 1-3 Strutture, non tecnici, oggi su Excel e 5-6 schede browser. Non sono early adopter di software gestionale: la barra di riferimento mentale è "più semplice di quello che faccio oggi", non "più potente di un PMS".

Cinque principi guidano ogni decisione di design successiva:

1. **Un solo posto dove guardare.** La home/dashboard è il punto di ingresso unico che riassume calendario, adempimenti in scadenza e prezzi — mai un elenco di moduli scollegati che l'host deve visitare a turno per capire "sono a posto?".
2. **Rassicurare, non certificare.** Ogni superficie di compliance (Adempimenti, Regime fiscale) comunica "ti aiuto a non dimenticare" e mai "sei in regola al 100%, garantito". Linguaggio e stati devono lasciare sempre uno spazio esplicito per il giudizio del commercialista/professionista — coerente con la Non-Goal del PRD (§8): HostPilot non è un commercialista.
3. **Verità sui tempi, mai falsa sincronia.** Ogni dato che dipende da un Feed iCal o da una conferma manuale dell'host mostra quando è stato aggiornato l'ultima volta. Mai presentare come "certo" ciò che non lo è (realizza NFR-2).
4. **Riduzione del carico cognitivo sugli adempimenti.** Un host con 4 Adempimenti su 1-3 Strutture può avere fino a 12 scadenze attive contemporaneamente: il design deve raggruppare, ordinare per urgenza e nascondere ciò che non richiede azione ora, mai mostrare tutto con pari peso visivo.
5. **Mobile-first plausibile, non mobile-only.** L'host controlla lo stato "al volo" da telefono (specialmente al check-in con l'ospite davanti, UJ-3) ma configura prezzi e regole con più calma, probabilmente da desktop/tablet. I flussi ad alta frequenza e bassa complessità (dashboard, conferma Alloggiati Web, marcare un Turno di pulizia completato) devono reggere una mano sola su schermo piccolo; i flussi a bassa frequenza e alta complessità (configurazione Regole di prezzo, setup tassa di soggiorno) possono assumere uno schermo più grande senza penalizzare eccessivamente il mobile.

`[OPZIONE UX]` **Livello di guida per l'utente non tecnico.** Due strade coerenti con NFR-5:
- Opz. 1 (**raccomandata**): onboarding guidato passo-passo con progress indicator esplicito + tooltip contestuali su termini normativi (CIN, Alloggiati Web, ISTAT) la prima volta che compaiono; l'host può sempre saltare e tornare dopo.
- Opz. 2: onboarding "a schermo libero" con tutti i campi visibili e checklist di completamento a lato.
Opz. 1 riduce l'abbandono per un utente che non conosce il dominio normativo (rischio §12.5 del PRD: se l'host non sente l'urgenza normativa, l'onboarding deve comunque essere basso-frizione). Opz. 2 è più veloce per un host già esperto, minoranza nel target.

---

## 2. Information Architecture

### 2.1 Mappa delle schermate principali

```
Dashboard (home)
├── Calendario unificato
│   ├── Vista mensile/settimanale multi-Struttura
│   └── Finestra di riconciliazione (modale/pannello, su Conflitto)
├── Regole di prezzo
│   ├── Elenco Regole per Struttura
│   └── Editor Regola (creazione/modifica)
├── Cruscotto Adempimenti
│   ├── Vista "in sospeso" / "da fare" per Struttura
│   ├── Flusso Alloggiati Web (per Ospite/check-in)
│   ├── Tassa di soggiorno (configurazione Comune + registro)
│   ├── ISTAT/ROSS1000 (configurazione Regione + stato periodo)
│   └── CIN (per Struttura + checklist esposizione)
├── Regime fiscale (pannello informativo, si attiva alla 3ª Struttura)
├── Operatività
│   ├── Turni di pulizia
│   └── Messaggi automatici (configurazione per evento/Struttura)
├── Strutture (gestione anagrafica: Comune, Regione, CIN, Canali/Feed)
└── Onboarding (flusso separato, solo al primo accesso)
```

### 2.2 Principio di navigazione

Navigazione primaria a 5 voci (mobile: tab bar in basso; desktop: sidebar) — **Dashboard, Calendario, Prezzi, Adempimenti, Operatività** — con **Strutture** raggiungibile da un'icona di impostazioni/account, non come voce di primo livello: l'host la visita raramente dopo l'onboarding. **Regime fiscale** non è una voce di navigazione autonoma: vive come pannello dentro Adempimenti/Dashboard, coerente con la sua natura informativa (FR-17), non operativa.

Ogni Struttura è un filtro trasversale (selettore in alto, "Tutte le Strutture" come default), non una sezione separata: con 1-3 Strutture l'host deve poter passare da una vista aggregata a una singola Struttura senza cambiare schermata.

### 2.3 Copertura FR → schermata

| Schermata | FR realizzate |
|---|---|
| Onboarding | FR-1, FR-2, FR-3 |
| Dashboard | FR-4 (riepilogo), FR-15 (riepilogo), FR-17 (banner) |
| Calendario unificato | FR-4, FR-5, FR-7 |
| Finestra di riconciliazione | FR-6 |
| Regole di prezzo | FR-8, FR-9, FR-10 |
| Cruscotto Adempimenti | FR-15, FR-16 |
| Flusso Alloggiati Web | FR-11 |
| Tassa di soggiorno | FR-12 |
| ISTAT/ROSS1000 | FR-13 |
| CIN | FR-14 |
| Regime fiscale (pannello) | FR-17 |
| Turni di pulizia | FR-18 |
| Messaggi automatici | FR-19 |
| Strutture (gestione) | FR-1, FR-2, FR-3 |

`[GAP PRD]` Nessuna FR copre esplicitamente una schermata di "impostazioni account/notifiche" (es. canale di notifica preferito, lingua — già fissata a IT da NFR-9). La UX Spec assume un pannello minimo di Account (email, password, preferenze di notifica) come infrastruttura implicita necessaria a qualunque prodotto con login; da confermare con Winston se richiede una FR dedicata in Fase 3.

---

## 3. User Flow chiave

_Mirrorano UJ-1…UJ-5 del PRD verbatim. Ogni flusso: stato d'ingresso → passi → stati di sistema → climax → risoluzione → edge case. Le FR realizzate sono indicate tra parentesi._

### UJ-1 — Marco collega i suoi due appartamenti la prima sera (FR-1, FR-2, FR-3, FR-14)

**Stato d'ingresso:** primo accesso, nessun dato.

1. **Crea l'account** (email/password) → schermata di benvenuto con 1 CTA: "Aggiungi la tua prima Struttura".
2. **Aggiunge la Struttura** "Bologna Centro": nome, Comune, Regione (obbligatori); CIN (opzionale, con badge "puoi aggiungerlo dopo — te lo ricordiamo").
3. **Collega i Canali**: incolla URL feed iCal Airbnb, poi Booking. Ogni collegamento mostra uno stato di caricamento esplicito ("Importazione in corso…") e poi **"Importate N prenotazioni — ultimo aggiornamento HH:MM"**. Se l'URL non è valido: errore inline puntuale sul campo, mai un fallimento silenzioso (realizza il vincolo NFR-2/FR-3).
4. **Sistema mostra il Calendario unificato** con le prenotazioni dei due Canali, distinte visivamente (v. §4 pattern colore-Canale), e un **badge di stato conflitti**: "0 conflitti" se pulito.
5. Se il CIN non è stato inserito al passo 2: badge non bloccante "1 adempimento aperto — CIN" visibile in Dashboard da subito, mai un blocco dell'onboarding.

**Climax:** Marco vede in un'unica griglia le prenotazioni Airbnb + Booking e il badge "0 conflitti": prova diretta che il collegamento ha funzionato.

**Risoluzione:** onboarding completato → redirect a Dashboard, con un banner una-tantum "Tutto pronto. Aggiungi un'altra Struttura o esplora gli Adempimenti" (dismissibile).

**Edge:**
- Feed iCal vuoto (nessuna prenotazione storica) → calendario mostra stato vuoto rassicurante ("Nessuna prenotazione ancora — è normale per un nuovo collegamento"), non un errore.
- Solo un Canale collegato (l'altro rimandato) → onboarding comunque completabile; il secondo Canale resta un invito visibile in Strutture, non un blocco.

### UJ-2 — Marco evita una doppia prenotazione durante un ponte (FR-5, FR-6, FR-7)

**Stato d'ingresso:** autenticato, calendario già collegato, alta occupazione.

1. Alla sincronizzazione periodica, il sistema rileva la sovrapposizione → **notifica push/email**: "Possibile doppia prenotazione — Bologna Centro, 15-17 agosto" (mai silenziosa: realizza NFR-3, la funzione di fiducia del prodotto).
2. Marco apre la **Finestra di riconciliazione**: vista affiancata delle due Prenotazioni sovrapposte, ciascuna con Canale, ospite (se noto), date, e **timestamp di sincronizzazione della fonte** ("Airbnb — sincronizzato alle 14:32", "Booking — sincronizzato alle 09:10"). Il ritardo del feed è dichiarato esplicitamente qui, non nascosto (NFR-2, FR-6).
3. Marco sceglie quale Prenotazione tenere → il sistema genera **istruzioni guidate passo-passo** per bloccare le date sull'altro Canale (link diretto all'host manager Airbnb/Booking dove possibile, con testo "Copia queste date e bloccale su Booking.com"). Nessuna scrittura automatica sull'OTA (Out of Scope FR-6).
4. Conferma → il Conflitto passa a stato **`gestito`**, resta visibile nello storico (non sparisce, si sposta da "azione richiesta" a "risolto") .

**Climax:** il Conflitto passa da badge rosso "azione richiesta" a stato verde "gestito": prova visiva immediata che il rischio è disinnescato.

**Risoluzione:** dashboard torna pulita (0 conflitti aperti).

**Edge:**
- Marco non risponde entro X ore → il Conflitto resta `rilevato`, in evidenza persistente in Dashboard (mai auto-nascosto: FR-6).
- Marco marca "gestito" ma in realtà non ha bloccato le date sull'altro canale (limite intrinseco del flusso manuale) → `[OPZIONE UX]` un secondo controllo alla sincronizzazione successiva: se il conflitto persiste ancora sui dati importati, il sistema riapre un nuovo Conflitto invece di fidarsi ciecamente della conferma umana. Raccomandato per contenere SM-C1 (falsi negativi peggiori di falsi positivi qui) — verificare con Winston la fattibilità architetturale.

### UJ-3 — Laura invia la comunicazione Alloggiati Web al check-in (FR-11)

**Stato d'ingresso:** ospite appena arrivato, termine legale stretto (24h standard / 6h per soggiorni < 24h), Laura probabilmente su mobile con l'ospite davanti.

1. Laura **registra il check-in** dell'Ospite (da una Prenotazione esistente in calendario, azione a un tocco: "Ospite arrivato").
2. Il sistema apre l'Adempimento Alloggiati Web con **scadenza calcolata e visibile** ("Da inviare entro le 14:20 di domani" / countdown per soggiorni < 24h) e avvia la **compilazione assistita**: campi precompilati da dati già noti della Prenotazione (nome, date), Laura completa/verifica i campi minimizzati del documento d'identità (v. §6 gestione dati sensibili).
3. Laura verifica i campi precompilati → **conferma l'invio**. Se il Livello di automazione è "Invio automatico" (parametrico, [DECISIONE G2-A]): il sistema tenta la trasmissione e mostra l'esito (successo/errore); in caso di errore l'Adempimento resta `in sospeso` con motivo dell'errore visibile, mai marcato completato senza esito reale (SM-C2).
4. Conferma ricevuta → l'Adempimento passa a **`completato`** con timestamp, e sparisce dalla lista "in sospeso".

**Climax:** la scadenza sparisce dalla lista "in sospeso" con una conferma visibile ("Comunicato — 24 luglio, 15:47"): sollievo immediato, in un momento in cui Laura è probabilmente sotto pressione (ospite in attesa).

**Risoluzione:** Adempimento tracciato `completato`, storico consultabile (NFR-7).

**Edge:**
- Documento illeggibile/mancante → Laura può salvare come bozza; l'Adempimento resta `in sospeso` con **promemoria di escalation** (frequenza crescente man mano che la scadenza si avvicina), mai marcato `completato`.
- Countdown < 2h (soglia per soggiorni < 24h) → il colore/urgenza visiva sale a un livello dedicato (v. §5 pattern di stato), distinto dalle scadenze normali a 24h.

### UJ-4 — Laura passa da 2 a 3 immobili e capisce che cambia il regime fiscale (FR-1, FR-17)

**Stato d'ingresso:** Laura aggiunge una 3ª Struttura da un flusso già noto (stesso flusso di FR-1).

1. Laura completa il form "Aggiungi Struttura" per il 3° immobile, come per la 1ª e 2ª.
2. Alla conferma, **prima** di tornare all'elenco Strutture, il sistema interpone un **pannello informativo a schermo intero** (non un semplice banner dismissibile-e-basta): titolo tipo "Con 3 Strutture cambia il tuo regime fiscale", spiegazione sintetica (presunzione di imprenditorialità, Partita IVA, aliquote citate come informative) e CTA primaria "Ho capito, continua" + CTA secondaria "Parlane con un commercialista" (link/placeholder di contenuto).
3. Da quel momento, un **pannello Regime fiscale persistente** appare in Dashboard/Adempimenti, sempre marcato come informativo, con disclaimer visibile in ogni stato (non solo alla prima visualizzazione — un host che torna dopo settimane deve ritrovare il disclaimer, non solo il fatto).

**Climax:** Laura capisce l'impatto nel momento in cui sta ancora decidendo/agendo (aggiunta della 3ª Struttura), non a consuntivo.

**Risoluzione:** la 3ª Struttura è aggiunta, il pannello Regime fiscale resta accessibile in permanenza.

**Edge:**
- Laura elimina la 3ª Struttura subito dopo (es. errore di inserimento) → il pannello Regime fiscale torna allo stato 1-2 Strutture; nessuna notifica residua fuorviante.
- `[OPZIONE UX]` legata a [DECISIONE G2-C] del PRD: se la profondità scelta è "solo avviso" (Opz.1 raccomandata dal PRD), il pannello persistente resta un blocco di testo breve + disclaimer; se fosse scelto un "riepilogo strutturato" (Opz.2), la stessa superficie ospiterebbe una tabella comparativa 1-2 vs 3 Strutture — la UX Spec prevede lo spazio per entrambe le profondità senza doverlo ridisegnare al gate.

### UJ-5 — Marco imposta i prezzi della stagione senza ricalcolare a mano (FR-8, FR-9, FR-10)

**Stato d'ingresso:** autenticato, almeno una Struttura attiva.

1. Marco apre **Regole di prezzo** per una Struttura → crea una Regola: tipo (stagione/weekend/last-minute/soggiorno minimo), intervallo di date o condizione, valore.
2. Ogni Regola creata è immediatamente visibile in un **elenco ordinabile** con la sua condizione e il suo effetto in linguaggio naturale ("Alta stagione: 1 giu – 15 set, +30%").
3. Marco torna al **Calendario** (o a una vista Prezzi affiancata) e vede l'**anteprima del prezzo calcolato per ogni data**, con indicazione di quale Regola l'ha determinato al passaggio del mouse/tap ("€145 — Weekend + Alta stagione"). Se più Regole insistono sulla stessa data, la precedenza (da FR-8, `[GAP PRD]` esatta ancora da confermare in §13.1 del PRD) è resa **sempre visibile e tracciabile**, mai un numero senza spiegazione.
4. Marco **esporta/consulta** i prezzi (FR-10) in un formato riportabile sui portali manualmente.

**Climax:** un'unica configurazione di Regole riempie tutto il calendario di prezzi coerenti; Marco non ricalcola più riga per riga su Excel.

**Risoluzione:** i prezzi sono un output consultabile, non push automatico (Out of Scope FR-10 — v. §8 sotto).

**Edge:**
- Due Regole in conflitto sulla stessa data senza precedenza chiara → `[GAP PRD]` la UX Spec raccomanda di mostrare sempre esplicitamente quale Regola ha "vinto" e perché, qualunque sia la precedenza scelta in Fase 3/Winston — è un requisito di trasparenza UI indipendente dalla regola di calcolo sottostante.
- Nessuna Regola definita ancora → il calendario mostra un prezzo di base placeholder con invito a configurare, mai un prezzo vuoto o "N/D" senza spiegazione.

---

## 4. Pattern per l'assistenza alla compliance (senza falsa certezza)

Principio cardine (dal PRD §0/Vision: "HostPilot assiste e ricorda, non certifica"). Regole di design vincolanti per ogni superficie di Adempimento:

1. **Linguaggio di stato onesto.** Verbi: "ricordato", "in scadenza", "inviato/comunicato", mai "conforme", "in regola al 100%", "certificato". Lo stato `completato` di un Adempimento significa "l'host ha confermato l'azione o il sistema ha registrato l'esito della trasmissione" — non un giudizio legale di conformità.
2. **Disclaimer contestuale, non un footer legale ignorato.** Ogni superficie che tocca un giudizio normativo (Regime fiscale FR-17, aliquote tassa di soggiorno) porta il disclaimer **accanto al contenuto rilevante** (non solo in un'informativa generale raggiungibile altrove) — es. "Informazione a scopo indicativo. Verifica con il tuo commercialista." subito sotto la cifra o l'affermazione normativa.
3. **Nessuna falsa automazione.** Dove il Livello di automazione è "Promemoria" o "Compilazione assistita" (non Invio automatico), l'interfaccia richiede sempre un'**azione umana esplicita di conferma** prima di marcare `completato` — mai un avanzamento automatico silenzioso di stato.
4. **Trasparenza sull'esito, non solo sul tentativo.** Quando l'Invio automatico è attivo, il sistema distingue chiaramente "inviato" da "tentato l'invio, esito sconosciuto/errore" — quest'ultimo non deve mai apparire come successo (realizza SM-C2, "0 falsi completati").
5. **Le scadenze mancate restano visibili, non si nascondono per pudore.** Un Adempimento scaduto e non completato resta evidenziato con severità alta (colore/badge dedicato) finché l'host non agisce o lo marca esplicitamente `non applicabile` con motivazione — mai auto-archiviato (FR-15).
6. **Gerarchia di urgenza a 3 livelli**, applicata coerentemente su Dashboard e Cruscotto Adempimenti:
   - **Normale** (scadenza > 48h): badge neutro, elenco ordinato per data.
   - **Urgente** (scadenza tra 6h e 48h, o soglia configurabile): badge di attenzione, sale in cima all'elenco.
   - **Critico/scaduto** (< 6h o scaduto): badge ad alto contrasto, notifica push se disponibile, resta in cima anche dopo il termine finché non risolto.

`[OPZIONE UX]` Copertura dei quattro Adempimenti nella stessa gerarchia visiva vs. trattamento differenziato (es. Alloggiati Web più "urgente" per natura penale, tassa di soggiorno più "amministrativa"):
- Opz. 1 (**raccomandata**): stessa gerarchia a 3 livelli per tutti e 4, differenziata solo da un'etichetta di tipo Adempimento — riduce il carico cognitivo (principio 4, §1) e non richiede all'host di imparare 4 logiche diverse.
- Opz. 2: severità di base diversa per tipo (es. Alloggiati Web parte già da "Urgente" a 48h invece di 6h) — più fedele al rischio legale reale (reato vs. sanzione amministrativa, PRD §2) ma aggiunge complessità percettiva.

---

## 5. Pattern di stato e gestione dati sensibili nell'UI

### 5.1 Stati di sistema ricorrenti (vocabolario visivo condiviso)

| Stato | Dove compare | Trattamento visivo |
|---|---|---|
| Sincronizzazione in corso | Import Feed iCal | Indicatore di caricamento + testo esplicito, mai un semplice spinner muto |
| Dati aggiornati alle HH:MM | Calendario, Conflitti | Etichetta persistente, non un tooltip nascosto (NFR-2) |
| Conflitto `rilevato` / `gestito` | Calendario, Dashboard | Badge rosso → verde; mai rimosso dallo storico |
| Adempimento `da fare` / `in sospeso` / `completato` / `non applicabile` | Cruscotto Adempimenti | 4 stati sempre distinguibili anche senza colore (v. §7 accessibilità) |
| Errore di configurazione (Comune/Regione non coperti) | Tassa di soggiorno, ISTAT | Stato distinto da "errore utente": tono informativo ("non ancora configurato per il tuo Comune"), non un errore rosso che implica colpa dell'host (FR-2, FR-12, FR-13) |
| Errore di trasmissione (invio automatico fallito) | Alloggiati Web | Stato distinto da "in sospeso non ancora tentato": mostra il motivo se disponibile |

### 5.2 Flusso dati identità Ospite (coerente con §7 del PRD — GDPR by design)

L'interfaccia di raccolta documento d'identità (UJ-3) segue questi vincoli di design, derivati da NFR-10…NFR-16:

- **Minimizzazione visibile:** il form mostra solo i campi effettivamente richiesti da Alloggiati Web — mai un form "generico documento" con campi extra opzionali. Se un campo non serve alla comunicazione, non esiste nel form.
- **Scopo dichiarato nel punto di raccolta:** una riga di microcopy accanto al form ("Questi dati servono solo per la comunicazione Alloggiati Web, come richiesto dalla legge") — non relegata a un'informativa privacy separata che l'host non legge.
- **Nessuna persistenza visiva superflua:** una volta che l'Adempimento è `completato`, il documento d'identità non deve restare esposto in chiaro nella UI corrente (es. nel dettaglio Prenotazione) — mostrare "documento acquisito, comunicazione inviata" senza re-visualizzare i dati sensibili per default; un'azione esplicita separata (se necessaria per audit, NFR-7) per rivederli.
- **Retention comunicata, non nascosta:** quando la [DECISIONE G2-D] fissa il periodo di retention, l'interfaccia lo comunica in modo comprensibile ("i dati del documento saranno cancellati automaticamente dopo N giorni dall'invio") — non un dettaglio sepolto nei Termini di Servizio.
- **Cifratura non è un'affermazione UI:** la UX Spec non promette meccanismi di cifratura in copy (competenza di Winston, NFR-13); si limita a comunicare trattamento sicuro in termini che l'host capisce ("i dati del documento sono protetti e usati solo per questo scopo").

`[GAP PRD]` Il periodo di retention esatto ([DECISIONE G2-D]) non è ancora fissato: la UX Spec lascia il campo "cancellazione automatica dopo N giorni" parametrico nel copy, da popolare quando la decisione è chiusa — non bloccante per il resto della spec.

---

## 6. Requisiti di accessibilità (a livello di specifica)

Realizza NFR-8 (`[ASSUNZIONE PRD]` WCAG 2.1 AA come riferimento — **confermata qui da Sally** come baseline raccomandata: coerente con un target non tecnico che può includere utenti meno esperti di tecnologia e non richiede giustificazione aggiuntiva per un prodotto verticale italiano B2C-like).

- **Contrasto colore:** tutti i badge di stato (Conflitto, Adempimento, urgenza) rispettano un rapporto di contrasto ≥ 4.5:1 per il testo; **mai il colore come unico veicolo di informazione** — ogni stato ha anche un'etichetta testuale e/o un'icona distintiva (critico per i colorblind, specialmente su badge rosso/verde di Conflitto e i tre livelli di urgenza §4.6).
- **Target di tocco:** azioni frequenti da mobile (conferma check-in, marcare Turno completato, confermare invio Alloggiati Web) hanno area di tocco minima 44×44px, coerente con l'uso "una mano sola, ospite davanti" di UJ-3.
- **Navigazione da tastiera:** tutti i flussi critici (Finestra di riconciliazione, compilazione assistita Alloggiati Web) devono essere completabili senza mouse — priorità alta perché sono i flussi a più alta posta (rischio legale/operativo).
- **Etichette e lettori di schermo:** i badge di stato e le scadenze countdown (UJ-3) hanno equivalenti testuali completi per screen reader ("Scadenza tra 4 ore" non solo un colore/icona countdown).
- **Linguaggio semplice:** termini normativi (CIN, Alloggiati Web, ISTAT/ROSS1000, presunzione di imprenditorialità) sempre accompagnati, alla prima occorrenza per sessione, da una spiegazione in linguaggio comune (tooltip o testo inline) — non solo dal glossario di prodotto.
- **Formati italiani:** date, valute, formati numerici in convenzione italiana ovunque (NFR-9) — es. date gg/mm/aaaa, valuta €, separatore decimale virgola.

`[OPZIONE UX]` Target di usabilità misurabili per NFR-5, da fissare con Fahad:
- Proposta: onboarding completo (UJ-1, incluso primo Feed iCal collegato) in **≤ 10 minuti** senza assistenza per un host non tecnico; risoluzione di un Conflitto (UJ-2) in **≤ 3 interazioni** dalla notifica alla conferma "gestito"; compilazione Alloggiati Web (UJ-3) in **≤ 2 minuti** dal check-in alla conferma d'invio. Numeri indicativi di Sally, da validare/confermare da Fahad — non sono nel PRD e non vanno trattati come decisi.

---

## 7. Allineamento con il PRD — mappa di copertura e gap

### 7.1 Copertura UJ → sezione UX Spec

| UJ (PRD) | Sezione UX Spec |
|---|---|
| UJ-1 | §3 UJ-1 |
| UJ-2 | §3 UJ-2 |
| UJ-3 | §3 UJ-3 |
| UJ-4 | §3 UJ-4 |
| UJ-5 | §3 UJ-5 |

### 7.2 Copertura NFR rilevanti per la UX

| NFR (PRD) | Come è coperta qui |
|---|---|
| NFR-2 (verità temporale) | §1 principio 3, §5.1 |
| NFR-5 (usabilità non tecnica) | §1, §6 (target proposti) |
| NFR-7 (osservabilità compliance) | §4.5, §5.2 |
| NFR-8 (accessibilità) | §6 |
| NFR-9 (localizzazione) | §6 |
| NFR-10…NFR-16 (privacy/GDPR) | §5.2 |

### 7.3 Gap e incoerenze da riconciliare con John (segnalazione, non decisione)

1. **`[GAP PRD]` §2.3** — nessuna FR copre esplicitamente un pannello Account/notifiche; assunto come infrastruttura implicita.
2. **`[GAP PRD]` §3 UJ-5** — precedenza esatta tra Regole di prezzo concorrenti non ancora fissata (nota anche in PRD §13.1); la UX Spec prevede solo che la precedenza, qualunque sia, sia sempre resa visibile e spiegata in UI.
3. **`[GAP PRD]` §5.2** — periodo di retention documenti identità ([DECISIONE G2-D]) non fissato; il copy resta parametrico.
4. **Dipendenza da [DECISIONE G2-A]** (Livello di automazione) — §3 UJ-3 e §4.3/4.4 sono scritti per reggere sia "Promemoria + Compilazione assistita" sia "Invio automatico" senza ridisegno, come richiesto dal PRD §5.4.
5. **Dipendenza da [DECISIONE G2-C]** (profondità Regime fiscale) — §3 UJ-4 prevede lo spazio per entrambe le profondità (avviso vs. riepilogo strutturato).
6. **`[OPZIONE UX]` §6** — i target numerici di usabilità proposti (10 min onboarding, 3 interazioni riconciliazione, 2 min Alloggiati Web) sono raccomandazioni di Sally, non ancora una decisione: da confermare a Fahad insieme a [DECISIONE G2-E] (metriche di successo), coerente con `project-context.md` §2.

Nessuna incoerenza bloccante rilevata tra questa UX Spec e il PRD: i gap sopra sono estensioni di dettaglio o dipendenze da decisioni già identificate dal PRD stesso al gate G2, non conflitti.

---

## 8. Note di design system (a livello di specifica)

_Lo stack e il design system concreto sono decisione di Winston in Fase 3 (gate G3, coerente con `project-context.md` §6). Questa sezione fissa solo i vincoli che la UX Spec impone a qualunque scelta successiva._

- Il design system scelto deve supportare **badge di stato con etichetta testuale + icona** (non solo colore) per rispettare §6.
- Deve supportare **countdown/scadenza relativa** leggibile (non solo data assoluta) per gli Adempimenti urgenti (UJ-3).
- Deve reggere **densità di informazione variabile per Struttura**: 1 Struttura vs 3 Strutture nella stessa vista (Dashboard, Calendario) senza degradare la leggibilità — il layout non deve essere pensato solo per il caso a 1 Struttura.
- Deve supportare un **layout responsive che upgrade da mobile a desktop senza reflow distruttivo** dei flussi ad alta frequenza (§1 principio 5).

---

_Fine UX Spec. Stato: draft, in attesa del gate umano **G2** (PRD + UX Spec insieme). Nessun handoff alla Fase 3 prima dell'approvazione di Fahad._

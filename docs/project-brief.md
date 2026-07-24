---
title: 'Project Brief — HostPilot'
status: draft
created: 2026-07-24
updated: 2026-07-24
author: Mary — Business Analyst
gate: G1
---

# Project Brief: HostPilot

## Executive Summary

HostPilot è un gestionale in abbonamento pensato per l'host privato italiano che affitta 1-3 appartamenti su Airbnb e Booking.com. Oggi questo host gestisce calendario, prezzi e adempimenti fiscali/normativi a mano, tipicamente su fogli Excel, rincorrendo scadenze sparse su portali diversi (Alloggiati Web, portale comunale della tassa di soggiorno, ROSS1000/portale regionale ISTAT) con il rischio concreto di doppie prenotazioni, sanzioni amministrative e — dal 2025/2026 — sanzioni fino a 8.000€ per un CIN mancante o gestito male. HostPilot centralizza calendario multi-struttura con sync iCal, un motore di regole di prezzo e gli adempimenti italiani in un unico strumento pensato per chi non ha (né vuole) un commercialista sempre a disposizione o un property manager.

Il momento è propizio: la normativa italiana sugli affitti brevi si è irrigidita sensibilmente nel biennio 2025-2026 (CIN obbligatorio, soglia dei tre immobili che fa scattare la presunzione di imprenditorialità e l'obbligo di Partita IVA, sanzioni penali — non solo amministrative — per Alloggiati Web) proprio mentre il segmento target del pilota (1-3 unità) si trova esattamente a ridosso della nuova soglia critica. Questo aumenta sia l'urgenza percepita dall'host sia la sensibilità dell'ambito: HostPilot deve essere costruito come strumento di compliance-assistita, non come motore di consulenza fiscale.

Questo documento è il primo artefatto del pilota di collaudo della BMAD Squad e alimenta la Fase 2 (PRD + UX) solo dopo approvazione umana esplicita (gate G1).

## Il Problema

**Chi è l'host-tipo.** Un privato — spesso con un'altra occupazione principale — che affitta 1-3 appartamenti di proprietà (raramente in sublocazione) su Airbnb e/o Booking.com. Non tecnico, non ha personale dedicato, spesso gestisce da solo calendario, pulizie e comunicazioni con gli ospiti, con il commercialista coinvolto solo a fine anno o su richiesta specifica.

**Job-to-be-done principali:**
1. "Voglio essere sicuro che nessuno prenoti due volte lo stesso appartamento lo stesso giorno" — oggi il rischio di double-booking esiste perché i feed iCal di Airbnb/Booking sono di sola lettura e non in tempo reale (vedi Vincoli tecnici sotto), e la riconciliazione manuale tra calendari è la prassi.
2. "Voglio smettere di dimenticare le comunicazioni obbligatorie" (Alloggiati Web, tassa di soggiorno, ISTAT/ROSS1000, CIN) — le scadenze sono strette (fino a 6 ore per Alloggiati Web su soggiorni brevi) e sparse su portali diversi con logiche e periodicità differenti.
3. "Voglio impostare prezzi diversi per stagione/weekend/last-minute senza ricalcolare tutto a mano ogni volta."
4. "Voglio coordinare le pulizie e i messaggi agli ospiti senza rincorrere WhatsApp e promemoria sparsi."

**Pain attuali (perché Excel non basta):**
- Excel non sincronizza in tempo reale con i portali OTA: l'host aggiorna manualmente due o più calendari, con margine d'errore alto proprio nei periodi di alta occupazione.
- Le scadenze normative sono penalmente/amministrativamente sanzionate (Alloggiati Web: reato, fino a 206€ per omissione; ROSS1000: fino a 2.500€/mese a seconda della Regione; CIN: 800-8.000€ per immobile) ma vivono su tre-quattro portali diversi, ciascuno con propria login, formato e calendario di scadenze — nessuno strumento consumer li unifica oggi in modo affidabile per il segmento 1-3 unità.
- La tassa di soggiorno cambia aliquota, esenzioni e modalità di versamento per ogni Comune (oltre 1.000 Comuni la applicano nel 2026): un foglio Excel non si aggiorna da solo quando il Comune cambia regolamento.
- Gli strumenti PMS/channel manager esistenti sono pensati per property manager multi-unità (es. Octorate richiede tipicamente almeno 5 unità) o sono generalisti/internazionali e non coprono gli adempimenti italiani (Alloggiati Web, ROSS1000, tassa di soggiorno comunale, CIN) come funzione nativa.

**Costo dello status quo:** tempo sottratto ogni settimana alla riconciliazione manuale dei calendari; rischio di sanzioni economiche dirette (dal 2025-2026 potenzialmente rilevanti, vedi sotto); rischio reputazionale/legale su gestione dati sensibili degli ospiti (documenti d'identità) senza una base minima di sicurezza.

**Assunzioni da validare (con l'umano/con interviste host, non nel pilota di questo brief):**
- Quanto gli host-tipo percepiscono davvero il rischio sanzionatorio come urgente (vs. "non mi hanno mai controllato") — impatta la value proposition primaria (compliance vs. produttività).
- Se l'host è disposto a inserire dati di identità degli ospiti in un sistema terzo (barriera di fiducia) o preferisce restare su invio manuale assistito.
- Disponibilità a pagare un abbonamento ricorrente per un problema oggi "risolto" gratis (anche se male) con Excel.

## La Soluzione

HostPilot offre, in un solo abbonamento pensato per 1-3 strutture:

1. **Calendario unificato multi-struttura** con sync iCal Airbnb/Booking e logica anti double-booking che tiene conto della non-tempestività dei feed OTA (finestre di conflitto e riconciliazione, non sincronia istantanea assunta).
2. **Motore di regole di prezzo** configurabile per stagionalità, weekend, last-minute, soggiorni minimi — senza bisogno di ricalcolare a mano.
3. **Adempimenti italiani assistiti**: promemoria e, dove tecnicamente e legalmente sostenibile, invio assistito verso Alloggiati Web, calcolo/registro della tassa di soggiorno configurabile per Comune, promemoria ROSS1000/portale regionale ISTAT, tracciamento CIN per immobile.
4. **Operatività**: calendario turni di pulizia, messaggi automatici (pre-arrivo, check-in, check-out) agli ospiti.

Il focus dell'esperienza è "un solo posto dove guardare" per un host che oggi apre 5-6 schede del browser diverse ogni settimana.

## Cosa rende HostPilot diverso

- **Adempimenti italiani come funzione nativa, non come plugin**: i concorrenti generalisti (Lodgify, Smoobu, RoomRaccoon) sono ottimi su calendario/pricing ma non integrano nativamente Alloggiati Web, tassa di soggiorno comunale, ROSS1000 e CIN nel flusso operativo italiano — è un gap di mercato osservato nella ricerca, non un vantaggio tecnico dimostrato: da validare con analisi competitiva più approfondita (CR) prima del PRD.
- **Dimensionato per 1-3 unità**, non per property manager: i player italiani esistenti (es. Octorate) partono da soglie minime (5+ unità) che escludono il segmento target di HostPilot; questa è oggi più un'osservazione di posizionamento che un moat difendibile — l'onestà richiede di segnalarlo come ipotesi da testare, non come fatto acquisito.
- **Nessun moat tecnico dichiarato in questa fase**: la differenziazione realistica nel breve termine è la profondità della copertura normativa italiana e la cura dell'esperienza per un utente non tecnico, non l'unicità architetturale (lo stack non è ancora deciso, Fase 3).

## A chi si rivolge

**Utente primario:** host privato italiano, 1-3 appartamenti, gestione diretta (non tramite property manager), attivo su Airbnb e/o Booking.com, non tecnico, oggi su Excel o strumenti informali. Successo per lui: zero doppie prenotazioni, zero scadenze mancate, tempo settimanale di gestione ridotto.

**Utente secondario (fuori scope pilota, ottica futura):** property manager multi-unità. Esplicitamente non l'obiettivo dell'MVP — funzionalità e pricing per questo segmento non vanno progettati ora per non diluire il focus.

## Criteri di successo

Da confermare con l'umano in Fase 2 (obiettivi misurabili non sono nella competenza di questo brief in dettaglio), ma come indicazione per il PRD:

- **Segnali di successo utente**: zero incidenti di double-booking segnalati; percentuale di comunicazioni obbligatorie (Alloggiati Web, ROSS1000, tassa di soggiorno) inviate in tempo tramite lo strumento vs. gestite fuori dallo strumento.
- **Segnali di business (pilota)**: numero di host che completano l'onboarding e collegano almeno un calendario iCal; tasso di conversione da prova gratuita/pilota ad abbonamento pagante.
- Metriche precise, target numerici e finestre temporali sono una decisione di prodotto: proposti qui solo come categorie, la definizione spetta a John/Sally in Fase 2.

## Scope

**Nel pilota (MVP, ipotesi di lavoro — da confermare in PRD):**
- Calendario unificato 1-3 strutture con sync iCal Airbnb/Booking e anti double-booking con finestra di riconciliazione.
- Motore di regole di prezzo base (stagionalità, weekend, last-minute, soggiorno minimo).
- Promemoria/assistenza per Alloggiati Web, tassa di soggiorno (configurabile per Comune), ROSS1000, CIN — grado di automazione (solo promemoria vs. invio assistito vs. invio automatico) è una decisione di prodotto aperta, vedi Rischi.
- Calendario pulizie e messaggistica automatica base agli ospiti.

**Esplicitamente fuori scope pilota:**
- Gestione multi-unità per property manager (soglie, ruoli, reportistica aggregata) — ottica futura.
- Consulenza fiscale o dichiarativa sostitutiva del commercialista: HostPilot assiste e ricorda, non decide né certifica al posto di un professionista.
- Pagamenti/fatturazione integrata, motore di revenue management avanzato, integrazioni OTA oltre Airbnb/Booking — da valutare in fasi successive.
- Scelta di stack tecnologico e architettura: di competenza di Winston in Fase 3, dietro gate G3.

## Ricerca di mercato

- **Alternative attuali dell'host-tipo**: fogli Excel/Google Sheets (prevalente per 1-3 unità), calendari manuali sui portali OTA, gruppi WhatsApp/Telegram per coordinare pulizie. Gli strumenti PMS/channel manager esistenti sul mercato italiano (Lodgify, Smoobu, RoomRaccoon, Avaibook, Octorate) coprono bene calendario/pricing/channel management ma non risultano — dalla ricerca condotta — offrire copertura nativa degli adempimenti italiani specifici (Alloggiati Web, tassa di soggiorno comunale, ROSS1000, CIN) come funzione di prodotto integrata; alcuni (es. Chekin, citato più volte come fonte editoriale su questi temi) sembrano posizionarsi proprio su compliance italiana/europea, e vanno trattati come concorrente diretto da analizzare con teardown dedicato (CR) prima del PRD.
- **Fascia di prezzo di riferimento**: gli strumenti generalisti per micro-host partono orientativamente da ~13-35€/mese per struttura (es. Lodgify da 13€/mese, Smoobu Professional da 29-35€/mese); Octorate richiede tipicamente un minimo di 5 unità e non pubblica un listino trasparente, il che lo rende meno rilevante come comparabile diretto per il segmento 1-3 unità. Questi dati orientano ma non validano la disponibilità a pagare per HostPilot: la willingness-to-pay reale non è stata testata con host reali e resta un'assunzione aperta.
- **Nota metodologica**: questa è una ricognizione rapida via ricerca web (non un teardown competitivo strutturato né interviste utente). Per il PRD si raccomanda un approfondimento dedicato con la capability CR (competitive teardown) sui 2-3 concorrenti più vicini (Lodgify, Smoobu, Chekin) e, se possibile, interviste dirette a host italiani nel segmento 1-3 unità.

## ⚠️ Ricerca normativa italiana (area a rischio alto — verificata via ricerca web, non da consulente)

**Tutte le fonti sono articoli editoriali/blog di settore consultati il 2026-07-24, non testi di legge primari**: prima di qualunque implementazione, i punti seguenti richiedono conferma di un commercialista o consulente legale, come richiesto esplicitamente da `docs/project-context.md`.

### Alloggiati Web / Questura
- Obbligo di comunicazione dei dati degli ospiti entro **24 ore dall'arrivo**, ridotto a **6 ore per soggiorni inferiori alle 24 ore**; il termine decorre dal check-in fisico. Portale attivo 24/7, weekend e festivi inclusi.
- La violazione **non è sanzione amministrativa ma reato**, con pene che secondo le fonti consultate arrivano fino a 206€ per omissione (da verificare l'esatta qualificazione penale con un legale).
- Implicazione GDPR: gestione di documenti d'identità → dato sensibile, richiede base giuridica, minimizzazione e retention definita — nessun dettaglio di retention è stato reperito nella ricerca svolta, punto da approfondire.
- Fonti: [Comunicazione alla Questura Ospiti — Chekin](https://chekin.com/it/blog/comunicazione-alla-questura-ospiti-guida/), [Alloggiati Web 2026 — Lodgify](https://www.lodgify.com/blog/it/alloggiati-web/), [Alloggiati Web — Domus CM](https://domuscm.com/blog/alloggiati-web-guida-completa) (verificate 2026-07-24).

### Tassa di soggiorno
- Natura **comunale**: aliquote, esenzioni e periodicità di versamento variano per Comune; oltre **1.000 Comuni italiani** la applicano nel 2026 secondo le fonti consultate.
- Esempio citato (Milano): registrazione gestore su piattaforma comunale dedicata, dichiarazione trimestrale, versamento via PagoPA — pattern probabilmente non generalizzabile ad altri Comuni senza verifica caso per caso.
- Una sentenza di Cassazione datata **23 gennaio 2026** (citata da una fonte secondaria, non verificata sul testo originale) attribuirebbe all'host l'obbligo di versamento anche se l'ospite si rifiuta di pagare — **da verificare sulla fonte primaria prima di qualunque assunzione di prodotto**.
- Implicazione per il modello dati: **non hardcodare aliquote/regole**, modellare per configurazione per Comune fin dal PRD.
- Fonti: [Tasse affitti brevi 2026 — Lodgify](https://www.lodgify.com/blog/it/tasse-affitti-brevi/), [Come si versa l'imposta di soggiorno — PartitaIva.it](https://www.partitaiva.it/come-versare-imposta-soggiorno/), [Tassa di soggiorno Milano — Hostmate](https://hostmate.it/tassa-di-soggiorno-milano/) (verificate 2026-07-24).

### ISTAT / ROSS1000
- Rilevazione a **obbligo di risposta** (art. 7, D.Lgs. 322/1989 citato dalle fonti): arrivi, presenze, provenienza ospiti, trasmessi tramite portale regionale (non un unico portale nazionale).
- Periodicità **variabile per Regione**, tipicamente mensile, **dovuta anche a movimento zero**; sanzioni citate fino a **2.500€/mese** a seconda della Regione.
- Regioni con implementazione ROSS1000 confermata dalla ricerca: Veneto (attivo dal 2018), Liguria (obbligo per appartamenti ammobiliati a uso turistico dal 1° aprile 2025), Lombardia, Emilia-Romagna. **Il tracciato e la piattaforma non sono uniformi a livello nazionale** — implicazione diretta sul prodotto: serve un modello dati flessibile per Regione, non un'unica integrazione.
- Fonti: [ROSS1000 guida per albergatori — Chekin](https://chekin.com/it/blog/ross1000-guida-per-albergatori-e-property-manager-italiani/), [Regione Veneto — ROSS1000](https://www.regione.veneto.it/web/turismo/rilevazione-flussi-turistici-ross1000), [Regione Liguria — ROSS1000](https://www.regione.liguria.it/homepage-turismo/cosa-cerchi/ross-1000.html) (verificate 2026-07-24).

### CIN (Codice Identificativo Nazionale) — non citato esplicitamente nel brief del leader ma emerso come vincolo critico nella ricerca
- Obbligatorio dal **2 gennaio 2025**, "a regime" dal 2026, richiesto sulla banca dati del Ministero del Turismo (BDSR) ed esposto in ogni annuncio.
- Sanzioni rilevanti: fino a **8.000€ per immobile senza CIN**, fino a **5.000€ per mancata indicazione negli annunci** secondo le fonti consultate.
- **Rilevanza diretta per lo scope del pilota**: tracciare il CIN per immobile e i suoi requisiti di esposizione sembra un candidato forte per l'MVP, da proporre esplicitamente al gate umano come possibile aggiunta al nucleo funzionale originario (non era nell'elenco delle 4 aree indicate dal leader).
- Fonti: [CIN affitti brevi 2026 — Verto AI](https://vertoai.it/blog/cin-codice-identificativo-nazionale), [Guida CIN — Lodgify](https://www.lodgify.com/blog/it/codice-cin-affitti-brevi/) (verificate 2026-07-24).

### Soglia dei tre immobili (Legge di Bilancio 2026) — implicazione critica per il posizionamento del pilota
- Dal **1° gennaio 2026**, la cedolare secca si applica solo ai primi due immobili in affitto breve; **dal terzo immobile scatta la presunzione assoluta di imprenditorialità** e l'obbligo di apertura Partita IVA — soglia abbassata rispetto ai cinque immobili validi fino al 2025.
- Aliquote progressive citate dalle fonti: 21% primo immobile, 26% secondo, 30% dal terzo/quarto (regime ordinario, non più cedolare secca).
- **Implicazione diretta per HostPilot**: il segmento target dichiarato (1-3 unità) è esattamente a cavallo della nuova soglia critica. Un host con 3 immobili è ora, per legge, un imprenditore — questo cambia potenzialmente i requisiti di prodotto (es. gestione P.IVA, fatturazione) per una fetta del pubblico target, ed è un punto da portare esplicitamente al gate umano: **il pilota copre "1-3 unità" come dichiarato, ma il 3° immobile porta con sé obblighi fiscali che il 1° e 2° non hanno** — va deciso se e come HostPilot ne tiene conto nell'MVP o lo dichiara esplicitamente fuori scope.
- Fonti: [Affitti brevi 2026, Partita IVA dal terzo immobile — Vikey](https://vikey.it/cedolare-secca-affitti-brevi-partita-iva-terzo-immobile/), [Studio Barberi — soglia affitti brevi 2026](https://www.studiobarberi.it/affitti-brevi-2026-nuova-soglia-appartamenti/) (verificate 2026-07-24).

## Rischi e assunzioni aperte (per il gate umano)

1. **Copertura normativa nell'MVP** — decisione di prodotto aperta: HostPilot deve limitarsi a *promemoria* delle scadenze (rischio più basso, valore più contenuto) o offrire *invio assistito/automatico* verso i portali istituzionali (valore più alto, ma introduce rischio legale/tecnico — es. automazione verso Alloggiati Web e ROSS1000 potrebbe richiedere integrazioni non documentate pubblicamente o accordi con le PA). Raccomandazione: partire da promemoria + compilazione assistita per il pilota, validare l'automazione end-to-end solo dopo. **Decisione dell'umano.**
2. **Il CIN non era tra le 4 aree indicate dal leader ma è emerso come rischio normativo rilevante (sanzioni fino a 8.000€/immobile)** — proposta: includerlo nel nucleo dell'MVP. **Decisione dell'umano.**
3. **La soglia dei tre immobili (Legge di Bilancio 2026)** rende il segmento "1-3 unità" eterogeneo dal punto di vista fiscale (1-2 unità: cedolare secca; 3 unità: Partita IVA e presunzione d'impresa). Va deciso se il prodotto tratta il caso "3 immobili" come standard o come edge case esplicitamente fuori scope pilota. **Decisione dell'umano.**
4. **Dati sensibili degli ospiti** (documenti d'identità per Alloggiati Web): nessuna indicazione di retention è stata reperita in questa ricerca. Prima del PRD serve una policy esplicita (base giuridica, minimizzazione, retention, cifratura at-rest) — coerente con `docs/project-context.md` §5, ma va reso concreto in Fase 2/3.
5. **Fonti normative non primarie**: l'intera sezione normativa di questo brief è basata su articoli editoriali di settore (Chekin, Lodgify, Verto AI e simili), spesso essi stessi fornitori concorrenti con incentivo a semplificare o enfatizzare il rischio normativo per vendere il proprio prodotto. **Raccomandazione forte**: prima dell'implementazione delle funzionalità di compliance (non prima del PRD), commissionare una verifica da parte di un commercialista o consulente legale su Alloggiati Web, tassa di soggiorno, ROSS1000, CIN e soglia dei tre immobili.
6. **Willingness to pay non validata**: la fascia di prezzo dei concorrenti (13-35€/mese) è un riferimento di mercato, non una conferma che l'host-tipo di HostPilot pagherebbe un abbonamento equivalente per un problema oggi gestito (male) gratis con Excel.
7. **Analisi competitiva non approfondita**: questo brief usa ricerca web rapida, non un teardown competitivo strutturato (capability CR). Raccomandato prima del PRD, specialmente su Chekin che sembra posizionarsi già su compliance italiana/europea.

## Vision

Se HostPilot ha successo, diventa il punto di riferimento operativo quotidiano per l'host privato italiano di affitti brevi: l'unico posto dove calendario, prezzo e adempimenti convivono senza sforzo, riducendo a quasi zero il rischio di sanzioni per dimenticanza e il tempo speso in coordinamento manuale. Nell'ottica a 2-3 anni, e solo dopo aver validato il segmento privato, il prodotto potrebbe estendersi al property manager multi-unità — esplicitamente fuori dallo scope di questo pilota, ma coerente con la direzione se il nucleo 1-3 unità dimostra ritenzione e disponibilità a pagare.

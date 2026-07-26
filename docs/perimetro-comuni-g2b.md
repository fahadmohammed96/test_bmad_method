# Perimetro iniziale G2-B — 6 Comuni + Regioni (tassa di soggiorno / ISTAT-ROSS1000)

**Decisione di riferimento:** `[DECISIONE G2-B]`, sciolta da Fahad il 2026-07-25 sull'issue MYL-33, registrata in `docs/prd.md` §14.1. Delega a Mary (Business Analyst), cap **6 Comuni**, criterio vincolante a tre punti **congiunti** (non media pesata).
**Autrice:** Mary — Business Analyst. **Data:** 2026-07-25. **Issue:** MYL-34.

> **Cosa NON è questo documento.** Non produce aliquote, importi, esenzioni o tracciati normativi: seleziona *quali* Comuni entrano nel perimetro configurabile (`config_normativa`, Epic 3). Il contenuto normativo dei regolamenti citati resta da validare dal commercialista di Fahad (Readiness R-5, PRD §12.1) — ogni riferimento normativo qui sotto è marcato **"da validare"**, mai come dato acquisito.

---

## 1. Il criterio, come applicato

1. **Massima densità di host privati 1-3 unità** — il target del prodotto (host piccoli), non il turismo generico o la grande gestione professionale.
2. **Regolamento comunale della tassa di soggiorno pubblicato e leggibile** — un Comune con regolamento caotico si scarta anche se "ovvio", motivando lo scarto.
3. **Le Regioni corrispondenti devono coprire almeno 3-4 sistemi ISTAT/ROSS1000 regionali diversi** — non solo aliquote diverse, ma piattaforme di rilevazione realmente diverse.

I tre punti sono congiunti: un candidato che soddisfa 1 e 3 ma inciampa su 2 non entra.

---

## 2. I 6 Comuni scelti

| # | Comune | Provincia | Regione | Sistema ISTAT regionale |
|---|---|---|---|---|
| 1 | San Gimignano | SI | Toscana | ROSS1000 |
| 2 | Vernazza | SP | Liguria | ROSS1000 |
| 3 | Alberobello | BA | Puglia | SPOT / SPOT Easy |
| 4 | Polignano a Mare | BA | Puglia | SPOT / SPOT Easy |
| 5 | Cefalù | PA | Sicilia | Turist@t (Osservatorio Turistico regionale) |
| 6 | Ortisei / St. Ulrich (Val Gardena) | BZ | Provincia Autonoma di Bolzano/Alto Adige | ASTAT — Tic-Web |

### 2.1 San Gimignano (SI, Toscana)

- **Punto 1:** borgo di ~7.600 abitanti la cui economia turistica è quasi interamente ricettività diffusa (case vacanza, B&B, agriturismi) nel centro storico UNESCO; assenza di catene alberghiere di grande scala. Fonte: profilo comune (Wikipedia, dato demografico) + assenza — nella ricerca condotta — di operatori multi-unità di scala paragonabile a quelli osservati nelle grandi città (§4). **Nota di trasparenza:** non ho trovato un dataset quantitativo (tipo InsideAirbnb) per San Gimignano; la valutazione di densità è qualitativa, dedotta dalla struttura del borgo e dall'assenza di segnalazioni di grande gestione professionale — dichiarato come tale, non spacciato per dato misurato.
- **Punto 2:** regolamento dell'imposta di soggiorno pubblicato in PDF sul sito istituzionale, aggiornato al 2025 (nuove tariffe e regolamento in vigore dal 1/1/2025), con struttura leggibile: tariffe per tipologia ricettiva, scadenze di versamento trimestrali (15 maggio / 15 settembre / 15 gennaio). **Da validare.** Fonte: comune.sangimignano.si.it, PDF "Regolamento imposta di soggiorno dal 2025".
- **Punto 3:** Toscana è tra le Regioni che adottano ROSS1000. Fonte: chekin.com, "ROSS1000: cos'è, come funziona e regioni (2026)" — **da validare** (fonte editoriale di settore, non testo di legge).

### 2.2 Vernazza (SP, Liguria)

- **Punto 1:** una delle Cinque Terre, ~750 abitanti, borgo dove la ricettività è quasi esclusivamente case vacanza/affittacamere a conduzione familiare data la scala del paese; nessuna grande catena alberghiera possibile per vincoli urbanistici e dimensione del centro storico. **Nota di trasparenza:** anche qui la densità è una deduzione qualitativa dalla scala del borgo, non un dato misurato — dichiarato.
- **Punto 2:** regolamento e tariffe 2025 pubblicati sul portale dedicato del Comune (vernazza.imposta-soggiorno.it) e sul sito istituzionale (comune.vernazza.sp.it); tariffa unica citata (3€/notte/persona, primi 3 giorni) con esenzioni esplicite (minori di 11 anni, autisti/accompagnatori di gruppo). Struttura semplice e leggibile. **Da validare.** Fonte: vernazza.imposta-soggiorno.it.
- **Punto 3:** Liguria adotta ROSS1000 — confermato anche dal portale regionale ("ROSS1000 – rilevazione flussi turistici", regione.liguria.it). Questa è l'unica affermazione di sistema regionale in questo documento con fonte istituzionale diretta (non solo editoriale).

### 2.3 Alberobello (BA, Puglia)

- **Punto 1:** capitale dei trulli, ~10.700 abitanti; il patrimonio ricettivo è dominato da trulli riconvertiti a case vacanza, tipicamente unità singole gestite dal proprietario o dalla famiglia, per ragioni strutturali (i trulli sono unità piccole, difficilmente aggregabili in portafogli di scala). **Nota di trasparenza:** stima qualitativa da fonti giornalistiche locali sul turismo di Alberobello, non da dataset quantitativo — dichiarato come tale.
- **Punto 2:** tariffe aggiornate ad aprile 2025 approvate con delibera di Consiglio Comunale (seduta 23/1/2025), pubblicate sul sito istituzionale (comune.alberobello.ba.it) e ripercorse da più testate locali (Corriere dell'Economia, PugliaLive); tre categorie ricettive, tetto di 3 pernottamenti consecutivi. Struttura ordinata. **Da validare** — non ho recuperato il PDF integrale del regolamento, solo sintesi giornalistiche + pagina istituzionale che conferma la delibera: questo è un gradino di evidenza più debole rispetto a San Gimignano/Vernazza e va segnalato.
- **Punto 3:** Puglia usa SPOT / SPOT Easy (Agenzia Regionale del Turismo Pugliapromozione — ARET), sistema distinto da ROSS1000, con base legale propria (L.R. 49/2017, modificata da L.R. 52/2019). Fonte istituzionale diretta: regione.puglia.it, aret.regione.puglia.it.

### 2.4 Polignano a Mare (BA, Puglia)

- **Punto 1:** ~17.500 abitanti, centro storico sulla falesia con altissima densità di case vacanza a conduzione privata/familiare; incluso (con Lecce) tra le città pugliesi analizzate in uno studio indipendente sulla concentrazione degli host Airbnb in Italia basato su dati InsideAirbnb, che rileva — a livello regionale pugliese (Lecce) — l'assenza di operatori con oltre 100 annunci, a differenza delle grandi città (Milano, Roma, Bologna) dove operano agenzie professionali con centinaia di unità. **Nota di trasparenza:** il dato quantitativo diretto (Gini/concentrazione host) copre Lecce, non Polignano; per Polignano l'affermazione di densità resta qualitativa per analogia territoriale, dichiarata come tale.
- **Punto 2:** regolamento approvato con delibera di Consiglio Comunale n.14 del 17/5/2023 (art. 52 D.Lgs. 446/1997), pubblicato in PDF sul sito istituzionale e su PayTourist; tariffe differenziate per categoria (2€/giorno standard, 3€/giorno 5 stelle/lusso), tetto di 7 pernottamenti. Struttura chiara. **Da validare.** Fonte: comune.polignanoamare.ba.it.
- **Punto 3:** stesso sistema regionale di Alberobello (SPOT/Puglia) — incluso non per aggiungere un sistema ISTAT ulteriore, ma perché soddisfa nettamente i punti 1-2 e rafforza la copertura del segmento "borgo costiero pugliese ad alta densità" con un secondo riferimento nella stessa Regione.

### 2.5 Cefalù (PA, Sicilia)

- **Punto 1:** ~13.000 abitanti, centro storico con forte prevalenza di case vacanza/B&B rispetto alla grande ricettività alberghiera; la ricerca condotta non ha però prodotto un dato quantitativo di concentrazione per Cefalù. **Nota di trasparenza dichiarata:** questo è il criterio 1 meno supportato da fonti tra i 6 Comuni — l'affermazione si basa sulla notorietà del centro storico di Cefalù come destinazione di ricettività diffusa (fonti giornalistiche locali su tariffe e turismo), non su un dataset. Segnalato esplicitamente come lacuna, non presentato come misura.
- **Punto 2:** regolamento e sistema di gestione pubblicati (portale eGov del Comune, egov.comune.cefalu.pa.it); tariffe (1,50-5€), periodo di applicazione limitato (1 aprile - 31 ottobre), esenzioni esplicite ed elencate (scolaresche, minori di 12 anni, guide, accompagnatori, autisti, giornalisti). Struttura leggibile. **Da validare.** Fonte: egov.comune.cefalu.pa.it, palermotoday.it (sintesi tariffe 2024).
- **Punto 3:** Sicilia usa **Turist@t** (Osservatorio Turistico della Regione Siciliana), piattaforma gestita dall'Assessorato Regionale del Turismo, distinta da ROSS1000 e con proprio account "UTENTE PMS" per i gestionali esterni. Fonte istituzionale diretta: osservatorioturistico.regione.sicilia.it.

### 2.6 Ortisei / St. Ulrich in Gröden (BZ, Val Gardena, Provincia Autonoma di Bolzano)

- **Punto 1:** la Val Gardena ha una tradizione consolidata di ricettività a conduzione familiare (camere/appartamenti privati, "Privatzimmervermietung", spesso affiancata all'attività agricola) accanto all'offerta alberghiera; è un mercato storicamente frammentato su piccoli operatori locali piuttosto che su agenzie multi-proprietà. **Nota di trasparenza:** anche questa è una valutazione qualitativa, non supportata da un dataset di concentrazione host — dichiarata come tale. È inoltre il Comune, tra i 6, con il profilo meno "urbano/appartamento" e più orientato a ricettività turistica alpina tradizionale: incluso principalmente per soddisfare in modo solido il punto 3 (si veda sotto), con il punto 1 verificato ma meno probante degli altri cinque.
- **Punto 2:** "Regolamento per l'istituzione e applicazione dell'imposta comunale di soggiorno" pubblicato sul sito istituzionale del Comune (comune.ortisei.bz.it), aggiornato con la delibera che raddoppia le tariffe dal 1/1/2026 (3-5€/notte/persona per categoria) per finanziare i Mondiali di sci alpino 2031, valida fino al 2030. Documento datato, tracciabile, con motivazione pubblica dell'aumento. Struttura leggibile. **Da validare.** Fonte: comune.ortisei.bz.it; blitzquotidiano.it e ilfattoquotidiano.it per il contesto dell'aumento.
- **Punto 3:** la Provincia Autonoma di Bolzano/Alto Adige **non** usa ROSS1000: la rilevazione del movimento turistico passa da **ASTAT** (Istituto provinciale di statistica) tramite il portale **Tic-Web**, che alimenta comunque il Sistema Statistico Nazionale (SISTAN) ma con piattaforma e ente gestore propri. Fonte istituzionale diretta: astat.provincia.bz.it — confermato anche da fonte terza indipendente (SISTAN, sistan.it).

---

## 3. Copertura ISTAT/ROSS1000 — il punto 3 verificato

**4 sistemi regionali distinti**, tutti confermati da fonte istituzionale diretta (non solo editoriale) per almeno un Comune del set:

| Sistema | Regione/Provincia | Comuni nel perimetro | Fonte istituzionale |
|---|---|---|---|
| **ROSS1000** | Toscana, Liguria | San Gimignano, Vernazza | regione.liguria.it (diretta); chekin.com per Toscana (editoriale, da validare) |
| **SPOT / SPOT Easy** | Puglia | Alberobello, Polignano a Mare | regione.puglia.it, aret.regione.puglia.it (diretta) |
| **Turist@t** | Sicilia | Cefalù | osservatorioturistico.regione.sicilia.it (diretta) |
| **ASTAT — Tic-Web** | Provincia Autonoma di Bolzano | Ortisei | astat.provincia.bz.it (diretta) |

Il set **non è concentrato su un'unica Regione** (punto 3 del mandato): 5 territori distinti (Toscana, Liguria, Puglia, Sicilia, PA Bolzano) su 6 Comuni, e i 4 sistemi sono realmente eterogenei — non varianti dello stesso portale con branding diverso. In particolare:

- ROSS1000 è il "modello nazionale" adottato dalla maggioranza delle Regioni (fonte: ross1000.it, editoriale ANBBA — da validare l'elenco esatto delle Regioni aderenti, che le fonti consultate non riportano in modo del tutto coerente tra loro).
- Puglia, Sicilia e PA Bolzano hanno **piattaforme regionali/provinciali proprie**, con basi normative regionali distinte (es. L.R. Puglia 49/2017) e — nel caso di Bolzano — un ente statistico provinciale autonomo (ASTAT) invece di ISTAT.

**Metodo di verifica:** per ciascun sistema ho cercato conferma su almeno una fonte istituzionale (dominio `.regione.*.it`, `.provincia.bz.it` o portale ufficiale della piattaforma), non solo su articoli di blog di fornitori concorrenti — coerente con il rischio già segnalato nel PRD (§12.1) sulle fonti editoriali. Dove non ho trovato una fonte istituzionale diretta (l'elenco completo delle Regioni ROSS1000), l'ho segnalato esplicitamente come dato da validare, invece di presentarlo come acquisito.

**Margine oltre il minimo richiesto:** il mandato chiede "almeno 3-4" sistemi; il set ne copre **4**, con margine per assorbire un eventuale errore di attribuzione su uno dei quattro (es. se la lista ROSS1000-Toscana risultasse imprecisa in validazione, restano comunque 3 sistemi confermati con fonte diretta: SPOT, Turist@t, ASTAT).

---

## 4. Comuni scartati che il lettore si aspetterebbe di trovare

Questa sezione è parte della consegna, non un'appendice.

### Roma e Milano — scartate per il punto 1 (turismo generico, non target)

Sono i due mercati Airbnb più grandi e maturi d'Italia, con una quota significativa di ricettività gestita da operatori professionali multi-unità, non dal segmento "host privato 1-3 unità" che è il target del prodotto:

- Roma: **28.034 annunci attivi**, tasso di occupazione 77%, tariffa media 146€/notte (fonte: trend-online.com, "Ecco qual è la città italiana con più Airbnb", 2025 — **da validare** con dato più recente/primario, fonte editoriale).
- Milano: mercato dove operano agenzie di gestione professionale con portafogli di centinaia di unità (es. "Italianway", 480 proprietà gestite solo a Milano secondo un'analisi indipendente su dati InsideAirbnb) — nonostante una quota di host "single-listing" alta in percentuale (~79%, stesso studio), il mercato in valore e in visibilità è trainato dalla fascia professionale, non dal segmento target. Fonte: bernomone.github.io, analisi indipendente su dati InsideAirbnb (estate 2025).
- Un articolo di settore (bergamonews.it, 2026) descrive esplicitamente Roma, Milano e Firenze come i mercati Airbnb "maturi" rispetto a mercati emergenti come Bergamo — confermando che il posizionamento di questi tre Comuni è quello di mercato consolidato/professionalizzato, non di frontiera del target host privato.

Non sono scartate per il punto 2: non ho verificato regolamenti caotici a Roma o Milano; lo scarto è esclusivamente sul punto 1, che essendo congiunto con gli altri due basta a escluderle.

### Firenze — scartata per il punto 2 (instabilità normativa) oltre che per il punto 1

Firenze combina entrambi i problemi:

- **Punto 1:** il centro storico UNESCO rappresenta il 5% del territorio comunale ma concentra circa il **75% degli appartamenti in affitto breve** (fonte: sni.unioncamere.it, sintesi della delibera comunale n.39/2023) — un segnale di alta concentrazione territoriale, ma in un contesto di grande scala urbana e forte presenza di gestione professionale, non del profilo "borgo a densità di host privati" cercato dal punto 1.
- **Punto 2 — la clausola che sorprende, applicata:** il Comune ha approvato nell'ottobre 2023 una delibera che vieta nuove attività di affitto breve nel centro storico UNESCO, poi dichiarata inefficace dal TAR nel luglio 2024 per un nuovo Piano Operativo Comunale (fonte: studiolessona.it, 055firenze.it). Un contesto normativo comunale **in contenzioso e in evoluzione attiva** al momento di questa analisi non soddisfa il criterio "regolamento pubblicato e leggibile" nello spirito del mandato: leggibile non significa solo "testo disponibile", significa anche stabile abbastanza da poter essere trasformato in configurazione senza rincorrere ogni ricorso amministrativo. Scartata, motivo documentato.

### Venezia — scartata per il punto 2 (complessità del regime, non illeggibilità del testo)

Venezia è l'unico Comune italiano con **due tributi turistici distinti e sovrapposti**: l'imposta di soggiorno tradizionale (per chi pernotta in struttura ricettiva registrata, limitata al centro storico esclusi le isole minori, tetto 5 notti) e il **contributo di accesso** (per i visitatori giornalieri senza pernottamento, attivo dal 2024, con tariffa differenziata 5€/10€ secondo anticipo di prenotazione e fasce orarie/date). Fonte: cda.ve.it (portale istituzionale del Comune di Venezia).

Il regolamento non è "caotico" nel senso di mal scritto o non pubblicato — è anzi ben documentato e con un portale FAQ dedicato — ma **il regime è strutturalmente il più complesso d'Italia**: due tributi con presupposti diversi, esenzioni incrociate (chi paga l'imposta di soggiorno deve dimostrare l'esenzione dal contributo di accesso nei giorni di sovrapposizione), e ambiti territoriali diversi (isole minori escluse da un tributo ma non necessariamente dall'altro). Configurare questo caso per primo, nel Comune più visibile e più atteso, avrebbe richiesto modellare un'eccezione strutturale prima ancora di validare il caso generale — un rischio di scope creep che il criterio 2, letto nello spirito indicato dal mandato ("se il regolamento è caotico il Comune si scarta, anche se ovvio"), è pensato per evitare in questa fase. Scartata, motivo documentato; buona candidata per un secondo perimetro dopo che il caso generale è in produzione.

---

## 5. Metodo e fonti — trasparenza sulla densità di host 1-3 unità

**Cosa esiste come dato pubblico verificabile:**
- Per il mercato nazionale: quasi 8 host su 10 in Italia (76%, dato 2021) mettono un solo annuncio sulla piattaforma Airbnb; le prenotazioni in aree rurali/borghi sono cresciute dal 21% (2019) al 37% del totale. Fonte: ricerca web, dati citati da fonti di settore su base InsideAirbnb/Airbnb (Airbnb + Touring Club Italiano, iniziativa borghi con Bandiera Arancione).
- Per singole grandi città: InsideAirbnb pubblica dataset scaricabili con granularità per host/annuncio (es. Milano, Roma) — usati indirettamente tramite l'analisi indipendente bernomone.github.io (Gini/concentrazione, ~8 città maggiori, dati estate 2025).
- Per i **6 Comuni scelti**, **non esiste un dataset quantitativo pubblico equivalente a InsideAirbnb**: la copertura di InsideAirbnb in Italia si ferma alle grandi città. La densità di host 1-3 unità nei 6 Comuni scelti è quindi una **valutazione qualitativa** basata su: dimensione demografica del Comune, struttura urbanistica del centro storico (che limita fisicamente la scala della gestione professionale), assenza — nella ricerca condotta — di segnalazioni di operatori multi-unità di scala paragonabile a quella osservata nelle grandi città, e per Polignano a Mare un'analogia territoriale con il dato quantitativo su Lecce (stessa Regione, stesso profilo di "città pugliese senza operatori sopra i 100 annunci").

**Questa è la lacuna dichiarata esplicitamente, come richiesto dal mandato:** il punto 1 del criterio, per 5 dei 6 Comuni (tutti tranne l'analogia parziale di Polignano), non è verificato da un numero misurato ma da un ragionamento qualitativo esplicito e da fonti giornalistiche/di settore, non da un dataset primario. Se in futuro emergesse un dataset comune-per-comune (es. un'estensione di InsideAirbnb, o un report ISTAT/Ministero del Turismo con granularità comunale), va usato per rivalidare il set — in particolare Cefalù e Ortisei, i due Comuni con l'evidenza più debole sul punto 1.

**Fonti usate, per categoria:**
- *Istituzionali dirette* (siti `.regione.*.it`, `.provincia.bz.it`, portali comunali `.comune.*.it`, portali statistici ufficiali): base per il punto 2 (tutti e 6 i Comuni) e per il punto 3 (Liguria, Puglia, Sicilia, PA Bolzano).
- *Editoriali di settore* (Chekin, Lodgify, ANBBA e simili — fornitori concorrenti o affini al settore compliance turistica): usate solo per colmare punti dove la fonte istituzionale diretta non è stata reperita in questa sessione di ricerca (es. elenco completo Regioni ROSS1000), e sempre marcate **"da validare"**, coerente con il rischio già registrato nel PRD §12.1.
- *Giornalistiche locali/nazionali*: usate per il contesto (tariffe, delibere, contenziosi) a supporto del punto 1 e delle motivazioni di scarto (§4).

---

## 6. Esito

**Lista dei 6 Comuni chiusa e motivata** secondo il mandato. Nessun blocco: il criterio applicato ai dati reali ha prodotto sei Comuni con margine sul punto 3 (4 sistemi contro il minimo di 3). La qualità del punto 1 varia tra i sei — dichiarata Comune per Comune in §2 e sintetizzata in §5 — e i due Comuni con l'evidenza più debole (Cefalù, Ortisei) sono segnalati come primi candidati a rivalidazione se emergono dati migliori prima della configurazione in Epic 3.

Questa lista alimenta il mandato del commercialista di Fahad (Readiness R-5): la verifica legale dei regolamenti dei 6 Comuni può ora partire su un perimetro definito.

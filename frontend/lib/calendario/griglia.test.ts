import { describe, expect, it } from "vitest";
import {
  collocazione,
  corsie,
  giorniDelPeriodo,
  giornoDellaSettimana,
  meseSpostato,
  periodoDelMese,
  periodoDellaSettimana,
  segmenti,
  settimanaSpostata,
} from "./griglia";

/**
 * AC 11 — mappatura intervallo → celle (AD-3).
 *
 * È un off-by-one di presentazione su una funzione pura: qui la matrice dei
 * confini costa millisecondi ed è esaustiva. Un e2e sullo stesso difetto
 * costerebbe cento volte tanto e coprirebbe un caso solo.
 */

const soggiorno = (check_in: string, check_out: string) => ({
  check_in,
  check_out,
});

describe("giorniDelPeriodo", () => {
  it("include entrambi gli estremi", () => {
    expect(giorniDelPeriodo({ da: "2026-08-01", a: "2026-08-03" })).toEqual([
      "2026-08-01",
      "2026-08-02",
      "2026-08-03",
    ]);
  });

  it("attraversa il cambio di ora legale senza perdere né duplicare giorni", () => {
    // 25 ottobre 2026: a Roma quel giorno ha 25 ore. Con un'aritmetica
    // basata su millisecondi in fuso locale, il 26 verrebbe generato due
    // volte o saltato — e le colonne della griglia si disallineerebbero da
    // lì in poi, per l'intero mese.
    expect(giorniDelPeriodo({ da: "2026-10-24", a: "2026-10-27" })).toEqual([
      "2026-10-24",
      "2026-10-25",
      "2026-10-26",
      "2026-10-27",
    ]);
    expect(giorniDelPeriodo({ da: "2026-03-28", a: "2026-03-30" })).toEqual([
      "2026-03-28",
      "2026-03-29",
      "2026-03-30",
    ]);
  });

  it("attraversa il cambio d'anno", () => {
    expect(giorniDelPeriodo({ da: "2026-12-31", a: "2027-01-01" })).toEqual([
      "2026-12-31",
      "2027-01-01",
    ]);
  });

  it("su un periodo rovesciato non inventa giorni", () => {
    expect(giorniDelPeriodo({ da: "2026-08-10", a: "2026-08-01" })).toEqual([]);
  });
});

describe("periodoDelMese", () => {
  it.each([
    ["2026-08-17", "2026-08-01", "2026-08-31"],
    ["2026-02-10", "2026-02-01", "2026-02-28"],
    ["2028-02-10", "2028-02-01", "2028-02-29"], // bisestile
    ["2026-12-25", "2026-12-01", "2026-12-31"],
  ])("da %s copre %s → %s", (riferimento, da, a) => {
    expect(periodoDelMese(riferimento)).toEqual({ da, a });
  });
});

describe("periodoDellaSettimana", () => {
  it("va da lunedì a domenica, come si legge un calendario in Italia", () => {
    // 2026-08-17 è un lunedì.
    expect(periodoDellaSettimana("2026-08-20")).toEqual({
      da: "2026-08-17",
      a: "2026-08-23",
    });
  });

  it("la domenica appartiene alla settimana che comincia il lunedì prima", () => {
    // Il difetto classico: con la domenica come primo giorno, la settimana
    // di un check-in domenicale è quella dopo, e l'Host non trova la
    // Prenotazione dove si aspetta.
    expect(periodoDellaSettimana("2026-08-23")).toEqual({
      da: "2026-08-17",
      a: "2026-08-23",
    });
  });

  it("il lunedì è il primo giorno della propria settimana", () => {
    expect(giornoDellaSettimana("2026-08-17")).toBe(0);
    expect(giornoDellaSettimana("2026-08-23")).toBe(6);
  });
});

describe("navigazione fra periodi", () => {
  it("il mese precedente e il successivo attraversano l'anno", () => {
    expect(meseSpostato("2026-01-01", -1)).toBe("2025-12-01");
    expect(meseSpostato("2026-12-01", 1)).toBe("2027-01-01");
  });

  it("la settimana si sposta di sette giorni, anche sul cambio d'ora", () => {
    expect(settimanaSpostata("2026-10-19", 1)).toBe("2026-10-26");
    expect(settimanaSpostata("2026-03-30", -1)).toBe("2026-03-23");
  });
});

describe("collocazione", () => {
  const agosto = giorniDelPeriodo({ da: "2026-08-01", a: "2026-08-31" });

  it("occupa le NOTTI, non i giorni: [check_in, check_out)", () => {
    // 10 → 14 agosto sono quattro notti (10, 11, 12, 13), non cinque.
    expect(collocazione(soggiorno("2026-08-10", "2026-08-14"), agosto)).toEqual({
      inizio: 9,
      celle: 4,
    });
  });

  it("una notte sola occupa una cella sola", () => {
    expect(collocazione(soggiorno("2026-08-01", "2026-08-02"), agosto)).toEqual({
      inizio: 0,
      celle: 1,
    });
  });

  it("un check-out sul primo giorno visibile non occupa nulla", () => {
    // L'ultima notte è il 31 luglio: in agosto questa Prenotazione non ha
    // pernottamenti, e disegnarla darebbe una cella che non corrisponde a
    // nessuna notte.
    expect(collocazione(soggiorno("2026-07-28", "2026-08-01"), agosto)).toBeNull();
  });

  it("un check-in sull'ultimo giorno visibile occupa l'ultima cella", () => {
    expect(collocazione(soggiorno("2026-08-31", "2026-09-03"), agosto)).toEqual({
      inizio: 30,
      celle: 1,
    });
  });

  it("ritaglia sui bordi chi entra da prima e chi esce da dopo", () => {
    // Senza il ritaglio l'indice sarebbe negativo a sinistra e l'ampiezza
    // sforerebbe la tabella a destra: la riga si allungherebbe oltre le
    // altre e le colonne si disallineerebbero.
    expect(collocazione(soggiorno("2026-07-28", "2026-08-03"), agosto)).toEqual({
      inizio: 0,
      celle: 2,
    });
    expect(collocazione(soggiorno("2026-08-30", "2026-09-05"), agosto)).toEqual({
      inizio: 29,
      celle: 2,
    });
    expect(collocazione(soggiorno("2026-07-01", "2026-09-30"), agosto)).toEqual({
      inizio: 0,
      celle: 31,
    });
  });

  it("attraversa il cambio di ora legale senza spostarsi di una cella", () => {
    const ottobre = giorniDelPeriodo({ da: "2026-10-01", a: "2026-10-31" });
    expect(collocazione(soggiorno("2026-10-24", "2026-10-27"), ottobre)).toEqual({
      inizio: 23,
      celle: 3,
    });
    const marzo = giorniDelPeriodo({ da: "2026-03-01", a: "2026-03-31" });
    expect(collocazione(soggiorno("2026-03-28", "2026-03-31"), marzo)).toEqual({
      inizio: 27,
      celle: 3,
    });
  });

  it("su una striscia vuota non colloca niente", () => {
    expect(collocazione(soggiorno("2026-08-10", "2026-08-14"), [])).toBeNull();
  });
});

describe("corsie", () => {
  const agosto = giorniDelPeriodo({ da: "2026-08-01", a: "2026-08-31" });

  it("mette in una corsia sola le Prenotazioni che non si toccano", () => {
    const voci = [
      soggiorno("2026-08-01", "2026-08-04"),
      soggiorno("2026-08-04", "2026-08-07"),
    ];
    expect(corsie(voci, agosto)).toHaveLength(1);
  });

  it("il turnover dello stesso giorno NON apre una seconda corsia", () => {
    // Check-out e check-in nello stesso giorno è il caso normale di un
    // affitto breve, non una sovrapposizione: le notti sono disgiunte.
    const [corsia] = corsie(
      [soggiorno("2026-08-01", "2026-08-05"), soggiorno("2026-08-05", "2026-08-08")],
      agosto,
    );
    expect(corsia).toHaveLength(2);
  });

  it("due Prenotazioni sovrapposte finiscono in corsie diverse ed è VISIBILE", () => {
    // È il caso che il prodotto esiste per far vedere: due portali che
    // hanno venduto la stessa notte. Disegnarne una sopra l'altra
    // nasconderebbe proprio ciò che l'Host deve notare.
    const disposte = corsie(
      [soggiorno("2026-08-10", "2026-08-15"), soggiorno("2026-08-12", "2026-08-18")],
      agosto,
    );
    expect(disposte).toHaveLength(2);
    expect(disposte[0]).toHaveLength(1);
    expect(disposte[1]).toHaveLength(1);
  });

  it("riempie la prima corsia libera invece di aprirne sempre una nuova", () => {
    const disposte = corsie(
      [
        soggiorno("2026-08-01", "2026-08-10"),
        soggiorno("2026-08-05", "2026-08-12"),
        soggiorno("2026-08-20", "2026-08-25"),
      ],
      agosto,
    );
    expect(disposte).toHaveLength(2);
    expect(disposte[0]).toHaveLength(2);
  });

  it("scarta chi non tocca il periodo invece di aprirgli una corsia vuota", () => {
    expect(corsie([soggiorno("2026-07-01", "2026-07-05")], agosto)).toEqual([]);
  });
});

describe("segmenti", () => {
  const settimana = giorniDelPeriodo({ da: "2026-08-01", a: "2026-08-07" });

  it("la somma delle ampiezze copre sempre tutta la striscia", () => {
    // È l'invariante che tiene allineate le colonne fra righe che usano
    // `colSpan`: se una riga somma sei celle e un'altra sette, la griglia
    // si sfalsa e le date smettono di corrispondere alle colonne.
    const casi = [
      [],
      [soggiorno("2026-08-01", "2026-08-03")],
      [soggiorno("2026-08-03", "2026-08-05")],
      [soggiorno("2026-08-06", "2026-08-08")],
      [soggiorno("2026-08-01", "2026-08-08")],
      [soggiorno("2026-07-30", "2026-08-10")],
    ];
    for (const corsia of casi) {
      const totale = segmenti(corsia, settimana).reduce(
        (somma, cella) => somma + cella.celle,
        0,
      );
      expect(totale).toBe(settimana.length);
    }
  });

  it("alterna vuoti e voci nell'ordine dei giorni", () => {
    const celle = segmenti(
      [soggiorno("2026-08-05", "2026-08-07"), soggiorno("2026-08-01", "2026-08-03")],
      settimana,
    );
    expect(celle.map((cella) => [cella.tipo, cella.celle])).toEqual([
      ["voce", 2],
      ["vuoto", 2],
      ["voce", 2],
      ["vuoto", 1],
    ]);
  });

  it("una corsia vuota è una sola cella larga quanto il periodo", () => {
    expect(segmenti([], settimana)).toEqual([{ tipo: "vuoto", celle: 7 }]);
  });
});

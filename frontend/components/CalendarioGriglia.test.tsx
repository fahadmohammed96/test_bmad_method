import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CalendarioGriglia } from "./CalendarioGriglia";
import type { VoceCalendario } from "@/lib/api/hooks";
import { giorniDelPeriodo } from "@/lib/calendario/griglia";

/**
 * Livello componente della griglia (AC 1, 2, 9, 10, 12).
 *
 * Qui si verifica ciò che il DOM dice: che il Canale sia distinguibile senza
 * il colore, che l'Ospite mancante non diventi un segnaposto, che una
 * Prenotazione uscita da `attiva` resti visibile con la sua etichetta, e che
 * le date siano in formato italiano.
 *
 * Quello che questo livello NON può vedere è la coerenza fra cache — qui gli
 * hook non esistono, quindi la cache non esiste nel loro mondo. Quella è
 * `frontend/e2e/calendario.spec.ts`, ed è l'unico testimone.
 */

const AGOSTO = giorniDelPeriodo({ da: "2026-08-01", a: "2026-08-31" });

const STRUTTURE = [
  { id: "s1", nome: "Bologna Centro" },
  { id: "s2", nome: "Mare Rimini" },
];

const voce = (dati: Partial<VoceCalendario> = {}): VoceCalendario => ({
  id: "p1",
  struttura_id: "s1",
  canale: "airbnb",
  check_in: "2026-08-10",
  check_out: "2026-08-14",
  notti: 4,
  sommario: null,
  stato: "attiva",
  ospite_principale: null,
  altri_ospiti: 0,
  ...dati,
});

const griglia = (voci: VoceCalendario[], strutture = STRUTTURE) =>
  render(
    <CalendarioGriglia giorni={AGOSTO} strutture={strutture} voci={voci} />,
  );

describe("aggregazione e distinzione per Canale (AC 1)", () => {
  it("mostra in un'unica griglia le Prenotazioni di tutte le Strutture", () => {
    griglia([
      voce({ id: "p1", struttura_id: "s1", ospite_principale: "Ospite Uno" }),
      voce({
        id: "p2",
        struttura_id: "s2",
        canale: "booking",
        ospite_principale: "Ospite Due",
      }),
    ]);

    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByText("Bologna Centro")).toBeInTheDocument();
    expect(screen.getByText("Mare Rimini")).toBeInTheDocument();
    expect(screen.getByText("Ospite Uno")).toBeInTheDocument();
    expect(screen.getByText("Ospite Due")).toBeInTheDocument();
  });

  it("distingue il Canale col TESTO, non solo col colore (UX-DR4)", () => {
    // Il colore da solo non arriva a chi non lo distingue e non sopravvive a
    // una stampa in bianco e nero — che per un calendario di pulizie è un
    // uso reale.
    griglia([
      voce({ id: "p1", canale: "airbnb" }),
      voce({ id: "p2", canale: "booking", check_in: "2026-08-20", check_out: "2026-08-22" }),
    ]);

    expect(screen.getByText("Airbnb")).toBeInTheDocument();
    expect(screen.getByText("Booking")).toBeInTheDocument();
  });

  it("una manuale si distingue da una da portale, e da «Altro»", () => {
    // Il Glossario mette l'inserimento manuale fra i Canali (PRD §4). Se
    // portasse la stessa etichetta di «Altro» — un terzo portale — l'Host non
    // distinguerebbe più ciò che ha scritto da ciò che è arrivato da fuori, che
    // è il confronto che gli interessa di più.
    griglia([
      voce({ id: "p1", canale: "manuale" }),
      voce({
        id: "p2",
        canale: "altro",
        check_in: "2026-08-20",
        check_out: "2026-08-22",
      }),
    ]);

    expect(screen.getByText("Inserita a mano")).toBeInTheDocument();
    expect(screen.getByText("Altro")).toBeInTheDocument();
  });

  it("una Struttura senza Prenotazioni resta una riga della griglia", () => {
    // Farla sparire darebbe una griglia in cui «non ho prenotazioni» e «non
    // ho quella Struttura» hanno lo stesso aspetto.
    griglia([]);

    expect(screen.getByText("Bologna Centro")).toBeInTheDocument();
    expect(screen.getByText("Mare Rimini")).toBeInTheDocument();
  });
});

describe("cosa mostra ogni Prenotazione (AC 2)", () => {
  it("Canale, Ospite, date e notti", () => {
    griglia([voce({ ospite_principale: "Ospite Inventato" })]);

    const cella = screen.getByText("Ospite Inventato").closest("td");
    expect(cella).not.toBeNull();
    const dentro = within(cella as HTMLElement);
    expect(dentro.getByText("Airbnb")).toBeInTheDocument();
    expect(dentro.getByText(/10\/08\/2026/)).toBeInTheDocument();
    expect(dentro.getByText(/4 notti/)).toBeInTheDocument();
  });

  it("senza Ospite noto scrive «Ospite non indicato», mai un finto nome", () => {
    // AD-21 / NFR-11: una Prenotazione senza Ospite resta valida, e il
    // segnaposto non deve somigliare a un nome — né essere il `sommario`,
    // che è testo opaco del portale.
    griglia([voce({ ospite_principale: null, sommario: "HMXY8Z - Airbnb" })]);

    expect(screen.getByText("Ospite non indicato")).toBeInTheDocument();
    expect(screen.queryByText(/HMXY8Z/)).toBeNull();
  });

  it("conta gli altri Ospiti registrati", () => {
    griglia([voce({ ospite_principale: "Intestatario", altri_ospiti: 2 })]);

    expect(screen.getByText("e altri 2 Ospiti")).toBeInTheDocument();
  });

  it("presenta le notti che riceve, senza ricalcolarle (AD-14)", () => {
    // Il numero arriva dall'API. Se il componente lo ricalcolasse dalle date
    // qui direbbe 4, e la differenza fra i due conti è esattamente il difetto
    // che AD-14 esiste per impedire.
    griglia([voce({ notti: 1 })]);

    expect(screen.getByText(/1 notte/)).toBeInTheDocument();
  });
});

describe("Prenotazioni non più attive (AC 12)", () => {
  it.each([
    ["cancellata", "Cancellata"],
    ["rimossa_dal_feed", "Non più nel portale"],
  ] as const)("%s resta visibile con la sua etichetta", (stato, etichetta) => {
    // AD-19 dice che non partecipano ai Conflitti, non che spariscono.
    // Farle sparire senza traccia contraddirebbe «archiviare, mai
    // distruggere» agli occhi dell'Host, che quella prenotazione l'ha vista
    // ieri (§4.2-12).
    griglia([voce({ stato, ospite_principale: "Ospite Inventato" })]);

    expect(screen.getByText("Ospite Inventato")).toBeInTheDocument();
    expect(screen.getByText(etichetta)).toBeInTheDocument();
  });

  it("una attiva non porta nessuna etichetta di stato", () => {
    griglia([voce({ ospite_principale: "Ospite Inventato" })]);

    expect(screen.queryByText("Cancellata")).toBeNull();
    expect(screen.queryByText("Attiva")).toBeNull();
  });

  it("l'attenuazione NON passa dall'opacità sul testo (E2-F4)", () => {
    // `opacity-*` sul contenitore composita l'opacità su tutto ciò che
    // contiene: a 0.7 il testo `text-xs` scendeva da 4.58:1 a 2.66:1, sotto
    // la soglia AA di 4.5:1 (NFR-8, WCAG 1.4.3). E a diventare illeggibile
    // era proprio il testo che PORTA lo stato — cioè l'informazione che AC
    // 12 e UX-DR4 vogliono affidata al testo e non al colore.
    //
    // jsdom non calcola il contrasto, quindi axe qui non lo vedrebbe: la
    // proprietà verificabile a questo livello è che l'attenuazione stia sul
    // bordo e sullo sfondo. Il contrasto reale lo misura l'e2e, su un chip
    // davvero renderizzato.
    griglia([
      voce({ stato: "rimossa_dal_feed", ospite_principale: "Ospite Inventato" }),
    ]);

    const chip = screen.getByText("Ospite Inventato").closest("div");
    const antenati: string[] = [];
    for (
      let nodo: HTMLElement | null = chip as HTMLElement;
      nodo !== null;
      nodo = nodo.parentElement
    ) {
      antenati.push(nodo.className ?? "");
    }
    const conOpacita = antenati.filter((classi) => /\bopacity-\d/.test(classi));
    expect(conOpacita).toEqual([]);
  });
});

describe("cancellazione di una manuale (Story 2.4, AC 3)", () => {
  it("senza `onCancella` la griglia è in sola lettura", () => {
    // La griglia è usata anche dove non c'è nulla da cancellare: l'azione è
    // opzionale, e la sua assenza non deve dipendere dal caso.
    griglia([voce({ canale: "manuale" })]);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("il nome accessibile del bottone porta la data", () => {
    // In una griglia mensile ci sono decine di bottoni «Cancella»: chi naviga
    // per elementi interattivi li sentirebbe tutti uguali.
    render(
      <CalendarioGriglia
        giorni={AGOSTO}
        strutture={STRUTTURE}
        voci={[voce({ canale: "manuale" })]}
        onCancella={() => {}}
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "Cancella la prenotazione del 10/08/2026",
      }),
    ).toBeInTheDocument();
  });

  it("mentre la cancellazione è in corso lo dice e non si riclicca", () => {
    render(
      <CalendarioGriglia
        giorni={AGOSTO}
        strutture={STRUTTURE}
        voci={[voce({ id: "p1", canale: "manuale" })]}
        onCancella={() => {}}
        idInCancellazione="p1"
      />,
    );

    expect(screen.getByText("Cancellazione in corso…")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("formati italiani (AC 10)", () => {
  it("le date sono gg/mm/aaaa e vengono dal modulo centralizzato", () => {
    griglia([voce({ check_in: "2026-08-03", check_out: "2026-08-09", notti: 6 })]);

    expect(screen.getByText(/03\/08\/2026 → 09\/08\/2026/)).toBeInTheDocument();
  });

  it("ogni colonna porta la data per esteso per chi non vede la griglia", () => {
    // L'iniziale «M» da sola è ambigua fra martedì e mercoledì: il testo
    // accessibile della colonna deve dire la data, non la sua abbreviazione.
    griglia([]);

    expect(
      screen.getByRole("columnheader", { name: "15/08/2026" }),
    ).toBeInTheDocument();
  });
});

describe("densità e sovrapposizioni (AC 9)", () => {
  it("con tre Strutture la griglia resta una tabella sola", () => {
    griglia(
      [voce({ id: "p1", struttura_id: "s3" })],
      [...STRUTTURE, { id: "s3", nome: "Lago Garda" }],
    );

    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByText("Lago Garda")).toBeInTheDocument();
  });

  it("due Prenotazioni sovrapposte sono ENTRAMBE visibili", () => {
    // È il caso che il prodotto esiste per far notare: disegnarne una sopra
    // l'altra nasconderebbe la doppia prenotazione.
    griglia([
      voce({ id: "p1", ospite_principale: "Ospite Uno" }),
      voce({
        id: "p2",
        canale: "booking",
        check_in: "2026-08-12",
        check_out: "2026-08-16",
        notti: 4,
        ospite_principale: "Ospite Due",
      }),
    ]);

    expect(screen.getByText("Ospite Uno")).toBeInTheDocument();
    expect(screen.getByText("Ospite Due")).toBeInTheDocument();
  });

  it("le righe di una Struttura hanno tutte la stessa larghezza in colonne", () => {
    // Invariante che tiene allineate le colonne quando le celle occupate
    // usano `colSpan`: se una riga somma trenta celle e un'altra trentuno,
    // le date smettono di corrispondere alle colonne.
    griglia([
      voce({ id: "p1", ospite_principale: "Ospite Uno" }),
      voce({
        id: "p2",
        check_in: "2026-08-12",
        check_out: "2026-08-16",
        ospite_principale: "Ospite Due",
      }),
    ]);

    const corpo = screen.getByText("Bologna Centro").closest("tbody");
    const larghezze = Array.from(
      (corpo as HTMLElement).querySelectorAll("tr"),
    ).map((riga) =>
      Array.from(riga.querySelectorAll("td")).reduce(
        (somma, cella) => somma + (cella.colSpan || 1),
        0,
      ),
    );
    expect(larghezze).toEqual([AGOSTO.length, AGOSTO.length]);
  });
});

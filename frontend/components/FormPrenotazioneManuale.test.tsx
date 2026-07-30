import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Il form di inserimento manuale (Story 2.4).
 *
 * Livello componente perché il difetto vive nel DOM: un campo dell'Ospite
 * dichiarato `required`, o precompilato con un valore dedotto, è una proprietà
 * del markup — e sarebbe la violazione dell'AC che dice che l'Host **può**, non
 * deve, indicare l'Ospite. Un test di integrazione non lo vedrebbe: il server
 * accetta comunque il payload che il form gli manda.
 */

const mutate = vi.fn();
const strutture = vi.fn();

vi.mock("@/lib/api/hooks", () => ({
  useStrutture: () => strutture(),
  useCreaPrenotazioneManuale: () => ({
    mutate,
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
  }),
}));

import { FormPrenotazioneManuale } from "./FormPrenotazioneManuale";

const BOLOGNA = { id: "s1", nome: "Bologna Centro", stato: "attiva" };
const RIMINI = { id: "s2", nome: "Mare Rimini", stato: "attiva" };
const ARCHIVIATA = { id: "s3", nome: "Vecchia Casa", stato: "archiviata" };

beforeEach(() => {
  mutate.mockReset();
  strutture.mockReturnValue({ data: [BOLOGNA] });
});

async function apri() {
  render(<FormPrenotazioneManuale />);
  await userEvent.click(
    screen.getByRole("button", { name: "Inserisci una prenotazione" }),
  );
}

async function compilaLeDate() {
  await userEvent.type(screen.getByLabelText("Arrivo"), "2026-09-10");
  await userEvent.type(screen.getByLabelText("Partenza"), "2026-09-14");
}

describe("l'Ospite è facoltativo DAVVERO", () => {
  it("nessun campo dell'Ospite è obbligatorio", async () => {
    await apri();

    for (const etichetta of [
      "Nome dell'Ospite (facoltativo)",
      "Email dell'Ospite (facoltativa)",
      "Telefono dell'Ospite (facoltativo)",
    ]) {
      expect(screen.getByLabelText(etichetta)).not.toBeRequired();
    }
  });

  it("ogni campo dell'Ospite DICHIARA di essere facoltativo", async () => {
    // Un campo che non lo dichiara si legge come obbligatorio, e il caso d'uso
    // più frequente dell'inserimento manuale — il blocco date — non ha nessun
    // Ospite da indicare.
    await apri();

    expect(
      screen.getByRole("group", { name: /Ospite \(facoltativo\)/ }),
    ).toBeVisible();
    expect(screen.getByLabelText(/Nome dell'Ospite \(facoltativo\)/)).toBeVisible();
  });

  it("nessun campo dell'Ospite parte con un valore", async () => {
    // «Mai precompilati con un valore dedotto» (NFR-11): non esiste una
    // sorgente da cui un nome di Ospite possa arrivare, e questo test è ciò
    // che impedisce di introdurne una domani.
    await apri();

    expect(screen.getByLabelText(/Nome dell'Ospite/)).toHaveValue("");
    expect(screen.getByLabelText(/Email dell'Ospite/)).toHaveValue("");
    expect(screen.getByLabelText(/Telefono dell'Ospite/)).toHaveValue("");
  });

  it("la nota NON diventa il nome dell'Ospite", async () => {
    // Il `sommario` è testo opaco della Prenotazione: scriverlo nella nota non
    // deve suggerire, riempire o proporre un nome — nemmeno come valore
    // iniziale del campo (`[DECISIONE MYL-40]` → PRD §14.2).
    await apri();

    await userEvent.type(
      screen.getByLabelText(/Nota \(facoltativa\)/),
      "Blocco per manutenzione",
    );

    expect(screen.getByLabelText(/Nome dell'Ospite/)).toHaveValue("");
  });

  it("un blocco date si salva senza toccare nessun campo dell'Ospite", async () => {
    await apri();
    await compilaLeDate();

    await userEvent.click(
      screen.getByRole("button", { name: "Salva la prenotazione" }),
    );

    expect(mutate).toHaveBeenCalledTimes(1);
    const [dati] = mutate.mock.calls[0];
    expect(dati.struttura_id).toBe("s1");
    expect(dati.check_in).toBe("2026-09-10");
    expect(dati.check_out).toBe("2026-09-14");
    // I campi vuoti si mandano come sono: è il SERVER a dire che tre campi
    // vuoti non sono un Ospite (AD-14). Normalizzare qui duplicherebbe una
    // regola di dominio sul lato sbagliato del confine, e la duplicazione
    // sopravviverebbe a un secondo client che non la fa.
    expect(dati.ospite).toEqual({ nome: "", email: "", telefono: "" });
  });

  it("un Ospite indicato viaggia nel payload", async () => {
    await apri();
    await compilaLeDate();
    await userEvent.type(
      screen.getByLabelText(/Nome dell'Ospite/),
      "Ospite Inventato",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Salva la prenotazione" }),
    );

    expect(mutate.mock.calls[0][0].ospite).toEqual({
      nome: "Ospite Inventato",
      email: "",
      telefono: "",
    });
  });
});

describe("la Struttura su cui si scrive", () => {
  it("con una sola Struttura è già scelta", async () => {
    await apri();

    expect(screen.getByLabelText("Struttura")).toHaveValue("s1");
  });

  it("con più Strutture non se ne elegge una d'ufficio", async () => {
    // Scriverebbe una Prenotazione sulla Struttura sbagliata al primo Host che
    // non guarda la tendina, e l'errore non è recuperabile con un `undo`.
    strutture.mockReturnValue({ data: [BOLOGNA, RIMINI] });
    await apri();

    expect(screen.getByLabelText("Struttura")).toHaveValue("");
  });

  it("una Struttura archiviata non è offerta", async () => {
    // Accetterebbe la scelta e il server la rifiuterebbe con un 422 (AD-20):
    // offrire una scelta che sappiamo già come finisce è un difetto di
    // prodotto, non un errore dell'Host.
    strutture.mockReturnValue({ data: [BOLOGNA, ARCHIVIATA] });
    await apri();

    expect(
      screen.queryByRole("option", { name: "Vecchia Casa" }),
    ).toBeNull();
    expect(screen.getByRole("option", { name: "Bologna Centro" })).toBeVisible();
  });

  it("senza Strutture attive lo dice, invece di mostrare un form inutile", async () => {
    strutture.mockReturnValue({ data: [ARCHIVIATA] });
    await apri();

    expect(
      screen.getByText(/Registra una Struttura per poter inserire/),
    ).toBeVisible();
    expect(screen.queryByLabelText("Arrivo")).toBeNull();
  });
});

describe("le date", () => {
  it("non partono da oggi: nessun valore iniziale, nessun orologio", async () => {
    // Un default «oggi» sarebbe un valore dedotto su un campo che decide
    // quali notti risultano occupate, e la superficie del Calendario non ha
    // un orologio proprio (guardia in lib/calendario/griglia.guardia.test.ts).
    await apri();

    expect(screen.getByLabelText("Arrivo")).toHaveValue("");
    expect(screen.getByLabelText("Partenza")).toHaveValue("");
  });

  it("la partenza non può precedere l'arrivo già nel browser", async () => {
    await apri();
    await userEvent.type(screen.getByLabelText("Arrivo"), "2026-09-10");

    // Non è un ricalcolo: è la STESSA stringa, e ferma l'errore più comune
    // senza reimplementare la semantica dell'intervallo (AD-3, AD-14). Il caso
    // `partenza = arrivo` resta un 422 del server, perché `min` ammette
    // l'uguaglianza.
    expect(screen.getByLabelText("Partenza")).toHaveAttribute(
      "min",
      "2026-09-10",
    );
  });

  it("dice all'Host che la notte della partenza resta libera", async () => {
    // È il confine dell'intervallo semiaperto detto in parole: è la ragione per
    // cui due prenotazioni che si toccano nello stesso giorno non sono un
    // conflitto, e l'Host deve poterlo capire senza leggere gli AD.
    await apri();

    expect(
      screen.getByText(/La notte della partenza resta libera/),
    ).toBeVisible();
  });
});

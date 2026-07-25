import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const struttureMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useStrutture: () => struttureMock(),
  useArchiviaStruttura: () => ({ mutate: vi.fn() }),
}));

import StrutturePage from "../(app)/strutture/page";

function struttura(n: number, extra: object = {}) {
  return {
    id: `s${n}`,
    nome: `Struttura ${n}`,
    comune: "Bologna",
    regione: "Emilia-Romagna",
    cin: "X",
    cin_mancante: false,
    stato: "attiva",
    ...extra,
  };
}

describe("Lista Strutture (FR-1)", () => {
  it("mostra badge CIN mancante non bloccante, testo + icona", () => {
    struttureMock.mockReturnValue({
      data: [struttura(1, { cin: null, cin_mancante: true })],
      isPending: false,
    });
    render(<StrutturePage />);
    expect(screen.getByText("CIN mancante")).toBeInTheDocument();
    expect(screen.getByText("Attiva")).toBeInTheDocument();
    // Il CTA di creazione resta disponibile: nessun blocco.
    expect(
      screen.getByRole("link", { name: /nuova struttura/i }),
    ).toBeInTheDocument();
  });

  it("con 3 attive spiega il cap del pilota e nasconde il CTA", () => {
    struttureMock.mockReturnValue({
      data: [struttura(1), struttura(2), struttura(3)],
      isPending: false,
    });
    render(<StrutturePage />);
    expect(screen.getByText(/il pilota copre da 1 a 3/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /nuova struttura/i })).toBeNull();
  });

  it("una archiviata non consuma il cap e resta visibile nello storico", () => {
    struttureMock.mockReturnValue({
      data: [struttura(1), struttura(2), struttura(3, { stato: "archiviata" })],
      isPending: false,
    });
    render(<StrutturePage />);
    expect(screen.getByText("Archiviata")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /nuova struttura/i }),
    ).toBeInTheDocument();
  });
});

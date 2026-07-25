import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const regimeMock = vi.fn();
const confermaMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useRegimeFiscale: () => regimeMock(),
  useConfermaLetturaRegime: () => ({
    mutate: confermaMock,
    isPending: false,
  }),
}));

import { PannelloTransizioneRegime } from "./PannelloTransizioneRegime";

const BASE = {
  stato: "disponibile",
  strutture_non_archiviate: 3,
  soglia: 3,
  oltre_soglia: true,
  regime: "imprenditoriale",
  testo: "Con 3 Strutture scatta la presunzione di imprenditorialità.",
  aliquote_citate: "cedolare secca 21% / 26%",
  disclaimer: "Informazione di orientamento, non una consulenza fiscale.",
  mostra_pannello_transizione: true,
};

describe("Pannello di transizione (UX-DR14, UJ-4)", () => {
  beforeEach(() => confermaMock.mockClear());

  it("alla transizione compare a schermo intero con disclaimer e due CTA", () => {
    regimeMock.mockReturnValue({ data: BASE });
    render(<PannelloTransizioneRegime />);

    const pannello = screen.getByRole("dialog");
    expect(pannello).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /cambia il tuo regime fiscale/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/consulenza fiscale/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ho capito, continua" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /commercialista/i }),
    ).toBeInTheDocument();
  });

  it('"Ho capito" conferma la lettura', () => {
    regimeMock.mockReturnValue({ data: BASE });
    render(<PannelloTransizioneRegime />);
    fireEvent.click(screen.getByRole("button", { name: "Ho capito, continua" }));
    expect(confermaMock).toHaveBeenCalled();
  });

  it("sotto soglia non compare: nessuna notifica residua", () => {
    regimeMock.mockReturnValue({
      data: { ...BASE, oltre_soglia: false, mostra_pannello_transizione: false },
    });
    render(<PannelloTransizioneRegime />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

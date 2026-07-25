import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const regimeMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useRegimeFiscale: () => regimeMock(),
}));

import { PannelloRegimeFiscale } from "./PannelloRegimeFiscale";

const DISCLAIMER =
  "Informazione di orientamento, non una consulenza fiscale: verifica sempre la tua situazione con un commercialista.";

function regime(extra: object = {}) {
  return {
    isPending: false,
    data: {
      stato: "disponibile",
      strutture_non_archiviate: 2,
      soglia: 3,
      oltre_soglia: false,
      regime: "cedolare_secca",
      testo: "Con 1-2 Strutture rientri di norma nella cedolare secca.",
      aliquote_citate: "cedolare secca 21% / 26%",
      disclaimer: DISCLAIMER,
      mostra_pannello_transizione: false,
      ...extra,
    },
  };
}

describe("PannelloRegimeFiscale persistente (UX-DR14)", () => {
  it("sotto soglia mostra il regime informativo e il disclaimer", () => {
    regimeMock.mockReturnValue(regime());
    render(<PannelloRegimeFiscale />);

    expect(screen.getByText("2 Strutture attive · Soglia: 3")).toBeInTheDocument();
    expect(
      screen.getByText(/rientri di norma nella cedolare secca/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/commercialista/)).toBeInTheDocument();
  });

  it("oltre soglia il disclaimer resta visibile", () => {
    regimeMock.mockReturnValue(
      regime({
        strutture_non_archiviate: 3,
        oltre_soglia: true,
        regime: "imprenditoriale",
        testo: "Con 3 Strutture serve la Partita IVA.",
      }),
    );
    render(<PannelloRegimeFiscale />);

    expect(screen.getByText(/Partita IVA/)).toBeInTheDocument();
    expect(screen.getByText(/commercialista/)).toBeInTheDocument();
  });

  it("senza parametri configurati non inventa un regime", () => {
    regimeMock.mockReturnValue(
      regime({
        stato: "configurazione_non_disponibile",
        soglia: null,
        regime: null,
        aliquote_citate: null,
        testo: "I parametri fiscali non sono ancora configurati.",
      }),
    );
    render(<PannelloRegimeFiscale />);

    expect(screen.getByText("Non ancora disponibile")).toBeInTheDocument();
    expect(screen.queryByText(/Soglia:/)).toBeNull();
  });
});

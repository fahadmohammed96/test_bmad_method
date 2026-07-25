import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/hooks", () => ({
  useRegioni: () => ({
    data: [
      { codice_istat: "08", nome: "Emilia-Romagna" },
      { codice_istat: "09", nome: "Toscana" },
    ],
  }),
  useComuni: () => ({
    data: [
      {
        codice_istat: "037006",
        nome: "Bologna",
        provincia: "BO",
        regione_codice_istat: "08",
      },
    ],
  }),
}));

import { CampiLuogo, type ValoriLuogo } from "./CampiLuogo";

const VUOTO: ValoriLuogo = { comune: "", comuneCodiceIstat: null, regione: "" };

describe("CampiLuogo (AD-9)", () => {
  const onChange = vi.fn();
  beforeEach(() => onChange.mockClear());

  it("scegliendo un Comune dai suggerimenti porta con sé codice e Regione", () => {
    render(<CampiLuogo valori={VUOTO} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Comune"), {
      target: { value: "Bologna" },
    });
    expect(onChange).toHaveBeenCalledWith({
      comune: "Bologna",
      comuneCodiceIstat: "037006",
      regione: "Emilia-Romagna",
    });
  });

  it("un Comune non in anagrafica resta scrivibile, senza codice", () => {
    render(<CampiLuogo valori={VUOTO} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Comune"), {
      target: { value: "Paese Inesistente" },
    });
    expect(onChange).toHaveBeenCalledWith({
      comune: "Paese Inesistente",
      comuneCodiceIstat: null,
      regione: "",
    });
  });

  it("le Regioni arrivano dall'anagrafica ufficiale", () => {
    render(<CampiLuogo valori={VUOTO} onChange={onChange} />);
    const select = screen.getByLabelText("Regione");
    expect(select).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Emilia-Romagna" }),
    ).toBeInTheDocument();
  });
});

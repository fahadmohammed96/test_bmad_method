import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const configurazioneMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useConfigurazioneNormativa: () => configurazioneMock(),
}));

import { PannelloConfigurazione } from "./PannelloConfigurazione";

const NON_DISPONIBILE = {
  stato: "configurazione_non_disponibile",
  motivo: "comune_non_configurato",
  messaggio:
    "La Tassa di soggiorno non è ancora configurata per il tuo Comune. Ti ricorderemo di gestirla a mano finché non lo sarà.",
  promemoria_manuale: true,
  parametri: null,
};

describe("PannelloConfigurazione (FR-2, AD-9)", () => {
  it("mostra i parametri quando il Comune è configurato", () => {
    configurazioneMock.mockReturnValue({
      isPending: false,
      data: {
        alla_data: "2026-07-25",
        tassa_soggiorno: {
          stato: "configurata",
          motivo: null,
          messaggio: "Configurazione disponibile e aggiornata.",
          promemoria_manuale: false,
          parametri: {
            importo_cent: 250,
            periodicita: "trimestrale",
            esenzione_eta_max: 12,
            esenzione_notti_oltre: null,
          },
        },
        istat: NON_DISPONIBILE,
      },
    });
    render(<PannelloConfigurazione strutturaId="s1" />);

    expect(screen.getByText(/2,50/)).toBeInTheDocument(); // formato italiano
    expect(screen.getByText(/Trimestrale/)).toBeInTheDocument();
    expect(screen.getByText(/minori di 12 anni/)).toBeInTheDocument();
    expect(screen.getByText("Configurata")).toBeInTheDocument();
  });

  it("degrada in sicurezza con messaggio informativo, senza importi", () => {
    configurazioneMock.mockReturnValue({
      isPending: false,
      data: {
        alla_data: "2026-07-25",
        tassa_soggiorno: NON_DISPONIBILE,
        istat: NON_DISPONIBILE,
      },
    });
    render(<PannelloConfigurazione strutturaId="s1" />);

    expect(screen.getAllByText("Non ancora configurata")).toHaveLength(2);
    expect(screen.getAllByText(/non è ancora configurata/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/€/)).toBeNull(); // mai un importo inventato
  });
});

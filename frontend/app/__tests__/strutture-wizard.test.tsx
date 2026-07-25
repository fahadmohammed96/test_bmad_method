import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const creaMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useCreaStruttura: () => ({
    mutate: creaMock,
    isPending: false,
    isError: false,
  }),
}));

import NuovaStrutturaPage from "../(app)/strutture/nuova/page";

function compilaFinoAlCin() {
  fireEvent.change(screen.getByLabelText(/nome della struttura/i), {
    target: { value: "Bologna Centro" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Avanti" }));
  fireEvent.change(screen.getByLabelText("Comune"), {
    target: { value: "Bologna" },
  });
  fireEvent.change(screen.getByLabelText("Regione"), {
    target: { value: "Emilia-Romagna" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Avanti" }));
}

describe("Wizard nuova Struttura (UX-DR3)", () => {
  beforeEach(() => creaMock.mockClear());

  it("guida passo-passo con progress indicator", () => {
    render(<NuovaStrutturaPage />);
    expect(screen.getByText("Passo 1 di 3")).toBeInTheDocument();
    compilaFinoAlCin();
    expect(screen.getByText("Passo 3 di 3")).toBeInTheDocument();
  });

  it("lo step CIN è saltabile: registra con cin null", () => {
    render(<NuovaStrutturaPage />);
    compilaFinoAlCin();
    fireEvent.click(screen.getByRole("button", { name: /salta per ora/i }));
    expect(creaMock).toHaveBeenCalledWith(
      {
        nome: "Bologna Centro",
        comune: "Bologna",
        regione: "Emilia-Romagna",
        cin: null,
      },
      expect.anything(),
    );
  });

  it("con CIN compilato lo invia", () => {
    render(<NuovaStrutturaPage />);
    compilaFinoAlCin();
    fireEvent.change(screen.getByLabelText(/cin/i), {
      target: { value: "IT01234567890AB" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /registra la struttura/i }),
    );
    expect(creaMock).toHaveBeenCalledWith(
      expect.objectContaining({ cin: "IT01234567890AB" }),
      expect.anything(),
    );
  });
});

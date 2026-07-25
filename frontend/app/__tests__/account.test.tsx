import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const mutatePreferenze = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useMe: () => ({
    data: {
      id: "x",
      email: "host@example.com",
      canale_notifica_preferito: "email",
    },
  }),
  useAggiornaPreferenze: () => ({
    mutate: mutatePreferenze,
    isSuccess: false,
  }),
  useCambiaPassword: () => ({
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
  }),
  useLogout: () => ({ mutate: vi.fn() }),
}));

import AccountPage from "../(app)/account/page";

describe("Pannello Account (UX-DR15)", () => {
  beforeEach(() => mutatePreferenze.mockClear());

  it("mostra email, preferenze di notifica, cambio password e Strutture", () => {
    render(<AccountPage />);
    expect(screen.getByText(/host@example\.com/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /preferenze di notifica/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /cambia password/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /strutture/i })).toBeInTheDocument();
  });

  it("cambiare canale invoca la mutazione tipizzata", () => {
    render(<AccountPage />);
    fireEvent.change(screen.getByRole("combobox", { name: /canale preferito/i }), {
      target: { value: "in_app" },
    });
    expect(mutatePreferenze).toHaveBeenCalledWith("in_app");
  });
});

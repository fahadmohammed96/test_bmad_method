import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

import { AppNav } from "./AppNav";

describe("AppNav (UX-DR1)", () => {
  it("mostra le 5 voci primarie, senza Strutture", () => {
    render(<AppNav />);
    for (const voce of [
      "Dashboard",
      "Calendario",
      "Prezzi",
      "Adempimenti",
      "Operatività",
    ]) {
      expect(screen.getByRole("link", { name: new RegExp(voce) })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(screen.queryByRole("link", { name: /strutture/i })).toBeNull();
  });

  it("la voce attiva è marcata con aria-current", () => {
    render(<AppNav />);
    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: /prezzi/i })).not.toHaveAttribute(
      "aria-current",
    );
  });
});

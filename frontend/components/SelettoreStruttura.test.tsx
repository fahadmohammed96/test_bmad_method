import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/hooks", () => ({
  useStrutture: () => ({
    data: [
      { id: "s1", nome: "Bologna Centro", stato: "attiva" },
      { id: "s2", nome: "Mare Rimini", stato: "attiva" },
      { id: "s3", nome: "Vecchia", stato: "archiviata" },
    ],
  }),
}));

import { SelettoreStruttura } from "./SelettoreStruttura";

describe("SelettoreStruttura (UX-DR1)", () => {
  it('ha "Tutte le Strutture" come default e le sole attive in lista', () => {
    render(<SelettoreStruttura />);
    const select = screen.getByRole("combobox", { name: /struttura/i });
    expect(select).toHaveValue("tutte");
    expect(
      screen.getByRole("option", { name: "Tutte le Strutture" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Bologna Centro" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Vecchia" })).toBeNull();
  });
});

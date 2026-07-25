import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SelettoreStruttura } from "./SelettoreStruttura";

describe("SelettoreStruttura (UX-DR1)", () => {
  it('ha "Tutte le Strutture" come default', () => {
    render(<SelettoreStruttura />);
    const select = screen.getByRole("combobox", { name: /struttura/i });
    expect(select).toHaveValue("tutte");
    expect(
      screen.getByRole("option", { name: "Tutte le Strutture" }),
    ).toBeInTheDocument();
  });
});

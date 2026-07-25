import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DashboardPage from "../(app)/dashboard/page";

describe("Dashboard frame (UX-DR2)", () => {
  it("mostra lo stato vuoto rassicurante e le sezioni future", () => {
    render(<DashboardPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/tutto tranquillo/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /calendario e conflitti/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /adempimenti in scadenza/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prezzi" })).toBeInTheDocument();
  });
});

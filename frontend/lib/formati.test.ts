import { describe, expect, it } from "vitest";
import { formatDataIt, formatEuroCent } from "./formati";

describe("formati italiani (UX-DR11)", () => {
  it("data in gg/mm/aaaa", () => {
    expect(formatDataIt(new Date(Date.UTC(2026, 6, 25, 12)))).toBe("25/07/2026");
  });

  it("valuta con virgola decimale e simbolo €", () => {
    // Nota CLDR it-IT: il separatore delle migliaia compare da 5 cifre in su.
    const testo = formatEuroCent(1234567);
    expect(testo).toContain("12.345,67");
    expect(testo).toContain("€");
    expect(formatEuroCent(14500)).toContain("145,00");
  });

  it("importi non interi rifiutati (convenzione centesimi)", () => {
    expect(() => formatEuroCent(12.5)).toThrow(TypeError);
  });
});

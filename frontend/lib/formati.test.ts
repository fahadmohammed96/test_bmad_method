import { describe, expect, it } from "vitest";
import { formatDataIt, formatEuroCent, formatGiornoIt } from "./formati";

describe("formati italiani (UX-DR11)", () => {
  it("data in gg/mm/aaaa", () => {
    expect(formatDataIt(new Date(Date.UTC(2026, 6, 25, 12)))).toBe("25/07/2026");
  });

  it("data di calendario ISO in gg/mm/aaaa, senza passare da un fuso", () => {
    // Le date di Prenotazione sono date locali Europe/Rome (AD-3), non
    // istanti: qui si riordinano i pezzi della stringa, così il risultato
    // non dipende da dove si trova il browser di chi guarda.
    expect(formatGiornoIt("2026-07-25")).toBe("25/07/2026");
    expect(formatGiornoIt("2026-01-01")).toBe("01/01/2026");
    // Confine del cambio d'ora legale: nessuno slittamento di un giorno.
    expect(formatGiornoIt("2026-10-25")).toBe("25/10/2026");
    expect(formatGiornoIt("2026-03-29")).toBe("29/03/2026");
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

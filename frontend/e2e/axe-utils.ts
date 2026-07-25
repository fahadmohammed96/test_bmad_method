import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/** Violazioni axe di impatto serious/critical (baseline WCAG 2.1 AA, NFR-8). */
export async function violazioniGravi(page: Page) {
  const risultati = await new AxeBuilder({ page }).analyze();
  return risultati.violations.filter((v) =>
    ["serious", "critical"].includes(v.impact ?? ""),
  );
}

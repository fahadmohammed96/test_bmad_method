import type { CanaleFeed } from "@/lib/api/hooks";
import { calendarioCopy } from "@/lib/copy/calendario";

/**
 * Distinzione visiva del Canale d'origine (FR-4, UX-DR4).
 *
 * **Testo + icona, mai solo colore.** Il colore da solo non arriva a chi non
 * lo distingue, e non sopravvive a una stampa in bianco e nero — che per un
 * calendario di pulizie è un uso reale. L'icona è `aria-hidden`: il nome del
 * Canale è già lì come testo, e leggerlo due volte a uno screen reader è
 * rumore.
 *
 * Il tratteggio (`▲` Airbnb, `■` Booking, `●` altro, `✎` inserita a mano) non
 * è decorazione: è la seconda dimensione oltre al colore, ed è ciò che rende la
 * griglia leggibile quando le prenotazioni di due portali si toccano.
 *
 * `manuale` è un Canale del Glossario (PRD §4), non un caso speciale: è ciò
 * che l'Host ha scritto di suo pugno, e distinguerlo da «Altro» — un terzo
 * portale — è il confronto che gli interessa più di tutti.
 */
const SEGNI: Record<CanaleFeed, string> = {
  airbnb: "▲",
  booking: "■",
  altro: "●",
  manuale: "✎",
};

const TONI: Record<CanaleFeed, string> = {
  airbnb: "border-accent/50 bg-accent/10 text-surface-contrast",
  booking: "border-primary/50 bg-primary/10 text-surface-contrast",
  altro: "border-muted/50 bg-surface text-surface-contrast",
  manuale: "border-primary/30 bg-surface text-surface-contrast",
};

export function BadgeCanale({ canale }: Readonly<{ canale: CanaleFeed }>) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs ${TONI[canale]}`}
    >
      <span aria-hidden="true">{SEGNI[canale]}</span>
      {calendarioCopy.canale[canale]}
    </span>
  );
}

"use client";

import { BadgeStato } from "@/components/BadgeStato";
import { useRegimeFiscale, type RegimeFiscale } from "@/lib/api/hooks";
import { regimeCopy } from "@/lib/copy/regime";

/**
 * Pannello Regime fiscale **persistente** (UX-DR14): resta accessibile in
 * ogni stato, con il disclaimer sempre visibile. Contenuto informativo,
 * mai un calcolo d'imposta (Non-Goal PRD §8).
 */
export function PannelloRegimeFiscale() {
  const { data: regime, isPending } = useRegimeFiscale();

  if (isPending || !regime) {
    return <output className="text-sm text-muted">Caricamento…</output>;
  }
  return <ContenutoRegime regime={regime} />;
}

export function ContenutoRegime({
  regime,
}: Readonly<{ regime: RegimeFiscale }>) {
  const disponibile = regime.stato === "disponibile";
  return (
    <section className="rounded-lg border p-4" aria-labelledby="titolo-regime">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="titolo-regime" className="font-semibold">
          {regimeCopy.titolo}
        </h2>
        <BadgeStato
          icona={disponibile ? "i" : "…"}
          testo={disponibile ? regimeCopy.disponibile : regimeCopy.nonDisponibile}
          tono="neutro"
        />
      </div>

      <p className="mt-2 text-sm">
        {regimeCopy.strutture(regime.strutture_non_archiviate)}
        {regime.soglia !== null && ` · ${regimeCopy.sogliaEtichetta}: ${regime.soglia}`}
      </p>
      <p className="mt-2 text-sm leading-relaxed">{regime.testo}</p>
      {regime.aliquote_citate && (
        <p className="mt-1 text-sm text-muted">
          {regimeCopy.aliquoteEtichetta}: {regime.aliquote_citate}
        </p>
      )}

      {/* Disclaimer sempre visibile, in ogni stato (UX-DR14). */}
      <p className="mt-3 border-t pt-2 text-xs text-muted">{regime.disclaimer}</p>
    </section>
  );
}

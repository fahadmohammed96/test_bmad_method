"use client";

import { useConfermaLetturaRegime, useRegimeFiscale } from "@/lib/api/hooks";
import { regimeCopy } from "@/lib/copy/regime";

/**
 * Pannello a schermo intero alla transizione di soglia (UX-DR14, UJ-4):
 * compare quando l'Host supera la soglia e resta finché non conferma la
 * lettura. Informativo con disclaimer, mai un calcolo d'imposta.
 */
export function PannelloTransizioneRegime() {
  const { data: regime } = useRegimeFiscale();
  const conferma = useConfermaLetturaRegime();

  if (!regime?.mostra_pannello_transizione) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="titolo-transizione-regime"
      className="fixed inset-0 z-50 flex items-center justify-center bg-surface p-6"
    >
      <div className="flex max-w-lg flex-col gap-4">
        <h2 id="titolo-transizione-regime" className="text-2xl font-semibold">
          {regime.soglia !== null
            ? regimeCopy.transizioneTitoloGenerico(regime.soglia)
            : regimeCopy.transizioneTitolo}
        </h2>
        <p className="leading-relaxed">{regime.testo}</p>
        {regime.aliquote_citate && (
          <p className="text-sm text-muted">
            {regimeCopy.aliquoteEtichetta}: {regime.aliquote_citate}
          </p>
        )}
        <p className="border-t pt-3 text-sm text-muted">{regime.disclaimer}</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => conferma.mutate()}
            disabled={conferma.isPending}
            className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
          >
            {regimeCopy.hoCapito}
          </button>
          <a
            href="https://www.agenziaentrate.gov.it"
            target="_blank"
            rel="noreferrer"
            className="rounded border px-3 py-2 text-sm"
          >
            {regimeCopy.parlaConCommercialista}
          </a>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { grigliaCopy } from "@/lib/copy/calendario";

/**
 * Cancellazione di una Prenotazione manuale, con conferma **inline**.
 *
 * **Perché una conferma.** Portare una Prenotazione a `cancellata` non è
 * reversibile dal prodotto: non esiste un percorso che la riporti ad `attiva`,
 * e un click accidentale su un chip largo pochi millimetri costerebbe una
 * prenotazione che l'Host deve reinserire a mano.
 *
 * **Perché non `window.confirm`.** Il dialogo nativo non è stilizzabile, non
 * dice *cosa* sta per succedere al dato in modo leggibile, e i browser
 * automatizzati lo rifiutano di default — cioè un test che lo attraversa
 * fallisce a valle in un modo che sembra un difetto della pagina. Due bottoni
 * nel DOM sono anche l'unica forma su cui axe può dire qualcosa.
 *
 * Le parole dicono la verità sul dato: la prenotazione **resta** nel
 * calendario, segnata come cancellata (AD-19, AD-20). Un «elimina» che
 * promette la sparizione sarebbe una bugia sull'unico punto che conta.
 */
export function AzioneCancellaPrenotazione({
  etichetta,
  inCorso,
  onConferma,
}: Readonly<{
  etichetta: string;
  inCorso: boolean;
  onConferma: () => void;
}>) {
  const [chiesto, setChiesto] = useState(false);

  if (inCorso) {
    return (
      <output className="text-xs text-muted">
        {grigliaCopy.cancellaInCorso}
      </output>
    );
  }

  if (!chiesto) {
    return (
      <button
        type="button"
        // Il nome accessibile porta la data: in una griglia ci sono decine di
        // bottoni «Cancella», e chi naviga per elementi interattivi li
        // sentirebbe tutti uguali.
        aria-label={etichetta}
        onClick={() => setChiesto(true)}
        className="self-start rounded border px-1.5 py-0.5 text-xs"
      >
        {grigliaCopy.cancellaBreve}
      </button>
    );
  }

  return (
    <div role="group" aria-label={etichetta} className="flex flex-col gap-1">
      <p className="text-xs">{grigliaCopy.cancellaDomanda}</p>
      <p className="text-xs text-muted">{grigliaCopy.cancellaSpiegazione}</p>
      <div className="flex flex-wrap gap-1">
        <button
          type="button"
          onClick={() => {
            setChiesto(false);
            onConferma();
          }}
          className="rounded border border-danger/40 px-1.5 py-0.5 text-xs text-danger"
        >
          {grigliaCopy.cancellaConferma}
        </button>
        <button
          type="button"
          onClick={() => setChiesto(false)}
          className="rounded border px-1.5 py-0.5 text-xs"
        >
          {grigliaCopy.cancellaAnnulla}
        </button>
      </div>
    </div>
  );
}

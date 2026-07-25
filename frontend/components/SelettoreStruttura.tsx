"use client";

import { useState } from "react";

export const TUTTE_LE_STRUTTURE = "tutte";

/**
 * Selettore Struttura trasversale (UX-DR1): "Tutte le Strutture" di default.
 * Le Strutture reali popolano la lista dalla Story 1.4.
 */
export function SelettoreStruttura() {
  const [selezione, setSelezione] = useState<string>(TUTTE_LE_STRUTTURE);
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">Struttura</span>
      <select
        value={selezione}
        onChange={(evento) => setSelezione(evento.target.value)}
        className="rounded border px-2 py-1"
      >
        <option value={TUTTE_LE_STRUTTURE}>Tutte le Strutture</option>
      </select>
    </label>
  );
}

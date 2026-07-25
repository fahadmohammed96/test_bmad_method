"use client";

import { useState } from "react";
import { useStrutture } from "@/lib/api/hooks";

export const TUTTE_LE_STRUTTURE = "tutte";

/**
 * Selettore Struttura trasversale (UX-DR1): "Tutte le Strutture" di default,
 * popolato con le Strutture attive dell'Host.
 */
export function SelettoreStruttura() {
  const [selezione, setSelezione] = useState<string>(TUTTE_LE_STRUTTURE);
  const { data: strutture } = useStrutture();
  const attive = (strutture ?? []).filter((s) => s.stato === "attiva");

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">Struttura</span>
      <select
        value={selezione}
        onChange={(evento) => setSelezione(evento.target.value)}
        className="rounded border px-2 py-1"
      >
        <option value={TUTTE_LE_STRUTTURE}>Tutte le Strutture</option>
        {attive.map((struttura) => (
          <option key={struttura.id} value={struttura.id}>
            {struttura.nome}
          </option>
        ))}
      </select>
    </label>
  );
}

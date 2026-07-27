"use client";

import {
  TUTTE_LE_STRUTTURE,
  useSelezioneStruttura,
} from "@/components/SelezioneStruttura";
import { useStrutture } from "@/lib/api/hooks";

export { TUTTE_LE_STRUTTURE };

/**
 * Selettore Struttura trasversale (UX-DR1): "Tutte le Strutture" di default,
 * popolato con le Strutture attive dell'Host.
 *
 * La selezione vive nel context e non qui: è ciò che permette al Calendario
 * di filtrare **senza cambiare schermata**, che è l'AC. Con lo stato locale
 * questa tendina cambierebbe solo se stessa.
 */
export function SelettoreStruttura() {
  const { selezione, imposta } = useSelezioneStruttura();
  const { data: strutture } = useStrutture();
  const attive = (strutture ?? []).filter((s) => s.stato === "attiva");

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">Struttura</span>
      <select
        value={selezione}
        onChange={(evento) => imposta(evento.target.value)}
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

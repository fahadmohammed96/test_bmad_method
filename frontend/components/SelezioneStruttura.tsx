"use client";

import { createContext, useContext, useMemo, useState } from "react";

/** Valore del selettore quando non si filtra su nessuna Struttura. */
export const TUTTE_LE_STRUTTURE = "tutte";

type Selezione = {
  readonly selezione: string;
  readonly imposta: (valore: string) => void;
};

const ContestoSelezione = createContext<Selezione | null>(null);

/**
 * Stato condiviso del selettore Struttura trasversale (UX-DR1).
 *
 * Il selettore vive nell'intestazione della shell e le superfici che filtra
 * vivono nel contenuto: senza uno stato condiviso sarebbero due componenti
 * che non si parlano, e «filtra senza cambiare schermata» diventerebbe
 * «cambia una tendina che non fa niente».
 *
 * Non è uno store globale — è un solo valore, ed è la ragione per cui sta in
 * un context invece che in una libreria di stato (spine: nessuno store
 * aggiuntivo senza motivazione registrata).
 */
export function ProviderSelezioneStruttura({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [selezione, imposta] = useState<string>(TUTTE_LE_STRUTTURE);
  const valore = useMemo(() => ({ selezione, imposta }), [selezione]);
  return (
    <ContestoSelezione.Provider value={valore}>
      {children}
    </ContestoSelezione.Provider>
  );
}

export function useSelezioneStruttura(): Selezione {
  const valore = useContext(ContestoSelezione);
  if (valore === null) {
    throw new Error(
      "useSelezioneStruttura richiede <ProviderSelezioneStruttura>",
    );
  }
  return valore;
}

/** La Struttura selezionata, o `undefined` per la vista aggregata. */
export function strutturaFiltrata(selezione: string): string | undefined {
  return selezione === TUTTE_LE_STRUTTURE ? undefined : selezione;
}

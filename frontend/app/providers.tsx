"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

/**
 * Provider del root layout: qui vive SOLO ciò che deve valere anche fuori
 * dalla shell autenticata.
 *
 * La selezione Struttura non è fra questi (E2-F3): sta in
 * `app/(app)/layout.tsx`, così uscire smonta il provider e l'Host successivo
 * nella stessa scheda non eredita il filtro del precedente.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

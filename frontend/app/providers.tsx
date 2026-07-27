"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ProviderSelezioneStruttura } from "@/components/SelezioneStruttura";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      {/* Il selettore Struttura sta nell'intestazione della shell e filtra
          il contenuto: la selezione va condivisa fra i due (UX-DR1). */}
      <ProviderSelezioneStruttura>{children}</ProviderSelezioneStruttura>
    </QueryClientProvider>
  );
}

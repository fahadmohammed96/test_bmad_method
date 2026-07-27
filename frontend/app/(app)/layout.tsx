"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppNav } from "@/components/AppNav";
import { PannelloTransizioneRegime } from "@/components/PannelloTransizioneRegime";
import { ProviderSelezioneStruttura } from "@/components/SelezioneStruttura";
import { SelettoreStruttura } from "@/components/SelettoreStruttura";
import { useMe } from "@/lib/api/hooks";
import { navCopy } from "@/lib/copy/nav";

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const { data: me, isPending, isError } = useMe();

  useEffect(() => {
    if (!isPending && (me === null || isError)) {
      router.replace("/accesso");
    }
  }, [isPending, me, isError, router]);

  if (isPending || me === null || isError || !me) {
    return (
      <p className="p-6 text-muted" role="status">
        Caricamento…
      </p>
    );
  }

  return (
    // **Il provider della selezione vive QUI, dentro la shell autenticata**
    // (E2-F3), non nel root layout. Sopra il route group sopravviveva
    // all'uscita, e l'Host successivo nella stessa scheda ereditava l'UUID
    // di una Struttura che non è sua: il `<select>` si presentava vuoto
    // dichiarando di non filtrare, e il calendario restava fermo su «non
    // riusciamo a caricare» — stabile, perché la chiave non cambiava e ogni
    // retry rifalliva sullo stesso 404.
    //
    // Montarlo qui non è «ricordarsi di azzerare al logout»: è la struttura
    // che lo garantisce, perché uscire dalla shell smonta il provider.
    <ProviderSelezioneStruttura>
      <div className="min-h-screen md:flex">
        <AppNav />
        <div className="flex-1">
          <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
            <SelettoreStruttura />
            <Link
              href="/account"
              className="text-sm underline-offset-2 hover:underline"
            >
              {navCopy.account} — {me.email}
            </Link>
          </header>
          <main className="p-4 pb-24 md:pb-6">{children}</main>
        </div>
        {/* Pannello a schermo intero alla transizione di soglia (UX-DR14):
            vive nella shell, così compare ovunque si trovi l'Host. */}
        <PannelloTransizioneRegime />
      </div>
    </ProviderSelezioneStruttura>
  );
}

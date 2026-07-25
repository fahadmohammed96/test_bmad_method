"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormCredenziali } from "@/components/FormCredenziali";
import { useRegistrazione } from "@/lib/api/hooks";
import { authCopy } from "@/lib/copy/auth";

export default function RegistrazionePage() {
  const router = useRouter();
  const registrazione = useRegistrazione();

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6">
      <FormCredenziali
        titolo={authCopy.registrazioneTitolo}
        azione={authCopy.registrati}
        inCorso={registrazione.isPending}
        errore={registrazione.isError ? registrazione.error.message : null}
        nuovaPassword
        onSubmit={(credenziali) =>
          registrazione.mutate(credenziali, {
            onSuccess: () => router.replace("/dashboard"),
          })
        }
      />
      <Link href="/accesso" className="text-sm underline-offset-2 hover:underline">
        {authCopy.vaiAdAccesso}
      </Link>
    </main>
  );
}

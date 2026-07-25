"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormCredenziali } from "@/components/FormCredenziali";
import { useLogin } from "@/lib/api/hooks";
import { authCopy } from "@/lib/copy/auth";

export default function AccessoPage() {
  const router = useRouter();
  const login = useLogin();

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6">
      <FormCredenziali
        titolo={authCopy.accessoTitolo}
        azione={authCopy.accedi}
        inCorso={login.isPending}
        errore={login.isError ? login.error.message : null}
        nuovaPassword={false}
        onSubmit={(credenziali) =>
          login.mutate(credenziali, {
            onSuccess: () => router.replace("/dashboard"),
          })
        }
      />
      <Link href="/registrazione" className="text-sm underline-offset-2 hover:underline">
        {authCopy.vaiARegistrazione}
      </Link>
    </main>
  );
}

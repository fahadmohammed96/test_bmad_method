"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/lib/api/hooks";

/** La home smista: Host autenticato → Dashboard, altrimenti → Accesso. */
export default function Home() {
  const router = useRouter();
  const { data: me, isPending, isError } = useMe();

  useEffect(() => {
    if (isPending) return;
    router.replace(me && !isError ? "/dashboard" : "/accesso");
  }, [isPending, me, isError, router]);

  return (
    <p className="p-6 text-muted" role="status">
      Caricamento…
    </p>
  );
}

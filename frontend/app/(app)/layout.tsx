"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppNav } from "@/components/AppNav";
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
    <div className="min-h-screen md:flex">
      <AppNav />
      <div className="flex-1">
        <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
          <SelettoreStruttura />
          <Link href="/account" className="text-sm underline-offset-2 hover:underline">
            {navCopy.account} — {me.email}
          </Link>
        </header>
        <main className="p-4 pb-24 md:pb-6">{children}</main>
      </div>
    </div>
  );
}

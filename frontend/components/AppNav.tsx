"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navCopy } from "@/lib/copy/nav";

const VOCI = [
  { href: "/dashboard", label: navCopy.dashboard, icona: "▦" },
  { href: "/calendario", label: navCopy.calendario, icona: "▤" },
  { href: "/prezzi", label: navCopy.prezzi, icona: "€" },
  { href: "/adempimenti", label: navCopy.adempimenti, icona: "✓" },
  { href: "/operativita", label: navCopy.operativita, icona: "☰" },
] as const;

/**
 * Navigazione primaria a 5 voci (UX-DR1): tab bar in basso su mobile,
 * sidebar su desktop. Strutture NON è una voce: vive in Account.
 */
export function AppNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label={navCopy.etichettaNav}
      className="fixed inset-x-0 bottom-0 z-10 border-t bg-surface md:static md:w-56 md:border-t-0 md:border-r"
    >
      <ul className="flex justify-around md:flex-col md:justify-start md:gap-1 md:p-4">
        {VOCI.map((voce) => {
          const attiva = pathname.startsWith(voce.href);
          return (
            <li key={voce.href}>
              <Link
                href={voce.href}
                aria-current={attiva ? "page" : undefined}
                className={`flex flex-col items-center gap-0.5 px-2 py-2 text-xs md:flex-row md:gap-2 md:rounded md:px-3 md:text-sm ${
                  attiva ? "font-semibold text-primary" : "text-muted"
                }`}
              >
                <span aria-hidden="true">{voce.icona}</span>
                {voce.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

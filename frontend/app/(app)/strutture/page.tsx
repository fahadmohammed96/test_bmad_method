"use client";

import Link from "next/link";
import { BadgeStato } from "@/components/BadgeStato";
import { useArchiviaStruttura, useStrutture } from "@/lib/api/hooks";
import { struttureCopy } from "@/lib/copy/strutture";

const MAX_ATTIVE = 3; // cap di prodotto del pilota, imposto dal backend

export default function StrutturePage() {
  const { data: strutture, isPending } = useStrutture();
  const archivia = useArchiviaStruttura();

  if (isPending) {
    return (
      <output className="text-muted">Caricamento…</output>
    );
  }

  const lista = strutture ?? [];
  const attive = lista.filter((s) => s.stato === "attiva").length;
  const capRaggiunto = attive >= MAX_ATTIVE;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{struttureCopy.titolo}</h1>
          <p className="text-sm text-muted">{struttureCopy.sottotitolo}</p>
        </div>
        {capRaggiunto ? (
          <output className="max-w-sm text-sm text-muted">
            {struttureCopy.capRaggiunto}
          </output>
        ) : (
          <Link
            href="/strutture/nuova"
            className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast"
          >
            {struttureCopy.nuova}
          </Link>
        )}
      </div>

      {lista.length === 0 && <p className="text-muted">{struttureCopy.nessuna}</p>}

      <ul className="flex flex-col gap-3">
        {lista.map((struttura) => (
          <li
            key={struttura.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"
          >
            <div className="flex flex-col gap-1">
              <span className="font-semibold">{struttura.nome}</span>
              <span className="text-sm text-muted">
                {struttura.comune} · {struttura.regione}
              </span>
              <span className="flex flex-wrap gap-2">
                {struttura.stato === "attiva" ? (
                  <BadgeStato icona="●" testo={struttureCopy.statoAttiva} tono="ok" />
                ) : (
                  <BadgeStato
                    icona="▪"
                    testo={struttureCopy.statoArchiviata}
                    tono="neutro"
                  />
                )}
                {struttura.stato === "attiva" && struttura.cin_mancante && (
                  <BadgeStato
                    icona="!"
                    testo={struttureCopy.cinMancante}
                    tono="avviso"
                  />
                )}
              </span>
            </div>
            {struttura.stato === "attiva" && (
              <span className="flex gap-2">
                <Link
                  href={`/strutture/${struttura.id}`}
                  className="rounded border px-3 py-1.5 text-sm"
                >
                  {struttureCopy.modifica}
                </Link>
                <button
                  type="button"
                  className="rounded border px-3 py-1.5 text-sm"
                  onClick={() => {
                    if (window.confirm(struttureCopy.archiviaConferma)) {
                      archivia.mutate(struttura.id);
                    }
                  }}
                >
                  {struttureCopy.archivia}
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

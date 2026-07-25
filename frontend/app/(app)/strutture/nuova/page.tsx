"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CampiLuogo, type ValoriLuogo } from "@/components/CampiLuogo";
import { useCreaStruttura } from "@/lib/api/hooks";
import { struttureCopy } from "@/lib/copy/strutture";

const TOTALE_PASSI = 3;

/**
 * Wizard di registrazione Struttura (UX-DR3): passo-passo con progress,
 * tooltip sui termini normativi, CIN sempre saltabile — l'onboarding non
 * si blocca mai.
 */
export default function NuovaStrutturaPage() {
  const router = useRouter();
  const crea = useCreaStruttura();
  const [passo, setPasso] = useState(1);
  const [nome, setNome] = useState("");
  const [luogo, setLuogo] = useState<ValoriLuogo>({
    comune: "",
    comuneCodiceIstat: null,
    regione: "",
  });
  const [cin, setCin] = useState("");

  function registra(conCin: boolean) {
    crea.mutate(
      {
        nome,
        comune: luogo.comune,
        regione: luogo.regione,
        comune_codice_istat: luogo.comuneCodiceIstat,
        cin: conCin && cin.trim() !== "" ? cin.trim() : null,
      },
      { onSuccess: () => router.push("/strutture") },
    );
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-semibold">{struttureCopy.wizardTitolo}</h1>
      <p className="text-sm text-muted" aria-live="polite">
        {struttureCopy.wizardPasso(passo, TOTALE_PASSI)}
      </p>

      {passo === 1 && (
        <form
          className="flex flex-col gap-3"
          onSubmit={(evento) => {
            evento.preventDefault();
            setPasso(2);
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            {struttureCopy.nomeEtichetta}
            <input
              required
              maxLength={200}
              value={nome}
              onChange={(evento) => setNome(evento.target.value)}
              className="rounded border px-2 py-2"
            />
          </label>
          <p className="text-xs text-muted">{struttureCopy.nomeAiuto}</p>
          <button
            type="submit"
            className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast"
          >
            {struttureCopy.wizardAvanti}
          </button>
        </form>
      )}

      {passo === 2 && (
        <form
          className="flex flex-col gap-3"
          onSubmit={(evento) => {
            evento.preventDefault();
            setPasso(3);
          }}
        >
          <CampiLuogo valori={luogo} onChange={setLuogo} />
          <details className="text-sm text-muted">
            <summary className="cursor-pointer">
              {struttureCopy.comuneAiutoTitolo}
            </summary>
            <p className="mt-1">{struttureCopy.comuneAiuto}</p>
          </details>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPasso(1)}
              className="rounded border px-3 py-2 text-sm"
            >
              {struttureCopy.wizardIndietro}
            </button>
            <button
              type="submit"
              className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast"
            >
              {struttureCopy.wizardAvanti}
            </button>
          </div>
        </form>
      )}

      {passo === 3 && (
        <form
          className="flex flex-col gap-3"
          onSubmit={(evento) => {
            evento.preventDefault();
            registra(true);
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            {struttureCopy.cinEtichetta}
            <input
              maxLength={30}
              value={cin}
              onChange={(evento) => setCin(evento.target.value)}
              className="rounded border px-2 py-2"
            />
          </label>
          <details className="text-sm text-muted">
            <summary className="cursor-pointer">
              {struttureCopy.cinAiutoTitolo}
            </summary>
            <p className="mt-1">{struttureCopy.cinAiuto}</p>
          </details>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setPasso(2)}
              className="rounded border px-3 py-2 text-sm"
            >
              {struttureCopy.wizardIndietro}
            </button>
            <button
              type="button"
              onClick={() => registra(false)}
              disabled={crea.isPending}
              className="rounded border px-3 py-2 text-sm disabled:opacity-50"
            >
              {struttureCopy.wizardSaltaCin}
            </button>
            <button
              type="submit"
              disabled={crea.isPending}
              className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
            >
              {struttureCopy.wizardRegistra}
            </button>
          </div>
          {crea.isError && (
            <p role="alert" className="text-sm text-danger">
              {crea.error.message}
            </p>
          )}
        </form>
      )}
    </div>
  );
}

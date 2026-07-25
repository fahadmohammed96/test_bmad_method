"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { CampiLuogo, type ValoriLuogo } from "@/components/CampiLuogo";
import { PannelloConfigurazione } from "@/components/PannelloConfigurazione";
import {
  useAggiornaStruttura,
  useStrutture,
  type StrutturaOutput,
} from "@/lib/api/hooks";
import { struttureCopy } from "@/lib/copy/strutture";

export default function ModificaStrutturaPage() {
  const params = useParams<{ struttura_id: string }>();
  const { data: strutture } = useStrutture();
  const struttura = (strutture ?? []).find((s) => s.id === params.struttura_id);

  if (!struttura) {
    return <output className="text-muted">Caricamento…</output>;
  }
  // key: rimonta il form se si naviga tra Strutture diverse.
  return <FormModifica key={struttura.id} struttura={struttura} />;
}

function FormModifica({
  struttura,
}: Readonly<{ struttura: StrutturaOutput }>) {
  const router = useRouter();
  const aggiorna = useAggiornaStruttura();
  const [nome, setNome] = useState(struttura.nome);
  const [luogo, setLuogo] = useState<ValoriLuogo>({
    comune: struttura.comune,
    comuneCodiceIstat: struttura.comune_codice_istat,
    regione: struttura.regione,
  });
  const [cin, setCin] = useState(struttura.cin ?? "");

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4">
      <h1 className="text-2xl font-semibold">
        {struttureCopy.modifica}: {struttura.nome}
      </h1>
      <form
        className="flex flex-col gap-3"
        onSubmit={(evento) => {
          evento.preventDefault();
          aggiorna.mutate(
            {
              struttura_id: struttura.id,
              modifiche: {
                nome,
                comune: luogo.comune,
                regione: luogo.regione,
                comune_codice_istat: luogo.comuneCodiceIstat,
                cin: cin.trim() === "" ? null : cin.trim(),
              },
            },
            { onSuccess: () => router.push("/strutture") },
          );
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
        <CampiLuogo valori={luogo} onChange={setLuogo} />
        <label className="flex flex-col gap-1 text-sm">
          {struttureCopy.cinEtichetta}
          <input
            maxLength={30}
            value={cin}
            onChange={(evento) => setCin(evento.target.value)}
            className="rounded border px-2 py-2"
          />
        </label>
        <p className="text-xs text-muted">{struttureCopy.cinMancanteNota}</p>
        <button
          type="submit"
          disabled={aggiorna.isPending}
          className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
        >
          {struttureCopy.salva}
        </button>
        {aggiorna.isError && (
          <p role="alert" className="text-sm text-danger">
            {aggiorna.error.message}
          </p>
        )}
      </form>

      <PannelloConfigurazione strutturaId={struttura.id} />
    </div>
  );
}

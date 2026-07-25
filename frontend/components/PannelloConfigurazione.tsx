"use client";

import { BadgeStato } from "@/components/BadgeStato";
import { useConfigurazioneNormativa } from "@/lib/api/hooks";
import { configurazioneCopy } from "@/lib/copy/configurazione";
import { formatEuroCent } from "@/lib/formati";

type Periodicita = keyof typeof configurazioneCopy.periodicita;

function Area({
  titolo,
  stato,
  messaggio,
  dettagli,
}: Readonly<{
  titolo: string;
  stato: "configurata" | "configurazione_non_disponibile";
  messaggio: string;
  dettagli: readonly string[];
}>) {
  const configurata = stato === "configurata";
  return (
    <section className="rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{titolo}</h3>
        <BadgeStato
          icona={configurata ? "●" : "…"}
          testo={
            configurata
              ? configurazioneCopy.configurata
              : configurazioneCopy.nonDisponibile
          }
          tono={configurata ? "ok" : "neutro"}
        />
      </div>
      {configurata ? (
        <ul className="mt-2 flex flex-col gap-0.5 text-sm">
          {dettagli.map((riga) => (
            <li key={riga}>{riga}</li>
          ))}
        </ul>
      ) : (
        // Tono informativo, mai di colpa: manca a noi, non all'Host.
        <p className="mt-2 text-sm text-muted">{messaggio}</p>
      )}
    </section>
  );
}

/** Stato della configurazione normativa della Struttura (FR-2, AD-9). */
export function PannelloConfigurazione({
  strutturaId,
}: Readonly<{ strutturaId: string }>) {
  const { data: configurazione, isPending } =
    useConfigurazioneNormativa(strutturaId);

  if (isPending || !configurazione) {
    return <output className="text-sm text-muted">Caricamento…</output>;
  }

  const { tassa_soggiorno: tassa, istat } = configurazione;
  const parametriTassa = tassa.parametri;
  const parametriIstat = istat.parametri;

  const dettagliTassa = parametriTassa
    ? [
        `${formatEuroCent(parametriTassa.importo_cent)} ${configurazioneCopy.importoPerNotte}`,
        `${configurazioneCopy.periodicitaEtichetta}: ${
          configurazioneCopy.periodicita[parametriTassa.periodicita as Periodicita]
        }`,
        ...(parametriTassa.esenzione_eta_max !== null
          ? [configurazioneCopy.esenzioneEta(parametriTassa.esenzione_eta_max)]
          : []),
        ...(parametriTassa.esenzione_notti_oltre !== null
          ? [
              configurazioneCopy.esenzioneNotti(
                parametriTassa.esenzione_notti_oltre,
              ),
            ]
          : []),
      ]
    : [];

  const dettagliIstat = parametriIstat
    ? [
        `${configurazioneCopy.tracciatoEtichetta}: ${parametriIstat.tracciato}`,
        `${configurazioneCopy.periodicitaEtichetta}: ${
          configurazioneCopy.periodicita[parametriIstat.periodicita as Periodicita]
        }`,
      ]
    : [];

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-semibold">{configurazioneCopy.titolo}</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <Area
          titolo={configurazioneCopy.tassaTitolo}
          stato={tassa.stato}
          messaggio={tassa.messaggio}
          dettagli={dettagliTassa}
        />
        <Area
          titolo={configurazioneCopy.istatTitolo}
          stato={istat.stato}
          messaggio={istat.messaggio}
          dettagli={dettagliIstat}
        />
      </div>
    </div>
  );
}

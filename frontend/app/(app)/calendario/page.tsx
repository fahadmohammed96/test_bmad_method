"use client";

import { useState } from "react";
import { CalendarioGriglia } from "@/components/CalendarioGriglia";
import {
  strutturaFiltrata,
  useSelezioneStruttura,
} from "@/components/SelezioneStruttura";
import { useCalendario } from "@/lib/api/hooks";
import {
  giorniDelPeriodo,
  meseSpostato,
  periodoDelMese,
  periodoDellaSettimana,
  settimanaSpostata,
} from "@/lib/calendario/griglia";
import { oggiIso } from "@/lib/calendario/oggi";
import { grigliaCopy } from "@/lib/copy/calendario";
import { formatOraIt } from "@/lib/formati";

type Vista = "mese" | "settimana";

/**
 * Il calendario unificato (FR-4, UJ-1).
 *
 * **Entrambe le viste sono MVP.** L'AC dice «griglia (mensile/settimanale)»
 * senza dire se sono due o una scelta (test design §4.2-13): con il periodo
 * ridotto a una funzione pura da una data di riferimento, la seconda vista
 * costa un parametro invece di una superficie, e l'ambiguità si chiude
 * facendole entrambe anziché scegliendo al posto di qualcun altro.
 *
 * Il livello presentazionale resta separabile dalla logica: periodo, corsie
 * e collocazione stanno in `lib/calendario/griglia.ts`, e questo file
 * compone. Se la decisione su A8 (libreria di componenti) arrivasse dopo, il
 * costo è riscrivere i componenti, non il calendario.
 */
export default function CalendarioPage() {
  const { selezione } = useSelezioneStruttura();
  const [vista, setVista] = useState<Vista>("mese");
  const [riferimento, setRiferimento] = useState<string>(() => oggiIso());

  const periodo =
    vista === "mese"
      ? periodoDelMese(riferimento)
      : periodoDellaSettimana(riferimento);
  const giorni = giorniDelPeriodo(periodo);

  const { data, isPending, isError } = useCalendario({
    da: periodo.da,
    a: periodo.a,
    struttura_id: strutturaFiltrata(selezione),
  });

  const sposta = (quanti: number) =>
    setRiferimento((corrente) =>
      vista === "mese"
        ? meseSpostato(corrente, quanti)
        : settimanaSpostata(corrente, quanti),
    );

  const cambiaVista = (prossima: Vista) => {
    setVista(prossima);
    // Passando a «mese» ci si riporta sul primo del mese corrente: la data
    // di riferimento resta dentro il periodo mostrato, altrimenti «periodo
    // successivo» salterebbe da un mese all'altro in modo imprevedibile.
    setRiferimento((corrente) =>
      prossima === "mese" ? periodoDelMese(corrente).da : corrente,
    );
  };

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{grigliaCopy.titolo}</h1>
        <p className="text-sm text-muted">{grigliaCopy.sottotitolo}</p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <fieldset className="flex items-center gap-2">
          <legend className="sr-only">{grigliaCopy.vistaEtichetta}</legend>
          {(["mese", "settimana"] as const).map((valore) => (
            <button
              key={valore}
              type="button"
              aria-pressed={vista === valore}
              onClick={() => cambiaVista(valore)}
              className={`rounded border px-3 py-1 text-sm ${
                vista === valore
                  ? "bg-primary text-primary-contrast"
                  : "bg-surface"
              }`}
            >
              {valore === "mese"
                ? grigliaCopy.vistaMese
                : grigliaCopy.vistaSettimana}
            </button>
          ))}
        </fieldset>
        <button
          type="button"
          onClick={() => sposta(-1)}
          className="rounded border px-3 py-1 text-sm"
        >
          {grigliaCopy.periodoPrecedente}
        </button>
        <button
          type="button"
          onClick={() => setRiferimento(oggiIso())}
          className="rounded border px-3 py-1 text-sm"
        >
          {grigliaCopy.oggi}
        </button>
        <button
          type="button"
          onClick={() => sposta(1)}
          className="rounded border px-3 py-1 text-sm"
        >
          {grigliaCopy.periodoSuccessivo}
        </button>
      </div>

      {/* UX-DR6 / NFR-2: la verità temporale è un'etichetta PERSISTENTE
          accanto ai dati, non un tooltip da scoprire. E quando non si sa,
          si dice che non si sa: mai un orario inventato. */}
      {data && <VeritaTemporale dati={data} />}

      {isPending ? (
        <output className="text-sm text-muted">{grigliaCopy.caricamento}</output>
      ) : isError || !data ? (
        // MAI «nessuna prenotazione» su un errore di caricamento: un
        // calendario pieno che si presenta come vuoto afferma il falso sullo
        // stato delle prenotazioni dell'Host.
        <output className="text-sm text-danger">
          {grigliaCopy.nonCaricato}
        </output>
      ) : data.strutture.length === 0 ? (
        <p className="text-sm text-muted">{grigliaCopy.nessunaStruttura}</p>
      ) : (
        <>
          <CalendarioGriglia
            giorni={giorni}
            strutture={data.strutture}
            voci={data.voci}
          />
          {data.voci.length === 0 && (
            <p className="text-sm text-muted">
              {grigliaCopy.nessunaPrenotazione}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function VeritaTemporale({
  dati,
}: Readonly<{ dati: NonNullable<ReturnType<typeof useCalendario>["data"]> }>) {
  if (dati.feed_collegati === 0) {
    return (
      <p className="text-sm text-muted">{grigliaCopy.nessunFeedCollegato}</p>
    );
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      {dati.ultimo_sync_riuscito_il ? (
        <p className="text-muted">
          {dati.feed_collegati > 1
            ? grigliaCopy.aggiornatoAlleDiPiuFeed(
                formatOraIt(new Date(dati.ultimo_sync_riuscito_il)),
                dati.feed_collegati,
              )
            : grigliaCopy.aggiornatoAlle(
                formatOraIt(new Date(dati.ultimo_sync_riuscito_il)),
              )}
        </p>
      ) : (
        <p className="text-muted">
          {grigliaCopy.maiSincronizzato(dati.feed_mai_sincronizzati)}
        </p>
      )}
      {dati.feed_in_errore > 0 && (
        <p className="text-danger">
          {grigliaCopy.feedInErrore(dati.feed_in_errore)}
        </p>
      )}
    </div>
  );
}

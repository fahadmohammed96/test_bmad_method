"use client";

import { useState } from "react";
import { BadgeStato } from "@/components/BadgeStato";
import {
  useCollegaFeed,
  useFeedIcal,
  type CanaleFeed,
  type FeedIcal,
} from "@/lib/api/hooks";
import { calendarioCopy } from "@/lib/copy/calendario";
import { formatOraIt } from "@/lib/formati";

const CANALI: readonly CanaleFeed[] = ["airbnb", "booking", "altro"] as const;

type CategoriaErrore = keyof typeof calendarioCopy.errore;

/** Esito dell'ultimo import, con la prova che il collegamento ha funzionato.
 *
 * Lo stato arriva dall'API già derivato (AD-14): qui non si ricalcola nulla,
 * si presenta. In particolare l'orario mostrato è quello dell'ultimo sync
 * **riuscito** — un run fallito non lo fa avanzare, che è precisamente la
 * falsa sincronia vietata da NFR-2.
 */
function EsitoImport({ feed }: Readonly<{ feed: FeedIcal }>) {
  if (feed.stato_sync === "in_corso") {
    return (
      <output className="text-sm text-muted">{calendarioCopy.importoInCorso}</output>
    );
  }
  if (feed.stato_sync === "mai_sincronizzato") {
    return (
      <BadgeStato
        icona="…"
        testo={calendarioCopy.maiSincronizzato}
        tono="neutro"
      />
    );
  }
  if (feed.stato_sync === "fallito") {
    const categoria = feed.categoria_errore as CategoriaErrore | null;
    return (
      <div className="flex flex-col gap-1">
        <BadgeStato icona="!" testo={calendarioCopy.nonRiuscito} tono="avviso" />
        {categoria && (
          <p className="text-sm text-danger">{calendarioCopy.errore[categoria]}</p>
        )}
        {/* Da quando il poller gira da solo, «non riuscito» senza un QUANDO
            non dice niente: un tentativo fallito due minuti fa e uno fallito
            tre giorni fa hanno la stessa etichetta e conseguenze opposte. */}
        {feed.ultimo_tentativo_il && (
          <p className="text-sm text-muted">
            {calendarioCopy.ultimoTentativo(
              formatOraIt(new Date(feed.ultimo_tentativo_il)),
            )}
          </p>
        )}
        {/* Un fallimento capita; una serie è un guasto, e va detto con
            parole diverse (AR-10). È lo stesso segnale su cui il backend
            fa scattare l'alert interno. */}
        {feed.fallimenti_consecutivi > 1 && (
          <p className="text-sm text-danger">
            {calendarioCopy.fallimentiConsecutivi(feed.fallimenti_consecutivi)}
          </p>
        )}
        {feed.ultimo_sync_riuscito_il ? (
          <p className="text-sm text-muted">
            {calendarioCopy.importate(
              feed.prenotazioni_attive,
              formatOraIt(new Date(feed.ultimo_sync_riuscito_il)),
            )}
          </p>
        ) : (
          // AC 11: mai un orario inventato né un vuoto ambiguo. Un Feed che
          // non ha MAI avuto un sync riuscito è il caso in cui la falsa
          // sincronia fa il danno massimo: il sistema dice «non so».
          <p className="text-sm text-muted">{calendarioCopy.maiAggiornato}</p>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      {/* Il timestamp non dovrebbe mai mancare su un run riuscito, ma se
          mancasse un trattino si leggerebbe come un valore: si dice che non
          si sa, invece di scrivere qualcosa al posto dell'orario (NFR-2). */}
      {feed.ultimo_sync_riuscito_il ? (
        <p className="text-sm">
          {calendarioCopy.importate(
            feed.prenotazioni_attive,
            formatOraIt(new Date(feed.ultimo_sync_riuscito_il)),
          )}
        </p>
      ) : (
        <p className="text-sm text-muted">{calendarioCopy.maiAggiornato}</p>
      )}
      {feed.prenotazioni_rimosse_dal_feed > 0 && (
        <p className="text-sm text-muted">
          {calendarioCopy.rimosseDalFeed(feed.prenotazioni_rimosse_dal_feed)}
        </p>
      )}
      {feed.eventi_malformati > 0 && (
        <p className="text-sm text-muted">
          {calendarioCopy.eventiMalformati(feed.eventi_malformati)}
        </p>
      )}
      {feed.eventi_ricorrenti_non_espansi > 0 && (
        <p className="text-sm text-muted">
          {calendarioCopy.ricorrentiNonEspansi(feed.eventi_ricorrenti_non_espansi)}
        </p>
      )}
    </div>
  );
}

/** Collegamento dei Feed iCal di una Struttura (FR-3, UJ-1). */
export function FeedIcalStruttura({
  strutturaId,
}: Readonly<{ strutturaId: string }>) {
  const { data: feed, isPending, isError } = useFeedIcal(strutturaId);
  const collega = useCollegaFeed();
  const [url, setUrl] = useState("");
  const [canale, setCanale] = useState<CanaleFeed>("airbnb");

  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-semibold">{calendarioCopy.feedTitolo}</h2>
      <p className="text-sm text-muted">{calendarioCopy.feedSottotitolo}</p>

      <form
        className="flex flex-col gap-3"
        onSubmit={(evento) => {
          evento.preventDefault();
          collega.mutate(
            { struttura_id: strutturaId, url: url.trim(), canale },
            { onSuccess: () => setUrl("") },
          );
        }}
      >
        <label className="flex flex-col gap-1 text-sm" htmlFor="feed-url">
          {calendarioCopy.urlEtichetta}
        </label>
        <input
          id="feed-url"
          type="url"
          required
          maxLength={2000}
          value={url}
          onChange={(evento) => setUrl(evento.target.value)}
          aria-describedby="feed-url-aiuto"
          className="rounded border px-2 py-2"
        />
        <p id="feed-url-aiuto" className="text-xs text-muted">
          {calendarioCopy.urlAiuto}
        </p>
        <label className="flex flex-col gap-1 text-sm" htmlFor="feed-canale">
          {calendarioCopy.canaleEtichetta}
        </label>
        <select
          id="feed-canale"
          value={canale}
          onChange={(evento) => setCanale(evento.target.value as CanaleFeed)}
          className="rounded border px-2 py-2"
        >
          {CANALI.map((valore) => (
            <option key={valore} value={valore}>
              {calendarioCopy.canale[valore]}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={collega.isPending}
          className="rounded bg-primary px-3 py-2 text-sm text-primary-contrast disabled:opacity-50"
        >
          {calendarioCopy.collega}
        </button>
        {collega.isError && (
          // Errore inline immediato sul campo, mai un fallimento silenzioso
          // (FR-3): l'URL non valido si scopre senza aspettare l'import.
          <p role="alert" className="text-sm text-danger">
            {collega.error.message}
          </p>
        )}
      </form>

      {isPending ? (
        <output className="text-sm text-muted">Caricamento…</output>
      ) : isError ? (
        // MAI «Nessun calendario collegato» su un errore di caricamento: una
        // Struttura con tre feed che si presenta come vuota afferma il falso
        // sullo stato del calendario, ed è la stessa classe di danno che
        // NFR-2 vieta — dichiarare certo ciò che non si sa.
        <output className="text-sm text-danger">{calendarioCopy.feedNonCaricati}</output>
      ) : (feed ?? []).length === 0 ? (
        <p className="text-sm text-muted">{calendarioCopy.nessunFeed}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {(feed ?? []).map((riga) => (
            <li key={riga.id} className="rounded-lg border p-4">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold">
                  {calendarioCopy.canale[riga.canale]}
                </h3>
                <span className="truncate text-xs text-muted">{riga.url}</span>
              </div>
              <div className="mt-2">
                <EsitoImport feed={riga} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

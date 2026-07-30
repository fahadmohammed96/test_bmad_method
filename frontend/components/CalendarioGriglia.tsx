import { AzioneCancellaPrenotazione } from "@/components/AzioneCancellaPrenotazione";
import { BadgeCanale } from "@/components/BadgeCanale";
import { BadgeStato } from "@/components/BadgeStato";
import type { VoceCalendario } from "@/lib/api/hooks";
import {
  corsie,
  giornoDellaSettimana,
  segmenti,
  type GiornoIso,
} from "@/lib/calendario/griglia";
import { grigliaCopy } from "@/lib/copy/calendario";
import { formatGiornoIt } from "@/lib/formati";

/**
 * La griglia unificata: una riga per Struttura, una colonna per notte (FR-4).
 *
 * **Perché una tabella e non dei riquadri posizionati.** Le colonne sono
 * giorni e le righe sono Strutture: è una tabella di dati, e dirlo nel
 * markup dà gratis ciò che un layout assoluto costringerebbe a ricostruire a
 * mano — intestazioni di riga e di colonna annunciate dallo screen reader,
 * navigazione per celle, e nessun testo che esiste solo come posizione.
 * Una Prenotazione occupa più notti con `colSpan`, che è esattamente il
 * costrutto che le tabelle hanno per questo.
 *
 * **Le corsie.** Due Prenotazioni sovrapposte sulla stessa Struttura non si
 * disegnano una sopra l'altra: aprono una riga in più. Nasconderne una
 * significherebbe nascondere proprio il fatto che il prodotto esiste per far
 * notare (FR-5).
 *
 * Nessun valore di dominio si calcola qui (AD-14): `notti`, `stato`,
 * `ospite_principale` e `altri_ospiti` arrivano dall'API. Questo componente
 * dispone celle e sceglie parole.
 */

// Iniziali dei giorni in italiano, lunedì per primo. Sono un'abbreviazione
// visiva: la data per esteso resta nell'intestazione per chi legge con uno
// screen reader, perché «M» da solo è ambiguo fra martedì e mercoledì.
const INIZIALI = ["L", "M", "M", "G", "V", "S", "D"] as const;

// Attenuazione di una Prenotazione non più attiva: **bordo e sfondo, mai il
// testo** (E2-F4). `opacity-*` sul contenitore composita l'opacità su tutto
// ciò che contiene: a 0.7 il testo `text-xs` scendeva da 4.58:1 a 2.66:1
// sullo sfondo della superficie, sotto la soglia AA di 4.5:1 (NFR-8, WCAG
// 1.4.3). E il testo che diventava illeggibile era proprio quello che PORTA
// lo stato — «Non più nel portale», le date, le notti — cioè l'informazione
// che AC 12 e UX-DR4 vogliono affidata al testo e non al colore.
const TONO_NON_ATTIVA = "border-dashed border-muted";

/** Solo una manuale ancora attiva si cancella da qui.
 *
 * Una Prenotazione che arriva da un portale la annulla il **portale**: il
 * sistema non scrive mai verso le OTA (AD-5), quindi un bottone qui
 * prometterebbe qualcosa che non facciamo, e lo stato divergerebbe al primo
 * sync. La regola è la stessa che il server impone con un 422: qui non si
 * ricalcola, si evita di offrire un'azione che sappiamo già come finisce.
 */
function siPuoCancellare(voce: VoceCalendario): boolean {
  return voce.canale === "manuale" && voce.stato === "attiva";
}

function ChipPrenotazione({
  voce,
  onCancella,
  inCancellazione,
}: Readonly<{
  voce: VoceCalendario;
  onCancella?: (prenotazione_id: string) => void;
  inCancellazione: boolean;
}>) {
  const attiva = voce.stato === "attiva";
  return (
    <div
      className={`flex h-full flex-col gap-1 rounded border bg-surface p-1.5 ${
        attiva ? "" : TONO_NON_ATTIVA
      }`}
    >
      <div className="flex flex-wrap items-center gap-1">
        <BadgeCanale canale={voce.canale} />
        {!attiva && (
          <BadgeStato
            icona="⊘"
            testo={grigliaCopy.stato[voce.stato]}
            tono="neutro"
          />
        )}
      </div>
      <p className="truncate font-medium">
        {voce.ospite_principale ?? grigliaCopy.ospiteNonIndicato}
      </p>
      {voce.altri_ospiti > 0 && (
        <p className="text-xs text-muted">
          {grigliaCopy.altriOspiti(voce.altri_ospiti)}
        </p>
      )}
      <p className="text-xs text-muted">
        {formatGiornoIt(voce.check_in)} → {formatGiornoIt(voce.check_out)} ·{" "}
        {grigliaCopy.notti(voce.notti)}
      </p>
      {onCancella !== undefined && siPuoCancellare(voce) && (
        <AzioneCancellaPrenotazione
          etichetta={grigliaCopy.cancella(formatGiornoIt(voce.check_in))}
          inCorso={inCancellazione}
          onConferma={() => onCancella(voce.id)}
        />
      )}
    </div>
  );
}

function IntestazioneGiorno({ giorno }: Readonly<{ giorno: GiornoIso }>) {
  return (
    <th scope="col" className="border p-1 text-center text-xs font-normal">
      <span aria-hidden="true" className="block">
        <span className="block text-muted">
          {INIZIALI[giornoDellaSettimana(giorno)]}
        </span>
        {Number(giorno.slice(8, 10))}
      </span>
      <span className="sr-only">{formatGiornoIt(giorno)}</span>
    </th>
  );
}

export function CalendarioGriglia({
  giorni,
  strutture,
  voci,
  onCancella,
  idInCancellazione = null,
}: Readonly<{
  giorni: readonly GiornoIso[];
  strutture: readonly { id: string; nome: string }[];
  voci: readonly VoceCalendario[];
  /** Assente = griglia in sola lettura: nessun chip mostra l'azione. */
  onCancella?: (prenotazione_id: string) => void;
  idInCancellazione?: string | null;
}>) {
  return (
    // Regione scorrevole RAGGIUNGIBILE DA TASTIERA. Un `overflow-x-auto`
    // senza `tabIndex` si scorre solo col mouse o col dito: chi naviga da
    // tastiera vede la prima metà del mese e non ha modo di arrivare alla
    // seconda. axe lo classifica `serious`, ed è la baseline che l'AC 8
    // impone sulla nuova superficie (NFR-8, UX-DR10).
    <div
      role="region"
      tabIndex={0}
      aria-label={grigliaCopy.regioneScorrevole}
      className="overflow-x-auto"
    >
      <table className="w-full min-w-max border-collapse text-sm">
        <caption className="sr-only">{grigliaCopy.descrizioneTabella}</caption>
        <thead>
          <tr>
            <th scope="col" className="border p-1 text-left">
              {grigliaCopy.intestazioneStruttura}
            </th>
            {giorni.map((giorno) => (
              <IntestazioneGiorno key={giorno} giorno={giorno} />
            ))}
          </tr>
        </thead>
        {strutture.map((struttura) => {
          const disposte = corsie(
            voci.filter((voce) => voce.struttura_id === struttura.id),
            giorni,
          );
          // Una Struttura senza Prenotazioni resta comunque una riga: farla
          // sparire darebbe una griglia in cui «non ho prenotazioni» e «non
          // ho quella Struttura» hanno lo stesso aspetto.
          const righe = disposte.length === 0 ? [[]] : disposte;
          return (
            <tbody key={struttura.id}>
              {righe.map((corsia, indice) => (
                <tr key={`${struttura.id}-${indice}`}>
                  {indice === 0 && (
                    <th
                      scope="rowgroup"
                      rowSpan={righe.length}
                      className="border p-2 text-left align-top font-medium"
                    >
                      {struttura.nome}
                    </th>
                  )}
                  {segmenti(corsia, giorni).map((cella, posizione) =>
                    cella.tipo === "vuoto" ? (
                      <td
                        key={`vuoto-${posizione}`}
                        colSpan={cella.celle}
                        className="border"
                      />
                    ) : (
                      <td
                        key={cella.voce.id}
                        colSpan={cella.celle}
                        className="border p-0.5 align-top"
                      >
                        <ChipPrenotazione
                          voce={cella.voce}
                          onCancella={onCancella}
                          inCancellazione={idInCancellazione === cella.voce.id}
                        />
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  useCreaPrenotazioneManuale,
  useStrutture,
  type PrenotazioneManualeInput,
} from "@/lib/api/hooks";
import { inserimentoCopy } from "@/lib/copy/calendario";

/**
 * Inserimento manuale di una Prenotazione (FR-7, Story 2.4).
 *
 * È la prima superficie in cui **l'Host scrive** nel calendario invece di
 * riceverlo dai portali, e la riga su cui si sbaglia in buona fede è una sola:
 * **l'Ospite è facoltativo davvero.**
 *
 * Tre conseguenze concrete, ognuna verificata da un test:
 *
 * 1. nessun campo dell'Ospite è `required`, e ognuno lo **dichiara**
 *    nell'etichetta: un campo che non dice di essere facoltativo si legge come
 *    obbligatorio, e il caso d'uso più frequente — il blocco date — non ha
 *    nessun Ospite da indicare;
 * 2. nessun campo dell'Ospite ha un valore iniziale. In particolare la **nota**
 *    non è un suggerimento di `nome`: è testo opaco della Prenotazione, e
 *    precompilarci il nome sarebbe un'identità dedotta (NFR-11,
 *    `[DECISIONE MYL-40]` → PRD §14.2);
 * 3. i campi vuoti si inviano **come sono**. Normalizzarli qui — decidere sul
 *    client se l'Ospite «c'è» — duplicherebbe una regola di dominio sul lato
 *    sbagliato del confine (AD-14): è il server a rispondere «tre campi vuoti
 *    non sono un Ospite», ed è l'unica risposta che vale anche per un altro
 *    client.
 *
 * Nessun orologio e nessuna aritmetica di date: le date di calendario restano
 * le stringhe `AAAA-MM-GG` che l'input produce (AD-3), e la guardia
 * `lib/calendario/griglia.guardia.test.ts` lo impone su questo file.
 */

const VUOTO = {
  struttura_id: "",
  check_in: "",
  check_out: "",
  sommario: "",
  nome: "",
  email: "",
  telefono: "",
} as const;

type Campi = { -readonly [K in keyof typeof VUOTO]: string };

const CLASSE_CAMPO = "rounded border bg-surface px-2 py-1 text-sm";

export function FormPrenotazioneManuale() {
  const { data: strutture } = useStrutture();
  const [aperto, setAperto] = useState(false);
  const [campi, setCampi] = useState<Campi>({ ...VUOTO });
  const crea = useCreaPrenotazioneManuale();

  // Solo le Strutture che accettano scritture: una archiviata rifiuterebbe la
  // Prenotazione (AD-20), e offrirla nella tendina significherebbe proporre
  // una scelta che sappiamo già come finisce. Lo stato arriva dall'API e qui si
  // presenta, non si deduce (AD-14).
  const attive = (strutture ?? []).filter(
    (struttura) => struttura.stato === "attiva",
  );
  // Con una sola Struttura è già scelta: non è un default dedotto, è l'unica
  // possibilità. Derivata invece che scritta nello stato, così non serve
  // sincronizzare uno `useState` con dei dati che arrivano dopo.
  const strutturaScelta =
    campi.struttura_id || (attive.length === 1 ? attive[0].id : "");

  const aggiorna = (campo: keyof Campi) => (valore: string) =>
    setCampi((corrente) => ({ ...corrente, [campo]: valore }));

  const salva = () => {
    const dati: PrenotazioneManualeInput = {
      struttura_id: strutturaScelta,
      check_in: campi.check_in,
      check_out: campi.check_out,
      sommario: campi.sommario,
      ospite: {
        nome: campi.nome,
        email: campi.email,
        telefono: campi.telefono,
      },
    };
    crea.mutate(dati, { onSuccess: () => setCampi({ ...VUOTO }) });
  };

  if (!aperto) {
    return (
      <div>
        <button
          type="button"
          aria-expanded={false}
          onClick={() => setAperto(true)}
          className="rounded border px-3 py-1 text-sm"
        >
          {inserimentoCopy.apri}
        </button>
      </div>
    );
  }

  return (
    <section className="flex flex-col gap-3 rounded border p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">{inserimentoCopy.titolo}</h2>
          <p className="text-sm text-muted">{inserimentoCopy.sottotitolo}</p>
        </div>
        <button
          type="button"
          aria-expanded
          onClick={() => setAperto(false)}
          className="rounded border px-3 py-1 text-sm"
        >
          {inserimentoCopy.chiudi}
        </button>
      </header>

      {attive.length === 0 ? (
        <p className="text-sm text-muted">
          {inserimentoCopy.nessunaStrutturaAttiva}
        </p>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(evento) => {
            evento.preventDefault();
            salva();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <label className="flex flex-col gap-1 text-sm">
              {inserimentoCopy.strutturaEtichetta}
              <select
                required
                value={strutturaScelta}
                onChange={(evento) =>
                  aggiorna("struttura_id")(evento.target.value)
                }
                className={CLASSE_CAMPO}
              >
                <option value="">—</option>
                {attive.map((struttura) => (
                  <option key={struttura.id} value={struttura.id}>
                    {struttura.nome}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-sm">
              {inserimentoCopy.arrivoEtichetta}
              <input
                type="date"
                required
                value={campi.check_in}
                onChange={(evento) => aggiorna("check_in")(evento.target.value)}
                className={CLASSE_CAMPO}
              />
            </label>

            <label className="flex flex-col gap-1 text-sm">
              {inserimentoCopy.partenzaEtichetta}
              <input
                type="date"
                required
                // `min` è la STESSA stringa del campo arrivo, non un calcolo:
                // ferma l'errore più comune nel browser senza reimplementare
                // la semantica dell'intervallo, che resta del server (AD-3,
                // AD-14). Il caso `partenza = arrivo` lo rifiuta il server con
                // un 422 inline, perché `min` ammette l'uguaglianza.
                min={campi.check_in || undefined}
                value={campi.check_out}
                onChange={(evento) => aggiorna("check_out")(evento.target.value)}
                aria-describedby="aiuto-partenza"
                className={CLASSE_CAMPO}
              />
            </label>
          </div>
          <p id="aiuto-partenza" className="text-xs text-muted">
            {inserimentoCopy.partenzaAiuto}
          </p>

          <label className="flex flex-col gap-1 text-sm">
            {inserimentoCopy.notaEtichetta}
            <input
              type="text"
              maxLength={500}
              value={campi.sommario}
              onChange={(evento) => aggiorna("sommario")(evento.target.value)}
              aria-describedby="aiuto-nota"
              className={CLASSE_CAMPO}
            />
          </label>
          <p id="aiuto-nota" className="text-xs text-muted">
            {inserimentoCopy.notaAiuto}
          </p>

          <fieldset className="flex flex-col gap-2 rounded border p-2">
            <legend className="px-1 text-sm font-medium">
              {inserimentoCopy.ospiteTitolo}
            </legend>
            <p className="text-xs text-muted">{inserimentoCopy.ospiteAiuto}</p>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1 text-sm">
                {inserimentoCopy.nomeEtichetta}
                <input
                  type="text"
                  maxLength={200}
                  value={campi.nome}
                  onChange={(evento) => aggiorna("nome")(evento.target.value)}
                  className={CLASSE_CAMPO}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                {inserimentoCopy.emailEtichetta}
                <input
                  type="email"
                  maxLength={320}
                  value={campi.email}
                  onChange={(evento) => aggiorna("email")(evento.target.value)}
                  className={CLASSE_CAMPO}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                {inserimentoCopy.telefonoEtichetta}
                <input
                  type="tel"
                  maxLength={50}
                  value={campi.telefono}
                  onChange={(evento) =>
                    aggiorna("telefono")(evento.target.value)
                  }
                  className={CLASSE_CAMPO}
                />
              </label>
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={crea.isPending}
              className="rounded border bg-primary px-3 py-1 text-sm text-primary-contrast disabled:opacity-60"
            >
              {crea.isPending
                ? inserimentoCopy.salvataggioInCorso
                : inserimentoCopy.salva}
            </button>
            {crea.isSuccess && (
              <output className="text-sm text-primary">
                {inserimentoCopy.salvata}
              </output>
            )}
          </div>

          {crea.isError && (
            // Errore inline immediato, mai un fallimento silenzioso: il testo
            // è il `detail` del `problem+json`, cioè una frase scritta per
            // l'Host, e dice sempre cosa è successo ai suoi dati.
            <output className="text-sm text-danger">
              {crea.error.message}
            </output>
          )}
        </form>
      )}
    </section>
  );
}

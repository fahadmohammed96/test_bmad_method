"use client";

import { useComuni, useRegioni } from "@/lib/api/hooks";
import { struttureCopy } from "@/lib/copy/strutture";

export type ValoriLuogo = {
  comune: string;
  comuneCodiceIstat: string | null;
  regione: string;
};

/**
 * Comune e Regione dall'anagrafica ISTAT (AD-9): il Comune si sceglie dai
 * suggerimenti (che portano il codice), la Regione dall'elenco ufficiale.
 * Restano scrivibili a mano: un luogo non ancora in anagrafica non blocca
 * la registrazione, la configurazione degraderà in sicurezza (FR-2).
 */
export function CampiLuogo({
  valori,
  onChange,
}: Readonly<{
  valori: ValoriLuogo;
  onChange: (valori: ValoriLuogo) => void;
}>) {
  const { data: regioni } = useRegioni();
  const { data: suggerimenti } = useComuni(valori.comune);

  function scegliComune(nome: string) {
    const trovato = (suggerimenti ?? []).find(
      (c) => c.nome.toLowerCase() === nome.trim().toLowerCase(),
    );
    const regione = trovato
      ? (regioni ?? []).find(
          (r) => r.codice_istat === trovato.regione_codice_istat,
        )
      : undefined;
    onChange({
      comune: nome,
      comuneCodiceIstat: trovato ? trovato.codice_istat : null,
      regione: regione ? regione.nome : valori.regione,
    });
  }

  return (
    <>
      {/* `htmlFor` esplicito: il datalist vive fuori dalla label, così il
          testo accessibile resta l'etichetta e non i suggerimenti. */}
      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor="campo-comune">{struttureCopy.comuneEtichetta}</label>
        <input
          id="campo-comune"
          required
          maxLength={120}
          list="elenco-comuni"
          value={valori.comune}
          onChange={(evento) => scegliComune(evento.target.value)}
          className="rounded border px-2 py-2"
        />
      </div>
      <datalist id="elenco-comuni">
        {(suggerimenti ?? []).map((comune) => (
          <option key={comune.codice_istat} value={comune.nome}>
            {comune.provincia}
          </option>
        ))}
      </datalist>

      <div className="flex flex-col gap-1 text-sm">
        <label htmlFor="campo-regione">{struttureCopy.regioneEtichetta}</label>
        <select
          id="campo-regione"
          required
          value={valori.regione}
          onChange={(evento) =>
            onChange({ ...valori, regione: evento.target.value })
          }
          className="rounded border px-2 py-2"
        >
          <option value="">{struttureCopy.regioneSegnaposto}</option>
          {(regioni ?? []).map((regione) => (
            <option key={regione.codice_istat} value={regione.nome}>
              {regione.nome}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}

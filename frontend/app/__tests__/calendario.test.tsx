import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * La superficie Calendario (AC 3, 4, 13 della Story 2.3).
 *
 * Livello componente: gli hook sono sostituiti, quindi qui si verifica cosa
 * la pagina CHIEDE e cosa MOSTRA — non la coerenza fra cache, che in questo
 * mondo non esiste e vive in `frontend/e2e/calendario.spec.ts`.
 */

const useCalendario = vi.fn();
const cancellaMutate = vi.fn();
const creaMutate = vi.fn();

const INERTE = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  isSuccess: false,
  error: null,
  variables: undefined,
};

vi.mock("@/lib/api/hooks", () => ({
  useCalendario: (parametri: unknown) => useCalendario(parametri),
  useStrutture: () => ({ data: [{ id: "s1", nome: "Bologna Centro", stato: "attiva" }] }),
  useCreaPrenotazioneManuale: () => ({ ...INERTE, mutate: creaMutate }),
  useCancellaPrenotazione: () => ({ ...INERTE, mutate: cancellaMutate }),
}));

// L'unico punto che legge l'orologio del client: fissarlo rende
// deterministico il periodo su cui la griglia si apre.
vi.mock("@/lib/calendario/oggi", () => ({ oggiIso: () => "2026-08-17" }));

import CalendarioPage from "../(app)/calendario/page";
import {
  ProviderSelezioneStruttura,
  useSelezioneStruttura,
} from "@/components/SelezioneStruttura";

const VUOTO = {
  da: "2026-08-01",
  a: "2026-08-31",
  stato_sync: "riuscito",
  ultimo_sync_riuscito_il: "2026-08-17T12:35:00Z",
  feed_collegati: 1,
  feed_mai_sincronizzati: 0,
  feed_in_errore: 0,
  strutture: [{ id: "s1", nome: "Bologna Centro" }],
  voci: [],
};

function rispondi(dati: Record<string, unknown> = {}) {
  useCalendario.mockReturnValue({
    data: { ...VUOTO, ...dati },
    isPending: false,
    isError: false,
  });
}

function mostra() {
  return render(
    <ProviderSelezioneStruttura>
      <CalendarioPage />
    </ProviderSelezioneStruttura>,
  );
}

beforeEach(() => {
  useCalendario.mockReset();
  cancellaMutate.mockReset();
  creaMutate.mockReset();
  rispondi();
});

const VOCE_MANUALE = {
  id: "p-manuale",
  struttura_id: "s1",
  canale: "manuale",
  check_in: "2026-08-10",
  check_out: "2026-08-14",
  notti: 4,
  sommario: null,
  stato: "attiva",
  ospite_principale: null,
  altri_ospiti: 0,
};

describe("inserimento manuale sulla superficie Calendario (Story 2.4)", () => {
  it("la griglia è il posto in cui si inserisce una prenotazione", () => {
    mostra();

    expect(
      screen.getByRole("button", { name: "Inserisci una prenotazione" }),
    ).toBeVisible();
  });

  it("cancellare una manuale passa dalla conferma, non dal primo click", async () => {
    // Portare a `cancellata` non è reversibile dal prodotto: un click
    // accidentale su un chip largo pochi millimetri costerebbe una
    // prenotazione da reinserire a mano.
    rispondi({ voci: [VOCE_MANUALE] });
    mostra();

    await userEvent.click(
      screen.getByRole("button", { name: /Cancella la prenotazione del/ }),
    );
    expect(cancellaMutate).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Sì, cancella" }));
    expect(cancellaMutate).toHaveBeenCalledWith("p-manuale");
  });

  it("rinunciare alla conferma non cancella nulla", async () => {
    rispondi({ voci: [VOCE_MANUALE] });
    mostra();

    await userEvent.click(
      screen.getByRole("button", { name: /Cancella la prenotazione del/ }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "No, lascia stare" }),
    );

    expect(cancellaMutate).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /Cancella la prenotazione del/ }),
    ).toBeVisible();
  });

  it("una Prenotazione da portale non offre la cancellazione", () => {
    // Il sistema non scrive mai verso le OTA (AD-5): un bottone qui
    // prometterebbe qualcosa che non facciamo, e lo stato divergerebbe dal
    // portale al primo sync.
    rispondi({ voci: [{ ...VOCE_MANUALE, canale: "airbnb" }] });
    mostra();

    expect(
      screen.queryByRole("button", { name: /Cancella la prenotazione del/ }),
    ).toBeNull();
  });

  it("una manuale già cancellata non si cancella di nuovo", () => {
    rispondi({ voci: [{ ...VOCE_MANUALE, stato: "cancellata" }] });
    mostra();

    expect(
      screen.queryByRole("button", { name: /Cancella la prenotazione del/ }),
    ).toBeNull();
    // Ma resta visibile con la sua etichetta (AD-19, AD-20).
    expect(screen.getByText("Cancellata")).toBeVisible();
  });
});

describe("verità temporale (AC 4 — NFR-2, UX-DR6)", () => {
  it("l'etichetta «dati aggiornati alle HH:MM» è PERSISTENTE nel documento", () => {
    // Non un `title` da scoprire passandoci sopra: un'informazione che
    // esiste solo al passaggio del mouse non esiste su mobile, e questa è
    // proprio quella che distingue un calendario aggiornato da uno fermo.
    mostra();

    expect(screen.getByText(/Dati aggiornati alle \d{2}:\d{2}/)).toBeVisible();
  });

  it("con più Feed dichiara che l'orario è quello del più vecchio", () => {
    rispondi({ feed_collegati: 3 });
    mostra();

    expect(screen.getByText(/vecchio fra 3 calendari collegati/)).toBeVisible();
  });

  it("se un Feed non ha MAI importato non si inventa un orario", () => {
    // È il caso in cui la falsa sincronia fa il danno massimo: mai un
    // orario che parla solo di metà dei dati mostrati.
    rispondi({
      ultimo_sync_riuscito_il: null,
      feed_collegati: 2,
      feed_mai_sincronizzati: 1,
    });
    mostra();

    expect(screen.queryByText(/Dati aggiornati alle/)).toBeNull();
    expect(screen.getByText(/potrebbe essere incompleta/)).toBeVisible();
  });

  it("senza Feed collegati lo dice, invece di tacere", () => {
    rispondi({
      feed_collegati: 0,
      ultimo_sync_riuscito_il: null,
      stato_sync: "mai_sincronizzato",
    });
    mostra();

    expect(screen.getByText(/Nessun calendario collegato/)).toBeVisible();
  });

  it("un Feed in errore è un avviso, non un silenzio", () => {
    rispondi({ feed_collegati: 2, feed_in_errore: 1 });
    mostra();

    expect(screen.getByText(/1 calendario non si sincronizza/)).toBeVisible();
  });
});

describe("stati di caricamento", () => {
  it("un errore NON si presenta come «nessuna prenotazione»", () => {
    // Un calendario pieno che si presenta come vuoto afferma il falso sullo
    // stato delle prenotazioni dell'Host: stessa classe di danno di NFR-2.
    useCalendario.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    });
    mostra();

    expect(screen.getByText(/Non riusciamo a caricare il calendario/)).toBeVisible();
    expect(screen.queryByText(/Nessuna prenotazione/)).toBeNull();
  });

  it("mentre carica non mostra una griglia vuota", () => {
    useCalendario.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    });
    mostra();

    expect(screen.getByText(/Caricamento del calendario/)).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("periodo e viste (§4.2-13)", () => {
  it("si apre sul mese corrente", () => {
    mostra();

    expect(useCalendario).toHaveBeenCalledWith(
      expect.objectContaining({ da: "2026-08-01", a: "2026-08-31" }),
    );
  });

  it("la vista settimanale chiede la settimana lunedì → domenica", async () => {
    mostra();

    await userEvent.click(screen.getByRole("button", { name: "Settimana" }));

    expect(useCalendario).toHaveBeenLastCalledWith(
      expect.objectContaining({ da: "2026-08-17", a: "2026-08-23" }),
    );
  });

  it("il periodo precedente e il successivo spostano di un mese", async () => {
    mostra();

    await userEvent.click(
      screen.getByRole("button", { name: "Periodo precedente" }),
    );
    expect(useCalendario).toHaveBeenLastCalledWith(
      expect.objectContaining({ da: "2026-07-01", a: "2026-07-31" }),
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Periodo successivo" }),
    );
    expect(useCalendario).toHaveBeenLastCalledWith(
      expect.objectContaining({ da: "2026-08-01", a: "2026-08-31" }),
    );
  });

  it("la vista attiva è annunciata, non solo colorata", () => {
    mostra();

    expect(screen.getByRole("button", { name: "Mese" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Settimana" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});

describe("selettore Struttura (AC 3 — UX-DR1)", () => {
  function ConSelettore() {
    const { imposta } = useSelezioneStruttura();
    return (
      <>
        <button type="button" onClick={() => imposta("s2")}>
          filtra
        </button>
        <CalendarioPage />
      </>
    );
  }

  it("in vista aggregata non chiede nessuna Struttura", () => {
    mostra();

    expect(useCalendario).toHaveBeenCalledWith(
      expect.objectContaining({ struttura_id: undefined }),
    );
  });

  it("selezionando una Struttura filtra SENZA cambiare schermata", async () => {
    render(
      <ProviderSelezioneStruttura>
        <ConSelettore />
      </ProviderSelezioneStruttura>,
    );

    await userEvent.click(screen.getByRole("button", { name: "filtra" }));

    expect(useCalendario).toHaveBeenLastCalledWith(
      expect.objectContaining({ struttura_id: "s2" }),
    );
    // Stessa superficie: il titolo del Calendario è ancora lì.
    expect(
      screen.getByRole("heading", { level: 1, name: "Calendario" }),
    ).toBeVisible();
  });
});

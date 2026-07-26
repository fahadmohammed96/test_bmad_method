import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const feedMock = vi.fn();
const collegaMock = vi.fn();
vi.mock("@/lib/api/hooks", () => ({
  useFeedIcal: () => feedMock(),
  useCollegaFeed: () => collegaMock(),
}));

import { FeedIcalStruttura } from "./FeedIcalStruttura";

const COLLEGA_INERTE = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
};

const FEED_BASE = {
  id: "feed-1",
  struttura_id: "struttura-1",
  url: "https://feed.example.com/calendario.ics",
  canale: "airbnb",
  collegato_il: "2026-07-26T08:00:00Z",
  ultimo_sync_riuscito_il: null,
  ultimo_tentativo_il: null,
  categoria_errore: null,
  prenotazioni_attive: 0,
  prenotazioni_rimosse_dal_feed: 0,
  eventi_malformati: 0,
  eventi_ricorrenti_non_espansi: 0,
};

function montaCon(feed: readonly unknown[]) {
  feedMock.mockReturnValue({ isPending: false, data: feed });
  collegaMock.mockReturnValue(COLLEGA_INERTE);
  render(<FeedIcalStruttura strutturaId="struttura-1" />);
}

describe("FeedIcalStruttura (FR-3, UJ-1)", () => {
  it("invita a collegare quando non c'è nessun calendario", () => {
    montaCon([]);
    expect(
      screen.getByText("Nessun calendario collegato a questa Struttura."),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Indirizzo del calendario (iCal)"),
    ).toBeInTheDocument();
  });

  it("mostra «Importazione in corso…» mentre il job non è ancora girato", () => {
    montaCon([{ ...FEED_BASE, stato_sync: "in_corso" }]);
    expect(screen.getByText("Importazione in corso…")).toBeInTheDocument();
  });

  it("mostra il conteggio e l'ultimo aggiornamento quando l'import è riuscito", () => {
    // 10:30 UTC = 12:30 in Europe/Rome (ora legale): l'orario mostrato è
    // quello locale dell'Host (UX-DR11).
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "riuscito",
        prenotazioni_attive: 3,
        ultimo_sync_riuscito_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText("Importate 3 prenotazioni — ultimo aggiornamento 12:30"),
    ).toBeInTheDocument();
  });

  it("usa il singolare con una sola prenotazione", () => {
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "riuscito",
        prenotazioni_attive: 1,
        ultimo_sync_riuscito_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText("Importata 1 prenotazione — ultimo aggiornamento 12:30"),
    ).toBeInTheDocument();
  });

  it("dichiara «mai sincronizzato» invece di tacere in modo ambiguo", () => {
    // NFR-2: il caso in cui la falsa sincronia farebbe il danno maggiore è
    // proprio il Feed che non ha MAI avuto un sync riuscito.
    montaCon([{ ...FEED_BASE, stato_sync: "mai_sincronizzato" }]);
    expect(screen.getByText("Mai sincronizzato")).toBeInTheDocument();
  });

  it("spiega l'errore senza dettagli tecnici quando l'ultimo run è fallito", () => {
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "url_non_raggiungibile",
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(screen.getByText("Ultimo tentativo non riuscito")).toBeInTheDocument();
    expect(
      screen.getByText(/Non riusciamo a raggiungere questo indirizzo/),
    ).toBeInTheDocument();
  });

  it("su un run fallito NON fa avanzare l'orario dell'ultimo aggiornamento", () => {
    // Il timestamp mostrato resta quello dell'ultimo sync RIUSCITO: è la
    // proprietà che NFR-2 protegge davvero.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "esito_http_inatteso",
        prenotazioni_attive: 2,
        ultimo_sync_riuscito_il: "2026-07-26T06:00:00Z",
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText("Importate 2 prenotazioni — ultimo aggiornamento 08:00"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/12:30/)).not.toBeInTheDocument();
  });

  it("dice che le prenotazioni uscite dal feed sono state conservate", () => {
    // AD-4/AD-19: non si cancella. Se l'Host non lo vede scritto, per lui
    // sono sparite comunque.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "riuscito",
        prenotazioni_attive: 2,
        prenotazioni_rimosse_dal_feed: 1,
        ultimo_sync_riuscito_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText(/non è più nel calendario del portale: l'abbiamo conservata/),
    ).toBeInTheDocument();
  });

  it("segnala gli eventi non leggibili e le ricorrenze non espanse", () => {
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "riuscito",
        prenotazioni_attive: 1,
        eventi_malformati: 2,
        eventi_ricorrenti_non_espansi: 1,
        ultimo_sync_riuscito_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText("2 eventi del calendario non erano leggibili e non sono stati importati."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("1 evento ricorrente è stato importato come singola prenotazione."),
    ).toBeInTheDocument();
  });

  it("mostra l'errore inline del collegamento sul campo", () => {
    feedMock.mockReturnValue({ isPending: false, data: [] });
    collegaMock.mockReturnValue({
      ...COLLEGA_INERTE,
      isError: true,
      error: new Error("Incolla l'indirizzo del calendario esportato dal portale"),
    });
    render(<FeedIcalStruttura strutturaId="struttura-1" />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Incolla l'indirizzo del calendario esportato dal portale",
    );
  });
});

import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  fallimenti_consecutivi: 0,
  prenotazioni_attive: 0,
  prenotazioni_rimosse_dal_feed: 0,
  eventi_malformati: 0,
  eventi_ricorrenti_non_espansi: 0,
};

function montaCon(feed: readonly unknown[]) {
  feedMock.mockReturnValue({ isPending: false, isError: false, data: feed });
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
    // L'orario del tentativo fallito compare, ma come TENTATIVO — mai come
    // «ultimo aggiornamento». Confondere le due frasi è la falsa sincronia.
    expect(screen.getByText("Ultimo tentativo alle 12:30")).toBeInTheDocument();
    expect(
      screen.queryByText(/ultimo aggiornamento 12:30/),
    ).not.toBeInTheDocument();
  });

  it("dice QUANDO è stato l'ultimo tentativo, non solo che è fallito", () => {
    // Da quando il poller gira da solo: un tentativo fallito due minuti fa e
    // uno fallito tre giorni fa portavano la stessa identica etichetta, e
    // hanno conseguenze opposte per l'Host.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "timeout",
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(screen.getByText("Ultimo tentativo alle 12:30")).toBeInTheDocument();
  });

  it("su un Feed MAI riuscito non mostra alcun orario di aggiornamento", () => {
    // AC 11 (P0): il caso in cui la falsa sincronia fa il danno massimo. Il
    // sistema dice «non so» — non un trattino, che si legge come un valore.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "url_non_raggiungibile",
        ultimo_sync_riuscito_il: null,
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText(
        "Non abbiamo mai ricevuto le prenotazioni di questo calendario.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/ultimo aggiornamento/)).not.toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
  });

  it("distingue un tentativo andato male da un Feed che ha smesso di funzionare", () => {
    // AR-10: è lo stesso segnale su cui il backend fa scattare l'alert
    // interno. Senza, i due casi arrivano identici alla superficie.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "url_non_raggiungibile",
        fallimenti_consecutivi: 4,
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(
      screen.getByText(/non riusciamo a sincronizzare questo calendario da 4 tentativi di fila/i),
    ).toBeInTheDocument();
  });

  it("un solo fallimento NON viene presentato come un guasto", () => {
    // L'altra metà: se la frase forte comparisse al primo intoppo, l'Host
    // imparerebbe a ignorarla e non servirebbe più quando conta.
    montaCon([
      {
        ...FEED_BASE,
        stato_sync: "fallito",
        categoria_errore: "timeout",
        fallimenti_consecutivi: 1,
        ultimo_tentativo_il: "2026-07-26T10:30:00Z",
      },
    ]);
    expect(screen.queryByText(/tentativi di fila/)).not.toBeInTheDocument();
    expect(screen.getByText("Ultimo tentativo non riuscito")).toBeInTheDocument();
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

  it("su errore di caricamento NON afferma che non ci sono calendari", () => {
    // La menzogna peggiore possibile su questa superficie: una Struttura con
    // tre feed collegati che, su un 500 o una sessione scaduta, si presenta
    // come «Nessun calendario collegato». Stessa classe di danno di NFR-2 —
    // il prodotto dichiara certo ciò che non sa.
    feedMock.mockReturnValue({
      isPending: false,
      isError: true,
      error: new Error("calendari non disponibili"),
      data: undefined,
    });
    collegaMock.mockReturnValue(COLLEGA_INERTE);
    render(<FeedIcalStruttura strutturaId="struttura-1" />);

    expect(
      screen.queryByText("Nessun calendario collegato a questa Struttura."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      /Non riusciamo a caricare i calendari/,
    );
  });

  it("mostra l'errore inline del collegamento sul campo", () => {
    feedMock.mockReturnValue({ isPending: false, isError: false, data: [] });
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

  it("invia URL ripulito e Canale scelto, e svuota il campo al successo", async () => {
    const mutate = vi.fn();
    feedMock.mockReturnValue({ isPending: false, isError: false, data: [] });
    collegaMock.mockReturnValue({ ...COLLEGA_INERTE, mutate });
    render(<FeedIcalStruttura strutturaId="struttura-1" />);

    const campo = screen.getByLabelText("Indirizzo del calendario (iCal)");
    await userEvent.type(campo, "  https://feed.example.com/c.ics  ");
    await userEvent.selectOptions(screen.getByLabelText("Canale"), "booking");
    await userEvent.click(screen.getByRole("button", { name: "Collega il calendario" }));

    expect(mutate).toHaveBeenCalledTimes(1);
    const [dati, opzioni] = mutate.mock.calls[0];
    expect(dati).toEqual({
      struttura_id: "struttura-1",
      // Gli spazi incollati insieme all'URL non arrivano al backend.
      url: "https://feed.example.com/c.ics",
      canale: "booking",
    });

    // Il reset avviene su `onSuccess`, non a fuoco perso: un campo svuotato
    // prima della conferma farebbe perdere l'URL su un errore.
    expect(campo).toHaveValue("https://feed.example.com/c.ics");
    act(() => opzioni.onSuccess());
    expect(campo).toHaveValue("");
  });

  it("mentre carica non dice né che ci sono né che non ci sono calendari", () => {
    // Lo stato `isPending` era scoperto: è il terzo caso, e come gli altri due
    // non deve affermare nulla sullo stato del calendario.
    feedMock.mockReturnValue({ isPending: true, isError: false, data: undefined });
    collegaMock.mockReturnValue(COLLEGA_INERTE);
    render(<FeedIcalStruttura strutturaId="struttura-1" />);

    expect(screen.getByRole("status")).toHaveTextContent("Caricamento…");
    expect(
      screen.queryByText("Nessun calendario collegato a questa Struttura."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Non riusciamo a caricare i calendari/),
    ).not.toBeInTheDocument();
  });

  it("ripulisce dall'URL gli spazi che il sanitizer del browser NON tocca", () => {
    // DECISIONE: la `.trim()` si TIENE, e ora e' pinnata per davvero.
    //
    // I due tentativi precedenti non pinnavano nulla, e la ragione e'
    // istruttiva: la sanitizzazione non sta nel layer di battitura ma nel
    // SETTER di `value` di jsdom per `input[type="url"]`, e sia `userEvent`
    // sia `fireEvent.change` scrivono attraverso quel setter. Quindi lo stato
    // non conteneva mai gli spazi ASCII e togliere la `.trim()` lasciava il
    // test verde. I browser reali sanitizzano allo stesso modo, quindi su
    // spazi ASCII la `.trim()` sarebbe stata codice morto.
    //
    // Ma il sanitizer togli solo lo spazio bianco ASCII: uno spazio
    // insecabile (U+00A0) sopravvive — ed e' esattamente quello che arriva
    // incollando un link da una pagina web. `String.trim()` lo rimuove.
    // Quindi la `.trim()` ha uno scopo reale, e questo test lo dimostra.
    const mutate = vi.fn();
    feedMock.mockReturnValue({ isPending: false, isError: false, data: [] });
    collegaMock.mockReturnValue({ ...COLLEGA_INERTE, mutate });
    render(<FeedIcalStruttura strutturaId="struttura-1" />);

    const campo = screen.getByLabelText("Indirizzo del calendario (iCal)");
    fireEvent.change(campo, {
      target: { value: " https://feed.example.com/c.ics " },
    });
    // Il sanitizer NON li ha toccati: sono ancora nel valore del campo.
    expect(campo).toHaveValue(" https://feed.example.com/c.ics ");

    fireEvent.submit(campo.closest("form")!);

    expect(mutate.mock.calls[0][0].url).toBe("https://feed.example.com/c.ics");
  });

  it("disabilita il bottone mentre il collegamento è in volo", () => {
    feedMock.mockReturnValue({ isPending: false, isError: false, data: [] });
    collegaMock.mockReturnValue({ ...COLLEGA_INERTE, isPending: true });
    render(<FeedIcalStruttura strutturaId="struttura-1" />);

    expect(
      screen.getByRole("button", { name: "Collega il calendario" }),
    ).toBeDisabled();
  });
});

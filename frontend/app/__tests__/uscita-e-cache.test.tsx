import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Cosa NON deve sopravvivere all'uscita di un Host (E2-F2, E2-F3).
 *
 * Il modo di guasto è lo stesso per entrambi e vale in una scheda sola: il
 * `QueryClient` e — prima di questo batch — il context della selezione
 * nascevano nel **root layout**, sopra il route group `(app)`, quindi
 * `router.replace("/accesso")` (navigazione lato client) non li smontava.
 * Chi entrava dopo trovava lo stato di chi era uscito.
 *
 * Da questa Story dentro la cache ci sono **dati personali di terzi**:
 * `ospite_principale` viaggia nella risposta del calendario. NFR-14 regge sul
 * server e cadeva qui.
 */

// Unica spia su `POST`: riceve anche il PERCORSO, e questo serve — la prova
// che la strada della scadenza non passa dal logout è che
// `/api/v1/auth/logout` non compare mai fra le chiamate.
const postApi = vi.fn();

vi.mock("@/lib/api/client", () => ({
  api: {
    POST: (...argomenti: unknown[]) => postApi(...argomenti),
    GET: vi.fn(),
    PATCH: vi.fn(),
  },
}));

import { useLogin, useLogout, useRegistrazione } from "@/lib/api/hooks";

const CHIAVE_CALENDARIO = ["calendario", "2026-08-01", "2026-08-31", "tutte"];

// Una risposta del calendario con un nome dentro: è ciò che non deve
// sopravvivere. Nome inventato (NFR-16).
const CON_OSPITE = {
  da: "2026-08-01",
  a: "2026-08-31",
  stato_sync: "riuscito",
  ultimo_sync_riuscito_il: "2026-08-17T12:35:00Z",
  feed_collegati: 1,
  feed_mai_sincronizzati: 0,
  feed_in_errore: 0,
  strutture: [{ id: "s1", nome: "Bologna Centro" }],
  voci: [{ id: "p1", ospite_principale: "Ospite Inventato" }],
};

function Uscita() {
  const logout = useLogout();
  return (
    <button type="button" onClick={() => logout.mutate()}>
      Esci
    </button>
  );
}

describe("E2-F2 — la cache non sopravvive al logout", () => {
  beforeEach(() => {
    postApi.mockReset();
    postApi.mockResolvedValue({ data: undefined, error: undefined });
  });

  it("le Prenotazioni dell'Host uscito non restano servibili al successivo", async () => {
    // La chiave non contiene l'identità dell'Host: quella del secondo Host
    // sarebbe byte-identica, e TanStack la servirebbe `success` entro i
    // cinque minuti di `gcTime`. Il primo paint sarebbero i dati altrui.
    const queryClient = new QueryClient();
    queryClient.setQueryData(CHIAVE_CALENDARIO, CON_OSPITE);
    queryClient.setQueryData(["strutture"], [{ id: "s1", nome: "Bologna Centro" }]);
    queryClient.setQueryData(["me"], { id: "h1", email: "primo@example.com" });

    render(
      <QueryClientProvider client={queryClient}>
        <Uscita />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Esci" }));

    await waitFor(() => {
      expect(queryClient.getQueryData(CHIAVE_CALENDARIO)).toBeUndefined();
    });
    expect(queryClient.getQueryData(["strutture"])).toBeUndefined();
  });

  it("dopo il logout `me` è esplicitamente nullo, non solo assente", async () => {
    // Svuotare e basta lascerebbe `me` `undefined`, cioè «non lo so»: la
    // shell resterebbe su «Caricamento…» invece di mandare all'accesso.
    const queryClient = new QueryClient();
    queryClient.setQueryData(["me"], { id: "h1", email: "primo@example.com" });

    render(
      <QueryClientProvider client={queryClient}>
        <Uscita />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Esci" }));

    await waitFor(() => {
      expect(queryClient.getQueryData(["me"])).toBeNull();
    });
  });
});

// ------------------------------------------- E2-F2, la strada della SCADENZA

/**
 * Il logout non è l'unico modo in cui una sessione finisce, ed era l'unico
 * chiuso.
 *
 * Una sessione muore anche da sé: cookie scaduto, `purge_sessioni_scadute`,
 * un riavvio del backend — o un «Esci» la cui risposta si perde dopo che il
 * server l'ha processata, e allora `onSuccess` non parte affatto. Su tutte
 * queste strade `useMe` prende un 401, la shell fa `router.replace`, e la
 * cache resta intatta perché nessuno l'ha svuotata.
 *
 * Chi entra dopo trova quindi le Prenotazioni del precedente — nomi di
 * Ospiti compresi — servite `success` entro i cinque minuti di `gcTime`,
 * perché le chiavi non portano l'identità dell'Host.
 *
 * Il rimedio non insegue le uscite una per una: è **l'ingresso** a garantire
 * che nella scheda non resti niente di chi c'era prima. Una sessione può
 * finire in molti modi, ma per vedere i dati bisogna entrare, e di porte
 * d'ingresso ce ne sono due sole.
 */

const SECONDO_HOST = { id: "h2", email: "secondo@example.com" };

function Ingresso({ hook }: Readonly<{ hook: typeof useLogin }>) {
  const ingresso = hook();
  return (
    <button
      type="button"
      onClick={() =>
        ingresso.mutate({ email: SECONDO_HOST.email, password: "non-reale" })
      }
    >
      Entra
    </button>
  );
}

describe("E2-F2 — la cache non sopravvive alla scadenza della sessione", () => {
  beforeEach(() => {
    postApi.mockReset();
    postApi.mockResolvedValue({ data: SECONDO_HOST, error: undefined });
  });

  function cacheDelPrimoHost() {
    const queryClient = new QueryClient();
    queryClient.setQueryData(CHIAVE_CALENDARIO, CON_OSPITE);
    queryClient.setQueryData(["strutture"], [
      { id: "s1", nome: "Bologna Centro" },
    ]);
    // Stato in cui il 401 ha già lasciato la scheda: `useMe` ha risolto a
    // `null` e la shell ha già rediretto. Nessun logout è mai avvenuto.
    queryClient.setQueryData(["me"], null);
    return queryClient;
  }

  it.each([
    ["useLogin", useLogin],
    ["useRegistrazione", useRegistrazione],
  ])(
    "%s non lascia entrare l'Host nuovo sui dati del precedente",
    async (_nome, hook) => {
      const queryClient = cacheDelPrimoHost();

      render(
        <QueryClientProvider client={queryClient}>
          <Ingresso hook={hook} />
        </QueryClientProvider>,
      );
      await userEvent.click(screen.getByRole("button", { name: "Entra" }));

      await waitFor(() => {
        expect(queryClient.getQueryData(["me"])).toEqual(SECONDO_HOST);
      });
      // Le due che portano dati personali di terzi e il filtro altrui.
      expect(queryClient.getQueryData(CHIAVE_CALENDARIO)).toBeUndefined();
      expect(queryClient.getQueryData(["strutture"])).toBeUndefined();
    },
  );

  it("la garanzia non passa dal logout: quella strada non viene percorsa", async () => {
    // Il punto dell'intero residuo. Se qualcuno «chiudesse» di nuovo il buco
    // svuotando altrove sull'uscita, questo test resterebbe verde e quello
    // sopra no — ed è per questo che ci sono entrambi.
    const queryClient = cacheDelPrimoHost();

    render(
      <QueryClientProvider client={queryClient}>
        <Ingresso hook={useLogin} />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));

    await waitFor(() => {
      expect(queryClient.getQueryData(["me"])).toEqual(SECONDO_HOST);
    });
    const percorsi = postApi.mock.calls.map(([percorso]) => percorso);
    expect(percorsi).not.toContain("/api/v1/auth/logout");
  });

  it("lo svuotamento precede la scrittura di `me`, non la annulla", async () => {
    // L'ordine è l'unico modo in cui questo fix si può sbagliare: uno
    // `clear()` dopo `setQueryData` cancellerebbe l'Host appena entrato e la
    // shell resterebbe su «Caricamento…» invece di aprirsi.
    const queryClient = cacheDelPrimoHost();

    render(
      <QueryClientProvider client={queryClient}>
        <Ingresso hook={useLogin} />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));

    await waitFor(() => {
      expect(queryClient.getQueryData(CHIAVE_CALENDARIO)).toBeUndefined();
    });
    expect(queryClient.getQueryData(["me"])).toEqual(SECONDO_HOST);
  });
});

// --------------------------------------------------------------- E2-F3

const useMe = vi.fn();

vi.mock("@/lib/api/hooks", async (importaOriginale) => {
  const originale =
    await importaOriginale<typeof import("@/lib/api/hooks")>();
  return {
    ...originale,
    useMe: () => useMe(),
    useStrutture: () => ({
      data: [
        { id: "s1", nome: "Bologna Centro", stato: "attiva" },
        { id: "s2", nome: "Mare Rimini", stato: "attiva" },
      ],
    }),
    useRegimeFiscale: () => ({ data: undefined }),
    useConfermaLetturaRegime: () => ({ mutate: vi.fn(), isPending: false }),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/calendario",
}));

import AppLayout from "../(app)/layout";

describe("E2-F3 — la selezione Struttura non sopravvive all'uscita", () => {
  beforeEach(() => {
    useMe.mockReset();
  });

  function shell() {
    return render(
      <QueryClientProvider client={new QueryClient()}>
        <AppLayout>
          <p>contenuto</p>
        </AppLayout>
      </QueryClientProvider>,
    );
  }

  it("uscendo dalla shell la selezione torna a «Tutte le Strutture»", async () => {
    // Il caso reale: Host A filtra su una sua Struttura, esce, Host B entra
    // nella stessa scheda. Con il provider sopra il route group, B ereditava
    // l'UUID di A — il `<select>` si presentava vuoto dichiarando di non
    // filtrare, e il calendario restava su «non riusciamo a caricare» in
    // modo stabile, perché ogni retry rifalliva sullo stesso 404.
    useMe.mockReturnValue({
      data: { id: "h1", email: "primo@example.com" },
      isPending: false,
      isError: false,
    });
    const { rerender } = shell();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /struttura/i }),
      "s2",
    );
    expect(screen.getByRole("combobox", { name: /struttura/i })).toHaveValue(
      "s2",
    );

    // Uscita: la shell smonta e la pagina di accesso prende il suo posto.
    useMe.mockReturnValue({ data: null, isPending: false, isError: false });
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <AppLayout>
          <p>contenuto</p>
        </AppLayout>
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("combobox", { name: /struttura/i })).toBeNull();

    // Rientro di un altro Host nella stessa scheda.
    useMe.mockReturnValue({
      data: { id: "h2", email: "secondo@example.com" },
      isPending: false,
      isError: false,
    });
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <AppLayout>
          <p>contenuto</p>
        </AppLayout>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("combobox", { name: /struttura/i })).toHaveValue(
      "tutte",
    );
  });

  it("il provider vive DENTRO la shell autenticata, non sopra", () => {
    // La proprietà strutturale che rende vero il test sopra: fuori dalla
    // shell il context non esiste affatto, quindi non c'è uno stato che
    // possa sopravvivere. Se qualcuno lo rimontasse nel root layout, questo
    // test resterebbe verde ma quello sopra no — ed è per questo che ci
    // sono entrambi.
    useMe.mockReturnValue({ data: null, isPending: true, isError: false });
    shell();

    expect(screen.queryByRole("combobox", { name: /struttura/i })).toBeNull();
  });
});

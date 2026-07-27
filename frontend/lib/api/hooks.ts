"use client";

/**
 * Hook di accesso all'API (AD-14): tutte le chiamate passano dal client
 * generato + TanStack Query. Nessun fetch tipizzato a mano.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { components } from "./schema";

export type HostOutput = components["schemas"]["HostOutput"];
export type CanaleNotifica = components["schemas"]["CanaleNotifica"];
export type StrutturaOutput = components["schemas"]["StrutturaOutput"];
export type StrutturaInput = components["schemas"]["StrutturaInput"];
export type ComuneOutput = components["schemas"]["ComuneOutput"];
export type RegioneOutput = components["schemas"]["RegioneOutput"];
export type ConfigurazioneNormativa =
  components["schemas"]["ConfigurazioneNormativaOutput"];
export type RegimeFiscale = components["schemas"]["RegimeFiscaleOutput"];
export type FeedIcal = components["schemas"]["FeedIcalOutput"];
export type FeedIcalInput = components["schemas"]["FeedIcalInput"];
export type CanaleFeed = components["schemas"]["CanaleFeed"];
export type Calendario = components["schemas"]["CalendarioOutput"];
export type VoceCalendario = components["schemas"]["VoceCalendarioOutput"];
export type StatoPrenotazione = components["schemas"]["StatoPrenotazione"];

type Problem = { title?: string; detail?: string };

function titoloErrore(error: unknown): string | undefined {
  const problem = error as Problem | undefined;
  return problem?.detail ?? problem?.title;
}

export function useMe() {
  return useQuery<HostOutput | null>({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/hosts/me");
      if (response.status === 401) return null;
      if (!data) throw new Error("profilo non disponibile");
      return data;
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useRegistrazione() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credenziali: { email: string; password: string }) => {
      const { data, error } = await api.POST("/api/v1/auth/registrazione", {
        body: credenziali,
      });
      if (!data) throw new Error(titoloErrore(error) ?? "registrazione fallita");
      return data;
    },
    onSuccess: (host) => queryClient.setQueryData(["me"], host),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credenziali: { email: string; password: string }) => {
      const { data, error } = await api.POST("/api/v1/auth/login", {
        body: credenziali,
      });
      if (!data) throw new Error(titoloErrore(error) ?? "accesso fallito");
      return data;
    },
    onSuccess: (host) => queryClient.setQueryData(["me"], host),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSuccess: () => {
      // **Si svuota TUTTA la cache, non solo `["me"]`** (E2-F2). Il
      // `QueryClient` nasce nel root layout e sopravvive a
      // `router.replace("/accesso")`, che è navigazione lato client; nessuna
      // chiave contiene l'identità dell'Host, quindi
      // `["calendario","2026-08-01","2026-08-31","tutte"]` di chi è appena
      // uscito è **byte-identica** a quella di chi entra dopo nella stessa
      // scheda. Entro i cinque minuti di `gcTime` TanStack la servirebbe
      // come `success`, e il primo paint del secondo Host sarebbero le
      // Prenotazioni del primo — nomi di Ospiti compresi.
      //
      // NFR-14 regge sul server e cadeva qui. Il buco preesisteva su
      // `["strutture"]` e `["me"]`; da questa Story dentro ci sono dati
      // personali di terzi, quindi si chiude adesso e per intero.
      queryClient.clear();
      queryClient.setQueryData(["me"], null);
    },
  });
}

export function useAggiornaPreferenze() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (canale: CanaleNotifica) => {
      const { data, error } = await api.PATCH("/api/v1/hosts/me/preferenze", {
        body: { canale_notifica_preferito: canale },
      });
      if (!data) throw new Error(titoloErrore(error) ?? "salvataggio fallito");
      return data;
    },
    onSuccess: (host) => queryClient.setQueryData(["me"], host),
  });
}

/** Il Regime fiscale è derivato dal numero di Strutture (AD-12): ogni
 * mutazione sulle Strutture invalida anche la sua cache. Il Calendario
 * aggrega le Strutture dell'Host, quindi vale lo stesso: una Struttura nuova
 * che non compare nella griglia finché non si ricarica la pagina è la stessa
 * classe di difetto della Story 1.6. */
function invalidaStruttureERegime(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["strutture"] });
  queryClient.invalidateQueries({ queryKey: ["regime-fiscale"] });
  queryClient.invalidateQueries({ queryKey: ["calendario"] });
}

export function useStrutture() {
  return useQuery<StrutturaOutput[]>({
    queryKey: ["strutture"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/strutture");
      if (!data) throw new Error(titoloErrore(error) ?? "strutture non disponibili");
      return data;
    },
  });
}

export function useCreaStruttura() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dati: StrutturaInput) => {
      const { data, error } = await api.POST("/api/v1/strutture", { body: dati });
      if (!data) throw new Error(titoloErrore(error) ?? "registrazione fallita");
      return data;
    },
    onSuccess: () => invalidaStruttureERegime(queryClient),
  });
}

export function useAggiornaStruttura() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      struttura_id: string;
      modifiche: Partial<StrutturaInput>;
    }) => {
      const { data, error } = await api.PATCH(
        "/api/v1/strutture/{struttura_id}",
        {
          params: { path: { struttura_id: input.struttura_id } },
          body: input.modifiche,
        },
      );
      if (!data) throw new Error(titoloErrore(error) ?? "salvataggio fallito");
      return data;
    },
    onSuccess: () => invalidaStruttureERegime(queryClient),
  });
}

export function useArchiviaStruttura() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (struttura_id: string) => {
      const { data, error } = await api.POST(
        "/api/v1/strutture/{struttura_id}/archivia",
        { params: { path: { struttura_id } } },
      );
      if (!data) throw new Error(titoloErrore(error) ?? "archiviazione fallita");
      return data;
    },
    onSuccess: () => invalidaStruttureERegime(queryClient),
  });
}

export function useRegioni() {
  return useQuery<RegioneOutput[]>({
    queryKey: ["regioni"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/regioni");
      if (!data) throw new Error(titoloErrore(error) ?? "regioni non disponibili");
      return data;
    },
    staleTime: Infinity, // anagrafica stabile
  });
}

/** Suggerimenti di Comune dall'anagrafica ISTAT (min. 2 caratteri). */
export function useComuni(ricerca: string) {
  return useQuery<ComuneOutput[]>({
    queryKey: ["comuni", ricerca],
    enabled: ricerca.trim().length >= 2,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/comuni", {
        params: { query: { ricerca: ricerca.trim() } },
      });
      if (!data) throw new Error(titoloErrore(error) ?? "ricerca non disponibile");
      return data;
    },
  });
}

export function useConfigurazioneNormativa(struttura_id: string) {
  return useQuery<ConfigurazioneNormativa>({
    queryKey: ["configurazione-normativa", struttura_id],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/strutture/{struttura_id}/configurazione-normativa",
        { params: { path: { struttura_id } } },
      );
      if (!data) {
        throw new Error(titoloErrore(error) ?? "configurazione non disponibile");
      }
      return data;
    },
  });
}

export function useRegimeFiscale() {
  return useQuery<RegimeFiscale>({
    queryKey: ["regime-fiscale"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/regime-fiscale");
      if (!data) throw new Error(titoloErrore(error) ?? "regime non disponibile");
      return data;
    },
  });
}

export function useConfermaLetturaRegime() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/regime-fiscale/conferma-lettura");
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["regime-fiscale"] }),
  });
}

/** Feed iCal collegati a una Struttura (FR-3).
 *
 * Finché un import è in corso la query si ripete: il progresso arriva
 * dall'API, il client non lo simula (AD-14). Appena lo stato non è più
 * `in_corso` il polling si ferma da sé — nessun timer che resta acceso.
 */
export function useFeedIcal(struttura_id: string) {
  return useQuery<FeedIcal[]>({
    queryKey: ["feed-ical", struttura_id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/feed-ical", {
        params: { query: { struttura_id } },
      });
      if (!data) throw new Error(titoloErrore(error) ?? "calendari non disponibili");
      return data;
    },
    refetchInterval: (query) =>
      (query.state.data ?? []).some((feed) => feed.stato_sync === "in_corso")
        ? 3000
        : false,
  });
}

export function useCollegaFeed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dati: FeedIcalInput) => {
      const { data, error } = await api.POST("/api/v1/feed-ical", { body: dati });
      if (!data) throw new Error(titoloErrore(error) ?? "collegamento fallito");
      return data;
    },
    onSuccess: (feed) => {
      queryClient.invalidateQueries({
        queryKey: ["feed-ical", feed.struttura_id],
      });
      // Il Calendario deriva dagli stessi Feed: collegarne uno cambia sia le
      // Prenotazioni sia l'etichetta «dati aggiornati alle HH:MM». Invalidare
      // solo la prima cache lascia l'altra ferma su un orario vecchio — ed è
      // precisamente la falsa sincronia che NFR-2 vieta.
      queryClient.invalidateQueries({ queryKey: ["calendario"] });
    },
  });
}

/** Il calendario unificato di un periodo (FR-4, UX-DR1, NFR-2).
 *
 * **Una sola query per la griglia E per l'etichetta del timestamp**, ed è una
 * scelta: sono valori derivati dalla stessa sorgente, e tenerli in due cache
 * distinte significa poterle vedere divergere — la griglia aggiornata e
 * l'orario fermo, cioè un calendario che si dichiara più vecchio (o più
 * fresco) di quello che mostra. Con una voce sola di cache la divergenza non
 * è un difetto improbabile: è impossibile.
 *
 * Finché un import è in corso la query si ripete, così il primo timestamp
 * arriva senza che l'Host debba ricaricare. Appena lo stato non è più
 * `in_corso` il polling si ferma da sé.
 */
export function useCalendario(parametri: {
  da: string;
  a: string;
  struttura_id?: string;
}) {
  const { da, a, struttura_id } = parametri;
  return useQuery<Calendario>({
    queryKey: ["calendario", da, a, struttura_id ?? "tutte"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/calendario", {
        params: { query: { da, a, ...(struttura_id ? { struttura_id } : {}) } },
      });
      if (!data) throw new Error(titoloErrore(error) ?? "calendario non disponibile");
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.stato_sync === "in_corso" ? 3000 : false,
  });
}

export function useCambiaPassword() {
  return useMutation({
    mutationFn: async (input: {
      password_attuale: string;
      password_nuova: string;
    }) => {
      const { error, response } = await api.POST("/api/v1/hosts/me/password", {
        body: input,
      });
      if (!response.ok) {
        throw new Error(titoloErrore(error) ?? "cambio password fallito");
      }
    },
  });
}

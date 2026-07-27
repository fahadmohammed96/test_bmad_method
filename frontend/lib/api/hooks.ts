"use client";

/**
 * Hook di accesso all'API (AD-14): tutte le chiamate passano dal client
 * generato + TanStack Query. Nessun fetch tipizzato a mano.
 */
import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
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

/**
 * Ingresso di un Host nella scheda: **prima si svuota, poi si scrive**.
 *
 * Il presidio sta qui e non sulle uscite (E2-F2). Una sessione finisce in
 * molti modi — il bottone «Esci», un cookie scaduto,
 * `purge_sessioni_scadute`, un riavvio del backend, o un logout la cui
 * risposta si perde dopo che il server l'ha processata — e su tutti quelli
 * che non sono il bottone nessun `onSuccess` parte: `useMe` prende un 401,
 * la shell fa `router.replace("/accesso")`, che è navigazione lato client, e
 * la cache resta intatta.
 *
 * Le chiavi non portano l'identità dell'Host, quindi
 * `["calendario","2026-08-01","2026-08-31","tutte"]` di chi se n'è andato è
 * **byte-identica** a quella di chi entra dopo: entro i cinque minuti di
 * `gcTime` TanStack la servirebbe `success`, e il primo paint del secondo
 * Host sarebbero le Prenotazioni del primo, `ospite_principale` compreso.
 * NFR-14 regge sul server e cadrebbe qui.
 *
 * Presidiare l'ingresso invece delle uscite rende la cosa vera per
 * costruzione: i modi di finire una sessione non sono enumerabili, le porte
 * per entrare sono due e sono queste.
 *
 * L'ORDINE è l'unico modo di sbagliare questo rimedio: uno `clear()` dopo la
 * scrittura cancellerebbe l'Host appena entrato, e la shell resterebbe su
 * «Caricamento…». C'è un test che lo pinna.
 */
function entra(queryClient: QueryClient, host: HostOutput) {
  queryClient.clear();
  queryClient.setQueryData(["me"], host);
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
    onSuccess: (host) => entra(queryClient, host),
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
    onSuccess: (host) => entra(queryClient, host),
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
      // NFR-14 regge sul server e cadeva qui.
      //
      // Questa però è la strada del BOTTONE, e da sola non basta (E2-F2): la
      // garanzia sta in `entra`, sull'ingresso, perché le uscite che non
      // passano di qui — cookie scaduto, 401, o questa stessa risposta
      // perduta — non eseguono nessun `onSuccess`. Qui si svuota comunque,
      // per non tenere dati personali in memoria un istante più del
      // necessario quando la strada del bottone c'è davvero.
      queryClient.clear();
      // `me` esplicitamente `null` e non `undefined`: «so che non c'è»
      // invece di «non lo so», altrimenti la shell resta su «Caricamento…»
      // invece di mandare all'accesso.
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

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
    onSuccess: () => queryClient.setQueryData(["me"], null),
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strutture"] }),
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strutture"] }),
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strutture"] }),
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

import { queryOptions, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

import type { AgentEvent, Atendimento } from "./engine";

export const escritorioConfigQuery = queryOptions({
  queryKey: ["escritorio", "config"],
  queryFn: async () => {
    const { data, response } = await api.GET("/api/escritorio/config");
    if (!data) throw new Error(`Falha ao ler a configuração do escritório: ${response.status}`);
    return data;
  },
  staleTime: 5 * 60_000,
  retry: false,
});

/** Verdadeiro só com a flag ligada no servidor. Qualquer erro conta como desligado. */
export function useEscritorioEnabled(): boolean {
  return useQuery(escritorioConfigQuery).data?.enabled ?? false;
}

export const atendimentosQuery = (live: boolean) =>
  queryOptions({
    queryKey: ["escritorio", "atendimentos"],
    queryFn: async (): Promise<Atendimento[]> => {
      const { data, response } = await api.GET("/api/escritorio/atendimentos");
      if (!data) throw new Error(`Falha ao listar atendimentos: ${response.status}`);
      return data;
    },
    refetchInterval: live ? 5_000 : false,
  });

/** Atendimento = conversa; sem conversa, o chamado. */
export interface AttendanceRef {
  conversationId: string | null;
  ticketId: string | null;
}

export const eventosQuery = (ref: AttendanceRef | null) =>
  queryOptions({
    queryKey: ["escritorio", "eventos", ref?.conversationId ?? ref?.ticketId ?? null],
    enabled: ref !== null,
    queryFn: async (): Promise<AgentEvent[]> => {
      const { data, response } = await api.GET("/api/escritorio/eventos", {
        params: {
          query: ref?.conversationId
            ? { conversation_id: ref.conversationId }
            : { ticket_id: ref?.ticketId ?? undefined },
        },
      });
      if (!data) throw new Error(`Falha ao carregar os eventos: ${response.status}`);
      return data;
    },
  });

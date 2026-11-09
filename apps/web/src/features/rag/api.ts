import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type RagOverview = components["schemas"]["OverviewOut"];
export type RagTrace = components["schemas"]["TraceOut"];
export type RagChunk = components["schemas"]["ChunkAnatomy"];

export const ragOverviewQuery = queryOptions({
  queryKey: ["admin", "rag", "overview"],
  queryFn: async (): Promise<RagOverview> => {
    const { data, response } = await api.GET("/api/admin/rag/overview");
    if (!data) throw new Error(`Falha ao carregar o resumo do RAG: ${response.status}`);
    return data;
  },
});

export function ragChunkQuery(id: string | null) {
  return queryOptions({
    queryKey: ["admin", "rag", "chunk", id],
    enabled: id !== null,
    queryFn: async (): Promise<RagChunk> => {
      const { data, response } = await api.GET("/api/admin/rag/chunks/{chunk_id}", {
        params: { path: { chunk_id: id ?? "" } },
      });
      if (!data) throw new Error(`Falha ao abrir o trecho: ${response.status}`);
      return data;
    },
  });
}

export async function traceQuestion(question: string): Promise<RagTrace> {
  const { data, response, error } = await api.POST("/api/admin/rag/trace", { body: { question } });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    throw new Error(
      typeof detail === "string" ? detail : `Não foi possível rastrear a pergunta (${response.status}).`,
    );
  }
  return data;
}

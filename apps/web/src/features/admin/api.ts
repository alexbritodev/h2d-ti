import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type AuditEntry = components["schemas"]["AuditEntry"];
export type CategoryRow = components["schemas"]["CategoryOut"];
export type SlaRow = components["schemas"]["SlaRow"];
export type PromptRow = components["schemas"]["PromptOut"];
export type TriageSettings = components["schemas"]["TriageSettings"];

export const auditQuery = queryOptions({
  queryKey: ["admin", "audit"],
  queryFn: async (): Promise<AuditEntry[]> => {
    const { data, response } = await api.GET("/api/admin/audit", { params: { query: { limit: 300 } } });
    if (!data) throw new Error(`Falha ao carregar a auditoria: ${response.status}`);
    return data;
  },
});

export const categoriesQuery = queryOptions({
  queryKey: ["admin", "categories"],
  queryFn: async (): Promise<CategoryRow[]> => {
    const { data, response } = await api.GET("/api/admin/categories");
    if (!data) throw new Error(`Falha ao carregar as categorias: ${response.status}`);
    return data;
  },
});

export const slaQuery = queryOptions({
  queryKey: ["admin", "sla"],
  queryFn: async (): Promise<SlaRow[]> => {
    const { data, response } = await api.GET("/api/admin/sla");
    if (!data) throw new Error(`Falha ao carregar os prazos: ${response.status}`);
    return data;
  },
});

export const promptsQuery = queryOptions({
  queryKey: ["admin", "prompts"],
  queryFn: async (): Promise<PromptRow[]> => {
    const { data, response } = await api.GET("/api/admin/prompts");
    if (!data) throw new Error(`Falha ao carregar os prompts: ${response.status}`);
    return data;
  },
});

export const triageSettingsQuery = queryOptions({
  queryKey: ["admin", "settings"],
  queryFn: async (): Promise<TriageSettings> => {
    const { data, response } = await api.GET("/api/admin/settings");
    if (!data) throw new Error(`Falha ao carregar os ajustes: ${response.status}`);
    return data;
  },
});

export async function saveTriageSettings(
  body: TriageSettings,
): Promise<{ ok: true } | { ok: false; message: string }> {
  const { response, error } = await api.PUT("/api/admin/settings", { body });
  if (response.ok) return { ok: true };
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return { ok: false, message: typeof detail === "string" ? detail : "Não foi possível salvar." };
}

/** "90" vira "1 h 30 min"; mantém a leitura curta dos prazos. */
export function formatMinutes(total: number): string {
  if (total < 60) return `${total} min`;
  if (total < 60 * 24) {
    const hours = Math.floor(total / 60);
    const minutes = total % 60;
    return minutes ? `${hours} h ${minutes} min` : `${hours} h`;
  }
  const days = Math.floor(total / (60 * 24));
  const hours = Math.floor((total % (60 * 24)) / 60);
  return hours ? `${days} d ${hours} h` : `${days} d`;
}

import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type KbDocument = components["schemas"]["DocumentOut"];
export type KbJob = components["schemas"]["JobOut"];
export type KbHit = components["schemas"]["HitOut"];
export type LibraryItem = components["schemas"]["LibraryItem"];
export type DocumentView = components["schemas"]["DocumentView"];
export type Visibility = components["schemas"]["Visibility"];

export const ACCEPTED_EXTENSIONS = ".md,.markdown,.txt";
export const MAX_UPLOAD_MB = 10;

export const documentsQuery = queryOptions({
  queryKey: ["kb", "documents"],
  queryFn: async (): Promise<KbDocument[]> => {
    const { data, response } = await api.GET("/api/kb/documents");
    if (!data) throw new Error(`Falha ao listar documentos: ${response.status}`);
    return data;
  },
});

export const jobsQuery = queryOptions({
  queryKey: ["kb", "jobs"],
  queryFn: async (): Promise<KbJob[]> => {
    const { data, response } = await api.GET("/api/kb/jobs", { params: { query: { limit: 30 } } });
    if (!data) throw new Error(`Falha ao listar jobs: ${response.status}`);
    return data;
  },
});

export const libraryQuery = queryOptions({
  queryKey: ["kb", "library"],
  queryFn: async (): Promise<LibraryItem[]> => {
    const { data, response } = await api.GET("/api/kb/library");
    if (!data) throw new Error(`Falha ao listar a base: ${response.status}`);
    return data;
  },
});

export function libraryDocumentQuery(id: string) {
  return queryOptions({
    queryKey: ["kb", "library", id],
    queryFn: async (): Promise<DocumentView> => {
      const { data, response } = await api.GET("/api/kb/library/{document_id}", {
        params: { path: { document_id: id } },
      });
      if (!data) throw new Error(`Falha ao abrir o documento: ${response.status}`);
      return data;
    },
  });
}

export function searchQuery(term: string) {
  return queryOptions({
    queryKey: ["kb", "search", term],
    queryFn: async (): Promise<KbHit[]> => {
      const { data, response } = await api.GET("/api/kb/search", {
        params: { query: { q: term, limit: 8 } },
      });
      if (!data) throw new Error(`Falha na busca: ${response.status}`);
      return data;
    },
    staleTime: 30_000,
  });
}

export const isActive = (jobs: KbJob[] | undefined) =>
  jobs?.some((job) => job.state === "queued" || job.state === "running") ?? false;

export type Outcome<T> = { ok: true; data: T } | { ok: false; message: string };

function message(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return first.msg.replace(/^Value error, /, "");
  }
  return fallback;
}

/** Envio multipart. O arquivo vai ao servidor, que guarda o original e enfileira o processamento. */
export async function uploadDocument(
  file: File,
  visibility: Visibility | "",
): Promise<Outcome<components["schemas"]["UploadOut"]>> {
  const form = new FormData();
  form.append("file", file);
  if (visibility) form.append("visibility", visibility);
  try {
    const response = await fetch("/api/kb/documents", {
      method: "POST",
      body: form,
      credentials: "same-origin",
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) return { ok: false, message: message(body, "Não foi possível enviar o arquivo.") };
    return { ok: true, data: body as components["schemas"]["UploadOut"] };
  } catch {
    return { ok: false, message: "Sem conexão com o servidor." };
  }
}

export async function reindex(id: string): Promise<Outcome<null>> {
  const { response, error } = await api.POST("/api/kb/documents/{document_id}/reindex", {
    params: { path: { document_id: id } },
  });
  return response.ok ? { ok: true, data: null } : { ok: false, message: message(error, "Não foi possível reindexar.") };
}

export async function updateDocument(
  id: string,
  body: { title?: string; category?: string; visibility?: Visibility },
): Promise<Outcome<KbDocument>> {
  const { data, error } = await api.PATCH("/api/kb/documents/{document_id}", {
    params: { path: { document_id: id } },
    body,
  });
  return data ? { ok: true, data } : { ok: false, message: message(error, "Não foi possível salvar.") };
}

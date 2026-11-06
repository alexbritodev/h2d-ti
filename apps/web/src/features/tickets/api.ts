import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Ticket = components["schemas"]["TicketOut"];
export type TicketDetail = components["schemas"]["TicketDetail"];
export type TicketEvent = components["schemas"]["EventOut"];
export type TicketStatus = components["schemas"]["TicketStatus"];
export type Priority = components["schemas"]["Priority"];
export type Technician = components["schemas"]["TechnicianOut"];

export interface TicketFilters {
  status?: TicketStatus;
  priority?: Priority;
  mine?: boolean;
  triage?: boolean;
}

export const ticketsQuery = (filters: TicketFilters = {}) =>
  queryOptions({
    queryKey: ["tickets", "list", filters],
    queryFn: async (): Promise<Ticket[]> => {
      const { data, response } = await api.GET("/api/tickets", {
        params: { query: { ...filters, limit: 200 } },
      });
      if (!data) throw new Error(`Falha ao listar chamados: ${response.status}`);
      return data;
    },
  });

export const ticketQuery = (id: string) =>
  queryOptions({
    queryKey: ["tickets", "detail", id],
    queryFn: async (): Promise<TicketDetail> => {
      const { data, response } = await api.GET("/api/tickets/{ticket_id}", {
        params: { path: { ticket_id: id } },
      });
      if (!data) throw new Error(`Falha ao abrir o chamado: ${response.status}`);
      return data;
    },
  });

export const techniciansQuery = queryOptions({
  queryKey: ["tickets", "technicians"],
  queryFn: async (): Promise<Technician[]> => {
    const { data, response } = await api.GET("/api/tickets/technicians");
    if (!data) throw new Error(`Falha ao listar técnicos: ${response.status}`);
    return data;
  },
});

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

export async function updateTicket(
  id: string,
  body: { status?: TicketStatus; technician_id?: string; reason?: string },
): Promise<Outcome<Ticket>> {
  const { data, error } = await api.PATCH("/api/tickets/{ticket_id}", {
    params: { path: { ticket_id: id } },
    body,
  });
  return data ? { ok: true, data } : { ok: false, message: message(error, "Não foi possível atualizar.") };
}

export async function commentTicket(id: string, text: string): Promise<Outcome<TicketEvent>> {
  const { data, error } = await api.POST("/api/tickets/{ticket_id}/comments", {
    params: { path: { ticket_id: id } },
    body: { text },
  });
  return data ? { ok: true, data } : { ok: false, message: message(error, "Não foi possível comentar.") };
}

export async function resolveTicket(id: string, solution: string): Promise<Outcome<Ticket>> {
  const { data, error } = await api.POST("/api/tickets/{ticket_id}/resolve", {
    params: { path: { ticket_id: id } },
    body: { solution },
  });
  return data ? { ok: true, data } : { ok: false, message: message(error, "Não foi possível resolver.") };
}

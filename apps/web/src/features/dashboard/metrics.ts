import { queryOptions } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Overview = components["schemas"]["Overview"];

export const PERIODS = [
  { days: 7, label: "7 dias" },
  { days: 14, label: "14 dias" },
  { days: 30, label: "30 dias" },
] as const;

export const overviewQuery = (days: number) =>
  queryOptions({
    queryKey: ["metrics", "overview", days],
    staleTime: 30_000,
    queryFn: async (): Promise<Overview> => {
      const { data, response } = await api.GET("/api/metrics/overview", {
        params: { query: { days } },
      });
      if (!data) throw new Error(`Falha ao carregar o dashboard: ${response.status}`);
      return data;
    },
  });

/** 0,5 vira "50%". Sem base de cálculo (nenhuma conversa, nenhum chamado resolvido), "—". */
export function percent(rate: number | null | undefined): string {
  return rate == null ? "—" : `${Math.round(rate * 100)}%`;
}

/** A API devolve o decimal como texto ("0.008750"); o custo por conversa é pequeno, então 4 casas. */
export function usd(value: string | number | null | undefined): string {
  if (value == null) return "—";
  return `US$ ${Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  })}`;
}

/** "2026-11-06" vira "06/11". */
export function shortDay(day: string): string {
  const [, month, date] = day.split("-");
  return `${date}/${month}`;
}

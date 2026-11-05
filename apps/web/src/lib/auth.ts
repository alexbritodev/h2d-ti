import { queryOptions, type QueryClient } from "@tanstack/react-query";

import { api, type User } from "./api/client";

export const meQuery = queryOptions({
  queryKey: ["me"],
  staleTime: 60_000,
  retry: false,
  queryFn: async (): Promise<User | null> => {
    const { data, response } = await api.GET("/api/auth/me");
    if (response.status === 401) return null;
    if (!data) throw new Error(`Falha ao consultar a sessão: ${response.status}`);
    return data;
  },
});

export type LoginResult = { ok: true; user: User } | { ok: false; reason: "credentials" | "server" };

export async function login(email: string, password: string): Promise<LoginResult> {
  try {
    const { data, response } = await api.POST("/api/auth/login", { body: { email, password } });
    if (data) return { ok: true, user: data };
    return { ok: false, reason: response.status === 401 ? "credentials" : "server" };
  } catch {
    return { ok: false, reason: "server" };
  }
}

export async function logout(queryClient: QueryClient): Promise<void> {
  await api.POST("/api/auth/logout");
  // Limpa tudo: nada da sessão anterior pode aparecer para a próxima pessoa.
  queryClient.clear();
}

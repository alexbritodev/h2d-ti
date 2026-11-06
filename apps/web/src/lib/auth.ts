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

export type InviteInfo = { name: string; email: string };

/** Quem é o dono do link. `null` quando ele não existe, já foi usado ou venceu. */
export async function getInvite(token: string): Promise<InviteInfo | null> {
  const { data } = await api.GET("/api/auth/invite/{token}", { params: { path: { token } } });
  return data ?? null;
}

export type AcceptResult = { ok: true; user: User } | { ok: false; message: string };

/** Define a senha pelo link. Em caso de sucesso a pessoa já fica com a sessão aberta. */
export async function acceptInvite(token: string, password: string): Promise<AcceptResult> {
  try {
    const { data, response, error } = await api.POST("/api/auth/invite/{token}", {
      params: { path: { token } },
      body: { password },
    });
    if (data) return { ok: true, user: data };
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    if (response.status === 404) {
      return { ok: false, message: "Link inválido ou vencido. Peça um novo ao administrador." };
    }
    if (Array.isArray(detail)) {
      const msg = (detail[0] as { msg?: string } | undefined)?.msg;
      if (msg) return { ok: false, message: msg.replace(/^Value error, /, "") };
    }
    return { ok: false, message: "Não foi possível definir a senha. Tente novamente." };
  } catch {
    return { ok: false, message: "Não foi possível conectar. Tente novamente em instantes." };
  }
}

export async function logout(queryClient: QueryClient): Promise<void> {
  await api.POST("/api/auth/logout");
  // Limpa tudo: nada da sessão anterior pode aparecer para a próxima pessoa.
  queryClient.clear();
}

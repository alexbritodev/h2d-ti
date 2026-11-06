import { queryOptions } from "@tanstack/react-query";

import { api, type Role } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type AdminUser = components["schemas"]["UserAdminOut"];
export type UserCreate = components["schemas"]["UserCreate"];
export type UserUpdate = components["schemas"]["UserUpdate"];

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  tech: "Técnico de TI",
  user: "Usuário",
};

export const usersQuery = queryOptions({
  queryKey: ["users"],
  queryFn: async (): Promise<AdminUser[]> => {
    const { data, response } = await api.GET("/api/users");
    if (!data) throw new Error(`Falha ao listar usuários: ${response.status}`);
    return data;
  },
});

/** Resposta de erro da API: `detail` é texto, ou uma lista quando a validação falha (422). */
function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    // O Pydantic prefixa "Value error, " nas mensagens das nossas regras.
    if (first?.msg) return first.msg.replace(/^Value error, /, "");
  }
  return fallback;
}

export type Outcome<T> = { ok: true; data: T } | { ok: false; message: string };

export async function createUser(body: UserCreate): Promise<Outcome<AdminUser>> {
  const { data, error } = await api.POST("/api/users", { body });
  return data ? { ok: true, data } : { ok: false, message: errorMessage(error, "Não foi possível criar o usuário.") };
}

export type UserInviteCreate = components["schemas"]["UserInviteCreate"];

/** Cria a conta sem senha e manda ao e-mail o link para a pessoa definir a dela. */
export async function inviteUser(body: UserInviteCreate): Promise<Outcome<AdminUser>> {
  const { data, error } = await api.POST("/api/users/invite", { body });
  return data ? { ok: true, data } : { ok: false, message: errorMessage(error, "Não foi possível enviar o convite.") };
}

/** Novo link (os anteriores deixam de valer): serve para quem não entrou ou esqueceu a senha. */
export async function resendInvite(id: string): Promise<Outcome<null>> {
  const { response, error } = await api.POST("/api/users/{user_id}/invite", {
    params: { path: { user_id: id } },
  });
  return response.ok
    ? { ok: true, data: null }
    : { ok: false, message: errorMessage(error, "Não foi possível enviar o link.") };
}

export async function updateUser(id: string, body: UserUpdate): Promise<Outcome<AdminUser>> {
  const { data, error } = await api.PATCH("/api/users/{user_id}", {
    params: { path: { user_id: id } },
    body,
  });
  return data ? { ok: true, data } : { ok: false, message: errorMessage(error, "Não foi possível salvar.") };
}

export async function resetPassword(id: string, password: string): Promise<Outcome<null>> {
  const { response, error } = await api.POST("/api/users/{user_id}/password", {
    params: { path: { user_id: id } },
    body: { password },
  });
  return response.ok
    ? { ok: true, data: null }
    : { ok: false, message: errorMessage(error, "Não foi possível redefinir a senha.") };
}

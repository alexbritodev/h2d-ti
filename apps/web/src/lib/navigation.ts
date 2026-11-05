import {
  BookOpen,
  ClipboardList,
  Database,
  FileUp,
  Headset,
  LayoutDashboard,
  ListChecks,
  type LucideIcon,
  MessagesSquare,
  Settings,
} from "lucide-react";

import type { Role } from "./api/client";

export interface NavItem {
  path: string;
  group: string;
  title: string;
  icon: LucideIcon;
  roles: readonly Role[];
}

const STAFF: readonly Role[] = ["tech", "admin"];
const EVERYONE: readonly Role[] = ["user", "tech", "admin"];
const ADMIN: readonly Role[] = ["admin"];

export const NAV_ITEMS: readonly NavItem[] = [
  { path: "/chat", group: "Atendimento", title: "Assistente", icon: MessagesSquare, roles: EVERYONE },
  { path: "/meus-chamados", group: "Atendimento", title: "Meus chamados", icon: Headset, roles: EVERYONE },
  { path: "/base", group: "Atendimento", title: "Base de conhecimento", icon: BookOpen, roles: EVERYONE },
  { path: "/chamados", group: "Operação de TI", title: "Fila de chamados", icon: ListChecks, roles: STAFF },
  { path: "/dashboard", group: "Operação de TI", title: "Dashboard", icon: LayoutDashboard, roles: STAFF },
  { path: "/admin/ingestao", group: "Administração", title: "Documentos", icon: FileUp, roles: ADMIN },
  { path: "/admin/cadastros", group: "Administração", title: "Cadastros", icon: Database, roles: ADMIN },
  { path: "/admin/auditoria", group: "Administração", title: "Auditoria", icon: ClipboardList, roles: ADMIN },
  { path: "/admin/configuracoes", group: "Administração", title: "Configurações", icon: Settings, roles: ADMIN },
];

export function navItemsFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

export function navGroupsFor(role: Role): { name: string; items: NavItem[] }[] {
  const groups = new Map<string, NavItem[]>();
  for (const item of navItemsFor(role)) {
    groups.set(item.group, [...(groups.get(item.group) ?? []), item]);
  }
  return [...groups].map(([name, items]) => ({ name, items }));
}

export function homeFor(role: Role): string {
  return { user: "/chat", tech: "/chamados", admin: "/dashboard" }[role];
}

/** Aceita só caminhos internos: "//site.com" e URLs absolutas levariam para fora do app. */
export function safeRedirect(target: unknown): string | null {
  return typeof target === "string" && /^\/(?![/\\])/.test(target) ? target : null;
}

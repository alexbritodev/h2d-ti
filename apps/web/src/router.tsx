import type { QueryClient } from "@tanstack/react-query";
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
  type RouterHistory,
} from "@tanstack/react-router";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { AuditPage } from "@/features/admin/AuditPage";
import { DocumentsPage } from "@/features/admin/DocumentsPage";
import { RegistersPage } from "@/features/admin/RegistersPage";
import { SettingsPage } from "@/features/admin/SettingsPage";
import { ChatPage } from "@/features/chat/ChatPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { KnowledgePage } from "@/features/kb/KnowledgePage";
import { MyTicketsPage } from "@/features/tickets/MyTicketsPage";
import { QueuePage } from "@/features/tickets/QueuePage";
import type { User } from "@/lib/api/client";
import { meQuery } from "@/lib/auth";
import { homeFor, NAV_ITEMS, safeRedirect } from "@/lib/navigation";

const PAGES: Record<string, () => ReactNode> = {
  "/chat": ChatPage,
  "/meus-chamados": MyTicketsPage,
  "/base": KnowledgePage,
  "/chamados": QueuePage,
  "/dashboard": DashboardPage,
  "/admin/ingestao": DocumentsPage,
  "/admin/cadastros": RegistersPage,
  "/admin/auditoria": AuditPage,
  "/admin/configuracoes": SettingsPage,
};

interface RouterContext {
  queryClient: QueryClient;
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: Outlet,
  notFoundComponent: () => <p className="p-8 text-center text-muted">Página não encontrada.</p>,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  validateSearch: (search: Record<string, unknown>) => ({
    redirect: safeRedirect(search.redirect) ?? undefined,
  }),
  beforeLoad: async ({ context, search }) => {
    const user = await context.queryClient.fetchQuery(meQuery);
    if (user) throw redirect({ to: search.redirect ?? homeFor(user.role) });
  },
  component: LoginPage,
});

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async ({ context, location }): Promise<{ user: User }> => {
    const user = await context.queryClient.fetchQuery(meQuery);
    if (!user) throw redirect({ to: "/login", search: { redirect: location.href } });
    return { user };
  },
  component: function AppLayout() {
    const { user } = appRoute.useRouteContext();
    return <AppShell user={user} />;
  },
});

const indexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  beforeLoad: ({ context }) => {
    throw redirect({ to: homeFor(context.user.role) });
  },
});

// A checagem aqui só organiza a interface. Quem protege os dados são os endpoints da API.
const screenRoutes = NAV_ITEMS.map((item) =>
  createRoute({
    getParentRoute: () => appRoute,
    path: item.path,
    beforeLoad: ({ context }) => {
      if (!item.roles.includes(context.user.role)) {
        throw redirect({ to: homeFor(context.user.role) });
      }
    },
    component: PAGES[item.path],
  }),
);

const routeTree = rootRoute.addChildren([
  loginRoute,
  appRoute.addChildren([indexRoute, ...screenRoutes]),
]);

export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({ routeTree, context: { queryClient }, history });
}

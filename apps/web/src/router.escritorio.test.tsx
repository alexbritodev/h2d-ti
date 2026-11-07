import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { User } from "@/lib/api/client";
import { createAppRouter } from "@/router";

const USER: User = {
  id: "0190a000-0000-7000-8000-000000000000",
  name: "Pessoa",
  email: "pessoa@h2d.local",
  department: null,
  role: "user",
};

class FakeEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener() {}
  close() {}
}

/** `config: null` simula a rota ausente (404), como num servidor sem o recurso. */
function mockApi(config: { enabled: boolean; demo: boolean } | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const { pathname } = new URL(request.url);
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (pathname === "/api/auth/me") return json(USER);
      if (pathname === "/api/health") return json({ status: "ok", version: "0.1.0" });
      if (pathname === "/api/escritorio/config") {
        return config ? json(config) : json({ detail: "não encontrado" }, 404);
      }
      if (pathname === "/api/escritorio/atendimentos") return json([]);
      return json({ detail: "não encontrado" }, 404);
    }),
  );
}

async function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }));
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await router.load();
  return router;
}

beforeEach(() => {
  localStorage.clear();
  window.scrollTo = vi.fn();
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("rota /escritorio atrás da flag", () => {
  it("com a flag desligada a rota leva para a página inicial e não há item no menu", async () => {
    mockApi({ enabled: false, demo: false });
    const router = await renderAt("/escritorio");

    await waitFor(() => expect(router.state.location.pathname).toBe("/chat"));
    expect(await screen.findByRole("link", { name: /Meus chamados/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Escritório/ })).toBeNull();
  });

  it("se a configuração não existir no servidor (404), conta como desligado", async () => {
    mockApi(null);
    const router = await renderAt("/escritorio");

    await waitFor(() => expect(router.state.location.pathname).toBe("/chat"));
    expect(screen.queryByRole("link", { name: /Escritório/ })).toBeNull();
  });

  it("com a flag ligada a rota abre e o item aparece no menu", async () => {
    mockApi({ enabled: true, demo: false });
    const router = await renderAt("/escritorio");

    await waitFor(() => expect(router.state.location.pathname).toBe("/escritorio"));
    expect(await screen.findByRole("heading", { name: "Escritório virtual" })).toBeTruthy();
    expect((await screen.findAllByRole("link", { name: /Escritório/ })).length).toBeGreaterThan(0);
  });
});

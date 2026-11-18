import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiStatus } from "./AppShell";

function renderStatus() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApiStatus />
    </QueryClientProvider>,
  );
}

describe("ApiStatus", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("exibe os três indicadores e detalhes ao abrir o menu", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            version: "0.1.0",
            backend: { status: "ok", detail: "Online", latency_ms: null },
            database: { status: "ok", detail: "Conectado", latency_ms: 4 },
            openrouter: { status: "degraded", detail: "Chave não configurada", latency_ms: null },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    renderStatus();

    const trigger = await screen.findByRole("status", { name: "Status dos serviços" });
    expect(trigger.textContent).toContain("Backend");
    expect(trigger.textContent).toContain("Banco");
    expect(trigger.textContent).toContain("OpenRouter");

    await waitFor(() => {
      expect(trigger.getAttribute("title")).toContain("OpenRouter (IA): Chave não configurada");
    });

    const user = userEvent.setup();
    await user.click(trigger);

    expect(await screen.findByText("Status dos serviços")).toBeTruthy();
    expect(screen.getByText("Online")).toBeTruthy();
    expect(screen.getByText("Conectado · 4 ms")).toBeTruthy();
    expect(screen.getByText("Chave não configurada")).toBeTruthy();
  });

  it("marca backend como sem conexão quando a requisição falha", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 503 })),
    );

    renderStatus();

    const trigger = await screen.findByRole("status", { name: "Status dos serviços" });
    await waitFor(() => {
      expect(trigger.getAttribute("title")).toContain("Backend (API): Sem conexão");
    });
  });
});

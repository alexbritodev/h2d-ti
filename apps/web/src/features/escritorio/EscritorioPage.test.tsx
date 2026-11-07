import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EscritorioPage } from "./EscritorioPage";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener() {}
  close() {
    this.closed = true;
  }
}

function mockApi(config: { enabled: boolean; demo: boolean }) {
  const fetchMock = vi.fn(async (request: Request) => {
    const { pathname } = new URL(request.url);
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (pathname === "/api/escritorio/config") return json(config);
    if (pathname === "/api/escritorio/atendimentos") return json([]);
    return json({ detail: "não encontrado" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <EscritorioPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("EscritorioPage", () => {
  it("sem atendimentos mostra o estado vazio e abre a conexão ao vivo", async () => {
    mockApi({ enabled: true, demo: false });
    renderPage();

    expect(await screen.findByText("Nenhum chamado em andamento")).toBeTruthy();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]!.url).toContain("/api/escritorio/stream");
  });

  it("mostra a conexão perdida e reconecta sozinho", async () => {
    mockApi({ enabled: true, demo: false });
    renderPage();
    await screen.findByText("Nenhum chamado em andamento");

    FakeEventSource.instances[0]!.onopen?.();
    expect(await screen.findByText("Ao vivo")).toBeTruthy();

    FakeEventSource.instances[0]!.onerror?.();
    expect(await screen.findByText("Conexão perdida. Reconectando…")).toBeTruthy();
    expect(FakeEventSource.instances[0]!.closed).toBe(true);
    // A nova conexão sobe sozinha, sem ação do usuário (espera de 500 ms).
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2), { timeout: 3000 });
  });

  it("a aba de demonstração só existe com a flag de demo ligada", async () => {
    mockApi({ enabled: true, demo: false });
    renderPage();
    await screen.findByText("Nenhum chamado em andamento");
    expect(screen.queryByRole("tab", { name: "Demonstração" })).toBeNull();
  });

  it("na demonstração, passo a passo avança a cena sem chamar a API de eventos", async () => {
    const fetchMock = mockApi({ enabled: true, demo: true });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Demonstração" }));
    expect(screen.getByText("Dúvida resolvida pela base")).toBeTruthy();
    const scene = screen.getByTestId("office-scene");
    expect(scene.getAttribute("data-active-room")).toBe("");

    await user.click(screen.getByRole("button", { name: "Próximo passo" }));
    expect(scene.getAttribute("data-active-room")).toBe("recepcao");
    await user.click(screen.getByRole("button", { name: "Próximo passo" }));
    expect(scene.getAttribute("data-active-room")).toBe("rag");
    expect(screen.getAllByRole("log")[0]!.textContent).toContain("Busca na base");

    await user.click(screen.getByRole("button", { name: "Reiniciar" }));
    const paths = fetchMock.mock.calls.map(([request]) => new URL(request.url).pathname);
    expect(paths.some((p) => p === "/api/escritorio/eventos")).toBe(false);
  });
});
